# Go ANIP Runtime Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a Go ANIP runtime that passes the 44-test conformance suite — the first non-reference-language implementation.

**Architecture:** Single Go module with 5 packages (core, crypto, server, service, httpapi) plus an example flight service. Built from bottom up: types → crypto → storage → delegation → service → HTTP → example → conformance.

**Tech Stack:** Go 1.22+, `go-jose/v4`, `modernc.org/sqlite`, `net/http`

**Design doc:** `docs/plans/2026-03-20-go-runtime-design.md`

---

## Implementation Order

The Go runtime is built bottom-up. Each task produces a compilable, testable package:

1. **Module scaffold + core types** — Go module, protocol types, constants
2. **Crypto** — key management, JWT, JWS, JWKS
3. **Server/storage** — SQLite storage, delegation engine, audit log, Merkle checkpoints
4. **Service** — orchestration, invocation routing, auth, permissions
5. **HTTP binding** — `net/http` handlers for all 9 protocol endpoints
6. **Example app** — flight service
7. **Conformance** — run the suite, fix failures
8. **CI** — GitHub Actions workflow

Each task depends on the previous ones. The implementer should build and test incrementally.

---

## Task 1: Module Scaffold + Core Types

**Files:**
- Create: `packages/go/go.mod`
- Create: `packages/go/core/constants.go`
- Create: `packages/go/core/models.go`
- Create: `packages/go/core/failure.go`
- Create: `packages/go/core/models_test.go`

- [ ] **Step 1: Initialize Go module**

```bash
cd packages/go
go mod init github.com/anip-protocol/anip/packages/go
```

- [ ] **Step 2: Create core/constants.go**

Protocol version, failure type constants, invocation ID generation.

```go
package core

import (
	"crypto/rand"
	"fmt"
)

const ProtocolVersion = "anip/0.11"

// Failure types
const (
	FailureAuthRequired    = "authentication_required"
	FailureInvalidToken    = "invalid_token"
	FailureTokenExpired    = "token_expired"
	FailureScopeInsufficient = "scope_insufficient"
	FailureUnknownCapability = "unknown_capability"
	FailureBudgetExceeded  = "budget_exceeded"
	FailurePurposeMismatch = "purpose_mismatch"
	FailureNotFound        = "not_found"
	FailureUnavailable     = "unavailable"
	FailureConcurrentLock  = "concurrent_lock"
	FailureInternalError   = "internal_error"
	FailureStreamingNotSupported = "streaming_not_supported"
)

// GenerateInvocationID returns a new invocation ID in the format inv-{12 hex chars}.
func GenerateInvocationID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return fmt.Sprintf("inv-%x", b)
}
```

- [ ] **Step 3: Create core/models.go**

Wire-facing protocol types. JSON tags match the ANIP wire format exactly.

The implementer should define these types based on the protocol reference:
- `CapabilityDeclaration` with all fields (name, description, inputs, output, side_effect, minimum_scope, cost, requires, response_modes, etc.)
- `SideEffect` — type + rollback_window
- `Cost` — certainty, financial, determined_by, compute, etc.
- `CapabilityInput`, `CapabilityOutput`
- `DelegationToken` — token_id, subject, scope, purpose, constraints, root_principal, expires, etc.
- `DelegationConstraints` — max_delegation_depth, concurrent_branches
- `Purpose` — capability, parameters, task_id
- `InvocationResult` — success, invocation_id, result, cost_actual, failure, client_reference_id
- `PermissionResponse` — available, restricted, denied arrays
- `AuditEntry` — all audit fields
- `Checkpoint` — checkpoint_id, merkle_root, range, timestamp, entry_count
- `TokenResponse` — issued, token_id, token, expires

Use the exact field names from the protocol reference in the design doc. All exported fields with `json:"snake_case"` tags where the protocol uses snake_case.

- [ ] **Step 4: Create core/failure.go**

