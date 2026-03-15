# Framework Bindings Design

**Goal:** Add three framework binding packages (`anip-flask`, `@anip/express`, `@anip/fastify`) following the same thin-routing-layer pattern as `anip-fastapi` and `@anip/hono`.

**Architecture:** Each binding exposes a single `mount_anip`/`mountAnip` function that takes a framework app + `ANIPService`, mounts 9 routes with identical behavior, and returns a lifecycle handle with `stop()`. Python uses a small `ANIPHandle` class; TypeScript returns `{ stop }`.

---

## Packages

| Package | Language | Framework dep | Version |
|---------|----------|--------------|---------|
| `anip-flask` | Python | `flask >= 3.0` | 0.3.0 |
| `@anip/express` | TypeScript | `express ^4.21.0` | 0.3.0 |
| `@anip/fastify` | TypeScript | `fastify ^5.0.0` | 0.3.0 |

All follow lockstep versioning with existing packages.

## Public API

**Python (Flask):**

```python
def mount_anip(app: Flask, service: ANIPService, prefix: str = "") -> ANIPHandle
```

`ANIPHandle` is a small class with a `.stop()` method.

**TypeScript (Express, Fastify):**

```typescript
function mountAnip(app, service, opts?: { prefix?: string }): { stop: () => void }
```

## Routes (9, identical across all bindings)

- `GET /.well-known/anip` — discovery document
- `GET /.well-known/jwks.json` — public keys
- `GET /anip/manifest` — signed manifest (raw bytes + `X-ANIP-Signature` header)
- `POST /anip/tokens` — issue token (requires auth)
- `POST /anip/permissions` — discover permissions (requires token)
- `POST /anip/invoke/{capability}` — invoke capability (requires token)
- `POST /anip/audit` — query audit log (requires token)
- `GET /anip/checkpoints` — list checkpoints
- `GET /anip/checkpoints/{id}` — get checkpoint by ID

## Lifecycle

`mount` calls `service.start()` immediately and returns a handle. Caller calls `handle.stop()` when done. This is consistent with the Hono binding. FastAPI keeps its native lifecycle hooks (unchanged).

## Error handling

Same status code mapping and error response format as existing bindings:

```json
{ "success": false, "failure": { "type": "<type>", "detail": "<detail>" } }
```

## Testing (8 tests per binding)

1. Discovery — `GET /.well-known/anip` returns 200
2. JWKS — `GET /.well-known/jwks.json` returns 200
3. Manifest — `GET /anip/manifest` returns 200 + signature header
4. Checkpoints list — `GET /anip/checkpoints` returns 200
5. Checkpoint not found — `GET /anip/checkpoints/nonexistent` returns 404
6. Token without auth — `POST /anip/tokens` returns 401
7. Invoke success — authenticated `POST /anip/invoke/{cap}` returns 200
8. Lifecycle — `stop()` callable without error

Test clients: Flask `test_client()`, Express `supertest`, Fastify `inject()`.

## CI and release updates

- `ci-python.yml`: add `anip-flask` to install + test steps
- `ci-typescript.yml`: add `express` and `fastify` to build + test steps
- `release.yml`: expand version validation from 10 to 13 packages
- Update any "10 packages" references to "13 packages"

## Dependencies

**anip-flask:** `anip-service >= 0.3.0`, `flask >= 3.0.0`. Dev: `pytest`.

**@anip/express:** `@anip/service: 0.3.0`, `express: ^4.21.0`. Dev: `@types/express`, `supertest`, `@types/supertest`.

**@anip/fastify:** `@anip/service: 0.3.0`, `fastify: ^5.0.0`.
