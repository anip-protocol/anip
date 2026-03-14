# ANIP Service Runtime Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan from this design.

**Goal:** Shift ANIP from a primitive toolkit to a configurable service runtime, making adoption feel like configuration rather than assembly.

**Core problem:** ANIP currently exposes mostly primitives. Developers must manually wire keys, storage, engine, manifest, audit, checkpoints, scheduling, sink publication, token issuance, permissions, and HTTP routes. Most will stop there.

**Solution:** Two new packages on top of the existing stack — a service runtime builder and framework bindings — plus restructured examples and docs that lead with the lightweight path.

---

## 1. Package Architecture

```
core → crypto → server → service → fastapi/hono
```

### New packages

| Package | Python | TypeScript |
|---------|--------|------------|
| Service runtime | `anip-service` | `@anip/service` |
| Framework bindings | `anip-fastapi` | `@anip/hono` |

### Filesystem layout

```
packages/
  python/
    anip-core/          (existing, unchanged)
    anip-crypto/        (existing, unchanged)
    anip-server/        (existing, unchanged)
    anip-service/       (new)
    anip-fastapi/       (new)
  typescript/
    core/               (existing, unchanged)
    crypto/             (existing, unchanged)
    server/             (existing, unchanged)
    service/            (new)
    hono/               (new)
```

### Layer responsibilities

- **core** — protocol types, models, constants
- **crypto** — key management, signing, verification
- **server** — DelegationEngine, AuditLog, MerkleTree, StorageBackend, CheckpointPolicy, buildManifest, discoverPermissions (available for Tier 2 adopters)
- **service** — `ANIPService` builder/runtime. Creates and owns all SDK instances. Registers capabilities. Exposes domain-level operations (not HTTP-shaped). Owns `InvocationContext` and `Capability` types.
- **fastapi/hono** — Mounts an `ANIPService` as HTTP routes. One function: `mount_anip()` / `mountAnip()`. Translates HTTP to service calls and service responses to HTTP. Nothing else.

### Key architectural principle

- **service** speaks protocol/domain concepts, not transport concepts
- **framework packages** own transport only

---

## 2. ANIPService API

### Tier 1: Simple adoption

**Python:**
```python
from anip_service import ANIPService

service = ANIPService(
    service_id="anip-flight-service",
    capabilities=[search_flights, book_flight],
    storage="sqlite:///anip.db",
    trust="signed",
)
```

**TypeScript:**
```typescript
import { createANIPService } from "@anip/service";

const service = createANIPService({
  serviceId: "anip-flight-service",
  capabilities: [searchFlights, bookFlight],
  storage: { type: "sqlite", path: "./anip.db" },
  trust: "signed",
});
```

### Tier 2: Advanced customization

```python
service = ANIPService(
    service_id="anip-flight-service",
    capabilities=[search_flights, book_flight],
    storage=my_custom_storage,           # any StorageBackend
    key_path="/etc/anip/keys",           # explicit key location
    trust={
        "level": "anchored",
        "anchoring": {
            "cadence": "PT30S",
            "max_lag": 120,
            "sinks": [my_witness_sink],
        },
    },
    audit_signer=my_custom_signer,
    checkpoint_policy=CheckpointPolicy(entry_count=100),
)
```

### Defaults

| Setting | Default | Why |
|---------|---------|-----|
| `storage` | `"sqlite:///anip.db"` | Persistent, zero-config |
| `trust` | `"signed"` | Secure but simple — no checkpoint infrastructure needed |
| `key_path` | `"./anip-keys"` | Local persistence, auto-generated |
| `checkpoints` | Off | Only activated when trust is `"anchored"` or explicitly configured |
| `sinks` | None | Advanced feature, off by default |

### Storage shorthand

The `storage` parameter accepts either a string shorthand or a `StorageBackend` instance:

- `"sqlite:///path/to/db"` — creates `SQLiteStorage`
- `":memory:"` — creates `InMemoryStorage` (testing)
- Any `StorageBackend` instance — used directly (Tier 2)

### What ANIPService owns internally

Once constructed, it creates and holds:
- `KeyManager` (from `key_path`)
- `StorageBackend` (from `storage` parameter)
- `DelegationEngine` (with `service_id`)
- `AuditLog` (with storage + signer wired from KeyManager)
- Manifest (auto-built from registered capabilities)
- `CheckpointScheduler` (if anchoring configured)
- Capability registry (declaration + handler map)

### Domain-level operations (framework-agnostic)

The service exposes methods that speak domain, not HTTP:

