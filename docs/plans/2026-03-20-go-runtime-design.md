# Go ANIP Runtime Design (Phase 1)

**Goal:** Implement a Go ANIP runtime that passes the conformance suite, providing the first non-reference-language implementation of the protocol.

**Architecture:** Single Go module with clear internal packages (core, crypto, server, service, httpapi). `net/http` binding only. Pure-Go SQLite for storage. `go-jose/v4` for all JOSE operations. Example flight service as conformance target.

**Tech Stack:** Go 1.22+, `go-jose/v4`, `modernc.org/sqlite`, `net/http`

---

## Scope

**Phase 1 (this design):**
- Core types and models
- Cryptography (key management, JWT, JWS, JWKS)
- Server primitives (delegation engine, audit log, Merkle checkpoints, SQLite storage)
- Service runtime (orchestration, invocation routing, auth)
- `net/http` HTTP binding
- Example flight service app
- Must pass the existing 44-test conformance suite

**Deferred (Phase 2):**
- Gin framework binding
- REST, GraphQL, MCP interface packages
- PostgreSQL storage
- OIDC authentication helpers

## Module Structure

Single Go module at `packages/go/`:

```
packages/go/
├── go.mod                    # module github.com/anip-protocol/anip/packages/go
├── go.sum
├── core/                     # protocol types, models, constants
│   ├── models.go             # CapabilityDeclaration, SideEffect, Cost, DelegationToken, etc.
│   ├── failure.go            # ANIPError (implements error), failure types, resolution
│   └── constants.go          # PROTOCOL_VERSION, failure type constants
├── crypto/                   # key management, JWT, JWS, JWKS
│   ├── keys.go               # KeyManager — generate/load/store ES256 key pairs
│   ├── jwt.go                # sign/verify delegation JWTs
│   ├── jws.go                # detached JWS for manifest signing
│   └── jwks.go               # JWKS serialization
├── server/                   # delegation engine, audit, checkpoints, storage
│   ├── delegation.go         # token issuance, resolution, scope validation
│   ├── audit.go              # audit log — append, query, filter
│   ├── checkpoint.go         # Merkle tree, checkpoint creation, proof generation
│   ├── storage.go            # Storage interface (token store, audit store, checkpoint store)
│   └── sqlite.go             # SQLite implementation (modernc.org/sqlite)
├── service/                  # ANIPService — orchestrates everything
│   ├── service.go            # Service struct, Config, lifecycle (Start/Shutdown)
│   ├── invoke.go             # capability invocation routing
│   └── permissions.go        # permission discovery
├── httpapi/                  # net/http binding
│   └── handler.go            # MountANIP(mux, service) — registers all protocol routes
└── examples/
    └── flights/              # Go flight service example
        ├── main.go
        └── capabilities.go
```

Users import: `github.com/anip-protocol/anip/packages/go/service`

## Dependencies

| Dependency | Purpose |
|-----------|---------|
| `go-jose/v4` | JWT signing/verification, JWS detached signatures, JWKS serialization, key thumbprints |
| `modernc.org/sqlite` | Pure-Go SQLite storage (no CGO) |
| Go stdlib | `net/http`, `crypto/ecdsa`, `crypto/elliptic`, `crypto/sha256`, `encoding/json`, `database/sql` |

No other external dependencies.

## Core Types (`core/`)

Wire-facing types with `json` tags matching the ANIP protocol format exactly (snake_case as used by the protocol).

### Key types:

```go
type CapabilityDeclaration struct {
    Name            string          `json:"name"`
    Description     string          `json:"description"`
    ContractVersion string          `json:"contract_version"`
    Inputs          []CapInput      `json:"inputs"`
    Output          CapOutput       `json:"output"`
    SideEffect      SideEffect      `json:"side_effect"`
    MinimumScope    []string        `json:"minimum_scope"`
    Cost            *Cost           `json:"cost,omitempty"`
    Requires        []CapRequires   `json:"requires,omitempty"`
    ResponseModes   []string        `json:"response_modes,omitempty"`
}

type SideEffect struct {
    Type           string `json:"type"`            // "read", "write", "irreversible", "transactional"
    RollbackWindow string `json:"rollback_window"` // "not_applicable", "none", duration
}

type DelegationToken struct {
    TokenID       string   `json:"token_id"`
    Subject       string   `json:"subject"`
    Scope         []string `json:"scope"`
    Capability    string   `json:"capability"`
    RootPrincipal string   `json:"root_principal"`
    ParentTokenID string   `json:"parent_token_id,omitempty"`
    Constraints   any      `json:"constraints,omitempty"`
    ExpiresAt     string   `json:"expires"`
}
```