```go
package core

// ANIPError is a structured protocol failure.
type ANIPError struct {
	ErrorType  string      `json:"type"`
	Detail     string      `json:"detail"`
	Resolution *Resolution `json:"resolution,omitempty"`
	Retry      bool        `json:"retry"`
}

type Resolution struct {
	Action               string  `json:"action"`
	Requires             *string `json:"requires"`
	GrantableBy          *string `json:"grantable_by"`
	EstimatedAvailability *string `json:"estimated_availability"`
}

func (e *ANIPError) Error() string {
	return e.ErrorType + ": " + e.Detail
}

// NewANIPError creates a new ANIPError.
func NewANIPError(errType, detail string) *ANIPError {
	return &ANIPError{ErrorType: errType, Detail: detail}
}

// WithResolution adds a resolution to the error.
func (e *ANIPError) WithResolution(action string) *ANIPError {
	e.Resolution = &Resolution{Action: action}
	return e
}

// WithRetry marks the error as retryable.
func (e *ANIPError) WithRetry() *ANIPError {
	e.Retry = true
	return e
}

// FailureStatusCode maps failure types to HTTP status codes.
func FailureStatusCode(failureType string) int {
	switch failureType {
	case FailureAuthRequired, FailureInvalidToken, FailureTokenExpired:
		return 401
	case FailureScopeInsufficient, FailureBudgetExceeded, FailurePurposeMismatch:
		return 403
	case FailureUnknownCapability, FailureNotFound:
		return 404
	case FailureUnavailable, FailureConcurrentLock:
		return 409
	case FailureInternalError:
		return 500
	default:
		return 400
	}
}
```

- [ ] **Step 5: Write core tests**

Test invocation ID format, ANIPError behavior, status code mapping, model JSON serialization.

- [ ] **Step 6: Verify and commit**

```bash
cd packages/go && go test ./core/... -v
git add packages/go/
git commit -m "feat(go): add core types, models, and constants"
```

---

## Task 2: Crypto Package

**Files:**
- Create: `packages/go/crypto/keys.go`
- Create: `packages/go/crypto/jwt.go`
- Create: `packages/go/crypto/jws.go`
- Create: `packages/go/crypto/jwks.go`
- Create: `packages/go/crypto/crypto_test.go`

- [ ] **Step 1: Add go-jose dependency**

```bash
cd packages/go && go get go.step.sm/crypto && go get github.com/go-jose/go-jose/v4
```

Or use the correct import path — check the actual go-jose v4 module path.

- [ ] **Step 2: Implement keys.go**

`KeyManager` that generates or loads two ES256 key pairs:
- Delegation key pair — for signing/verifying delegation JWTs
- Audit key pair — for signing audit entries

Key storage: JSON files on disk (same format as Python/TS — `delegation_key.json`, `audit_key.json` or a combined `anip-keys/` directory).

Key ID (`kid`): computed from JWK thumbprint per RFC 7638.

- [ ] **Step 3: Implement jwt.go**

- `SignDelegationJWT(key, claims) → (string, error)` — sign a delegation token as ES256 JWT
- `VerifyDelegationJWT(key, token, issuer, audience) → (claims, error)` — verify and decode

JWT claims must include: `jti`, `iss`, `sub`, `aud`, `iat`, `exp`, `scope`, `root_principal`, `capability`, `parent_token_id`, `purpose`, `constraints`.

- [ ] **Step 4: Implement jws.go**

- `SignDetachedJWS(key, payload) → (string, error)` — create detached JWS signature for manifest
- `VerifyDetachedJWS(key, payload, signature) → error` — verify

Used for the `X-ANIP-Signature` header on `GET /anip/manifest`.

- [ ] **Step 5: Implement jwks.go**

- `ToJWKS(delegationPub, auditPub) → map[string]any` — serialize public keys as JWKS
- Each key includes `kid`, `kty: "EC"`, `crv: "P-256"`, `x`, `y`, `alg: "ES256"`, `use`

- [ ] **Step 6: Write tests**

- Key generation and round-trip load/store
- JWT sign → verify round-trip
- JWT verification fails with wrong key
- JWS detached sign → verify
- JWKS output has correct format

- [ ] **Step 7: Commit**

```bash
cd packages/go && go test ./crypto/... -v
git add packages/go/
git commit -m "feat(go): add crypto package — keys, JWT, JWS, JWKS"
```

---

## Task 3: Server Package (Storage + Delegation + Audit + Checkpoints)

**Files:**
- Create: `packages/go/server/storage.go` — Storage interface
- Create: `packages/go/server/sqlite.go` — SQLite implementation
- Create: `packages/go/server/delegation.go` — token issuance and resolution
- Create: `packages/go/server/audit.go` — audit log
- Create: `packages/go/server/checkpoint.go` — Merkle tree + checkpoints
- Create: `packages/go/server/server_test.go`