```python
service.get_discovery()
service.get_manifest()
service.get_jwks()
service.issue_token(authenticated_principal, request)
service.discover_permissions(token)
service.invoke(capability_name, token, params)
service.query_audit(token, filters)
service.get_checkpoints(...)
service.get_checkpoint(checkpoint_id, options)
```

Token resolution also lives in the service:
```python
service.resolve_bearer_token(jwt_string)
```

Framework bindings call these methods. Tests call them directly. No HTTP types leak into the service layer.

---

## 3. Capability Model

### Capability object

Bundles declaration + handler. This is what developers author.

**Python:**
```python
from anip_service import Capability, InvocationContext

search_flights = Capability(
    declaration=CapabilityDeclaration(
        name="search_flights",
        description="Search available flights",
        ...
    ),
    handler=handle_search,
)

def handle_search(ctx: InvocationContext, params: dict) -> dict:
    flights = find_flights(params["origin"], params["destination"])
    return {"flights": flights, "count": len(flights)}
```

**TypeScript:**
```typescript
import { defineCapability } from "@anip/service";

export const searchFlights = defineCapability({
  declaration: { name: "search_flights", ... },
  handler: (ctx, params) => {
    const flights = findFlights(params.origin, params.destination);
    return { flights, count: flights.length };
  },
});
```

### InvocationContext

```python
@dataclass
class InvocationContext:
    token: DelegationToken
    root_principal: str
    subject: str
    scopes: list[str]
    delegation_chain: list[str]  # token IDs

    def set_cost_actual(self, cost: dict) -> None:
        """Set actual cost for variance tracking against declared cost."""
        ...
```

Extensible later with `invocation_id`, `client_reference_id` without changing the handler signature.

### Handler contract

- **Input:** `(ctx: InvocationContext, params: dict) -> result`
- **Output:** Plain result data (dict/object). The runtime wraps it into a success `InvokeResponse`.
- **Errors:** Raise `ANIPError(type, detail)` for structured failures. Unhandled exceptions become `"internal_error"` with detail redacted in response, logged in audit.
- **Cost tracking:** Call `ctx.set_cost_actual({...})` instead of mixing cost metadata into return values.

### Runtime invocation flow

When `service.invoke(capability_name, token, params)` is called:

1. Validate token (delegation chain, scope, constraints)
2. Check capability exists and token has required scope
3. Acquire exclusive lock if configured for this capability (opt-in, not automatic)
4. Build `InvocationContext` from token
5. Call `handler(ctx, params)`
6. If handler returns normally: wrap in success `InvokeResponse`
7. If handler raises `ANIPError`: wrap in structured failure `InvokeResponse`
8. If handler raises unexpected exception: wrap in `"internal_error"` failure, log details in audit
9. Extract cost from context if set, compute variance against declaration
10. Log audit entry (with signature)
11. Trigger checkpoint if policy threshold met
12. Release lock if held
13. Return the response

---

## 4. Framework Bindings

One function. Mounts all ANIP routes onto an existing app.

### Python (`anip-fastapi`)

```python
from fastapi import FastAPI
from anip_fastapi import mount_anip

app = FastAPI()
mount_anip(app, service)
```

### TypeScript (`@anip/hono`)

```typescript
import { Hono } from "hono";
import { mountAnip } from "@anip/hono";

const app = new Hono();
mountAnip(app, service);
```

### Route table

| Route | Method | Service method |
|-------|--------|----------------|
| `/.well-known/anip` | GET | `service.get_discovery()` |
| `/.well-known/jwks.json` | GET | `service.get_jwks()` |
| `/anip/manifest` | GET | `service.get_manifest()` |
| `/anip/tokens` | POST | `service.issue_token(principal, request)` |
| `/anip/permissions` | GET | `service.discover_permissions(token)` |
| `/anip/invoke/{capability}` | POST | `service.invoke(capability, token, params)` |
| `/anip/audit` | GET | `service.query_audit(token, filters)` |
| `/anip/checkpoints` | GET | `service.get_checkpoints(...)` |
| `/anip/checkpoints/{id}` | GET | `service.get_checkpoint(id, options)` |

### Binding responsibilities

**Owns:**
- Parse `Authorization: Bearer <jwt>` header
- Call `service.resolve_bearer_token(jwt)` for token resolution
- Parse request body / query params
- Map service responses to HTTP status codes (200, 400, 401, 403, 404, 409)
- Map `ANIPError` types to appropriate HTTP status
- Set response headers

**Does NOT own:**
- Validation logic
- Audit logging
- Token issuance logic
- Anything protocol-specific

### Customization

Optional prefix: `mount_anip(app, service, prefix="/v1")` mounts under `/v1/...`. Default is no prefix.