### ANIPError:

```go
type ANIPError struct {
    ErrorType  string      `json:"type"`
    Detail     string      `json:"detail"`
    Resolution *Resolution `json:"resolution,omitempty"`
    Retry      bool        `json:"retry"`
}

func (e *ANIPError) Error() string {
    return e.ErrorType + ": " + e.Detail
}
```

Implements the `error` interface so it works with Go error handling idioms (`if err != nil`).

## Crypto (`crypto/`)

Uses `go-jose/v4` for all JOSE operations. Stdlib `crypto/ecdsa` with P-256 for key generation.

### KeyManager

- Generate or load ES256 key pairs (delegation key + audit key)
- Persist keys to disk as JSON (same format as Python/TS)
- Two key pairs: one for delegation tokens, one for audit entry signing
- Key ID (`kid`) computed from JWK thumbprint (RFC 7638)

### JWT

- Sign delegation tokens as ES256 JWTs with standard claims (`jti`, `iss`, `aud`, `sub`, `exp`, `iat`) plus ANIP claims (`scope`, `capability`, `root_principal`, `parent_token_id`, `constraints`)
- Verify JWTs against the delegation public key

### JWS

- Detached JWS signatures for manifest signing (`X-ANIP-Signature` header)

### JWKS

- Serialize public keys as JWKS (`/.well-known/jwks.json`)
- Standard JWK format with `kid`, `kty`, `crv`, `x`, `y`, `alg`, `use`

## Server (`server/`)

### Storage Interface

```go
type Storage interface {
    // Tokens
    StoreToken(token *core.DelegationToken) error
    GetToken(tokenID string) (*core.DelegationToken, error)

    // Audit
    AppendAuditEntry(entry *AuditEntry) error
    QueryAudit(filters AuditFilters) ([]AuditEntry, error)

    // Checkpoints
    StoreCheckpoint(cp *Checkpoint) error
    ListCheckpoints(limit int) ([]Checkpoint, error)
    GetCheckpoint(id string) (*Checkpoint, error)
}
```

SQLite implementation via `modernc.org/sqlite` through `database/sql`. Same schema as Python/TS — tokens table, audit_log table (indexed on capability, timestamp, root_principal, invocation_id), checkpoints table.

### Delegation Engine

- Issue root tokens (from bootstrap auth principal)
- Issue child tokens (sub-delegation with scope narrowing)
- Resolve bearer tokens: verify JWT → load stored token → compare claims against stored state
- Validate scope sufficiency for capability invocation

### Audit Log

- Append entry on every invocation (success or failure)
- Query with filters: capability, since, invocation_id, client_reference_id, limit
- Entries scoped to root principal (no cross-principal leakage)

### Checkpoints

- Merkle tree over audit entries (SHA-256)
- Checkpoint creation with `checkpoint_id`, `merkle_root`, `timestamp`, `entry_count`, `range` (from/to entry indices)
- Pagination via `next_cursor` on list endpoint
- Inclusion proof generation when `include_proof=true&leaf_index=N` is requested
- If proof generation fails because audit entries have been deleted by retention enforcement:
  - Return HTTP 200 (not an error)
  - Omit `inclusion_proof` field
  - Include `proof_unavailable: "audit_entries_expired"`
  - The checkpoint itself remains valid (merkle root was computed at checkpoint time)
- Not-found checkpoint returns 404

## Service (`service/`)

Orchestrates core + crypto + server into a usable runtime.