This is the largest task. The implementer should build incrementally: storage first, then delegation, then audit, then checkpoints.

- [ ] **Step 1: Define Storage interface (storage.go)**

```go
type Storage interface {
	// Tokens
	StoreToken(token map[string]any) error
	LoadToken(tokenID string) (map[string]any, error)

	// Audit
	AppendAuditEntry(entry map[string]any) (map[string]any, error) // returns entry with sequence_number, previous_hash
	QueryAuditEntries(filters AuditFilters) ([]map[string]any, error)
	GetMaxAuditSequence() (int, error)
	GetAuditEntriesRange(first, last int) ([]map[string]any, error)
	UpdateAuditSignature(seqNum int, signature string) error

	// Checkpoints
	StoreCheckpoint(body map[string]any, signature string) error
	ListCheckpoints(limit int) ([]map[string]any, error)
	GetCheckpointByID(id string) (map[string]any, error)
}
```

- [ ] **Step 2: Implement SQLite storage (sqlite.go)**

Use `modernc.org/sqlite` via `database/sql`. Tables:
- `delegation_tokens` — token_id (PK), data (JSON blob)
- `audit_log` — sequence_number (PK, autoincrement), timestamp, capability, token_id, root_principal, invocation_id, client_reference_id, data (JSON), previous_hash, signature
- `checkpoints` — checkpoint_id (PK), data (JSON), signature

Indexes on audit_log: capability, timestamp, root_principal, invocation_id.

- [ ] **Step 3: Implement delegation engine (delegation.go)**

- `IssueDelegationToken(km *crypto.KeyManager, storage Storage, principal string, req TokenRequest) → (TokenResponse, error)`
- `ResolveBearerToken(km *crypto.KeyManager, storage Storage, serviceID string, jwtString string) → (*core.DelegationToken, error)`
  - Verify JWT signature
  - Load stored token by `jti`
  - Compare signed claims against stored values (subject, scope, capability, root_principal, constraints)
- Scope validation: check that token's scope covers the capability's minimum_scope

- [ ] **Step 4: Implement audit log (audit.go)**

- `AppendAuditEntry(storage, km, entry) → error` — atomically assign sequence, compute previous_hash chain, sign entry
- `QueryAudit(storage, rootPrincipal, filters) → (AuditResponse, error)` — filter by capability, since, invocation_id, limit
- Previous hash: `sha256:hex(sha256(previous_entry_json))` — chain integrity

- [ ] **Step 5: Implement Merkle tree + checkpoints (checkpoint.go)**

RFC 6962 Merkle tree:
- Leaf hash: `SHA256(0x00 || data)`
- Node hash: `SHA256(0x01 || left || right)`
- Root: `sha256:hex`

Checkpoint creation:
- Range of audit entries → compute Merkle root
- Store checkpoint with ID, root, range, timestamp, entry_count, signature

Inclusion proof generation:
- Given leaf_index, return proof path `[{hash, side}]`
- If audit entries expired (deleted by retention), return `proof_unavailable: "audit_entries_expired"`

- [ ] **Step 6: Write tests**

- SQLite CRUD for tokens, audit entries, checkpoints
- Delegation: issue → resolve round-trip, scope validation
- Audit: append → query, hash chain integrity, filtering
- Merkle: tree construction, root computation, inclusion proof verification
- Checkpoint: create and retrieve

- [ ] **Step 7: Commit**

```bash
cd packages/go && go test ./server/... -v
git add packages/go/
git commit -m "feat(go): add server package — storage, delegation, audit, checkpoints"
```

---

## Task 4: Service Package

**Files:**
- Create: `packages/go/service/service.go`
- Create: `packages/go/service/invoke.go`
- Create: `packages/go/service/permissions.go`
- Create: `packages/go/service/service_test.go`

- [ ] **Step 1: Implement service.go**

The Service struct orchestrates crypto + server + capabilities.

```go
type Config struct {
	ServiceID    string
	Capabilities []CapabilityDef
	Storage      string // "sqlite:///path" or ":memory:"
	Trust        string // "signed" or "anchored"
	KeyPath      string
	Authenticate func(bearer string) (principal string, ok bool)
}

type CapabilityDef struct {
	Declaration core.CapabilityDeclaration
	Handler     func(ctx InvocationContext, params map[string]any) (map[string]any, error)
}

type Service struct { /* private fields */ }

func New(cfg Config) *Service
func (s *Service) Start() error    // init storage, load/generate keys
func (s *Service) Shutdown() error // close storage
```

