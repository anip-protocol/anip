# v0.7 Discovery Trust & Metadata Posture — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `posture` block to `/.well-known/anip` that exposes audit, lineage, metadata policy, failure disclosure, and anchoring posture — making trust characteristics inspectable before invocation.

**Architecture:** Posture is computed entirely from existing service configuration (trust level, anchoring policy, checkpoint config). No new constructor parameters needed. New typed models in both runtimes serialize into the discovery response dict. The posture block is OPTIONAL per schema — services MAY omit it, but reference implementations MUST include it.

**Tech Stack:** Python/Pydantic, TypeScript/Zod, JSON Schema (draft 2020-12)

**Design doc:** `/Users/samirski/Development/codex/ANIP/docs/anip-v07-discovery-trust-and-metadata-posture.md`

**Worktree:** `/Users/samirski/Development/ANIP/.worktrees/v07-discovery-posture` (branch: `feature/v07-discovery-posture`)

**Test commands:**
- Python: `.venv/bin/python -m pytest packages/python -x -q`
- TypeScript: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`

---

## Task 1: Version Bumps

Bump all version constants and package files from 0.6 → 0.7.

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/constants.py`
- Modify: `packages/typescript/core/src/constants.ts`
- Modify: `packages/python/anip-core/pyproject.toml`
- Modify: `packages/python/anip-crypto/pyproject.toml`
- Modify: `packages/python/anip-server/pyproject.toml`
- Modify: `packages/python/anip-service/pyproject.toml`
- Modify: `packages/python/anip-fastapi/pyproject.toml`
- Modify: `packages/typescript/core/package.json`
- Modify: `packages/typescript/crypto/package.json`
- Modify: `packages/typescript/server/package.json`
- Modify: `packages/typescript/service/package.json`
- Modify: `packages/typescript/express/package.json`
- Modify: `packages/typescript/fastify/package.json`
- Modify: `packages/typescript/hono/package.json`
- Modify: `packages/python/anip-core/src/anip_core/models.py` (default values referencing version)
- Modify: `packages/typescript/core/src/models.ts` (default values referencing version)
- Test: `packages/python/anip-core/tests/test_models.py`
- Test: `packages/typescript/core/tests/models.test.ts`

**Step 1: Update Python constants**

In `packages/python/anip-core/src/anip_core/constants.py`:
```python
PROTOCOL_VERSION = "anip/0.7"
MANIFEST_VERSION = "0.7.0"
```

**Step 2: Update TypeScript constants**

In `packages/typescript/core/src/constants.ts`:
```typescript
export const PROTOCOL_VERSION = "anip/0.7";
export const MANIFEST_VERSION = "0.7.0";
```

**Step 3: Update Python model defaults**

In `packages/python/anip-core/src/anip_core/models.py`:
- `ManifestMetadata.version` default: `"0.3.0"` → `"0.7.0"` (line 207)
- `ANIPManifest.protocol` default: `"anip/0.3"` → `"anip/0.7"` (line 240)

**Step 4: Update TypeScript model defaults**

In `packages/typescript/core/src/models.ts`:
- `ManifestMetadata.version` default: `"0.2.0"` → `"0.7.0"` (line 241)
- `ANIPManifest.protocol` default: `"anip/0.3"` → `"anip/0.7"` (line 258)

**Step 5: Update all pyproject.toml versions**

Change `version = "0.6.0"` to `version = "0.7.0"` in:
- `packages/python/anip-core/pyproject.toml`
- `packages/python/anip-crypto/pyproject.toml`
- `packages/python/anip-server/pyproject.toml`
- `packages/python/anip-service/pyproject.toml`
- `packages/python/anip-fastapi/pyproject.toml`

**Step 6: Update all package.json versions**

Change `"version": "0.6.0"` to `"version": "0.7.0"` in:
- `packages/typescript/core/package.json`
- `packages/typescript/crypto/package.json`
- `packages/typescript/server/package.json`
- `packages/typescript/service/package.json`
- `packages/typescript/express/package.json`
- `packages/typescript/fastify/package.json`
- `packages/typescript/hono/package.json`

**Step 7: Update JSON Schema $id**

In `schema/anip.schema.json` and `schema/discovery.schema.json`:
Change `v0.6` to `v0.7` in the `$id` field.

**Step 8: Fix test assertions that reference old version**

In `packages/python/anip-core/tests/test_models.py`, find the test `test_protocol_version` and update:
```python
assert PROTOCOL_VERSION == "anip/0.7"
```

In `packages/typescript/core/tests/models.test.ts`, find the test for `PROTOCOL_VERSION` and update:
```typescript
expect(PROTOCOL_VERSION).toBe("anip/0.7");
```

**Step 9: Run all tests**

```bash
.venv/bin/python -m pytest packages/python -x -q
cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose
```