```go
type Config struct {
    ServiceID    string
    Capabilities []CapabilityDef
    Storage      string // "sqlite:///path" or ":memory:"
    Trust        string // "signed" or "anchored"
    KeyPath      string
    Authenticate func(bearer string) (principal string, ok bool)
}

type Service struct { ... }

func New(cfg Config) *Service
func (s *Service) Start() error
func (s *Service) Shutdown() error
func (s *Service) AuthenticateBearer(bearer string) (string, bool)
func (s *Service) ResolveBearerToken(jwt string) (*core.DelegationToken, error)
func (s *Service) IssueToken(principal string, req TokenRequest) (TokenResponse, error)
func (s *Service) Invoke(capName string, token *core.DelegationToken, params map[string]any, opts InvokeOpts) (map[string]any, error)
func (s *Service) DiscoverPermissions(token *core.DelegationToken) PermissionResponse
func (s *Service) GetDiscovery(baseURL string) map[string]any
func (s *Service) GetManifest() (manifest any, signature string)
func (s *Service) GetJWKS() map[string]any
func (s *Service) QueryAudit(token *core.DelegationToken, filters AuditFilters) (AuditResponse, error)
func (s *Service) ListCheckpoints() (CheckpointListResponse, error)
func (s *Service) GetCheckpoint(id string, includeProof bool, leafIndex int) (any, error)
```

`Authenticate` returns `(principal, ok)` — Go idiom for "found or not found".

## HTTP Binding (`httpapi/`)

```go
func MountANIP(mux *http.ServeMux, svc *service.Service)
```

No error return — route registration is deterministic.

Registers all 9 protocol endpoints. Auth handling follows the reference bindings exactly:

**Token issuance (`POST /anip/tokens`):** Bootstrap auth only — extract bearer, call `svc.AuthenticateBearer()` to get a principal. API keys, OIDC tokens, etc. This is the bootstrap entry point.

**Protected routes (`/anip/invoke/*`, `/anip/permissions`, `/anip/audit`):** ANIP delegation JWT only — extract bearer, call `svc.ResolveBearerToken()` to get a `DelegationToken`. No API key fallback. If JWT resolution fails, return structured `ANIPError` (`invalid_token`, `authentication_required`). The caller must first obtain a token via `/anip/tokens`.

This matches the Python/TS bindings where `_extract_principal` handles token issuance and `_resolve_token` handles protected routes — they are separate code paths, not fallback chains.

- Failure responses use structured `ANIPError` with `type`, `detail`, `resolution`, `retry`
- HTTP status mapping: 401 for auth errors, 403 for scope/budget, 404 for unknown capability

`{capability}` path parameter: Go 1.22+ `ServeMux` supports `{name}` patterns natively.

## Example App

Same flight service as Python/TS:
- `search_flights` — read, `travel.search` scope, returns flight list
- `book_flight` — irreversible, financial, `travel.book` scope, returns booking with cost actual

Bootstrap auth: `demo-human-key` → `human:samir@example.com`, `demo-agent-key` → `agent:demo-agent`.

## Testing

### Conformance suite (protocol acceptance gate)

```bash
cd conformance
pytest --base-url=http://localhost:8080 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=samples/flight-service.json -v
```

Must pass all 44 tests. This validates the Go runtime implements the protocol correctly at the HTTP level.

### Go unit tests (implementation safety)

Each package gets Go tests (`*_test.go`) covering:
- `core/` — model serialization, ANIPError behavior
- `crypto/` — key generation, JWT round-trip, JWS verify, JWKS format
- `server/` — delegation issuance/resolution, audit append/query, Merkle tree correctness, SQLite storage
- `service/` — invocation routing, scope validation, permission discovery
- `httpapi/` — route registration, auth extraction, error response shapes

### CI

Add a `ci-go.yml` workflow:
- Go versions: 1.22, 1.23
- `go build ./...`
- `go test ./...`
- Start example app, run conformance suite

## Known Protocol Gaps

**Streaming invocations:** The ANIP protocol defines streaming response mode (`response_modes: ["streaming"]`) with SSE transport (progress events → completed/failed). Phase 1 implements **unary invocation only**. Capabilities that declare `response_modes: ["unary"]` work correctly. Capabilities requesting `stream: true` should return a structured error (`streaming_not_supported`). This is an honest protocol gap — the Go runtime is not a complete v0.11 implementation until streaming is added in Phase 2.

## What This Does NOT Cover

- Gin framework binding (Phase 2)
- REST, GraphQL, MCP interface packages (Phase 2)
- PostgreSQL storage (Phase 2)
- OIDC authentication
- Streaming invocations / SSE (Phase 2 — see Known Protocol Gaps above)
- Horizontal scaling / multi-replica
- Go module publishing to proxy.golang.org (happens automatically via git tags)