Methods:
- `AuthenticateBearer(bearer) → (principal, ok)` — try bootstrap auth only
- `ResolveBearerToken(jwt) → (*DelegationToken, error)` — verify + resolve ANIP JWT
- `IssueToken(principal, req) → (TokenResponse, error)` — issue delegation token
- `Invoke(capName, token, params, opts) → (map[string]any, error)` — route to handler, audit
- `DiscoverPermissions(token) → PermissionResponse`
- `GetDiscovery(baseURL) → map[string]any` — build discovery document
- `GetSignedManifest() → (manifestJSON, signature)` — manifest + detached JWS
- `GetJWKS() → map[string]any`
- `QueryAudit(token, filters) → (AuditResponse, error)`
- `ListCheckpoints() → ([]Checkpoint, error)`
- `GetCheckpoint(id, includeProof, leafIndex) → (any, error)`

- [ ] **Step 2: Implement invoke.go**

Invocation flow:
1. Look up capability by name (return `unknown_capability` if not found)
2. Validate token scope covers capability's `minimum_scope`
3. Generate `invocation_id`
4. Call handler
5. Append audit entry (success or failure)
6. Return structured result

Handle `stream: true` by returning `streaming_not_supported` error (Phase 1).

- [ ] **Step 3: Implement permissions.go**

For each registered capability, check if the token's scope covers the capability's `minimum_scope`:
- Covered → `available`
- Partially covered or missing → `restricted` with reason
- Denied (never grantable) → `denied`

- [ ] **Step 4: Write tests**

- Service lifecycle: New → Start → Shutdown
- Token issuance and resolution
- Invocation: success, unknown capability, scope mismatch
- Permission discovery: available vs restricted
- Discovery document structure
- JWKS format

- [ ] **Step 5: Commit**

```bash
cd packages/go && go test ./service/... -v
git add packages/go/
git commit -m "feat(go): add service package — orchestration, invocation, permissions"
```

---

## Task 5: HTTP Binding

**Files:**
- Create: `packages/go/httpapi/handler.go`
- Create: `packages/go/httpapi/handler_test.go`

- [ ] **Step 1: Implement handler.go**

```go
func MountANIP(mux *http.ServeMux, svc *service.Service)
```

Registers all 9 routes. Each handler:
1. Extracts auth where needed
2. Parses request (JSON body, query params, path params)
3. Calls the appropriate service method
4. Returns JSON response with correct status code and headers

Auth patterns:
- Token issuance (`POST /anip/tokens`): bootstrap auth via `svc.AuthenticateBearer()`
- Protected routes (`/anip/invoke/*`, `/anip/permissions`, `/anip/audit`): ANIP JWT via `svc.ResolveBearerToken()` — no API key fallback
- Public routes (discovery, JWKS, manifest, checkpoints): no auth

Error responses: all failures return `{"success": false, "failure": {...}}` with appropriate HTTP status code from `core.FailureStatusCode()`.

Manifest response includes `X-ANIP-Signature` header with detached JWS.

Path parameter extraction for `/anip/invoke/{capability}` and `/anip/checkpoints/{id}` — use Go 1.22+ `ServeMux` patterns.

- [ ] **Step 2: Write tests**

Use `httptest.NewServer` + `http.Client` for end-to-end HTTP tests:
- Discovery returns 200 with required fields
- JWKS returns keys
- Manifest has signature header
- Token issuance with valid API key returns issued token
- Token issuance without auth returns 401
- Invoke with valid JWT returns success
- Invoke without auth returns 401
- Invoke with invalid JWT returns 401 with `invalid_token`
- Unknown capability returns 404
- Permissions returns available/restricted/denied
- Audit returns entries
- Checkpoints returns list

- [ ] **Step 3: Commit**

```bash
cd packages/go && go test ./httpapi/... -v
git add packages/go/
git commit -m "feat(go): add HTTP binding — net/http handlers for all protocol routes"
```

---

## Task 6: Example Flight Service

**Files:**
- Create: `packages/go/examples/flights/main.go`
- Create: `packages/go/examples/flights/capabilities.go`

- [ ] **Step 1: Implement capabilities.go**

Two capabilities matching the Python/TS examples:

