# Go Gin Binding Design

**Goal:** Add a Gin framework binding for the Go ANIP runtime, providing the second Go HTTP framework target.

**Architecture:** New `ginapi` package in the existing Go module. Same 9 routes, same service-layer calls, same auth semantics. Gin-native request/response handling. Small shared utilities for bearer extraction and error response formatting extracted from `httpapi` to avoid duplication.

**Tech Stack:** `github.com/gin-gonic/gin`

---

## Package Structure

```
packages/go/
├── internal/httputil/       # NEW — shared bearer extraction, error response helpers
│   └── helpers.go
├── httpapi/
│   └── handler.go           # MODIFIED — uses internal/httputil for shared logic
├── ginapi/                   # NEW
│   ├── handler.go            # MountANIPGin(router, svc) — all 9 routes
│   └── handler_test.go
```

## Public API

```go
func MountANIPGin(router *gin.Engine, svc *service.Service)
```

No return value — route registration is deterministic. Caller owns service lifecycle.

## Shared Utilities (`internal/httputil/`)

Small helpers shared by both `httpapi` and `ginapi`:

- `ExtractBearer(authHeader string) string` — parse `Authorization: Bearer` header
- `FailureResponse(err *core.ANIPError) (statusCode int, body map[string]any)` — format error
- `AuthFailureTokenEndpoint() (int, map[string]any)` — 401 for missing API key on token issuance
- `AuthFailureJWTEndpoint() (int, map[string]any)` — 401 for missing JWT on protected routes

These are pure functions, no framework dependency.

## Routes

Same 9 routes as `httpapi`, using Gin conventions:

| Route | Gin Pattern | Auth |
|-------|-------------|------|
| `GET /.well-known/anip` | `router.GET` | none |
| `GET /.well-known/jwks.json` | `router.GET` | none |
| `GET /anip/manifest` | `router.GET` | none |
| `POST /anip/tokens` | `router.POST` | bootstrap (API key) |
| `POST /anip/permissions` | `router.POST` | ANIP JWT |
| `POST /anip/invoke/:capability` | `router.POST` | ANIP JWT |
| `POST /anip/audit` | `router.POST` | ANIP JWT |
| `GET /anip/checkpoints` | `router.GET` | none |
| `GET /anip/checkpoints/:id` | `router.GET` | none |

Path params: `:capability` and `:id` (Gin syntax).

## Testing

- Gin test context with `httptest.NewRecorder` for unit tests
- Conformance suite against a Gin-based example (optional — same service, just different binding)

## What This Does NOT Cover

- Gin middleware integration (auth middleware, CORS, etc.)
- Gin-specific error handling beyond ANIP protocol errors
