#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/studio/docker-compose.yml"
PROJECT_NAME="${STUDIO_COMPOSE_PROJECT:-anip-studio-smoke}"
API_PORT="${STUDIO_API_PORT:-8100}"
WEB_PORT="${STUDIO_WEB_PORT:-8080}"
API_URL="${STUDIO_SMOKE_API_URL:-http://127.0.0.1:${API_PORT}}"
WEB_URL="${STUDIO_SMOKE_WEB_URL:-http://127.0.0.1:${WEB_PORT}}"
KEEP_STACK="${STUDIO_SMOKE_KEEP_STACK:-0}"
SKIP_BUILD="${STUDIO_SMOKE_SKIP_BUILD:-0}"

export STUDIO_API_PORT="$API_PORT"
export STUDIO_WEB_PORT="$WEB_PORT"
export STUDIO_READ_ONLY="${STUDIO_READ_ONLY:-1}"
export STUDIO_SEED_SHOWCASES="${STUDIO_SEED_SHOWCASES:-1}"

cleanup() {
  if [[ "$KEEP_STACK" != "1" ]]; then
    docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans >/dev/null
  fi
}
trap cleanup EXIT

expect_status() {
  local method="$1"
  local url="$2"
  local expected="$3"
  local body="${4:-{}}"
  local status
  status="$(
    curl -sS -o /tmp/anip-studio-smoke-response.json \
      -w "%{http_code}" \
      -X "$method" \
      -H "Content-Type: application/json" \
      --data "$body" \
      "$url"
  )"
  if [[ "$status" != "$expected" ]]; then
    echo "expected $method $url to return $expected, got $status" >&2
    cat /tmp/anip-studio-smoke-response.json >&2 || true
    exit 1
  fi
}

docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans >/dev/null
if [[ "$SKIP_BUILD" == "1" ]]; then
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
else
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up --build -d
fi

for _ in $(seq 1 120); do
  if curl -fsS "$API_URL/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "$API_URL/api/health" >/dev/null
curl -fsS "$WEB_URL/studio/" >/dev/null

runtime_status="$(curl -fsS "$API_URL/api/runtime-status")"
if [[ "$runtime_status" != *'"read_only_mode":true'* ]]; then
  echo "expected Studio runtime status to report read_only_mode=true" >&2
  echo "$runtime_status" >&2
  exit 1
fi

projects="$(curl -fsS "$API_URL/api/projects")"
if [[ "$projects" != *'"id"'* ]]; then
  echo "expected seeded Studio projects to be present" >&2
  echo "$projects" >&2
  exit 1
fi

expect_status POST "$API_URL/api/workspaces" 403 '{"id":"blocked-smoke-workspace","name":"Blocked Smoke Workspace"}'
expect_status PUT "$API_URL/api/runtime-config" 403 '{"assistant_provider":"openai"}'
expect_status POST "$API_URL/studio-assistant/anip/invoke/assistant.propose" 403 '{"parameters":{}}'

validate_status="$(
  curl -sS -o /tmp/anip-studio-smoke-validate.json \
    -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    --data '{"requirements":{},"shape":{},"scenario":{}}' \
    "$API_URL/api/validate-shape"
)"
if [[ "$validate_status" == "403" ]]; then
  echo "read-only mode must not block validation endpoints" >&2
  cat /tmp/anip-studio-smoke-validate.json >&2 || true
  exit 1
fi

echo "Studio compose smoke passed: ${WEB_URL}/studio/"