`search_flights`:
- Side effect: read
- Scope: `travel.search`
- Inputs: origin (airport_code), destination (airport_code), date (date)
- Returns: flight list with flight_number, departure_time, arrival_time, price, currency, stops, count
- Same test data as Python/TS (3 flights for SEA→SFO on 2026-03-10, 0 for 2099-01-01)

`book_flight`:
- Side effect: irreversible
- Scope: `travel.book`
- Financial: estimated $280-500
- Requires: search_flights
- Inputs: flight_number (string), date (date), passengers (integer, default 1)
- Returns: booking_id (BK-xxx), flight details, total_cost
- Sets cost_actual via invocation context

- [ ] **Step 2: Implement main.go**

```go
package main

import (
	"log"
	"net/http"

	"github.com/anip-protocol/anip/packages/go/httpapi"
	"github.com/anip-protocol/anip/packages/go/service"
)

func main() {
	svc := service.New(service.Config{
		ServiceID:    "anip-flight-service",
		Capabilities: []service.CapabilityDef{SearchFlights(), BookFlight()},
		Storage:      "sqlite:///anip.db",
		Trust:        "signed",
		KeyPath:      "./anip-keys",
		Authenticate: func(bearer string) (string, bool) {
			keys := map[string]string{
				"demo-human-key":  "human:samir@example.com",
				"demo-agent-key":  "agent:demo-agent",
			}
			p, ok := keys[bearer]
			return p, ok
		},
	})

	if err := svc.Start(); err != nil {
		log.Fatal(err)
	}
	defer svc.Shutdown()

	mux := http.NewServeMux()
	httpapi.MountANIP(mux, svc)

	log.Println("ANIP Flight Service (Go) running on http://localhost:8080")
	if err := http.ListenAndServe(":8080", mux); err != nil {
		log.Fatal(err)
	}
}
```

- [ ] **Step 3: Build and run**

```bash
cd packages/go/examples/flights
go build -o flight-service .
./flight-service &
curl http://localhost:8080/.well-known/anip | jq .
```

- [ ] **Step 4: Commit**

```bash
git add packages/go/examples/
git commit -m "feat(go): add flight service example app"
```

---

## Task 7: Conformance Suite

- [ ] **Step 1: Run conformance suite against Go example app**

```bash
# Start Go example app
cd packages/go/examples/flights && go run . &
sleep 2

# Run conformance
cd conformance
source .venv/bin/activate
pytest --base-url=http://localhost:8080 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=samples/flight-service.json -v
```

- [ ] **Step 2: Fix any failures**

The conformance suite tests exact protocol shapes. Common issues:
- Field name mismatches (Go JSON tags)
- Missing fields in responses
- Wrong HTTP status codes
- Auth error response shapes
- Invocation ID format
- Discovery document structure

Fix failures one at a time, re-run until all 44 tests pass.

- [ ] **Step 3: Commit fixes**

```bash
git add packages/go/
git commit -m "fix(go): pass conformance suite — all 44 tests"
```

---

## Task 8: CI Workflow

**Files:**
- Create: `.github/workflows/ci-go.yml`

- [ ] **Step 1: Create workflow**

```yaml
name: CI — Go

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      should_test: ${{ steps.filter.outputs.src }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            src:
              - "packages/go/**"
              - ".github/workflows/ci-go.yml"

  test:
    needs: changes
    if: needs.changes.outputs.should_test == 'true'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        go-version: ["1.22", "1.23"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go-version }}

      - name: Build
        working-directory: packages/go
        run: go build ./...

      - name: Test
        working-directory: packages/go
        run: go test ./... -v

  conformance:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.23"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Build and start Go example
        working-directory: packages/go/examples/flights
        run: |
          go build -o flight-service .
          ./flight-service &
          sleep 3

      - name: Install and run conformance suite
        run: |
          pip install -e "./conformance"
          pytest conformance/ \
            --base-url=http://localhost:8080 \
            --bootstrap-bearer=demo-human-key \
            --sample-inputs=conformance/samples/flight-service.json \
            -v

  go-ci:
    if: always()
    needs: [changes, test]
    runs-on: ubuntu-latest
    steps:
      - name: Passed
        if: needs.test.result == 'success' || needs.test.result == 'skipped'
        run: echo "Go CI passed"
      - name: Failed
        if: needs.test.result == 'failure' || needs.test.result == 'cancelled'
        run: exit 1
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci-go.yml
git commit -m "ci: add Go CI workflow with conformance suite"
```
