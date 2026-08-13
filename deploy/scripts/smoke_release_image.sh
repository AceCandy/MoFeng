#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 1 || ! "$1" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]]; then
    echo "usage: $0 <repository@sha256:digest>" >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    echo "docker compose is required" >&2
    exit 1
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$project_root/deploy/docker-compose.yml"
image_ref="$1"
project_name="mofeng-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"
project_name="${project_name,,}"
local_repo="${project_name}/mofeng"
local_image="${local_repo}:local"
env_file="$(mktemp "${TMPDIR:-/tmp}/mofeng-smoke.XXXXXX.env")"

compose=(
    docker compose
    --project-name "$project_name"
    --env-file "$env_file"
    -f "$compose_file"
    --profile postgres
)

cleanup() {
    "${compose[@]}" down --volumes --remove-orphans --timeout 10 >/dev/null 2>&1 || true
    docker image rm "$local_image" >/dev/null 2>&1 || true
    rm -f "$env_file"
}

report_failure() {
    local status=$?
    echo "release image smoke failed" >&2
    "${compose[@]}" ps >&2 || true
    "${compose[@]}" logs --tail=80 pg app worker >&2 || true
    return "$status"
}

trap report_failure ERR
trap cleanup EXIT

cat >"$env_file" <<EOF
COMPOSE_PROJECT_NAME=$project_name
IMAGE_REPO=$local_repo
ENVIRONMENT=development
DEBUG=false
SECRET_KEY=smoke-only-secret-key-$project_name
POSTGRES_USER=mofeng_smoke
POSTGRES_PASSWORD=smoke-only-password-$project_name
POSTGRES_DATABASE=mofeng_smoke
BOOTSTRAP_CREATE_DEFAULT_ADMIN=false
APP_PORT=0
REDIS_URL=
LINUXDO_REDIRECT_URI=http://127.0.0.1/api/auth/linuxdo/register
EOF

docker pull "$image_ref"
docker tag "$image_ref" "$local_image"

"${compose[@]}" up -d --wait pg
"${compose[@]}" run --rm --no-deps migrate python -m app.db.cli db-migrate
"${compose[@]}" run --rm --no-deps bootstrap python -m app.db.cli db-bootstrap
"${compose[@]}" run --rm --no-deps migrate python -m app.db.cli db-check
"${compose[@]}" up -d --no-deps app worker

app_endpoint="$("${compose[@]}" port app 6100 | head -n 1)"
app_port="${app_endpoint##*:}"
if ! [[ "$app_port" =~ ^[0-9]+$ ]]; then
    echo "failed to resolve the app port" >&2
    exit 1
fi

for _ in {1..60}; do
    if curl -fsS "http://127.0.0.1:${app_port}/api/ready" \
        | python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ready"'; then
        break
    fi
    sleep 2
done
curl -fsS "http://127.0.0.1:${app_port}/api/ready" \
    | python3 -c 'import json, sys; assert json.load(sys.stdin)["status"] == "ready"'

for _ in {1..60}; do
    if "${compose[@]}" exec -T worker python -m app.worker health \
        | python3 -c 'import json, sys; assert json.load(sys.stdin)["healthy"] is True'; then
        break
    fi
    sleep 2
done
"${compose[@]}" exec -T worker python -m app.worker health \
    | python3 -c 'import json, sys; assert json.load(sys.stdin)["healthy"] is True'
"${compose[@]}" exec -T worker python -m app.worker metrics \
    | python3 -c 'import json, sys; assert isinstance(json.load(sys.stdin), dict)'

echo "release image smoke passed: $image_ref"
