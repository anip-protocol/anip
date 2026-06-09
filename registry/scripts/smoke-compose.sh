#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/registry/docker-compose.yml"
PROJECT_NAME="${ANIP_REGISTRY_COMPOSE_PROJECT:-anip-registry-smoke}"
REGISTRY_PORT="${ANIP_REGISTRY_PORT:-8200}"
REGISTRY_URL="${ANIP_REGISTRY_SMOKE_URL:-http://127.0.0.1:${REGISTRY_PORT}}"
PUBLISH_TOKEN="${ANIP_REGISTRY_PUBLISH_TOKEN:-local-dev-registry-token}"
OUTPUT_DIR="${ANIP_REGISTRY_SMOKE_OUTPUT:-/tmp/anip-registry-smoke-generated}"
KEEP_STACK="${ANIP_REGISTRY_SMOKE_KEEP_STACK:-0}"
SKIP_BUILD="${ANIP_REGISTRY_SMOKE_SKIP_BUILD:-0}"

export ANIP_REGISTRY_PORT="$REGISTRY_PORT"
export ANIP_REGISTRY_PUBLISH_TOKEN="$PUBLISH_TOKEN"

cleanup() {
  if [[ "$KEEP_STACK" != "1" ]]; then
    docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans >/dev/null
  fi
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans >/dev/null
if [[ "$SKIP_BUILD" == "1" ]]; then
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
else
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up --build -d
fi

for _ in $(seq 1 90); do
  if curl -fsS "$REGISTRY_URL/registry-api/v1/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "$REGISTRY_URL/registry-api/v1/healthz" >/dev/null

(
  cd "$REPO_ROOT/packages/go"
  go run ./cmd/anip-registry-smoke \
    --registry-url "$REGISTRY_URL" \
    --publish-token "$PUBLISH_TOKEN" \
    --output "$OUTPUT_DIR"
)
