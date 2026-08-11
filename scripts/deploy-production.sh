#!/usr/bin/env bash
set -Eeuo pipefail

release="${1:?release version is required}"
backend_image="${2:?backend image digest is required}"
frontend_image="${3:?frontend image digest is required}"
aws_region="${4:?AWS region is required}"
backup_s3_uri="${5:-}"
healthcheck_url="${6:-https://signaltrade.cloud/healthz}"
monitoring_ssm_prefix="${7:-/signaltrade/production/monitoring}"
monitoring_public_url="${8:-https://signaltrade.cloud/monitoring/}"

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

if [[ ! -f .env ]]; then
  echo "$project_dir/.env is required" >&2
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
compose=(docker compose --env-file .env --env-file "$release_env" -f "$compose_file")
registry=""

read_monitoring_parameter() {
  aws ssm get-parameter \
    --region "$aws_region" \
    --with-decryption \
    --name "${monitoring_ssm_prefix%/}/$1" \
    --query 'Parameter.Value' \
    --output text
}

logout_registry() {
  if [[ -n "$registry" ]]; then
    docker logout "$registry" >/dev/null 2>&1 || true
  fi
}
trap logout_registry EXIT

rollback() {
  exit_code=$?
  trap - ERR

  echo "Deployment failed for $release (exit $exit_code)" >&2
  if [[ -f "$previous_env" ]]; then
    echo "Rolling application images back to the previous release" >&2
    cp "$previous_env" "$release_env"
    docker compose --env-file .env --env-file "$release_env" -f "$compose_file" pull backend strategy-worker frontend
    docker compose --env-file .env --env-file "$release_env" -f "$compose_file" up -d --no-build --remove-orphans db backend strategy-worker frontend
  else
    echo "No previous release metadata exists; automatic rollback is unavailable" >&2
  fi

  docker compose --env-file .env --env-file "$release_env" -f "$compose_file" ps -a || true
  exit "$exit_code"
}
trap rollback ERR

if [[ -f "$release_env" ]]; then
  cp "$release_env" "$previous_env"
fi

umask 077
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
"${compose[@]}" up -d --no-build db

db_ready=false
for _ in $(seq 1 60); do
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

monitoring_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "${monitoring_public_url%/}/api/health")"
if [[ "$monitoring_status" != "401" ]]; then
  echo "External monitoring access control check failed: expected 401, got $monitoring_status" >&2
  false
fi

printf '%s\n' "$release" > "$project_dir/.deployed-release"
"${compose[@]}" ps -a
echo "Deployment completed: $release"
