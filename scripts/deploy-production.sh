#!/usr/bin/env bash
set -Eeuo pipefail

release="${1:?release version is required}"
backend_image="${2:?backend image digest is required}"
frontend_image="${3:?frontend image digest is required}"
aws_region="${4:?AWS region is required}"
backup_s3_uri="${5:-}"
healthcheck_url="${6:-https://signaltrade.cloud/healthz}"
secrets_manager_secret_id="${7:?Secrets Manager secret ID or ARN is required}"
parameter_store_config_id="${8:?Parameter Store config name or ARN is required}"
monitoring_ssm_prefix="${9:-/signaltrade/production/monitoring}"
monitoring_public_url="${10:-https://signaltrade.cloud/monitoring/}"

if [[ ! "$release" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid release version: $release" >&2
  exit 2
fi

for image in "$backend_image" "$frontend_image"; do
  if [[ "$image" != *@sha256:* ]] || [[ "$image" =~ [[:space:]] ]]; then
    echo "Deployment images must use immutable sha256 digests: $image" >&2
    exit 2
  fi
done

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "$secrets_manager_secret_id" =~ [[:space:]] ]]; then
  echo "Secrets Manager secret ID must not contain whitespace" >&2
  exit 2
fi

if [[ "$parameter_store_config_id" =~ [[:space:]] ]]; then
  echo "Parameter Store config ID must not contain whitespace" >&2
  exit 2
fi

exec 9>"$project_dir/.deploy.lock"
if ! flock -n 9; then
  echo "Another deployment is already running" >&2
  exit 3
fi

compose_file="$project_dir/docker-compose.production.yml"
monitoring_compose_file="$project_dir/monitoring/docker-compose.yml"
release_env="$project_dir/.release.env"
previous_env="$project_dir/.release.previous.env"
temporary_env="$project_dir/.release.env.tmp"
backup_dir="$project_dir/backups"
monitoring_secrets_dir="$project_dir/.monitoring-secrets"
monitoring_htpasswd_file="$monitoring_secrets_dir/htpasswd"
umask 077
secret_json="$(mktemp /tmp/signaltrade-secret-json.XXXXXX)"
secret_env="$(mktemp /tmp/signaltrade-secret-env.XXXXXX)"
config_json="$(mktemp /tmp/signaltrade-config-json.XXXXXX)"
config_env="$(mktemp /tmp/signaltrade-config-env.XXXXXX)"
registry=""

read_monitoring_parameter() {
  aws ssm get-parameter \
    --region "$aws_region" \
    --with-decryption \
    --name "${monitoring_ssm_prefix%/}/$1" \
    --query 'Parameter.Value' \
    --output text
}

cleanup_runtime() {
  if [[ -n "$registry" ]]; then
    docker logout "$registry" >/dev/null 2>&1 || true
  fi
  rm -f "$secret_json" "$secret_env" "$config_json" "$config_env"
}
trap cleanup_runtime EXIT

aws secretsmanager get-secret-value \
  --region "$aws_region" \
  --secret-id "$secrets_manager_secret_id" \
  --version-stage AWSCURRENT \
  --query SecretString \
  --output text > "$secret_json"

python3 scripts/render-secrets-env.py "$secret_json" "$secret_env"

aws ssm get-parameter \
  --region "$aws_region" \
  --name "$parameter_store_config_id" \
  --query Parameter.Value \
  --output text > "$config_json"

python3 scripts/render-config-env.py "$config_json" "$config_env"

chmod 600 "$secret_json" "$secret_env" "$config_json" "$config_env"
rm -f "$secret_json" "$config_json"
secret_json=""
config_json=""

compose=(
  docker compose
  --env-file "$config_env"
  --env-file "$secret_env"
  --env-file "$release_env"
  -f "$compose_file"
)

rollback() {
  exit_code=$?
  trap - ERR

  echo "Deployment failed for $release (exit $exit_code)" >&2
  if [[ -f "$previous_env" ]]; then
    echo "Rolling application images back to the previous release" >&2
    cp "$previous_env" "$release_env"
    "${compose[@]}" pull backend strategy-worker frontend
    "${compose[@]}" up -d --no-build --remove-orphans backend strategy-worker frontend
  else
    echo "No previous release metadata exists; automatic rollback is unavailable" >&2
  fi

  "${compose[@]}" ps -a || true
  exit "$exit_code"
}
trap rollback ERR

if [[ -f "$release_env" ]]; then
  cp "$release_env" "$previous_env"
fi

printf 'RELEASE_VERSION=%s\nBACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' \
  "$release" "$backend_image" "$frontend_image" > "$temporary_env"
mv "$temporary_env" "$release_env"

grafana_admin_user="$(read_monitoring_parameter grafana-admin-user)"
grafana_admin_password="$(read_monitoring_parameter grafana-admin-password)"
postgres_exporter_dsn="$(read_monitoring_parameter postgres-exporter-dsn)"
monitoring_proxy_basic_auth="$(read_monitoring_parameter proxy-basic-auth)"