Developers add non-ANIP routes using their framework normally — the ANIP routes are mounted alongside.

---

## 5. Trust Tiers

Moving between tiers is a configuration change, not a code rewrite. Handler code is identical across all trust levels.

### Tier 1: Signed (default)

```python
trust="signed"
```

- JWT-signed tokens, cryptographically verified
- Signed manifest with JWKS
- Local audit log with hash chain and signatures
- Local integrity guarantees
- No checkpoints, no sinks, no external dependencies
- Fully valid, spec-compliant ANIP service

### Tier 2: Anchored

```python
trust={
    "level": "anchored",
    "anchoring": {
        "cadence": "PT30S",
        "max_lag": 120,
        "sinks": [my_qualifying_sink],
    },
}
```

Adds on top of signed:
- Automatic checkpoint scheduling
- Sink publication to qualifying external witnesses
- Anchoring lag tracking in discovery
- Consistency/inclusion proof endpoints activated

**Important:** `LocalFileSink` exists for development and testing but is non-qualifying for real anchored trust posture. True anchored mode requires external witness sinks (`witness:`, `https:`).

### Tier 3: Attested (future, reserved)

`trust="attested"` is accepted but raises a clear error: not yet supported. Design space reserved.

### What each tier activates internally

| Component | Signed | Anchored |
|---|---|---|
| KeyManager | yes | yes |
| DelegationEngine | yes | yes |
| AuditLog + signing | yes | yes |
| CheckpointScheduler | no | yes |
| Sinks | no | yes |
| Anchoring lag in discovery | no | yes |
| Proof endpoints | available but no data | active |

---

## 6. Example App Restructuring

### Target layout

**Python:**
```
examples/anip/
  capabilities/
    search_flights.py    # declaration + handler
    book_flight.py       # declaration + handler
  domain/
    flights.py           # flight data, booking logic (ANIP-free)
  app.py                 # one ANIPService() + mount_anip()
  main.py                # uvicorn bootstrap only
```

**TypeScript:**
```
examples/anip-ts/
  src/
    capabilities/
      search-flights.ts  # declaration + handler
      book-flight.ts     # declaration + handler
    domain/
      flights.ts         # flight data, booking logic (ANIP-free)
    app.ts               # one createANIPService() + mountAnip()
    main.ts              # serve() bootstrap only
```

### What disappears from examples

| Current file | Replaced by |
|---|---|
| `sdk.ts` / `engine.py` | Service runtime owns singletons |
| `data/database.ts` / `data/database.py` | Service runtime owns audit, storage, checkpoints |
| `delegation-helpers.ts` | Validation logic in service runtime |
| `sink-queue.ts` / `primitives/checkpoint.py` | Checkpoint scheduling in service runtime |
| All manual route definitions in server.ts/main.py | Framework binding mounts them |

### What stays

- `domain/` — business logic, fully ANIP-free
- `capabilities/` — declaration + handler, the only ANIP-aware authored code
- `app.*` — configuration entrypoint
- `main.*` — trivial server bootstrap

### Line count target

| | Current | After |
|---|---|---|
| Python example | ~900 lines | ~150 lines |
| TypeScript example | ~1,200 lines | ~150 lines |
| Protocol plumbing in examples | ~80% | ~0% |

---

## 7. Documentation & Mental Model

### Target mental model

> "ANIP is a service runtime you configure — define your capabilities, choose your trust level, start the server."

Primitives are still documented, but positioned as the advanced/customization path.

### Doc structure

1. **Quickstart** — define capabilities, launch a service (< 50 lines, copy-pasteable)
2. **Capabilities** — declaration format, handler contract, error handling
3. **Configuration** — storage, trust levels, key management
4. **Advanced** — custom storage backends, custom sinks, checkpoint policies, direct SDK access
5. **Reference** — core types, crypto API, server primitives

### Lite vs Advanced marker

Every doc section introducing an advanced concept:

> **Advanced.** The default signed trust mode handles this automatically. Read this section if you need to customize [X].

This gives developers permission to skip sections and still ship a valid service.

---

## Standing Design Refinements

These were agreed during design review and must be carried through to implementation:

1. `anip-service` must remain transport-agnostic — no HTTP types in the service layer
2. `LocalFileSink` is dev-only, non-qualifying for real anchored trust — frame honestly
3. Cost tracking via `ctx.set_cost_actual()`, not magic underscore keys in handler return values
4. Locking is opt-in per capability configuration, not automatic for all side effects
5. `domain/` in examples must be fully ANIP-free
6. Discovery endpoint (`/.well-known/anip`) is separate from manifest endpoint (`/anip/manifest`)