Expected: All 297 tests pass (152 Python + 145 TypeScript).

**Step 10: Commit**

```bash
git add -A
git commit -m "chore: bump all versions to 0.7.0 for discovery posture release"
```

---

## Task 2: Python Posture Models

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

## Task 3: TypeScript Posture Models

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

## Task 4: Python Service — Emit Posture in Discovery

Update `get_discovery()` to compute and include the posture block from existing service state.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/python/anip-service/tests/test_service_init.py`

**Context:** The service already has all the data needed to compute posture:
- `self._trust_level` → audit.signed, anchoring.enabled
- `self._manifest.trust.anchoring` → anchoring.cadence, anchoring.max_lag
- `self._checkpoint_policy` → anchoring presence
- Lineage, metadata_policy, failure_disclosure are protocol constants

**Step 1: Write failing tests**

Add to the `TestANIPServiceInit` class in `packages/python/anip-service/tests/test_service_init.py`:

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

def test_discovery_posture_anchored(self):
    from anip_server import LocalFileSink, CheckpointPolicy
    import tempfile, os
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
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest packages/python/anip-service/tests/test_service_init.py -x -q -k "posture"
```

Expected: KeyError — `posture` not in discovery response.

**Step 3: Update `get_discovery()` in `service.py`**

Add import at top of `packages/python/anip-service/src/anip_service/service.py` (with existing anip_core imports):
```python
from anip_core import (
    ...existing imports...,
    AnchoringPosture,
    DiscoveryPosture,
)
```

Replace the `get_discovery()` method body (lines 152-179) with:

```python
def get_discovery(self) -> dict[str, Any]:
    """Return lightweight discovery document."""
    caps_summary = {}
    for name, cap in self._capabilities.items():
        decl = cap.declaration
        caps_summary[name] = {
            "description": decl.description,
            "side_effect": decl.side_effect.type.value if decl.side_effect else None,
            "minimum_scope": decl.minimum_scope,
            "contract_version": decl.contract_version,
        }

    # Build posture from existing service state
    anchoring_src = self._manifest.trust.anchoring if self._manifest.trust else None
    is_anchored = self._trust_level in ("anchored", "attested")
    posture = DiscoveryPosture(
        anchoring=AnchoringPosture(
            enabled=is_anchored,
            cadence=anchoring_src.cadence if anchoring_src else None,
            max_lag=anchoring_src.max_lag if anchoring_src else None,
            proofs_available=is_anchored,
        ),
    )

    return {
        "anip_discovery": {
            "profile": "full",
            "capabilities": caps_summary,
            "trust_level": self._trust_level,
            "posture": posture.model_dump(),
            "endpoints": {
                "manifest": "/anip/manifest",
                "tokens": "/anip/tokens",
                "invoke": "/anip/invoke/{capability}",
                "permissions": "/anip/permissions",
                "audit": "/anip/audit",
                "checkpoints": "/anip/checkpoints",
                "jwks": "/.well-known/jwks.json",
            },
        }
    }
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest packages/python -x -q
```

