# v0.7 Discovery Trust & Metadata Posture — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `posture` block to `/.well-known/anip` that exposes audit, lineage, metadata policy, failure disclosure, and anchoring posture — making trust characteristics inspectable before invocation.

**Architecture:** Before adding posture, align the existing discovery response with its own schema and spec (the current implementations drift significantly). Discovery uses `"anip-compliant"` compliance (5 core primitives) since the reference implementations do not implement handshake, graph, or test endpoints. `base_url` is derived from the incoming request at the HTTP binding layer — the service method accepts it as a parameter, and each binding extracts it from the request. Then add typed posture models in both runtimes, computed from existing service configuration. The posture block is OPTIONAL per schema — services MAY omit it, but reference implementations MUST include it.

**Tech Stack:** Python/Pydantic, TypeScript/Zod, JSON Schema (draft 2020-12)

**Design doc:** `/Users/samirski/Development/codex/ANIP/docs/anip-v07-discovery-trust-and-metadata-posture.md`

**Worktree:** `/Users/samirski/Development/ANIP/.worktrees/v07-discovery-posture` (branch: `feature/v07-discovery-posture`)

**Test commands:**
- Python: `.venv/bin/python -m pytest packages/python -x -q`
- TypeScript: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`

---

## Task 1: Version Bumps

Bump all version constants, package configs, model defaults, manifest builder, and test fixtures from 0.3/0.6 → 0.7.

**Files:**

Source constants:
- Modify: `packages/python/anip-core/src/anip_core/constants.py:3-4`
- Modify: `packages/typescript/core/src/constants.ts:1-2`

Model defaults:
- Modify: `packages/python/anip-core/src/anip_core/models.py:207,240`
- Modify: `packages/typescript/core/src/models.ts:241,258`

Manifest builder:
- Modify: `packages/typescript/server/src/manifest.ts:45` (hardcoded `"0.3.0"` — use `MANIFEST_VERSION` constant)

Package configs (version field):
- Modify: `packages/python/anip-core/pyproject.toml:3`
- Modify: `packages/python/anip-crypto/pyproject.toml:3`
- Modify: `packages/python/anip-server/pyproject.toml:3`
- Modify: `packages/python/anip-service/pyproject.toml:3`
- Modify: `packages/python/anip-fastapi/pyproject.toml:3`
- Modify: `packages/typescript/core/package.json:3`
- Modify: `packages/typescript/crypto/package.json:3`
- Modify: `packages/typescript/server/package.json:3`
- Modify: `packages/typescript/service/package.json:3`
- Modify: `packages/typescript/express/package.json:3`
- Modify: `packages/typescript/fastify/package.json:3`
- Modify: `packages/typescript/hono/package.json:3`

Package configs (inter-package dependency versions):
- Modify: `packages/python/anip-crypto/pyproject.toml:7` (`anip-core>=0.6.0` → `>=0.7.0`)
- Modify: `packages/python/anip-server/pyproject.toml:7-8` (`anip-core`, `anip-crypto` deps)
- Modify: `packages/python/anip-service/pyproject.toml:7-8` (`anip-core`, `anip-crypto` deps)
- Modify: `packages/typescript/crypto/package.json:16` (`@anip/core`)
- Modify: `packages/typescript/server/package.json:16-17` (`@anip/core`, `@anip/crypto`)
- Modify: `packages/typescript/service/package.json:16-18` (`@anip/core`, `@anip/crypto`, `@anip/server`)
- Modify: `packages/typescript/express/package.json:16` (`@anip/service`)
- Modify: `packages/typescript/fastify/package.json:16` (`@anip/service`)
- Modify: `packages/typescript/hono/package.json:16` (`@anip/service`)

JSON Schema `$id`:
- Modify: `schema/anip.schema.json` (v0.6 → v0.7 in `$id`)
- Modify: `schema/discovery.schema.json` (v0.6 → v0.7 in `$id`)

Test fixtures:
- Modify: `packages/python/anip-core/tests/test_models.py:16,104-105` (`anip/0.3` → `anip/0.7`)
- Modify: `packages/python/anip-crypto/tests/test_jwt_jws.py:83,90` (`anip/0.3` → `anip/0.7`)
- Modify: `packages/python/anip-server/tests/test_manifest.py:18` (`anip/0.3` → `anip/0.7`)
- Modify: `packages/typescript/core/tests/models.test.ts:19,85` (`anip/0.3` → `anip/0.7`)
- Modify: `packages/typescript/crypto/tests/crypto.test.ts:146,154` (`anip/0.3` → `anip/0.7`)

**Step 1: Update source constants (Python + TypeScript)**

`packages/python/anip-core/src/anip_core/constants.py`:
```python
PROTOCOL_VERSION = "anip/0.7"
MANIFEST_VERSION = "0.7.0"
```

`packages/typescript/core/src/constants.ts`:
```typescript
export const PROTOCOL_VERSION = "anip/0.7";
export const MANIFEST_VERSION = "0.7.0";
```

**Step 2: Update model defaults**

`packages/python/anip-core/src/anip_core/models.py`:
- Line 207: `version: str = "0.7.0"`
- Line 240: `protocol: str = "anip/0.7"`

`packages/typescript/core/src/models.ts`:
- Line 241: `version: z.string().default("0.7.0"),`
- Line 258: `protocol: z.string().default("anip/0.7"),`

**Step 3: Fix TypeScript manifest builder to use constant instead of hardcoded string**

`packages/typescript/server/src/manifest.ts` — add `MANIFEST_VERSION` to the import from `@anip/core` (line 9), then change line 45 from:
```typescript
version: "0.3.0",
```
to:
```typescript
version: MANIFEST_VERSION,
```

**Step 4: Update all package versions**

Use find-and-replace across all pyproject.toml files: `version = "0.6.0"` → `version = "0.7.0"`.
Use find-and-replace across all package.json files: `"0.6.0"` → `"0.7.0"` (for `@anip/*` entries).
Update all Python inter-package deps: `>=0.6.0` → `>=0.7.0`.

**Step 5: Regenerate package-lock.json**

```bash
cd packages/typescript && npm install
```

**Step 6: Update JSON Schema `$id`**

In `schema/anip.schema.json` and `schema/discovery.schema.json`: change `v0.6` → `v0.7` in the `$id` field.

**Step 7: Update test fixtures**

Search for all `"anip/0.3"` in test files and update to `"anip/0.7"`. Key locations:
- Python: `test_models.py` (lines 16, 104-105), `test_jwt_jws.py` (lines 83, 90), `test_manifest.py` (line 18)
- TypeScript: `models.test.ts` (lines 19, 85), `crypto.test.ts` (lines 146, 154)

**Step 8: Run all tests**

```bash
.venv/bin/python -m pytest packages/python -x -q
cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose
```

Expected: All 297 tests pass.

**Step 9: Commit**

```bash
git add -A
git commit -m "chore: bump all versions to 0.7.0 for discovery posture release"
```

---

## Task 2: Discovery Contract Alignment

Before adding posture, fix the existing discovery responses to conform to the spec (SPEC.md §6.1) and JSON schema. Currently both runtimes emit a minimal discovery document missing required fields (`protocol`, `compliance`, `base_url`, `auth`), with wrong `profile` shape (string `"full"` instead of versioned object), and incomplete capability summaries (missing `financial`, using `contract_version` instead of `contract`).

**Design decisions:**
- **`compliance`**: Use `"anip-compliant"` (5 core primitives), NOT `"anip-complete"`. The reference implementations do not implement handshake, graph, or test endpoints — claiming `"anip-complete"` would be a contract violation per SPEC.md §3.
- **`base_url`**: Derived from the incoming HTTP request at the binding layer, NOT a constructor parameter. The service method `get_discovery(base_url=...)` / `getDiscovery({ baseUrl })` accepts it as a call-time parameter. Each HTTP binding (FastAPI, Express, Hono, Fastify) extracts the origin from the request and passes it through. This satisfies the spec requirement that `base_url` be "derived from the incoming request, not hardcoded."
- **`endpoints`**: Only list endpoints that actually exist in the HTTP bindings. No `handshake`, `graph`, or `test` — those are not implemented.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py:152-179` (get_discovery signature + body)
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py:39-41` (pass base_url from request)
- Modify: `packages/typescript/service/src/service.ts:59-60,375-403` (ANIPService interface + getDiscovery)
- Modify: `packages/typescript/express/src/routes.ts:15-17` (pass baseUrl from req)
- Modify: `packages/typescript/hono/src/routes.ts:14` (pass baseUrl from req)
- Modify: `packages/typescript/fastify/src/routes.ts:13-15` (pass baseUrl from req)
- Modify: `packages/python/anip-service/tests/test_service_init.py`
- Modify: `packages/typescript/service/tests/service.test.ts`

**Step 1: Write failing tests (Python)**

Update and extend the `test_discovery_document` test in `packages/python/anip-service/tests/test_service_init.py`:

```python
def test_discovery_document(self):
    service = ANIPService(
        service_id="test-service",
        capabilities=[_test_cap()],
        storage=":memory:",
    )
    disc = service.get_discovery(base_url="https://test.example.com")
    ad = disc["anip_discovery"]

    # Required fields per SPEC.md §6.1
    assert ad["protocol"] == "anip/0.7"
    assert ad["compliance"] == "anip-compliant"
    assert ad["base_url"] == "https://test.example.com"
    assert ad["profile"]["core"] == "1.0"
    assert ad["auth"]["delegation_token_required"] is True
    assert ad["auth"]["minimum_scope_for_discovery"] == "none"

    # Capability summary shape
    greet = ad["capabilities"]["greet"]
    assert greet["description"] == "Say hello"
    assert greet["side_effect"] == "read"
    assert greet["minimum_scope"] == ["greet"]
    assert greet["financial"] is False
    assert greet["contract"] == "1.0"
    assert "contract_version" not in greet

    # Trust and endpoints — only actually implemented endpoints
    assert ad["trust_level"] == "signed"
    assert ad["endpoints"]["manifest"] == "/anip/manifest"
    assert ad["endpoints"]["permissions"] == "/anip/permissions"
    assert ad["endpoints"]["invoke"] == "/anip/invoke/{capability}"
    assert ad["endpoints"]["tokens"] == "/anip/tokens"
    assert ad["endpoints"]["audit"] == "/anip/audit"
    assert ad["endpoints"]["checkpoints"] == "/anip/checkpoints"
    assert "handshake" not in ad["endpoints"]  # not implemented
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/python/anip-service/tests/test_service_init.py::TestANIPServiceInit::test_discovery_document -x -q
```

Expected: TypeError or KeyError — `get_discovery()` doesn't accept `base_url` yet.

**Step 3: Rewrite Python `get_discovery()` to accept `base_url` parameter**

In `packages/python/anip-service/src/anip_service/service.py`, change the method signature and body:

```python
def get_discovery(self, *, base_url: str | None = None) -> dict[str, Any]:
    """Return lightweight discovery document per SPEC.md §6.1."""
    from anip_core import PROTOCOL_VERSION, DEFAULT_PROFILE

    caps_summary = {}
    for name, cap in self._capabilities.items():
        decl = cap.declaration
        caps_summary[name] = {
            "description": decl.description,
            "side_effect": decl.side_effect.type.value if decl.side_effect else None,
            "minimum_scope": decl.minimum_scope,
            "financial": decl.cost is not None and decl.cost.financial is not None,
            "contract": decl.contract_version,
        }

    doc: dict[str, Any] = {
        "protocol": PROTOCOL_VERSION,
        "compliance": "anip-compliant",
        "profile": DEFAULT_PROFILE,
        "auth": {
            "delegation_token_required": True,
            "supported_formats": ["anip-v1"],
            "minimum_scope_for_discovery": "none",
        },
        "capabilities": caps_summary,
        "trust_level": self._trust_level,
        "endpoints": {
            "manifest": "/anip/manifest",
            "permissions": "/anip/permissions",
            "invoke": "/anip/invoke/{capability}",
            "tokens": "/anip/tokens",
            "audit": "/anip/audit",
            "checkpoints": "/anip/checkpoints",
            "jwks": "/.well-known/jwks.json",
        },
    }

    if base_url is not None:
        doc["base_url"] = base_url

    return {"anip_discovery": doc}
```

**Step 4: Update FastAPI route to pass `base_url` from request**

In `packages/python/anip-fastapi/src/anip_fastapi/routes.py`, change the discovery route:

```python
@app.get(f"{prefix}/.well-known/anip")
async def discovery(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return service.get_discovery(base_url=base_url)
```

**Step 5: Run Python tests**

```bash
.venv/bin/python -m pytest packages/python -x -q
```

Expected: All pass. The FastAPI route test may need updating if it asserts on `base_url`.

**Step 6: Write failing tests (TypeScript)**

Update `discovery document structure` test in `packages/typescript/service/tests/service.test.ts`:

```typescript
it("discovery document structure", () => {
  const { service } = makeService();
  const disc = service.getDiscovery({ baseUrl: "https://test.example.com" }) as Record<string, any>;
  const ad = disc.anip_discovery;

  // Required fields per SPEC.md §6.1
  expect(ad.protocol).toBe("anip/0.7");
  expect(ad.compliance).toBe("anip-compliant");
  expect(ad.base_url).toBe("https://test.example.com");
  expect(ad.profile.core).toBe("1.0");
  expect(ad.auth.delegation_token_required).toBe(true);
  expect(ad.auth.minimum_scope_for_discovery).toBe("none");

  // Capability summary shape
  expect(ad.capabilities["greet"].description).toBe("Say hello");
  expect(ad.capabilities["greet"].financial).toBe(false);
  expect(ad.capabilities["greet"].contract).toBe("1.0");
  expect(ad.capabilities["greet"].contract_version).toBeUndefined();

  // Trust and endpoints — only implemented endpoints
  expect(ad.trust_level).toBe("signed");
  expect(ad.endpoints.manifest).toBe("/anip/manifest");
  expect(ad.endpoints.permissions).toBe("/anip/permissions");
  expect(ad.endpoints.handshake).toBeUndefined();
});

it("discovery omits base_url when not passed", () => {
  const { service } = makeService();
  const disc = service.getDiscovery() as Record<string, any>;
  expect(disc.anip_discovery.base_url).toBeUndefined();
});
```

**Step 7: Update TypeScript `ANIPService` interface and `getDiscovery()` implementation**

In `packages/typescript/service/src/service.ts`:

Change the interface:
```typescript
getDiscovery(opts?: { baseUrl?: string }): Record<string, unknown>;
```

Rewrite the implementation:

```typescript
getDiscovery(opts?: { baseUrl?: string }): Record<string, unknown> {
  const capsSummary: Record<string, unknown> = {};
  for (const [name, cap] of capabilities) {
    const decl = cap.declaration;
    capsSummary[name] = {
      description: decl.description,
      side_effect: decl.side_effect?.type ?? null,
      minimum_scope: decl.minimum_scope,
      financial: decl.cost?.financial != null,
      contract: decl.contract_version,
    };
  }

  const doc: Record<string, unknown> = {
    protocol: PROTOCOL_VERSION,
    compliance: "anip-compliant",
    profile: { ...DEFAULT_PROFILE },
    auth: {
      delegation_token_required: true,
      supported_formats: ["anip-v1"],
      minimum_scope_for_discovery: "none",
    },
    capabilities: capsSummary,
    trust_level: trustLevel,
    endpoints: {
      manifest: "/anip/manifest",
      permissions: "/anip/permissions",
      invoke: "/anip/invoke/{capability}",
      tokens: "/anip/tokens",
      audit: "/anip/audit",
      checkpoints: "/anip/checkpoints",
      jwks: "/.well-known/jwks.json",
    },
  };

  if (opts?.baseUrl) {
    doc.base_url = opts.baseUrl;
  }

  return { anip_discovery: doc };
},
```

Add `PROTOCOL_VERSION` and `DEFAULT_PROFILE` to the import from `@anip/core` if not already imported.

**Step 8: Update HTTP bindings to pass `baseUrl` from request**

Express (`packages/typescript/express/src/routes.ts`):
```typescript
router.get("/.well-known/anip", (req, res) => {
  const baseUrl = `${req.protocol}://${req.get("host")}`;
  res.json(service.getDiscovery({ baseUrl }));
});
```

Hono (`packages/typescript/hono/src/routes.ts`):
```typescript
app.get(`${p}/.well-known/anip`, (c) => {
  const baseUrl = new URL(c.req.url).origin;
  return c.json(service.getDiscovery({ baseUrl }));
});
```

Fastify (`packages/typescript/fastify/src/routes.ts`):
```typescript
app.get(`${p}/.well-known/anip`, async (req) => {
  const baseUrl = `${req.protocol}://${req.hostname}`;
  return service.getDiscovery({ baseUrl });
});
```

**Step 9: Run all tests**

```bash
.venv/bin/python -m pytest packages/python -x -q
cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose
```

Expected: All pass. HTTP binding tests (Express/Hono/Fastify) will now see `base_url` in discovery output — update assertions if needed.

**Step 10: Commit**

```bash
git add packages/python/anip-service/ packages/python/anip-fastapi/ packages/typescript/service/ packages/typescript/express/ packages/typescript/hono/ packages/typescript/fastify/
git commit -m "fix: align discovery response with SPEC.md §6.1 — base_url from request, anip-compliant, correct endpoints"
```

---

## Task 3: Python Posture Models

Add typed Pydantic models for the five posture sub-objects.

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`
- Test: `packages/python/anip-core/tests/test_models.py`

**Step 1: Write failing tests**

Add to the end of `packages/python/anip-core/tests/test_models.py`:

```python
# --- Discovery Posture (v0.7) ---


def test_audit_posture_defaults():
    ap = AuditPosture()
    assert ap.enabled is True
    assert ap.signed is True
    assert ap.queryable is True
    assert ap.retention is None


def test_audit_posture_with_retention():
    ap = AuditPosture(retention="P90D")
    assert ap.retention == "P90D"


def test_client_reference_id_posture_defaults():
    crp = ClientReferenceIdPosture()
    assert crp.supported is True
    assert crp.max_length == 256
    assert crp.opaque is True
    assert crp.propagation == "bounded"


def test_lineage_posture_defaults():
    lp = LineagePosture()
    assert lp.invocation_id is True
    assert lp.client_reference_id is not None
    assert lp.client_reference_id.supported is True


def test_metadata_policy_defaults():
    mp = MetadataPolicy()
    assert mp.bounded_lineage is True
    assert mp.freeform_context is False
    assert mp.downstream_propagation == "minimal"


def test_failure_disclosure_defaults():
    fd = FailureDisclosure()
    assert fd.detail_level == "redacted"


def test_failure_disclosure_full():
    fd = FailureDisclosure(detail_level="full")
    assert fd.detail_level == "full"


def test_anchoring_posture_defaults():
    ap = AnchoringPosture()
    assert ap.enabled is False
    assert ap.cadence is None
    assert ap.max_lag is None
    assert ap.proofs_available is False


def test_anchoring_posture_enabled():
    ap = AnchoringPosture(enabled=True, cadence="PT30S", max_lag=120, proofs_available=True)
    assert ap.enabled is True
    assert ap.cadence == "PT30S"
    assert ap.max_lag == 120
    assert ap.proofs_available is True


def test_discovery_posture_defaults():
    dp = DiscoveryPosture()
    assert dp.audit.enabled is True
    assert dp.lineage.invocation_id is True
    assert dp.metadata_policy.bounded_lineage is True
    assert dp.failure_disclosure.detail_level == "redacted"
    assert dp.anchoring.enabled is False


def test_discovery_posture_roundtrip():
    dp = DiscoveryPosture(
        anchoring=AnchoringPosture(enabled=True, cadence="PT30S", max_lag=120, proofs_available=True),
    )
    d = dp.model_dump()
    assert d["audit"]["enabled"] is True
    assert d["anchoring"]["enabled"] is True
    assert d["anchoring"]["cadence"] == "PT30S"
    restored = DiscoveryPosture.model_validate(d)
    assert restored.anchoring.enabled is True
    assert restored.anchoring.cadence == "PT30S"
```

Also add the imports at the top of the test file:
```python
from anip_core import (
    ...,
    AuditPosture,
    ClientReferenceIdPosture,
    LineagePosture,
    MetadataPolicy,
    FailureDisclosure,
    AnchoringPosture,
    DiscoveryPosture,
)
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/python/anip-core/tests/test_models.py -x -q -k "posture or lineage_posture or metadata_policy or failure_disclosure or anchoring_posture or discovery_posture"
```

Expected: ImportError — models don't exist yet.

**Step 3: Add posture models to `models.py`**

Insert after the `TrustPosture` class (after line 236) in `packages/python/anip-core/src/anip_core/models.py`:

```python
# --- Discovery Posture (v0.7) ---


class AuditPosture(BaseModel):
    enabled: bool = True
    signed: bool = True
    queryable: bool = True
    retention: str | None = None


class ClientReferenceIdPosture(BaseModel):
    supported: bool = True
    max_length: int = 256
    opaque: bool = True
    propagation: str = "bounded"


class LineagePosture(BaseModel):
    invocation_id: bool = True
    client_reference_id: ClientReferenceIdPosture = Field(default_factory=ClientReferenceIdPosture)


class MetadataPolicy(BaseModel):
    bounded_lineage: bool = True
    freeform_context: bool = False
    downstream_propagation: str = "minimal"


class FailureDisclosure(BaseModel):
    detail_level: str = "redacted"


class AnchoringPosture(BaseModel):
    enabled: bool = False
    cadence: str | None = None
    max_lag: int | None = None
    proofs_available: bool = False


class DiscoveryPosture(BaseModel):
    audit: AuditPosture = Field(default_factory=AuditPosture)
    lineage: LineagePosture = Field(default_factory=LineagePosture)
    metadata_policy: MetadataPolicy = Field(default_factory=MetadataPolicy)
    failure_disclosure: FailureDisclosure = Field(default_factory=FailureDisclosure)
    anchoring: AnchoringPosture = Field(default_factory=AnchoringPosture)
```

**Step 4: Export from `__init__.py`**

Add to `packages/python/anip-core/src/anip_core/__init__.py`:
- Import: `AuditPosture`, `ClientReferenceIdPosture`, `LineagePosture`, `MetadataPolicy`, `FailureDisclosure`, `AnchoringPosture`, `DiscoveryPosture`
- Add all seven to `__all__`

**Step 5: Run tests**

```bash
.venv/bin/python -m pytest packages/python/anip-core/tests/test_models.py -x -q
```

Expected: All pass.

**Step 6: Commit**

```bash
git add packages/python/anip-core/
git commit -m "feat(core): add Python discovery posture models (v0.7)"
```

---

## Task 4: TypeScript Posture Models

Add Zod schemas for the five posture sub-objects.

**Files:**
- Modify: `packages/typescript/core/src/models.ts`
- Test: `packages/typescript/core/tests/models.test.ts`

**Step 1: Write failing tests**

Add to the end of `packages/typescript/core/tests/models.test.ts`:

```typescript
// --- Discovery Posture (v0.7) ---

describe("AuditPosture", () => {
  it("defaults to enabled, signed, queryable", () => {
    const ap = AuditPosture.parse({});
    expect(ap.enabled).toBe(true);
    expect(ap.signed).toBe(true);
    expect(ap.queryable).toBe(true);
    expect(ap.retention).toBeNull();
  });

  it("accepts retention", () => {
    const ap = AuditPosture.parse({ retention: "P90D" });
    expect(ap.retention).toBe("P90D");
  });
});

describe("ClientReferenceIdPosture", () => {
  it("defaults correctly", () => {
    const crp = ClientReferenceIdPosture.parse({});
    expect(crp.supported).toBe(true);
    expect(crp.max_length).toBe(256);
    expect(crp.opaque).toBe(true);
    expect(crp.propagation).toBe("bounded");
  });
});

describe("LineagePosture", () => {
  it("defaults correctly", () => {
    const lp = LineagePosture.parse({});
    expect(lp.invocation_id).toBe(true);
    expect(lp.client_reference_id.supported).toBe(true);
  });
});

describe("MetadataPolicy", () => {
  it("defaults correctly", () => {
    const mp = MetadataPolicy.parse({});
    expect(mp.bounded_lineage).toBe(true);
    expect(mp.freeform_context).toBe(false);
    expect(mp.downstream_propagation).toBe("minimal");
  });
});

describe("FailureDisclosure", () => {
  it("defaults to redacted", () => {
    const fd = FailureDisclosure.parse({});
    expect(fd.detail_level).toBe("redacted");
  });

  it("accepts full", () => {
    const fd = FailureDisclosure.parse({ detail_level: "full" });
    expect(fd.detail_level).toBe("full");
  });
});

describe("AnchoringPosture", () => {
  it("defaults to disabled", () => {
    const ap = AnchoringPosture.parse({});
    expect(ap.enabled).toBe(false);
    expect(ap.cadence).toBeNull();
    expect(ap.max_lag).toBeNull();
    expect(ap.proofs_available).toBe(false);
  });

  it("accepts enabled with config", () => {
    const ap = AnchoringPosture.parse({
      enabled: true,
      cadence: "PT30S",
      max_lag: 120,
      proofs_available: true,
    });
    expect(ap.enabled).toBe(true);
    expect(ap.cadence).toBe("PT30S");
    expect(ap.max_lag).toBe(120);
    expect(ap.proofs_available).toBe(true);
  });
});

describe("DiscoveryPosture", () => {
  it("defaults fully", () => {
    const dp = DiscoveryPosture.parse({});
    expect(dp.audit.enabled).toBe(true);
    expect(dp.lineage.invocation_id).toBe(true);
    expect(dp.metadata_policy.bounded_lineage).toBe(true);
    expect(dp.failure_disclosure.detail_level).toBe("redacted");
    expect(dp.anchoring.enabled).toBe(false);
  });

  it("roundtrips with anchoring", () => {
    const input = {
      anchoring: { enabled: true, cadence: "PT30S", max_lag: 120, proofs_available: true },
    };
    const dp = DiscoveryPosture.parse(input);
    expect(dp.anchoring.enabled).toBe(true);
    expect(dp.anchoring.cadence).toBe("PT30S");
  });
});
```

Add the necessary imports at the top of the test file.

**Step 2: Run tests to verify they fail**

```bash
cd packages/typescript && npx tsc -b core && npx vitest run core/tests/models.test.ts --reporter=verbose
```

Expected: FAIL — schemas not exported.

**Step 3: Add Zod schemas to `models.ts`**

Insert after the `TrustPosture` block (after line 223) in `packages/typescript/core/src/models.ts`:

```typescript
// ---------------------------------------------------------------------------
// Discovery Posture (v0.7)
// ---------------------------------------------------------------------------

export const AuditPosture = z.object({
  enabled: z.boolean().default(true),
  signed: z.boolean().default(true),
  queryable: z.boolean().default(true),
  retention: z.string().nullable().default(null),
});
export type AuditPosture = z.infer<typeof AuditPosture>;

export const ClientReferenceIdPosture = z.object({
  supported: z.boolean().default(true),
  max_length: z.number().int().default(256),
  opaque: z.boolean().default(true),
  propagation: z.string().default("bounded"),
});
export type ClientReferenceIdPosture = z.infer<typeof ClientReferenceIdPosture>;

export const LineagePosture = z.object({
  invocation_id: z.boolean().default(true),
  client_reference_id: ClientReferenceIdPosture.default({}),
});
export type LineagePosture = z.infer<typeof LineagePosture>;

export const MetadataPolicy = z.object({
  bounded_lineage: z.boolean().default(true),
  freeform_context: z.boolean().default(false),
  downstream_propagation: z.string().default("minimal"),
});
export type MetadataPolicy = z.infer<typeof MetadataPolicy>;

export const FailureDisclosure = z.object({
  detail_level: z.string().default("redacted"),
});
export type FailureDisclosure = z.infer<typeof FailureDisclosure>;

export const AnchoringPosture = z.object({
  enabled: z.boolean().default(false),
  cadence: z.string().nullable().default(null),
  max_lag: z.number().nullable().default(null),
  proofs_available: z.boolean().default(false),
});
export type AnchoringPosture = z.infer<typeof AnchoringPosture>;

export const DiscoveryPosture = z.object({
  audit: AuditPosture.default({}),
  lineage: LineagePosture.default({}),
  metadata_policy: MetadataPolicy.default({}),
  failure_disclosure: FailureDisclosure.default({}),
  anchoring: AnchoringPosture.default({}),
});
export type DiscoveryPosture = z.infer<typeof DiscoveryPosture>;
```

**Step 4: Run tests**

```bash
cd packages/typescript && npx tsc -b core && npx vitest run core/tests/models.test.ts --reporter=verbose
```

Expected: All pass.

**Step 5: Commit**

```bash
git add packages/typescript/core/
git commit -m "feat(core): add TypeScript discovery posture schemas (v0.7)"
```

---

## Task 5: Python Service — Emit Posture in Discovery

Add the `posture` block to the Python discovery response, computed from existing service state.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/python/anip-service/tests/test_service_init.py`

**Context:**
- `self._trust_level` → determines anchoring.enabled
- `self._manifest.trust.anchoring` → anchoring.cadence, anchoring.max_lag
- `self._checkpoint_policy` → determines proofs_available (must be non-None AND anchored)

**Critical:** `proofs_available` MUST be `True` only when BOTH `trust_level` is `"anchored"/"attested"` AND `self._checkpoint_policy is not None`. An anchored service without checkpoint scheduling cannot produce proofs.

**Step 1: Write failing tests**

Add to `TestANIPServiceInit` in `packages/python/anip-service/tests/test_service_init.py`:

```python
def test_discovery_includes_posture(self):
    service = ANIPService(
        service_id="test-service",
        capabilities=[_test_cap()],
        storage=":memory:",
    )
    disc = service.get_discovery()
    posture = disc["anip_discovery"]["posture"]
    assert posture["audit"]["enabled"] is True
    assert posture["audit"]["signed"] is True
    assert posture["audit"]["queryable"] is True
    assert posture["lineage"]["invocation_id"] is True
    assert posture["lineage"]["client_reference_id"]["supported"] is True
    assert posture["lineage"]["client_reference_id"]["max_length"] == 256
    assert posture["metadata_policy"]["bounded_lineage"] is True
    assert posture["metadata_policy"]["freeform_context"] is False
    assert posture["failure_disclosure"]["detail_level"] == "redacted"
    assert posture["anchoring"]["enabled"] is False
    assert posture["anchoring"]["proofs_available"] is False

def test_discovery_posture_anchored_with_policy(self):
    from anip_server import LocalFileSink, CheckpointPolicy
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
            trust={
                "level": "anchored",
                "anchoring": {
                    "cadence": "PT30S",
                    "max_lag": 120,
                    "sinks": [LocalFileSink(directory=tmpdir)],
                },
            },
            checkpoint_policy=CheckpointPolicy(max_entries=100),
        )
        disc = service.get_discovery()
        posture = disc["anip_discovery"]["posture"]
        assert posture["anchoring"]["enabled"] is True
        assert posture["anchoring"]["cadence"] == "PT30S"
        assert posture["anchoring"]["max_lag"] == 120
        assert posture["anchoring"]["proofs_available"] is True

def test_discovery_posture_anchored_without_policy(self):
    """Anchored trust without checkpoint policy — proofs NOT available."""
    service = ANIPService(
        service_id="test-service",
        capabilities=[_test_cap()],
        storage=":memory:",
        trust={"level": "anchored", "anchoring": {"cadence": "PT30S", "max_lag": 120}},
    )
    disc = service.get_discovery()
    posture = disc["anip_discovery"]["posture"]
    assert posture["anchoring"]["enabled"] is True
    assert posture["anchoring"]["proofs_available"] is False
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/python/anip-service/tests/test_service_init.py -x -q -k "posture"
```

Expected: KeyError — `posture` not in discovery response.

**Step 3: Add posture to `get_discovery()` in `service.py`**

Add to imports at top of file:
```python
from anip_core import (
    ...existing imports...,
    AnchoringPosture,
    DiscoveryPosture,
)
```

In the `get_discovery()` method (which now accepts `*, base_url: str | None = None`), after building `caps_summary` and before building the `doc` dict, add:

```python
    # Build posture from existing service state (v0.7)
    anchoring_src = self._manifest.trust.anchoring if self._manifest.trust else None
    is_anchored = self._trust_level in ("anchored", "attested")
    posture = DiscoveryPosture(
        anchoring=AnchoringPosture(
            enabled=is_anchored,
            cadence=anchoring_src.cadence if anchoring_src else None,
            max_lag=anchoring_src.max_lag if anchoring_src else None,
            proofs_available=is_anchored and self._checkpoint_policy is not None,
        ),
    )
```

Then add `"posture": posture.model_dump(),` to the `doc` dict (before endpoints).

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest packages/python -x -q
```

Expected: All pass.

**Step 5: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(service): emit posture block in Python discovery response (v0.7)"
```

---

## Task 6: TypeScript Service — Emit Posture in Discovery

Add the `posture` block to the TypeScript discovery response.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Test: `packages/typescript/service/tests/service.test.ts`

**Context:** The `trustLevel` string, `anchoringPolicy` object, and `checkpointPolicy` are all in the `createANIPService` closure scope.

**Critical:** Same as Python — `proofs_available` requires both anchored trust AND checkpoint policy.

**Step 1: Write failing tests**

Add to the `ANIPService construction` describe block in `packages/typescript/service/tests/service.test.ts`:

```typescript
it("discovery includes posture block", () => {
  const { service } = makeService();
  const disc = service.getDiscovery() as Record<string, any>;
  const posture = disc.anip_discovery.posture;
  expect(posture).toBeDefined();
  expect(posture.audit.enabled).toBe(true);
  expect(posture.audit.signed).toBe(true);
  expect(posture.audit.queryable).toBe(true);
  expect(posture.lineage.invocation_id).toBe(true);
  expect(posture.lineage.client_reference_id.supported).toBe(true);
  expect(posture.lineage.client_reference_id.max_length).toBe(256);
  expect(posture.metadata_policy.bounded_lineage).toBe(true);
  expect(posture.metadata_policy.freeform_context).toBe(false);
  expect(posture.failure_disclosure.detail_level).toBe("redacted");
  expect(posture.anchoring.enabled).toBe(false);
  expect(posture.anchoring.proofs_available).toBe(false);
});

it("discovery posture reflects anchored trust with checkpoint policy", () => {
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [testCap()],
    storage: { type: "memory" },
    trust: {
      level: "anchored",
      anchoring: {
        cadence: "PT30S",
        maxLag: 120,
      },
    },
    checkpointPolicy: { maxEntries: 100 },
  });
  const disc = service.getDiscovery() as Record<string, any>;
  const posture = disc.anip_discovery.posture;
  expect(posture.anchoring.enabled).toBe(true);
  expect(posture.anchoring.cadence).toBe("PT30S");
  expect(posture.anchoring.max_lag).toBe(120);
  expect(posture.anchoring.proofs_available).toBe(true);
});

it("discovery posture: anchored without checkpoint policy has no proofs", () => {
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [testCap()],
    storage: { type: "memory" },
    trust: {
      level: "anchored",
      anchoring: {
        cadence: "PT30S",
        maxLag: 120,
      },
    },
  });
  const disc = service.getDiscovery() as Record<string, any>;
  const posture = disc.anip_discovery.posture;
  expect(posture.anchoring.enabled).toBe(true);
  expect(posture.anchoring.proofs_available).toBe(false);
});
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/typescript && npx tsc -b core crypto server service && npx vitest run service/tests/service.test.ts --reporter=verbose
```

Expected: `posture` is undefined.

**Step 3: Add posture to `getDiscovery()` in `service.ts`**

In the `getDiscovery(opts?)` method (which now accepts `opts?: { baseUrl?: string }`), add after building `capsSummary`:

```typescript
  const isAnchored = trustLevel === "anchored" || trustLevel === "attested";
```

Then add `posture` to the `doc` object (before endpoints):

```typescript
    posture: {
      audit: {
        enabled: true,
        signed: true,
        queryable: true,
        retention: null,
      },
      lineage: {
        invocation_id: true,
        client_reference_id: {
          supported: true,
          max_length: 256,
          opaque: true,
          propagation: "bounded",
        },
      },
      metadata_policy: {
        bounded_lineage: true,
        freeform_context: false,
        downstream_propagation: "minimal",
      },
      failure_disclosure: {
        detail_level: "redacted",
      },
      anchoring: {
        enabled: isAnchored,
        cadence: anchoringPolicy?.cadence ?? null,
        max_lag: anchoringPolicy?.max_lag ?? null,
        proofs_available: isAnchored && checkpointPolicy !== null,
      },
    },
```

**Step 4: Run all tests**

```bash
cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose
```

Expected: All pass.

**Step 5: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(service): emit posture block in TypeScript discovery response (v0.7)"
```

---

## Task 7: JSON Schema — Align with Discovery Changes + Add Posture

Sync the discovery JSON schema with the contract changes made in Task 2, then add posture. Three schema fixes before adding posture:

1. **`base_url`**: Remove from top-level `required` — it's binding-injected, not always present in service-layer output
2. **`endpoints.handshake`**: Remove from `endpoints.required` — handshake is not implemented in the reference runtimes. It remains as an optional property in the schema.
3. **`endpoints` optional properties**: Add `checkpoints` and `jwks` as optional properties (the reference implementations emit them but the schema didn't define them)

**Files:**
- Modify: `schema/discovery.schema.json`

**Step 1: Remove `base_url` from the top-level `required` array**

In `schema/discovery.schema.json`, the `anip_discovery.required` array currently is:
```json
["protocol", "compliance", "base_url", "profile", "auth", "capabilities", "endpoints"]
```
Change to:
```json
["protocol", "compliance", "profile", "auth", "capabilities", "endpoints"]
```

**Step 2: Remove `handshake` from `endpoints.required`**

The `endpoints.required` array currently is:
```json
["manifest", "handshake", "permissions", "invoke", "tokens"]
```
Change to:
```json
["manifest", "permissions", "invoke", "tokens"]
```

`handshake` remains as an optional property in `endpoints.properties` — services that implement it can still advertise it.

**Step 3: Add missing endpoint properties**

Add `checkpoints` and `jwks` as optional string properties in `endpoints.properties` (alongside the existing `graph`, `audit`, `test`):
```json
"checkpoints": { "type": "string" },
"jwks": { "type": "string" }
```

**Step 4: Add `posture` property**

Add a `posture` property inside `anip_discovery.properties` in `schema/discovery.schema.json`, after the `endpoints` property and before `metadata`:

```json
"posture": {
  "type": "object",
  "properties": {
    "audit": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean", "description": "Whether audit logging is active" },
        "signed": { "type": "boolean", "description": "Whether audit entries are signed" },
        "queryable": { "type": "boolean", "description": "Whether audit log is queryable via endpoint" },
        "retention": {
          "type": ["string", "null"],
          "description": "ISO 8601 duration for audit log retention (e.g., 'P90D'), or null if unspecified"
        }
      },
      "required": ["enabled", "signed", "queryable"],
      "additionalProperties": false
    },
    "lineage": {
      "type": "object",
      "properties": {
        "invocation_id": { "type": "boolean", "description": "Whether server-generated invocation IDs are assigned" },
        "client_reference_id": {
          "type": "object",
          "properties": {
            "supported": { "type": "boolean" },
            "max_length": { "type": "integer" },
            "opaque": { "type": "boolean", "description": "Whether client_reference_id is treated as opaque (not interpreted)" },
            "propagation": {
              "type": "string",
              "enum": ["bounded", "local_only", "policy"],
              "description": "How client_reference_id propagates"
            }
          },
          "required": ["supported"],
          "additionalProperties": false
        }
      },
      "required": ["invocation_id"],
      "additionalProperties": false
    },
    "metadata_policy": {
      "type": "object",
      "properties": {
        "bounded_lineage": { "type": "boolean", "description": "Whether lineage metadata is bounded (not unbounded transport channel)" },
        "freeform_context": { "type": "boolean", "description": "Whether arbitrary freeform context fields are accepted" },
        "downstream_propagation": {
          "type": "string",
          "enum": ["minimal", "policy", "service_defined"],
          "description": "How metadata propagates downstream"
        }
      },
      "required": ["bounded_lineage"],
      "additionalProperties": false
    },
    "failure_disclosure": {
      "type": "object",
      "properties": {
        "detail_level": {
          "type": "string",
          "enum": ["full", "redacted", "policy"],
          "description": "How much error detail is surfaced to callers"
        }
      },
      "required": ["detail_level"],
      "additionalProperties": false
    },
    "anchoring": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean", "description": "Whether Merkle checkpoints are active" },
        "cadence": {
          "type": ["string", "null"],
          "description": "ISO 8601 duration for checkpoint cadence (e.g., 'PT30S')"
        },
        "max_lag": {
          "type": ["integer", "null"],
          "description": "Maximum seconds between newest audit entry and latest checkpoint"
        },
        "proofs_available": { "type": "boolean", "description": "Whether inclusion/consistency proofs are available" }
      },
      "required": ["enabled"],
      "additionalProperties": false
    }
  },
  "required": ["audit", "lineage", "metadata_policy", "failure_disclosure", "anchoring"],
  "additionalProperties": false,
  "description": "Service governance posture — trust-relevant characteristics inspectable before invocation (v0.7)"
}
```

Note: `posture` is NOT added to the top-level `required` array — it is OPTIONAL. Services running older versions can omit it.

**Step 2: Verify schema is valid JSON**

```bash
python3 -c "import json; json.load(open('schema/discovery.schema.json'))"
```

Expected: No error.

**Step 3: Commit**

```bash
git add schema/
git commit -m "feat(schema): add posture block to discovery JSON schema (v0.7)"
```

---

## Task 8: SPEC.md — Discovery Alignment + Posture Section

Update the spec to reflect all discovery contract changes (compliance semantics, endpoint requirements, base_url binding-injection) made in Task 2, then add normative posture language.

**Files:**
- Modify: `SPEC.md`

**Step 1: Update spec title**

Line 1: change `v0.6` to `v0.7`.

**Step 2: Align §6.1 discovery example with Task 2 contract changes**

In the YAML example in §6.1 (around line 445–500), make these changes:

1. Change `compliance: "anip-complete"` → `compliance: "anip-compliant"` (reference implementations implement 5 core primitives, not all 9)
2. Remove `handshake` from the `endpoints` block in the example (not implemented in reference runtimes)
3. Add a comment on `base_url` noting it is injected by the HTTP binding layer at request time, not hardcoded

**Step 3: Update §6.1 Fields descriptions for alignment changes**

In the fields list after the example:

1. **`compliance`**: Clarify the two tiers — `"anip-compliant"` requires the 5 core primitives (manifest, permissions, invoke, tokens, audit); `"anip-complete"` requires all 9 (adds handshake, graph, test, checkpoints). A service MUST NOT claim `"anip-complete"` unless all 9 endpoints are implemented and functional.
2. **`base_url`**: Add note that this field MUST be derived from the incoming HTTP request by the binding layer, not hardcoded or constructor-injected. It MAY be absent in service-layer output and populated at the HTTP boundary.
3. **`endpoints`**: Clarify which endpoints are REQUIRED (manifest, permissions, invoke, tokens) vs OPTIONAL (handshake, graph, audit, test, checkpoints, jwks). A service MUST only advertise endpoints it actually implements.

**Step 4: Add posture field to §6.1 discovery document example**

In the YAML example in §6.1 (after `trust_level` around line 496), add:

```yaml
  posture:                                    # OPTIONAL (v0.7) — governance posture summary
    audit:
      enabled: true
      signed: true
      queryable: true
      retention: "P90D"
    lineage:
      invocation_id: true
      client_reference_id:
        supported: true
        max_length: 256
        opaque: true
        propagation: "bounded"
    metadata_policy:
      bounded_lineage: true
      freeform_context: false
      downstream_propagation: "minimal"
    failure_disclosure:
      detail_level: "redacted"
    anchoring:
      enabled: true
      cadence: "PT30S"
      max_lag: 120
      proofs_available: true
```

**Step 5: Add posture field description to Fields section**

After the `trust_level` bullet, add:

```markdown
- **posture** (OPTIONAL, v0.7) — governance posture summary. Exposes trust-relevant service characteristics that agents can inspect before invocation. Contains five sub-objects: `audit`, `lineage`, `metadata_policy`, `failure_disclosure`, and `anchoring`. See Section 6.7 for full field definitions. Services MUST NOT expose internal infrastructure details (database engines, ORM types, queue implementations) in posture fields.
```

**Step 6: Add §6.7 Discovery Posture section**

Insert a new section after §6.6 Streaming Invocations (after line 933). Full section content:

- Purpose and rationale
- Posture vs. Manifest distinction
- `posture.audit` field table (enabled, signed, queryable, retention)
- `posture.lineage` field table (invocation_id, client_reference_id with sub-fields)
- `posture.metadata_policy` field table (bounded_lineage, freeform_context, downstream_propagation)
- `posture.failure_disclosure` field table (detail_level) with enforcement note
- `posture.anchoring` field table (enabled, cadence, max_lag, proofs_available) with constraint: `proofs_available` MUST be `true` only when the service has active checkpoint scheduling — anchored trust level alone is insufficient
- "What posture MUST NOT expose" section

**Step 7: Update §13 Roadmap**

Add row: `| **Discovery posture (§6.7)** | MAY — v0.7 | Implemented: posture block with audit, lineage, metadata_policy, failure_disclosure, and anchoring sub-objects | — |`

Update the narrative paragraph to include v0.7.

**Step 8: Update §14 Resolved Questions**

Add: `- **Governance posture visibility.** Discovery posture block exposes audit, lineage, metadata policy, failure disclosure, and anchoring characteristics. *(Resolved in v0.7)*`

**Step 9: Update spec footer**

Update to mention v0.7.

**Step 10: Commit**

```bash
git add SPEC.md
git commit -m "spec: align §6.1 discovery contract + add §6.7 Discovery Posture (v0.7)"
```

---

## Task 9: Documentation Updates

Update README, SECURITY, CONTRIBUTING, and other docs for v0.7.

**Files:**
- Modify: `README.md`
- Modify: `SECURITY.md`
- Modify: `CONTRIBUTING.md`
- Modify: `GUIDE.md`
- Modify: `docs/trust-model.md`
- Modify: `schema/README.md`
- Modify: `skills/anip-consumer.md`
- Modify: `skills/anip-implementer.md`
- Modify: `skills/anip-validator.md`

**Step 1: Update README.md**

- Update version/status to v0.7 with discovery posture mention
- Add posture to feature list
- Update "What's next" section

**Step 2: Update SECURITY.md**

- Add v0.7 row to version table: `| v0.7 | Current — discovery posture, governance visibility |`
- Move v0.6 to "Stable"
- Add "What v0.7 Adds" paragraph

**Step 3: Update CONTRIBUTING.md**

- Update resolved questions list to include v0.7

**Step 4: Update GUIDE.md**

- Update version references from v0.6 to v0.7

**Step 5: Update `schema/README.md`**

- Bump version references
- Add posture types to schema table

**Step 6: Update skills files**

- Update spec version headers in consumer, implementer, validator skills

**Step 7: Update `docs/trust-model.md`**

- Add discovery posture mention in trust model overview

**Step 8: Commit**

```bash
git add README.md SECURITY.md CONTRIBUTING.md GUIDE.md docs/ schema/README.md skills/
git commit -m "docs: update all documentation to reflect v0.7 discovery posture"
```
