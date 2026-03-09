#!/usr/bin/env bash
# E2E tests for the ANIP REST adapter (TypeScript)
# Usage: ./test-e2e.sh
#
# Starts the TypeScript ANIP server + REST adapter in Docker,
# runs curl-based tests, and tears everything down.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.test.yaml"
PROJECT_NAME="anip-rest-ts-e2e"
ADAPTER_URL="http://127.0.0.1:3003"

PASSED=0
FAILED=0
TOTAL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() {
  PASSED=$((PASSED + 1))
  TOTAL=$((TOTAL + 1))
  echo -e "  ${GREEN}✓${NC} $1"
}

fail() {
  FAILED=$((FAILED + 1))
  TOTAL=$((TOTAL + 1))
  echo -e "  ${RED}✗${NC} $1"
  echo "    Response: $2"
}

cleanup() {
  echo ""
  echo "Tearing down containers..."
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting containers..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build --wait 2>&1

echo "Waiting for adapter..."
for i in $(seq 1 30); do
  if curl -sf "$ADAPTER_URL/openapi.json" > /dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "Adapter failed to start within 30s"
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs
    exit 1
  fi
  sleep 1
done
echo ""

# ── Test 1: Search flights ──────────────────────────────────────────
echo "Test 1: Search flights"
RESP=$(curl -sf "$ADAPTER_URL/api/search_flights?origin=SEA&destination=SFO&date=2026-03-10")
SUCCESS=$(echo "$RESP" | jq -r '.success')
HAS_FLIGHTS=$(echo "$RESP" | jq -r '.result.flights | length > 0')
if [ "$SUCCESS" = "true" ] && [ "$HAS_FLIGHTS" = "true" ]; then
  pass "GET /api/search_flights → 200, success=true, flights returned"
else
  fail "GET /api/search_flights" "$RESP"
fi

# ── Test 2: Book flight ─────────────────────────────────────────────
echo "Test 2: Book flight"
RESP=$(curl -sf -X POST "$ADAPTER_URL/api/book_flight" \
  -H "Content-Type: application/json" \
  -d '{"flight_number":"AA100","date":"2026-03-10","passengers":1}')
SUCCESS=$(echo "$RESP" | jq -r '.success')
HAS_BOOKING=$(echo "$RESP" | jq -r '.result.booking_id != null')
HAS_COST=$(echo "$RESP" | jq -r '.cost_actual != null')
HAS_WARNINGS=$(echo "$RESP" | jq -r '.warnings | length > 0')
if [ "$SUCCESS" = "true" ] && [ "$HAS_BOOKING" = "true" ] && [ "$HAS_COST" = "true" ] && [ "$HAS_WARNINGS" = "true" ]; then
  pass "POST /api/book_flight → 200, success=true, booking_id + cost_actual + warnings"
else
  fail "POST /api/book_flight" "$RESP"
fi

# ── Test 3: Book flight over budget ─────────────────────────────────
echo "Test 3: Book flight over budget"
HTTP_CODE=$(curl -s -o /tmp/anip-rest-ts-e2e.json -w "%{http_code}" -X POST "$ADAPTER_URL/api/book_flight" \
  -H "Content-Type: application/json" \
  -d '{"flight_number":"AA100","date":"2026-03-10","passengers":5}')
RESP=$(cat /tmp/anip-rest-ts-e2e.json)
SUCCESS=$(echo "$RESP" | jq -r '.success')
FAILURE_TYPE=$(echo "$RESP" | jq -r '.failure.type')
if [ "$HTTP_CODE" = "403" ] && [ "$SUCCESS" = "false" ] && [ "$FAILURE_TYPE" = "budget_exceeded" ]; then
  pass "POST /api/book_flight (5 passengers) → 403, budget_exceeded"
else
  fail "POST /api/book_flight (5 passengers) → expected 403/budget_exceeded, got $HTTP_CODE/$FAILURE_TYPE" "$RESP"
fi

# ── Test 4: OpenAPI spec has ANIP extensions ─────────────────────────
echo "Test 4: OpenAPI spec"
RESP=$(curl -sf "$ADAPTER_URL/openapi.json")
HAS_ANIP=$(echo "$RESP" | jq '[.paths | to_entries[].value | to_entries[].value | has("x-anip-side-effect")] | any')
if [ "$HAS_ANIP" = "true" ]; then
  pass "GET /openapi.json → has x-anip-side-effect extensions"
else
  fail "GET /openapi.json → missing x-anip-* extensions" "$(echo "$RESP" | jq -c '.paths | keys')"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Results: ${GREEN}${PASSED} passed${NC}, ${RED}${FAILED} failed${NC}, ${TOTAL} total"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