Expected: All pass (existing tests should remain green — they don't assert the absence of `posture`).

**Step 5: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(service): emit posture block in Python discovery response (v0.7)"
```

---

## Task 5: TypeScript Service — Emit Posture in Discovery

Update `getDiscovery()` to compute and include the posture block.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Test: `packages/typescript/service/tests/service.test.ts`

**Context:** The service closure already has `trustLevel` (string) and `anchoringPolicy` (object with cadence/max_lag). The `trustPosture` variable (line 230) is in scope but only used for `buildManifest`. We need to reference it inside `getDiscovery()`.

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
});

it("discovery posture reflects anchored trust", () => {
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
  expect(posture.anchoring.cadence).toBe("PT30S");
  expect(posture.anchoring.max_lag).toBe(120);
  expect(posture.anchoring.proofs_available).toBe(true);
});
```

**Step 2: Run tests to verify they fail**

```bash
cd packages/typescript && npx tsc -b core crypto server service && npx vitest run service/tests/service.test.ts --reporter=verbose
```

Expected: `posture` is undefined.

**Step 3: Update `getDiscovery()` in `service.ts`**

In `packages/typescript/service/src/service.ts`, replace the `getDiscovery()` method (lines 375-403):

```typescript
getDiscovery(): Record<string, unknown> {
  const capsSummary: Record<string, unknown> = {};
  for (const [name, cap] of capabilities) {
    const decl = cap.declaration;
    capsSummary[name] = {
      description: decl.description,
      side_effect: decl.side_effect?.type ?? null,
      minimum_scope: decl.minimum_scope,
      contract_version: decl.contract_version,
    };
  }

  const isAnchored = trustLevel === "anchored" || trustLevel === "attested";

  return {
    anip_discovery: {
      profile: "full",
      capabilities: capsSummary,
      trust_level: trustLevel,
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
          proofs_available: isAnchored,
        },
      },
      endpoints: {
        manifest: "/anip/manifest",
        tokens: "/anip/tokens",
        invoke: "/anip/invoke/{capability}",
        permissions: "/anip/permissions",
        audit: "/anip/audit",
        checkpoints: "/anip/checkpoints",
        jwks: "/.well-known/jwks.json",
      },
    },
  };
},
```

**Step 4: Run tests**

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

## Task 6: JSON Schema — Add Posture Block

Add the `posture` property to the discovery JSON schema.

**Files:**
- Modify: `schema/discovery.schema.json`

**Step 1: Add `posture` property**

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
cd /Users/samirski/Development/ANIP/.worktrees/v07-discovery-posture
python3 -c "import json; json.load(open('schema/discovery.schema.json'))"
```

Expected: No error.

**Step 3: Commit**

```bash
git add schema/
git commit -m "feat(schema): add posture block to discovery JSON schema (v0.7)"
```

---

## Task 7: SPEC.md — Discovery Posture Section

Add normative specification language for the posture block.

**Files:**
- Modify: `SPEC.md`

**Step 1: Add posture field to §6.1 discovery document example**

In the YAML example in §6.1 (around line 496 after `trust_level: "anchored"`), add:

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

**Step 2: Add posture field description**

In the Fields section after the `trust_level` bullet (around line 524), add:

```markdown
- **posture** (OPTIONAL, v0.7) — governance posture summary. Exposes trust-relevant service characteristics that agents can inspect before invocation. Contains five sub-objects:
  - `audit` — whether audit logging is active, signed, queryable, and for how long entries are retained
  - `lineage` — whether invocation IDs and client reference IDs are supported, and how they propagate
  - `metadata_policy` — whether lineage is bounded, whether freeform context is accepted, and how metadata propagates downstream
  - `failure_disclosure` — how much error detail is surfaced to callers (`"full"`, `"redacted"`, or `"policy"`)
  - `anchoring` — whether Merkle checkpoints are active, their cadence, maximum lag, and whether proofs are available

  The posture block exposes governance semantics, not implementation trivia. Services MUST NOT expose internal infrastructure details (database engines, ORM types, queue implementations) in posture fields.

  See Section 6.7 for full field definitions and semantics.
```

**Step 3: Add §6.7 Discovery Posture section**

Insert a new section after §6.6 Streaming Invocations (after line 933):

```markdown
### 6.7 Discovery Posture (v0.7)

The discovery posture block allows agents to inspect a service's governance characteristics before invocation. This is the bridge between the market conversation about agent-scale trust and the protocol reality of how a specific ANIP service behaves.

The posture block is OPTIONAL. When present, it MUST conform to the schema defined in `schema/discovery.schema.json`.

#### Posture vs. Manifest

Discovery posture summarizes **service-level governance**. Manifest capabilities describe **per-capability contracts**. The distinction:

- Discovery posture: "This service signs audit entries, bounds lineage, and redacts failure details."
- Manifest capability: "The `book_flight` capability has side-effect `irreversible`, costs $50–$200, and requires scope `travel.book`."

#### `posture.audit`

Tells callers whether audit logging exists and how usable it is.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | MUST | Whether audit logging is active |
| `signed` | boolean | MUST | Whether audit entries carry per-entry signatures |
| `queryable` | boolean | MUST | Whether the audit log is queryable via the audit endpoint |
| `retention` | string \| null | MAY | ISO 8601 duration for audit log retention (e.g., `"P90D"`). Null means unspecified. |

#### `posture.lineage`

Tells callers whether cross-action correlation exists and how constrained it is.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invocation_id` | boolean | MUST | Whether server-generated invocation IDs are assigned to every invocation |
| `client_reference_id` | object | MAY | Client reference ID policy (see sub-fields below) |

**`client_reference_id` sub-fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `supported` | boolean | MUST | Whether the service accepts caller-supplied reference IDs |
| `max_length` | integer | MAY | Maximum length in characters (default: 256) |
| `opaque` | boolean | MAY | Whether the service treats the value as opaque (does not interpret it) |
| `propagation` | string | MAY | How the reference ID propagates: `"bounded"` (stored with the invocation only), `"local_only"` (not persisted), or `"policy"` (service-defined) |

#### `posture.metadata_policy`

Makes ANIP's bounded-lineage stance explicit. This is one of the most important posture fields — it tells adopters that ANIP is not silently turning metadata into an unbounded transport channel.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bounded_lineage` | boolean | MUST | Whether lineage metadata is bounded (not an unbounded transport channel) |
| `freeform_context` | boolean | MAY | Whether arbitrary freeform context fields are accepted in invocation requests |
| `downstream_propagation` | string | MAY | How metadata propagates to downstream services: `"minimal"`, `"policy"`, or `"service_defined"` |

#### `posture.failure_disclosure`

Indicates how much error detail is surfaced to normal callers.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `detail_level` | string | MUST | Error detail level: `"full"` (raw error details), `"redacted"` (generic messages), or `"policy"` (service-defined) |

A service claiming `"redacted"` MUST NOT include raw exception text, stack traces, or internal identifiers in error responses. This is enforced for streaming invocations (§6.6) and SHOULD be enforced for unary responses.

#### `posture.anchoring`

Summarizes service-level anchoring state without exposing internal sink details.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | MUST | Whether Merkle checkpoints are active |
| `cadence` | string \| null | MAY | ISO 8601 duration for checkpoint production cadence (e.g., `"PT30S"`) |
| `max_lag` | integer \| null | MAY | Maximum seconds between newest audit entry and latest checkpoint |
| `proofs_available` | boolean | MAY | Whether inclusion and consistency proofs are available via checkpoint endpoints |

A service claiming `trust_level: "anchored"` MUST set `anchoring.enabled: true`. Services MUST NOT expose raw sink URIs, internal credentials, or private identifiers in posture fields.

#### What posture MUST NOT expose

Services MUST NOT include implementation internals in posture or any discovery field:

- Database engines, ORM choices, or storage backends
- Internal logging frameworks or queue implementations
- Worker-thread details or local filesystem paths
- Internal sink credentials or private identifiers

Posture exposes governance semantics, not deployment topology.
```

**Step 4: Update §13 Roadmap**

In the roadmap table (around line 1266), add a new row after the streaming row:

```markdown
| **Discovery posture (§6.7)** | MAY — v0.7 | Implemented: posture block with audit, lineage, metadata_policy, failure_disclosure, and anchoring sub-objects | — |
```

Update the narrative paragraph after the table (around line 1269) to include v0.7:

Replace the sentence starting "v0.6 adds streaming invocations" to include: "v0.7 makes governance posture inspectable at discovery time — audit, lineage, metadata policy, failure disclosure, and anchoring characteristics are now visible before invocation."

**Step 5: Update §14 Resolved Questions**

Add to the resolved list (around line 1297):

```markdown
- **Governance posture visibility.** Discovery `posture` block exposes audit, lineage, metadata policy, failure disclosure, and anchoring characteristics at the service level. Posture describes governance semantics, not implementation internals. *(Resolved in v0.7)*
```

**Step 6: Update spec footer**

Update the footer (line 1301) to mention v0.7:

```markdown
*ANIP is an open specification under active development. This is v0.7 — discovery posture makes governance characteristics inspectable before invocation, building on v0.6's streaming, v0.3's anchored trust, v0.4's invocation lineage, and v0.5's async storage. Federated trust and cross-service delegation remain future goals. If you see something missing, wrong, or underspecified, [open an issue](https://github.com/anip-protocol/anip/issues).*
```

Update the title (line 1) from `v0.6` to `v0.7`.

**Step 7: Commit**

```bash
git add SPEC.md
git commit -m "spec: add §6.7 Discovery Posture normative language (v0.7)"
```

---

## Task 8: Documentation Updates

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

- Update the version/status line to mention v0.7 and discovery posture
- Add posture to the feature list or "What's new" section
- Update the "What's next" section

**Step 2: Update SECURITY.md**

- Add v0.7 to the version table: `| v0.7 | Current — discovery posture, governance visibility |`
- Move v0.6 from "Current" to "Stable"
- Add "What v0.7 Adds" section:
  ```
  - **Discovery posture (v0.7)** — `posture` block in `/.well-known/anip` exposes audit, lineage, metadata policy, failure disclosure, and anchoring characteristics at the service level
  - Posture describes governance semantics, not implementation internals — no database engines, ORM types, or infrastructure details
  ```

**Step 3: Update CONTRIBUTING.md**

- Update the resolved questions list to include v0.7 (governance posture visibility)

**Step 4: Update GUIDE.md**

- Update any version references from v0.6 to v0.7

**Step 5: Update `schema/README.md`**

- Bump schema version references from v0.6 to v0.7
- Add `DiscoveryPosture` and sub-types row to the schema table

**Step 6: Update skills files**

- Update spec version references in `skills/anip-consumer.md`, `skills/anip-implementer.md`, `skills/anip-validator.md`

**Step 7: Update `docs/trust-model.md`**

- Add discovery posture as a new section or mention in the trust model overview

**Step 8: Commit**

```bash
git add README.md SECURITY.md CONTRIBUTING.md GUIDE.md docs/ schema/README.md skills/
git commit -m "docs: update all documentation to reflect v0.7 discovery posture"
```
