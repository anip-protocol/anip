#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-examples/showcase/superset_fronting/compose/docker-compose.yml}"

docker compose -f "$COMPOSE_FILE" down --remove-orphans
docker compose -f "$COMPOSE_FILE" run --rm superset superset db upgrade
docker compose -f "$COMPOSE_FILE" run --rm superset superset fab create-admin \
  --username admin \
  --firstname ANIP \
  --lastname Admin \
  --email admin@example.com \
  --password admin || true
docker compose -f "$COMPOSE_FILE" run --rm superset superset init
docker compose -f "$COMPOSE_FILE" run --rm superset superset load_examples
docker compose -f "$COMPOSE_FILE" up -d

echo "Waiting for Superset health endpoint..."
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:18088/health >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

cat > /tmp/anip-superset.env <<'ENV'
export SUPERSET_BASE_URL="http://127.0.0.1:18088"
export SUPERSET_USERNAME="admin"
export SUPERSET_PASSWORD="admin"
export SUPERSET_WORKSPACE_SCOPE="local"
ENV

echo "Superset is ready at http://127.0.0.1:18088"
echo "Smoke env written to /tmp/anip-superset.env"
