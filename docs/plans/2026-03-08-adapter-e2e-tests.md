# Adapter E2E Test Scripts — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create 4 Docker-based e2e test scripts (one per adapter) that start the ANIP server + adapter in containers, run curl tests, validate responses, and clean up.

**Architecture:** Each adapter gets a `Dockerfile`, `docker-compose.test.yaml`, and `test-e2e.sh`. The compose file stands up the ANIP server + adapter on a shared network. The test script orchestrates: up → wait for health → run tests → report → down.

**Tech Stack:** Docker, docker-compose, bash, curl, jq

**Pairings:**
- `rest-py` + `graphql-py` → Python ANIP server (`examples/anip`, port 8000)
- `rest-ts` + `graphql-ts` → TypeScript ANIP server (`examples/anip-ts`, port 8000)

---

### Task 1: REST Python Adapter — Dockerfile

**Files:**
- Create: `adapters/rest-py/Dockerfile`

**Step 1: Create the Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY anip_rest_adapter/ anip_rest_adapter/

RUN pip install --no-cache-dir .

EXPOSE 3001

CMD ["anip-rest-adapter"]
```

**Step 2: Verify it builds**

Run: `cd adapters/rest-py && docker build -t anip-rest-py-test . && echo "BUILD OK"`
Expected: BUILD OK

**Step 3: Commit**

```bash
git add adapters/rest-py/Dockerfile
git commit -m "chore: add Dockerfile for rest-py adapter"
```

---

### Task 2: REST Python Adapter — docker-compose.test.yaml

**Files:**
- Create: `adapters/rest-py/docker-compose.test.yaml`

The compose file starts the Python ANIP server and the REST adapter. The adapter config is passed via environment variables so no config file is needed inside the container.

**Step 1: Create the compose file**

```yaml
services:
  anip-server:
    build:
      context: ../../examples/anip
    ports:
      - "9100:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/anip/manifest"]
      interval: 3s
      timeout: 5s
      retries: 10

  rest-adapter:
    build:
      context: .
    ports:
      - "3001:3001"
    environment:
      ANIP_SERVICE_URL: "http://anip-server:8000"
      ANIP_ADAPTER_PORT: "3001"
      ANIP_ISSUER: "human:test@example.com"
      ANIP_SCOPE: "travel.search,travel.book:max_$500"
    depends_on:
      anip-server:
        condition: service_healthy
```

**Step 2: Verify compose config is valid**

Run: `cd adapters/rest-py && docker compose -f docker-compose.test.yaml config > /dev/null && echo "CONFIG OK"`
Expected: CONFIG OK

**Step 3: Commit**

```bash
git add adapters/rest-py/docker-compose.test.yaml
git commit -m "chore: add docker-compose.test.yaml for rest-py e2e tests"
```

---

### Task 3: REST Python Adapter — test-e2e.sh

**Files:**
- Create: `adapters/rest-py/test-e2e.sh`

The script starts containers, waits for the adapter to be ready, runs 4 test cases, reports results, and tears down.

**Test cases:**
1. Search flights — `GET /api/search_flights?origin=SEA&destination=SFO&date=2026-03-10` → 200, `success: true`, result has flights array
2. Book flight — `POST /api/book_flight` with `{"flight_number":"AA100","date":"2026-03-10","passengers":1}` → 200, `success: true`, result has booking_id, response has cost_actual and warnings
3. Book flight over budget — `POST /api/book_flight` with `{"flight_number":"AA100","date":"2026-03-10","passengers":5}` → 403, `success: false`, failure.type is `budget_exceeded`
4. OpenAPI spec — `GET /openapi.json` → 200, has `x-anip-side-effect` in at least one path

**Step 1: Create the test script**

```bash
#!/usr/bin/env bash
# E2E tests for the ANIP REST adapter (Python)
# Usage: ./test-e2e.sh
#
# Starts the Python ANIP server + REST adapter in Docker,
# runs curl-based tests, and tears everything down.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.test.yaml"
PROJECT_NAME="anip-rest-py-e2e"
ADAPTER_URL="http://localhost:3001"

PASSED=0
FAILED=0
TOTAL=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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

# Wait for adapter to be ready
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
HTTP_CODE=$(curl -s -o /tmp/anip-rest-e2e.json -w "%{http_code}" -X POST "$ADAPTER_URL/api/book_flight" \
  -H "Content-Type: application/json" \
  -d '{"flight_number":"AA100","date":"2026-03-10","passengers":5}')
