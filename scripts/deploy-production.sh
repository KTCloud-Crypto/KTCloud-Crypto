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
release_env="$project_dir/.release.env"
previous_env="$project_dir/.release.previous.env"
temporary_env="$project_dir/.release.env.tmp"
backup_dir="$project_dir/backups"
umask 077
secret_json="$(mktemp /tmp/signaltrade-secret-json.XXXXXX)"
secret_env="$(mktemp /tmp/signaltrade-secret-env.XXXXXX)"
config_json="$(mktemp /tmp/signaltrade-config-json.XXXXXX)"
config_env="$(mktemp /tmp/signaltrade-config-env.XXXXXX)"
registry=""

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
    "${compose[@]}" up -d --no-build --remove-orphans db backend strategy-worker frontend
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

registry="${backend_image%%/*}"
aws ecr get-login-password --region "$aws_region" \
  | docker login --username AWS --password-stdin "$registry"

"${compose[@]}" pull backend strategy-worker frontend
"${compose[@]}" up -d --no-build db

db_ready=false
for _ in $(seq 1 60); do
  # 컨테이너 내부의 환경변수로 확장해야 하므로 의도적으로 single quote를 사용합니다.
  # shellcheck disable=SC2016
  if "${compose[@]}" exec -T db sh -c \
    'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    db_ready=true
    break
  fi
  sleep 1
done

if [[ "$db_ready" != true ]]; then
  echo "Database did not become ready within 60 seconds" >&2
  "${compose[@]}" logs --tail=100 db >&2 || true
  false
fi

mkdir -p "$backup_dir"
backup_file="$backup_dir/fastapi_db-${release}-$(date -u +%Y%m%dT%H%M%SZ).dump"
backup_temporary_file="${backup_file}.tmp"
# shellcheck disable=SC2016
if ! "${compose[@]}" exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_temporary_file"; then
  rm -f "$backup_temporary_file"
  echo "Database backup failed" >&2
  false
fi
mv "$backup_temporary_file" "$backup_file"

if [[ -n "$backup_s3_uri" ]]; then
  aws s3 cp --only-show-errors "$backup_file" "${backup_s3_uri%/}/$(basename "$backup_file")"
fi
find "$backup_dir" -type f -name '*.dump' -mtime +7 -delete

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

printf '%s\n' "$release" > "$project_dir/.deployed-release"
"${compose[@]}" ps -a
echo "Deployment completed: $release"
