#!/usr/bin/env bash
# E2E tests for the ANIP GraphQL adapter (Python)
# Usage: ./test-e2e.sh
#
# Starts the Python ANIP server + GraphQL adapter in Docker,
# runs curl-based tests, and tears everything down.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.test.yaml"
PROJECT_NAME="anip-graphql-py-e2e"
ADAPTER_URL="http://127.0.0.1:3002"

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

gql() {
  curl -sL -X POST "$ADAPTER_URL/graphql" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$1\"}"
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
  if curl -sf "$ADAPTER_URL/schema.graphql" > /dev/null 2>&1; then
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
echo "Test 1: Search flights (Query)"
RESP=$(gql '{ searchFlights(origin: \"SEA\", destination: \"SFO\", date: \"2026-03-10\") { success result } }')
SUCCESS=$(echo "$RESP" | jq -r '.data.searchFlights.success')
if [ "$SUCCESS" = "true" ]; then
  pass "searchFlights query → success=true"
else
  fail "searchFlights query" "$RESP"
fi

# ── Test 2: Book flight ─────────────────────────────────────────────
echo "Test 2: Book flight (Mutation)"
RESP=$(gql 'mutation { bookFlight(flightNumber: \"AA100\", date: \"2026-03-10\", passengers: 1) { success result costActual { financial { amount currency } } } }')
SUCCESS=$(echo "$RESP" | jq -r '.data.bookFlight.success')
HAS_COST=$(echo "$RESP" | jq -r '.data.bookFlight.costActual.financial.amount != null')
if [ "$SUCCESS" = "true" ] && [ "$HAS_COST" = "true" ]; then
  pass "bookFlight mutation → success=true, costActual present"
else
  fail "bookFlight mutation" "$RESP"
fi

# ── Test 3: Book flight over budget ─────────────────────────────────
echo "Test 3: Book flight over budget (Mutation)"
RESP=$(gql 'mutation { bookFlight(flightNumber: \"AA100\", date: \"2026-03-10\", passengers: 5) { success failure { type detail resolution { action requires grantableBy } } } }')
SUCCESS=$(echo "$RESP" | jq -r '.data.bookFlight.success')
FAILURE_TYPE=$(echo "$RESP" | jq -r '.data.bookFlight.failure.type')
if [ "$SUCCESS" = "false" ] && [ "$FAILURE_TYPE" = "budget_exceeded" ]; then
  pass "bookFlight (5 passengers) → success=false, budget_exceeded"
else
  fail "bookFlight (5 passengers)" "$RESP"
fi

# ── Test 4: Schema SDL has ANIP directives ───────────────────────────
echo "Test 4: Schema SDL"
SCHEMA=$(curl -sf "$ADAPTER_URL/schema.graphql")
if echo "$SCHEMA" | grep -q "@anipSideEffect"; then
  pass "GET /schema.graphql → contains @anipSideEffect directive"
else
  fail "GET /schema.graphql → missing @anipSideEffect" "$(echo "$SCHEMA" | head -5)"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "Results: ${GREEN}${PASSED} passed${NC}, ${RED}${FAILED} failed${NC}, ${TOTAL} total"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