RESP=$(cat /tmp/anip-rest-e2e.json)
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
HAS_ANIP=$(echo "$RESP" | jq 'paths | to_entries | map(.value | to_entries | map(.value | has("x-anip-side-effect"))) | flatten | any')
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
```

**Step 2: Make executable and commit**

```bash
chmod +x adapters/rest-py/test-e2e.sh
git add adapters/rest-py/test-e2e.sh
git commit -m "test: add e2e test script for rest-py adapter"
```

---

### Task 4: REST TypeScript Adapter — Dockerfile

**Files:**
- Create: `adapters/rest-ts/Dockerfile`

The TS adapter uses tsx at dev time but can be compiled with tsc for production. We'll use the multi-stage build pattern from the TS ANIP server.

**Step 1: Create the Dockerfile**

```dockerfile
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src/ ./src/

RUN npx tsc

FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist/ ./dist/

EXPOSE 3001

CMD ["node", "dist/index.js"]
```

**Step 2: Verify it builds**

Run: `cd adapters/rest-ts && docker build -t anip-rest-ts-test . && echo "BUILD OK"`
Expected: BUILD OK

**Step 3: Commit**

```bash
git add adapters/rest-ts/Dockerfile
git commit -m "chore: add Dockerfile for rest-ts adapter"
```

---

### Task 5: REST TypeScript Adapter — docker-compose.test.yaml

**Files:**
- Create: `adapters/rest-ts/docker-compose.test.yaml`

Uses the TypeScript ANIP server.

**Step 1: Create the compose file**

```yaml
services:
  anip-server:
    build:
      context: ../../examples/anip-ts
    ports:
      - "9101:8000"
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8000/anip/manifest"]
      interval: 3s
      timeout: 5s
      retries: 10

  rest-adapter:
    build:
      context: .
    ports:
      - "3003:3001"
    environment:
      ANIP_SERVICE_URL: "http://anip-server:8000"
      ANIP_ADAPTER_PORT: "3001"
      ANIP_ISSUER: "human:test@example.com"
      ANIP_SCOPE: "travel.search,travel.book:max_$500"
    depends_on:
      anip-server:
        condition: service_healthy
```

Note: The TS ANIP server's alpine image has `wget` but not `curl`, so the healthcheck uses `wget --spider`.

**Step 2: Commit**

```bash
git add adapters/rest-ts/docker-compose.test.yaml
git commit -m "chore: add docker-compose.test.yaml for rest-ts e2e tests"
```

---

### Task 6: REST TypeScript Adapter — test-e2e.sh

**Files:**
- Create: `adapters/rest-ts/test-e2e.sh`

Same structure as rest-py but with port 3003 and project name `anip-rest-ts-e2e`.

**Step 1: Create the test script**

```bash
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
ADAPTER_URL="http://localhost:3003"

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
HAS_ANIP=$(echo "$RESP" | jq 'paths | to_entries | map(.value | to_entries | map(.value | has("x-anip-side-effect"))) | flatten | any')
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
```

**Step 2: Make executable and commit**

```bash
chmod +x adapters/rest-ts/test-e2e.sh
git add adapters/rest-ts/test-e2e.sh
git commit -m "test: add e2e test script for rest-ts adapter"
```

---

### Task 7: GraphQL Python Adapter — Dockerfile

**Files:**
- Create: `adapters/graphql-py/Dockerfile`

**Step 1: Create the Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY anip_graphql_adapter/ anip_graphql_adapter/

RUN pip install --no-cache-dir .

EXPOSE 3002

CMD ["anip-graphql-adapter"]
```

**Step 2: Verify it builds**

Run: `cd adapters/graphql-py && docker build -t anip-graphql-py-test . && echo "BUILD OK"`
Expected: BUILD OK

**Step 3: Commit**

```bash
git add adapters/graphql-py/Dockerfile
git commit -m "chore: add Dockerfile for graphql-py adapter"
```

---

### Task 8: GraphQL Python Adapter — docker-compose.test.yaml

**Files:**
- Create: `adapters/graphql-py/docker-compose.test.yaml`

**Step 1: Create the compose file**

```yaml
services:
  anip-server:
    build:
      context: ../../examples/anip
    ports:
      - "9102:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/anip/manifest"]
      interval: 3s
      timeout: 5s
      retries: 10

  graphql-adapter:
    build:
      context: .
    ports:
      - "3002:3002"
    environment:
      ANIP_SERVICE_URL: "http://anip-server:8000"
      ANIP_ADAPTER_PORT: "3002"
      ANIP_ISSUER: "human:test@example.com"
      ANIP_SCOPE: "travel.search,travel.book:max_$500"
    depends_on:
      anip-server:
        condition: service_healthy
```

**Step 2: Commit**