for monitoring_value in "$grafana_admin_user" "$grafana_admin_password" "$postgres_exporter_dsn" "$monitoring_proxy_basic_auth"; do
  if [[ -z "$monitoring_value" || "$monitoring_value" == *$'\n'* || "$monitoring_value" == *$'\r'* ]]; then
    echo "Monitoring SSM parameters must be non-empty single-line values" >&2
    exit 2
  fi
done

if [[ ! "$monitoring_proxy_basic_auth" =~ ^[^:]+:\$ ]]; then
  echo "proxy-basic-auth must be a single htpasswd entry" >&2
  exit 2
fi

mkdir -p "$monitoring_secrets_dir"
chmod 700 "$monitoring_secrets_dir"
printf '%s\n' "$monitoring_proxy_basic_auth" > "$monitoring_htpasswd_file"
chmod 644 "$monitoring_htpasswd_file"
export MONITORING_HTPASSWD_FILE="$monitoring_htpasswd_file"

monitoring_compose=(docker compose -f "$monitoring_compose_file")
env \
  GRAFANA_ADMIN_USER="$grafana_admin_user" \
  GRAFANA_ADMIN_PASSWORD="$grafana_admin_password" \
  GRAFANA_PORT=3000 \
  GRAFANA_ROOT_URL="$monitoring_public_url" \
  POSTGRES_EXPORTER_DSN="$postgres_exporter_dsn" \
  "${monitoring_compose[@]}" up -d --build

monitoring_healthy=false
for _ in $(seq 1 60); do
  if curl --fail --silent --show-error http://127.0.0.1:3000/api/health >/dev/null; then
    monitoring_healthy=true
    break
  fi
  sleep 2
done

if [[ "$monitoring_healthy" != true ]]; then
  echo "Grafana did not become ready within 120 seconds" >&2
  "${monitoring_compose[@]}" ps -a >&2 || true
  "${monitoring_compose[@]}" logs --tail=100 grafana prometheus loki >&2 || true
  false
fi

registry="${backend_image%%/*}"
aws ecr get-login-password --region "$aws_region" \
  | docker login --username AWS --password-stdin "$registry"

"${compose[@]}" pull backend strategy-worker frontend

db_ready=false
for _ in $(seq 1 60); do
  # 컨테이너 내부의 DATABASE_URL을 사용해야 하므로 의도적으로 single quote를 사용합니다.
  # shellcheck disable=SC2016
  if "${compose[@]}" run --rm --no-deps migrate sh -c \
    'pg_isready --dbname="$DATABASE_URL"' >/dev/null 2>&1; then
    db_ready=true
    break
  fi
  sleep 1
done

if [[ "$db_ready" != true ]]; then
  echo "Database did not become ready within 60 seconds" >&2
  false
fi

mkdir -p "$backup_dir"
backup_file="$backup_dir/fastapi_db-${release}-$(date -u +%Y%m%dT%H%M%SZ).dump"
backup_temporary_file="${backup_file}.tmp"
# 컨테이너 내부의 DATABASE_URL을 사용해야 하므로 의도적으로 single quote를 사용합니다.
# shellcheck disable=SC2016
if ! "${compose[@]}" run --rm --no-deps migrate sh -c \
  'pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --no-privileges' \
  > "$backup_temporary_file"; then
  rm -f "$backup_temporary_file"
  echo "Database backup failed" >&2
  false
fi
mv "$backup_temporary_file" "$backup_file"

if [[ -n "$backup_s3_uri" ]]; then
  aws s3 cp --only-show-errors "$backup_file" "${backup_s3_uri%/}/$(basename "$backup_file")"
fi
# S3 업로드 여부와 무관하게 EC2에는 최근 72시간의 dump만 남깁니다.
find "$backup_dir" -type f -name '*.dump' -mmin +4320 -delete

"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --no-build --remove-orphans backend strategy-worker frontend

healthy=false
for _ in $(seq 1 45); do
  if curl --fail --silent --show-error "$healthcheck_url" >/dev/null; then
    healthy=true
    break
  fi
  sleep 2
done

if [[ "$healthy" != true ]]; then
  echo "Health check failed: $healthcheck_url" >&2
  false
fi

monitoring_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "${monitoring_public_url%/}/api/health")"
if [[ "$monitoring_status" != "401" ]]; then
  echo "External monitoring access control check failed: expected 401, got $monitoring_status" >&2
  false
fi

printf '%s\n' "$release" > "$project_dir/.deployed-release"

# 실행 중인 image와 최근 release는 유지하고 오래된 미사용 image/cache만 정리합니다.
# 정리 실패 때문에 정상 배포를 rollback하지는 않되 운영 로그에는 경고를 남깁니다.
if ! docker image prune --all --force --filter "until=168h"; then
  echo "Warning: failed to prune Docker images older than 7 days" >&2
fi
if ! docker builder prune --all --force --filter "until=168h"; then
  echo "Warning: failed to prune Docker build cache older than 7 days" >&2
fi

"${compose[@]}" ps -a
docker system df
echo "Deployment completed: $release"
