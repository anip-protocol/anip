# v0.4 Lineage Design

**Goal:** Add protocol-level lineage to ANIP invoke operations via two fields: a server-generated `invocation_id` and an optional caller-supplied `client_reference_id`.

**Architecture:** Lineage fields are added to core models and flow through the existing request→context→audit→response pipeline. The service runtime generates `invocation_id` early (before validation) so both success and failure paths are traceable. Framework bindings pass lineage fields through with a small wiring change.

**Scope:** Invoke only. Not token issuance, not permission discovery.

---

## Model Cleanup: Collapse InvokeRequest

v0.4 removes the legacy `InvokeRequest` / `InvokeRequestV2` split. ANIP is pre-1.0 with no customers — no backward compatibility needed.

**What changes:**
- Delete `InvokeRequest` (the old embedded-`DelegationToken`-object form with `delegation_token`, `parameters`, `budget`)
- Rename `InvokeRequestV2` → `InvokeRequest` (the JWT-based form with `token`, `parameters`, `budget`)
- The renamed `InvokeRequest` becomes the single canonical invoke request model

**Files affected by the collapse:**

| File | Change |
|------|--------|
| `packages/python/anip-core/src/anip_core/models.py` | Delete old `InvokeRequest` class (line 257), rename `InvokeRequestV2` → `InvokeRequest` (line 250) |
| `packages/python/anip-core/src/anip_core/__init__.py` | Remove `InvokeRequestV2` from imports and `__all__`, keep `InvokeRequest` |
| `packages/typescript/core/src/models.ts` | Delete old `InvokeRequest` Zod schema + type (lines 267-272), rename `InvokeRequestV2` → `InvokeRequest` (lines 301-306) |
| `schema/generate.py` | Update `InvokeRequest` reference (already points to the right class after rename) |
| `schema/README.md` | No change needed (already says `InvokeRequest`) |
| `SPEC.md` | No change needed (already says `InvokeRequest`) |
| `skills/anip-implementer.md` | Update `InvokeRequest` description to reflect JWT-based shape |

**No runtime code imports these models directly** — the service layer and bindings work with dicts/parsed bodies, not typed `InvokeRequest` objects. The collapse is a model-definition and export cleanup.

## Core Models (anip-core / @anip-dev/core)

**InvokeRequest** (single canonical shape):

| Field | Type | Notes |
|-------|------|-------|
| `token` | `str` | JWT string |
| `parameters` | `dict` | Default `{}` |
| `budget` | `dict \| None` | Default `null` |
| `client_reference_id` | `str \| None` | Optional, opaque, max 256 chars |

**InvokeResponse:**

| Field | Type | Notes |
|-------|------|-------|
| `success` | `bool` | |
| `invocation_id` | `str` | Always present, format `inv-{hex12}` |
| `client_reference_id` | `str \| None` | Echoed back if provided |
| `result` | `dict \| None` | |
| `cost_actual` | `CostActual \| None` | |
| `failure` | `ANIPFailure \| None` | |
| `session` | `dict \| None` | |

**Validation:**
- `client_reference_id`: Pydantic `Field(max_length=256)`, Zod `.max(256)`
- `invocation_id`: light regex `^inv-[0-9a-f]{12}$`

## Service Runtime (anip-service / @anip-dev/service)

**`invoke()` signature change:**

```
invoke(capability, token, params, client_reference_id=None)
```

**Behavior:**

1. Generate `invocation_id` at top of invoke, before any validation (`inv-{uuid.hex[:12]}`)
2. `client_reference_id` comes from the invoke request model (sibling to `parameters`, not inside it)
3. Both added to `InvocationContext` — handlers can read them for their own correlation
4. Both included in response (success and failure)
5. Both passed to audit logging
6. Lineage covers all paths inside `invoke()`: unknown capability, delegation validation failure, handler errors, and success. Bearer auth failures (401) happen in bindings before `invoke()` is called — they are transport-level rejections, not invocations, and do not receive lineage.

## Server Layer (anip-server / @anip-dev/server)

**Audit `log_entry()`:** Accepts `invocation_id` and `client_reference_id` as optional fields in `entry_data`. No logic changes — just records what it's given.

**Storage schema:**

```sql
invocation_id TEXT,          -- nullable (non-invoke audit rows)
client_reference_id TEXT     -- nullable (optional field)
```

```sql
CREATE INDEX idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX idx_audit_client_reference_id ON audit_log(client_reference_id);
```

Service guarantees `invocation_id` is present for invoke audit entries. Storage allows null for flexibility (non-invoke audit rows).

**Audit query:** Two new optional filters (exact match):
- `invocation_id` — unique lookup
- `client_reference_id` — returns all matching entries

No migration needed (pre-1.0, ephemeral DBs).

## Framework Bindings (all 5)

Small wiring change only:
- Extract `client_reference_id` from request body alongside `parameters`
- Pass as 4th argument to `service.invoke()`
- No other logic changes

Applies to: anip-fastapi, anip-flask, @anip-dev/hono, @anip-dev/express, @anip-dev/fastify.

## Version Bump

0.3.0 → 0.4.0 across all 13 packages (lockstep).

| Layer | Python | TypeScript |
|-------|--------|------------|
| Core | anip-core | @anip-dev/core |
| Crypto | anip-crypto | @anip-dev/crypto |
| Server | anip-server | @anip-dev/server |
| Service | anip-service | @anip-dev/service |
| Bindings | anip-fastapi, anip-flask | @anip-dev/hono, @anip-dev/express, @anip-dev/fastify |

Inter-package dependencies updated to `>=0.4.0` / `"0.4.0"`.

CI and release workflows: no structural changes.

## ID Formats

| ID | Generated by | Format | Example |
|----|-------------|--------|---------|
| `invocation_id` | Server (service runtime) | `inv-{12 hex chars}` | `inv-a1b2c3d4e5f6` |
| `client_reference_id` | Caller | Opaque string, max 256 | `task:abc/step:3` |

## What v0.4 Does NOT Do

- Standardize raw prompts in the protocol
- Require prompt contents to be stored
- Introduce nested correlation objects
- Add lineage to token issuance or permission discovery
- Maintain backward compatibility with old model shapes