```bash
git add adapters/graphql-py/docker-compose.test.yaml
git commit -m "chore: add docker-compose.test.yaml for graphql-py e2e tests"
```

---

### Task 9: GraphQL Python Adapter — test-e2e.sh

**Files:**
- Create: `adapters/graphql-py/test-e2e.sh`

GraphQL tests use POST with JSON query bodies. Note: Ariadne mounts at `/graphql/` (trailing slash), so we use `-L` to follow the 307 redirect from `/graphql`.

**Test cases:**
1. Search flights — Query `{ searchFlights(...) { success result } }` → success=true, result has flights
2. Book flight — Mutation `{ bookFlight(...) { success result costActual { financial { amount currency } } } }` → success=true, booking_id in result
3. Book over budget — Mutation with 5 passengers → success=false, failure.type=budget_exceeded
4. Schema SDL — `GET /schema.graphql` → contains `@anipSideEffect` directive

**Step 1: Create the test script**

```bash
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
ADAPTER_URL="http://localhost:3002"

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
```

**Step 2: Make executable and commit**

```bash
chmod +x adapters/graphql-py/test-e2e.sh
git add adapters/graphql-py/test-e2e.sh
git commit -m "test: add e2e test script for graphql-py adapter"
```

---

### Task 10: GraphQL TypeScript Adapter — Dockerfile

**Files:**
- Create: `adapters/graphql-ts/Dockerfile`

**Step 1: Create the Dockerfile**

```dockerfile
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src/ ./src/

RUN npx tsc

FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist/ ./dist/

EXPOSE 3002

CMD ["node", "dist/index.js"]
```

**Step 2: Verify it builds**

Run: `cd adapters/graphql-ts && docker build -t anip-graphql-ts-test . && echo "BUILD OK"`
Expected: BUILD OK

**Step 3: Commit**

```bash
git add adapters/graphql-ts/Dockerfile
git commit -m "chore: add Dockerfile for graphql-ts adapter"
```

---

### Task 11: GraphQL TypeScript Adapter — docker-compose.test.yaml

**Files:**
- Create: `adapters/graphql-ts/docker-compose.test.yaml`

Uses the TypeScript ANIP server.

**Step 1: Create the compose file**

```yaml
services:
  anip-server:
    build:
      context: ../../examples/anip-ts
    ports:
      - "9103:8000"
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8000/anip/manifest"]
      interval: 3s
      timeout: 5s
      retries: 10

  graphql-adapter:
    build:
      context: .
    ports:
      - "3004:3002"
    environment:
      ANIP_SERVICE_URL: "http://anip-server:8000"
      ANIP_ADAPTER_PORT: "3002"
      ANIP_ISSUER: "human:test@example.com"
      ANIP_SCOPE: "travel.search,travel.book:max_$500"
    depends_on:
      anip-server:
        condition: service_healthy
```

**Step 2: Commit**

```bash
git add adapters/graphql-ts/docker-compose.test.yaml
git commit -m "chore: add docker-compose.test.yaml for graphql-ts e2e tests"
```

---

### Task 12: GraphQL TypeScript Adapter — test-e2e.sh

**Files:**
- Create: `adapters/graphql-ts/test-e2e.sh`

Same test cases as graphql-py but port 3004 and project `anip-graphql-ts-e2e`. The TS GraphQL adapter serves at `/graphql` without trailing-slash redirect, so no `-L` needed.

**Step 1: Create the test script**

```bash
#!/usr/bin/env bash
# E2E tests for the ANIP GraphQL adapter (TypeScript)
# Usage: ./test-e2e.sh
#
# Starts the TypeScript ANIP server + GraphQL adapter in Docker,
# runs curl-based tests, and tears everything down.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.test.yaml"
PROJECT_NAME="anip-graphql-ts-e2e"
ADAPTER_URL="http://localhost:3004"

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
```

**Step 2: Make executable and commit**

```bash
chmod +x adapters/graphql-ts/test-e2e.sh
git add adapters/graphql-ts/test-e2e.sh
git commit -m "test: add e2e test script for graphql-ts adapter"
```

---

### Task 13: Run all 4 e2e test scripts and verify they pass

**Step 1: Run each test script**

```bash
cd adapters/rest-py && ./test-e2e.sh
cd adapters/rest-ts && ./test-e2e.sh
cd adapters/graphql-py && ./test-e2e.sh
cd adapters/graphql-ts && ./test-e2e.sh
```

Expected: All 4 pass with 4/4 tests each (16 total).

**Step 2: Fix any failures, re-run, and commit fixes**

If any test fails, inspect the Docker logs (`docker compose -p <project> -f docker-compose.test.yaml logs`) and fix the root cause.
