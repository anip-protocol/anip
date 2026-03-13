# ANIP SDK Packages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract reusable SDK packages (anip-core, anip-crypto, anip-server) from the v0.3 reference implementations for Python and TypeScript.

**Architecture:** Three packages per language with dependency chain `core → crypto → server`. Standalone PyPI packages for Python, npm workspace with scoped packages for TypeScript.

**Tech Stack:** Python (Pydantic, cryptography, PyJWT), TypeScript (Zod, jose, better-sqlite3), pytest, vitest.

---

## Phase 1: Package Scaffolding

### Task 1: Create Python package directory structure

**Files:**
- Create: `packages/python/anip-core/pyproject.toml`
- Create: `packages/python/anip-core/src/anip_core/__init__.py`
- Create: `packages/python/anip-crypto/pyproject.toml`
- Create: `packages/python/anip-crypto/src/anip_crypto/__init__.py`
- Create: `packages/python/anip-server/pyproject.toml`
- Create: `packages/python/anip-server/src/anip_server/__init__.py`

**Step 1: Create directory tree**

```bash
mkdir -p packages/python/anip-core/src/anip_core
mkdir -p packages/python/anip-core/tests
mkdir -p packages/python/anip-crypto/src/anip_crypto
mkdir -p packages/python/anip-crypto/tests
mkdir -p packages/python/anip-server/src/anip_server
mkdir -p packages/python/anip-server/tests
```

**Step 2: Write anip-core pyproject.toml**

```toml
[project]
name = "anip-core"
version = "0.3.0"
description = "ANIP protocol types, models, and constants"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 3: Write anip-crypto pyproject.toml**

```toml
[project]
name = "anip-crypto"
version = "0.3.0"
description = "ANIP cryptographic primitives — key management, JWT, JWS, JWKS"
requires-python = ">=3.11"
dependencies = [
    "anip-core>=0.3.0",
    "cryptography>=42.0",
    "PyJWT[crypto]>=2.8",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 4: Write anip-server pyproject.toml**

```toml
[project]
name = "anip-server"
version = "0.3.0"
description = "ANIP server primitives — delegation, audit, checkpoints, Merkle trees"
requires-python = ">=3.11"
dependencies = [
    "anip-core>=0.3.0",
    "anip-crypto>=0.3.0",
]

[project.optional-dependencies]
sqlite = ["aiosqlite>=0.19"]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 5: Write placeholder `__init__.py` for each package**

Each `__init__.py` should contain:
```python
"""ANIP <package-name>."""
```

**Step 6: Commit**

```bash
git add packages/python/
git commit -m "chore: scaffold Python SDK package structure"
```

---

### Task 2: Create TypeScript workspace and package structure

**Files:**
- Create: `packages/typescript/package.json`
- Create: `packages/typescript/tsconfig.base.json`
- Create: `packages/typescript/core/package.json`
- Create: `packages/typescript/core/tsconfig.json`
- Create: `packages/typescript/core/src/index.ts`
- Create: `packages/typescript/crypto/package.json`
- Create: `packages/typescript/crypto/tsconfig.json`
- Create: `packages/typescript/crypto/src/index.ts`
- Create: `packages/typescript/server/package.json`
- Create: `packages/typescript/server/tsconfig.json`
- Create: `packages/typescript/server/src/index.ts`

**Step 1: Create directory tree**

```bash
mkdir -p packages/typescript/core/src packages/typescript/core/tests
mkdir -p packages/typescript/crypto/src packages/typescript/crypto/tests
mkdir -p packages/typescript/server/src packages/typescript/server/tests
```

**Step 2: Write workspace root package.json**

```json
{
  "name": "anip-sdk",
  "private": true,
  "workspaces": ["core", "crypto", "server"]
}
```

**Step 3: Write tsconfig.base.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": "src"
  }
}
```

**Step 4: Write core/package.json**

```json
{
  "name": "@anip/core",
  "version": "0.3.0",
  "description": "ANIP protocol types, models, and constants",
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 5: Write crypto/package.json**

```json
{
  "name": "@anip/crypto",
  "version": "0.3.0",
  "description": "ANIP cryptographic primitives — key management, JWT, JWS, JWKS",
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/core": "0.3.0",
    "jose": "^6.2.1"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 6: Write server/package.json**

```json
{
  "name": "@anip/server",
  "version": "0.3.0",
  "description": "ANIP server primitives — delegation, audit, checkpoints, Merkle trees",
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/core": "0.3.0",
    "@anip/crypto": "0.3.0",
    "better-sqlite3": "^12.6.2"
  },
  "devDependencies": {
    "@types/better-sqlite3": "^7.6.13",
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 7: Write tsconfig.json for each package**

Each package `tsconfig.json`:
```json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

**Step 8: Write placeholder index.ts files**

Each `src/index.ts`:
```typescript
// @anip/<package> — ANIP SDK
```

**Step 9: Install dependencies**

```bash
cd packages/typescript && npm install
```

**Step 10: Commit**

```bash
git add packages/typescript/
git commit -m "chore: scaffold TypeScript SDK workspace structure"
```

---

## Phase 2: anip-core

### Task 3: Python anip-core — protocol models

Extract all Pydantic models from `examples/anip/anip_server/primitives/models.py` into the core package.

**Files:**
- Create: `packages/python/anip-core/src/anip_core/models.py`
- Create: `packages/python/anip-core/src/anip_core/failures.py`
- Create: `packages/python/anip-core/src/anip_core/constants.py`
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`

**Step 1: Write test for model imports**

Create `packages/python/anip-core/tests/test_models.py`:

```python
"""Tests for anip-core protocol models."""
import pytest
from anip_core import (
    ANIPManifest,
    CapabilityDeclaration,
    DelegationToken,
    TrustPosture,
    AnchoringPolicy,
    SideEffectType,
    ConcurrentBranches,
    PermissionResponse,
    InvokeResponse,
    ANIPFailure,
    PROTOCOL_VERSION,
)


def test_protocol_version():
    assert PROTOCOL_VERSION == "anip/0.3"


def test_delegation_token_roundtrip():
    token = DelegationToken(
        token_id="tok-1",
        issuer="svc",
        subject="agent",
        scope=["travel.search"],
        purpose={"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        parent=None,
        expires="2026-12-31T23:59:59Z",
        constraints={"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    )
    d = token.model_dump()
    assert d["token_id"] == "tok-1"
    assert d["scope"] == ["travel.search"]
    restored = DelegationToken.model_validate(d)
    assert restored.token_id == token.token_id


def test_trust_posture_defaults():
    tp = TrustPosture()
    assert tp.level == "signed"
    assert tp.anchoring is None


def test_trust_posture_anchored():
    tp = TrustPosture(
        level="anchored",
        anchoring=AnchoringPolicy(
            cadence="PT60S",
            max_lag=100,
            sink=["witness:example.com"],
        ),
    )
    assert tp.anchoring.max_lag == 100
    assert tp.anchoring.sink == ["witness:example.com"]


def test_capability_declaration():
    decl = CapabilityDeclaration(
        name="test",
        description="A test capability",
        contract_version="1.0",
        inputs=[],
        output={"type": "object", "fields": []},
        side_effect={"type": "read", "rollback_window": None},
        minimum_scope=["test.read"],
    )
    assert decl.name == "test"
    assert decl.side_effect.type == SideEffectType.READ


def test_anip_failure():
    failure = ANIPFailure(
        type="scope_insufficient",
        detail="Missing required scope",
        resolution={"action": "request_broader_scope"},
        retry=False,
    )
    assert failure.type == "scope_insufficient"
    assert failure.retry is False


def test_manifest_structure():
    manifest = ANIPManifest(
        protocol="anip/0.3",
        profile={"core": "1.0"},
        capabilities={},
    )
    assert manifest.protocol == "anip/0.3"


def test_permission_response():
    resp = PermissionResponse(available=[], restricted=[], denied=[])
    assert len(resp.available) == 0


def test_side_effect_type_enum():
    assert SideEffectType.READ == "read"
    assert SideEffectType.IRREVERSIBLE == "irreversible"


def test_concurrent_branches_enum():
    assert ConcurrentBranches.EXCLUSIVE == "exclusive"
    assert ConcurrentBranches.ALLOWED == "allowed"
```

**Step 2: Run test to verify it fails**

```bash
cd packages/python/anip-core && pip install -e ".[dev]" && pytest tests/ -v
```

Expected: ImportError — `anip_core` has no models yet.

**Step 3: Extract models**

Copy and adapt models from `examples/anip/anip_server/primitives/models.py`.

`packages/python/anip-core/src/anip_core/models.py` — all Pydantic BaseModel classes:
- Enums: `SideEffectType`, `ConcurrentBranches`, `CostCertainty`, `SessionType`
- Side-effects: `SideEffect`
- Delegation: `Purpose`, `DelegationConstraints`, `DelegationToken`, `TokenRequest`
- Capabilities: `CapabilityInput`, `CapabilityOutput`, `Cost`, `CostActual`, `CapabilityRequirement`, `CapabilityComposition`, `SessionInfo`, `ObservabilityContract`, `CapabilityDeclaration`
- Permissions: `AvailableCapability`, `RestrictedCapability`, `DeniedCapability`, `PermissionResponse`
- Invocation: `TokenPresentation`, `InvokeRequestV2`, `InvokeRequest`, `InvokeResponse`
- Manifest: `ProfileVersions`, `ManifestMetadata`, `ServiceIdentity`, `ANIPManifest`
- Trust (v0.3): `AnchoringPolicy`, `TrustPolicyTrigger`, `TrustPosture`
- Checkpoint: `CheckpointBody` (new model for SDK)

Key changes from source:
- Remove `from ..capabilities` imports — models must be self-contained
- `ANIPManifest.protocol` defaults to `"anip/0.3"`
- `ManifestMetadata.version` defaults to `"0.3.0"`
- Add `CheckpointBody` model (currently only a dict in database.py)

`packages/python/anip-core/src/anip_core/failures.py`:
```python
"""Structured failure types for ANIP protocol."""
from .models import ANIPFailure, Resolution

# Re-export for convenience
__all__ = ["ANIPFailure", "Resolution"]
```

`packages/python/anip-core/src/anip_core/constants.py`:
```python
"""ANIP protocol constants."""

PROTOCOL_VERSION = "anip/0.3"
MANIFEST_VERSION = "0.3.0"
DEFAULT_PROFILE = {
    "core": "1.0",
    "cost": "1.0",
    "capability_graph": "1.0",
    "state_session": "1.0",
    "observability": "1.0",
}
SUPPORTED_ALGORITHMS = ["ES256"]
LEAF_HASH_PREFIX = b"\x00"
NODE_HASH_PREFIX = b"\x01"
```

**Step 4: Write facade `__init__.py`**

```python
"""ANIP Core — protocol types, models, and constants."""

from .models import (
    ANIPFailure,
    ANIPManifest,
    AnchoringPolicy,
    AvailableCapability,
    CapabilityComposition,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    CapabilityRequirement,
    CheckpointBody,
    ConcurrentBranches,
    Cost,
    CostActual,
    CostCertainty,
    DelegationConstraints,
    DelegationToken,
    DeniedCapability,
    InvokeRequest,
    InvokeRequestV2,
    InvokeResponse,
    ManifestMetadata,
    ObservabilityContract,
    PermissionResponse,
    ProfileVersions,
    Purpose,
    Resolution,
    RestrictedCapability,
    ServiceIdentity,
    SessionInfo,
    SessionType,
    SideEffect,
    SideEffectType,
    TokenPresentation,
    TokenRequest,
    TrustPolicyTrigger,
    TrustPosture,
)
from .constants import (
    DEFAULT_PROFILE,
    LEAF_HASH_PREFIX,
    MANIFEST_VERSION,
    NODE_HASH_PREFIX,
    PROTOCOL_VERSION,
    SUPPORTED_ALGORITHMS,
)

__all__ = [
    # Models
    "ANIPFailure",
    "ANIPManifest",
    "AnchoringPolicy",
    "AvailableCapability",
    "CapabilityComposition",
    "CapabilityDeclaration",
    "CapabilityInput",
    "CapabilityOutput",
    "CapabilityRequirement",
    "CheckpointBody",
    "ConcurrentBranches",
    "Cost",
    "CostActual",
    "CostCertainty",
    "DelegationConstraints",
    "DelegationToken",
    "DeniedCapability",
    "InvokeRequest",
    "InvokeRequestV2",
    "InvokeResponse",
    "ManifestMetadata",
    "ObservabilityContract",
    "PermissionResponse",
    "ProfileVersions",
    "Purpose",
    "Resolution",
    "RestrictedCapability",
    "ServiceIdentity",
    "SessionInfo",
    "SessionType",
    "SideEffect",
    "SideEffectType",
    "TokenPresentation",
    "TokenRequest",
    "TrustPolicyTrigger",
    "TrustPosture",
    # Constants
    "DEFAULT_PROFILE",
    "LEAF_HASH_PREFIX",
    "MANIFEST_VERSION",
    "NODE_HASH_PREFIX",
    "PROTOCOL_VERSION",
    "SUPPORTED_ALGORITHMS",
]
```

**Step 5: Run tests to verify they pass**

```bash
cd packages/python/anip-core && pytest tests/ -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add packages/python/anip-core/
git commit -m "feat(anip-core): extract Python protocol models and constants"
```

---

### Task 4: TypeScript @anip/core — protocol models

Extract all Zod schemas from `examples/anip-ts/src/types.ts` into the core package.

**Files:**
- Create: `packages/typescript/core/src/models.ts`
- Create: `packages/typescript/core/src/failures.ts`
- Create: `packages/typescript/core/src/constants.ts`
- Modify: `packages/typescript/core/src/index.ts`

**Step 1: Write test**

Create `packages/typescript/core/tests/models.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import {
  ANIPManifest,
  DelegationToken,
  TrustPosture,
  AnchoringPolicy,
  ANIPFailure,
  CapabilityDeclaration,
  PermissionResponse,
  PROTOCOL_VERSION,
} from "../src/index.js";

describe("Protocol constants", () => {
  it("exports correct protocol version", () => {
    expect(PROTOCOL_VERSION).toBe("anip/0.3");
  });
});

describe("DelegationToken", () => {
  it("parses valid token", () => {
    const result = DelegationToken.safeParse({
      token_id: "tok-1",
      issuer: "svc",
      subject: "agent",
      scope: ["travel.search"],
      purpose: { capability: "search_flights", parameters: {}, task_id: "t1" },
      parent: null,
      expires: "2026-12-31T23:59:59Z",
      constraints: { max_delegation_depth: 3, concurrent_branches: "allowed" },
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing required fields", () => {
    const result = DelegationToken.safeParse({ token_id: "tok-1" });
    expect(result.success).toBe(false);
  });
});

describe("TrustPosture", () => {
  it("defaults to signed level", () => {
    const result = TrustPosture.parse({});
    expect(result.level).toBe("signed");
  });

  it("parses anchored with policy", () => {
    const result = TrustPosture.parse({
      level: "anchored",
      anchoring: {
        cadence: "PT60S",
        max_lag: 100,
        sink: ["witness:example.com"],
      },
    });
    expect(result.anchoring?.max_lag).toBe(100);
  });
});

describe("ANIPFailure", () => {
  it("parses failure with resolution", () => {
    const result = ANIPFailure.parse({
      type: "scope_insufficient",
      detail: "Missing scope",
      resolution: { action: "request_broader_scope" },
      retry: false,
    });
    expect(result.type).toBe("scope_insufficient");
  });
});

describe("ANIPManifest", () => {
  it("parses minimal manifest", () => {
    const result = ANIPManifest.safeParse({
      protocol: "anip/0.3",
      profile: { core: "1.0" },
      capabilities: {},
    });
    expect(result.success).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd packages/typescript && npx vitest run --project core
```

Expected: FAIL — imports don't resolve.

**Step 3: Extract Zod schemas**

Copy all Zod schema definitions from `examples/anip-ts/src/types.ts` into `packages/typescript/core/src/models.ts`.

Key changes from source:
- Remove any import from non-core modules
- Add `AnchoringPolicy`, `TrustPosture`, `TrustPolicyTrigger` (v0.3 additions)
- Add `CheckpointBody` schema
- Export both schemas (for runtime) and inferred types (for compile-time)

`packages/typescript/core/src/constants.ts`:
```typescript
export const PROTOCOL_VERSION = "anip/0.3";
export const MANIFEST_VERSION = "0.3.0";
export const DEFAULT_PROFILE = {
  core: "1.0",
  cost: "1.0",
  capability_graph: "1.0",
  state_session: "1.0",
  observability: "1.0",
};
export const SUPPORTED_ALGORITHMS = ["ES256"] as const;
export const LEAF_HASH_PREFIX = 0x00;
export const NODE_HASH_PREFIX = 0x01;
```

`packages/typescript/core/src/failures.ts`:
```typescript
export { ANIPFailure, Resolution } from "./models.js";
export type { ANIPFailure as ANIPFailureType, Resolution as ResolutionType } from "./models.js";
```

**Step 4: Write facade index.ts**

```typescript
export * from "./models.js";
export * from "./constants.js";
```

**Step 5: Run tests**

```bash
cd packages/typescript && npx vitest run --project core
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add packages/typescript/core/
git commit -m "feat(@anip/core): extract TypeScript protocol schemas and constants"
```

---

## Phase 3: anip-crypto

### Task 5: Python anip-crypto — key management

Extract `KeyManager` from `examples/anip/anip_server/primitives/crypto.py`.

**Files:**
- Create: `packages/python/anip-crypto/src/anip_crypto/keys.py`
- Create: `packages/python/anip-crypto/src/anip_crypto/canonicalize.py`

**Step 1: Write test**

Create `packages/python/anip-crypto/tests/test_keys.py`:

```python
"""Tests for KeyManager and key operations."""
import json
import tempfile
from pathlib import Path
from anip_crypto import KeyManager


def test_generate_keys():
    km = KeyManager()
    jwks = km.get_jwks()
    assert len(jwks["keys"]) == 2
    assert jwks["keys"][0]["use"] == "sig"
    assert jwks["keys"][1]["use"] == "audit"


def test_separate_key_ids():
    km = KeyManager()
    jwks = km.get_jwks()
    delegation_kid = jwks["keys"][0]["kid"]
    audit_kid = jwks["keys"][1]["kid"]
    assert delegation_kid != audit_kid


def test_persist_and_load():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    km1 = KeyManager(key_path=path)
    jwks1 = km1.get_jwks()
    km2 = KeyManager(key_path=path)
    jwks2 = km2.get_jwks()
    assert jwks1["keys"][0]["kid"] == jwks2["keys"][0]["kid"]
    assert jwks1["keys"][1]["kid"] == jwks2["keys"][1]["kid"]
    Path(path).unlink()
```

**Step 2: Run test — expected FAIL**

```bash
cd packages/python/anip-crypto && pip install -e ".[dev]" && pip install -e ../anip-core && pytest tests/test_keys.py -v
```

**Step 3: Implement KeyManager**

`packages/python/anip-crypto/src/anip_crypto/keys.py`:

Extract `KeyManager` class from `examples/anip/anip_server/primitives/crypto.py`. Include:
- `__init__`, `_generate_keys`, `_derive_kid`, `_save_keys`, `_load_keys`
- `get_jwks()`
- Properties: `private_key`, `public_key`, `kid`, `audit_private_key`, `audit_public_key`, `audit_kid`
- Keep `_b64url_encode` and `_b64url_decode` as module-level helpers

Key change: Remove hardcoded audience from `verify_jwt` — make it a parameter with no default.

`packages/python/anip-crypto/src/anip_crypto/canonicalize.py`:
```python
"""Canonical JSON helpers for verifiable ANIP artifacts."""
import json
from typing import Any


def canonicalize(data: dict[str, Any], *, exclude: set[str] | None = None) -> bytes:
    """Produce canonical JSON bytes for signing/hashing.

    Sorts keys, uses compact separators, optionally excludes fields.
    """
    filtered = {k: v for k, v in sorted(data.items()) if k not in (exclude or set())}
    return json.dumps(filtered, separators=(",", ":"), sort_keys=True).encode()
```

**Step 4: Run tests — expected PASS**

```bash
pytest tests/test_keys.py -v
```

**Step 5: Commit**

```bash
git add packages/python/anip-crypto/
git commit -m "feat(anip-crypto): extract Python KeyManager and canonicalization"
```

---

### Task 6: Python anip-crypto — JWT, JWS, JWKS, verification

**Files:**
- Create: `packages/python/anip-crypto/src/anip_crypto/jwt.py`
- Create: `packages/python/anip-crypto/src/anip_crypto/jws.py`
- Create: `packages/python/anip-crypto/src/anip_crypto/jwks.py`
- Create: `packages/python/anip-crypto/src/anip_crypto/verify.py`
- Modify: `packages/python/anip-crypto/src/anip_crypto/__init__.py`

**Step 1: Write tests**

Create `packages/python/anip-crypto/tests/test_jwt_jws.py`:

```python
"""Tests for JWT and JWS operations."""
import json
from anip_crypto import KeyManager
from anip_crypto.jwt import sign_jwt, verify_jwt
from anip_crypto.jws import sign_jws_detached, verify_jws_detached, sign_jws_detached_audit, verify_jws_detached_audit
from anip_crypto.jwks import build_jwks
from anip_crypto.canonicalize import canonicalize
from anip_crypto.verify import verify_audit_entry_signature


def test_jwt_sign_verify():
    km = KeyManager()
    token = sign_jwt(km, {"sub": "agent", "aud": "test-svc"})
    claims = verify_jwt(km, token, audience="test-svc")
    assert claims["sub"] == "agent"


def test_jwt_wrong_audience_fails():
    import pytest
    km = KeyManager()
    token = sign_jwt(km, {"sub": "agent", "aud": "svc-a"})
    with pytest.raises(Exception):
        verify_jwt(km, token, audience="svc-b")


def test_jws_detached_delegation():
    km = KeyManager()
    payload = b"manifest-bytes"
    jws = sign_jws_detached(km, payload)
    parts = jws.split(".")
    assert len(parts) == 3
    assert parts[1] == ""
    verify_jws_detached(km, jws, payload)


def test_jws_detached_audit():
    km = KeyManager()
    payload = b"checkpoint-body"
    jws = sign_jws_detached_audit(km, payload)
    verify_jws_detached_audit(km, jws, payload)


def test_jws_delegation_key_cannot_verify_audit_signature():
    import pytest
    km = KeyManager()
    payload = b"data"
    jws = sign_jws_detached_audit(km, payload)
    with pytest.raises(Exception):
        verify_jws_detached(km, jws, payload)


def test_build_jwks():
    km = KeyManager()
    jwks = build_jwks(km)
    assert len(jwks["keys"]) == 2
    assert jwks["keys"][0]["alg"] == "ES256"


def test_canonicalize():
    data = {"b": 2, "a": 1, "signature": "remove-me"}
    canonical = canonicalize(data, exclude={"signature"})
    parsed = json.loads(canonical)
    assert list(parsed.keys()) == ["a", "b"]


def test_verify_audit_entry_signature():
    km = KeyManager()
    entry = {"capability": "test", "timestamp": "2026-01-01T00:00:00Z", "success": True}
    from anip_crypto.keys import KeyManager as KM
    sig = km.sign_audit_entry(entry)
    verify_audit_entry_signature(km, entry, sig)
```

**Step 2: Run tests — expected FAIL**

```bash
cd packages/python/anip-crypto && pytest tests/ -v
```

**Step 3: Implement JWT, JWS, JWKS, verify modules**

`jwt.py` — Extract `sign_jwt` and `verify_jwt` as standalone functions that take a `KeyManager`:
```python
"""JWT signing and verification for ANIP delegation tokens."""
import jwt as pyjwt
from .keys import KeyManager


def sign_jwt(key_manager: KeyManager, payload: dict) -> str:
    """Sign a JWT with the delegation key (ES256)."""
    return pyjwt.encode(
        payload,
        key_manager.private_key,
        algorithm="ES256",
        headers={"kid": key_manager.kid},
    )


def verify_jwt(key_manager: KeyManager, token: str, *, audience: str) -> dict:
    """Verify a JWT signature and audience."""
    return pyjwt.decode(
        token,
        key_manager.public_key,
        algorithms=["ES256"],
        audience=audience,
    )
```

`jws.py` — Extract detached JWS operations from `crypto.py`. Four public functions:
- `sign_jws_detached(key_manager, payload)` — delegation key
- `verify_jws_detached(key_manager, jws, payload)` — delegation key
- `sign_jws_detached_audit(key_manager, payload)` — audit key
- `verify_jws_detached_audit(key_manager, jws, payload)` — audit key

`jwks.py`:
```python
"""JWKS construction for ANIP services."""
from .keys import KeyManager


def build_jwks(key_manager: KeyManager) -> dict:
    """Build a JWKS response containing both public keys."""
    return key_manager.get_jwks()
```

`verify.py` — Verification helpers:
```python
"""Verification helpers for ANIP signed artifacts."""
import hashlib
import jwt as pyjwt
from .keys import KeyManager
from .canonicalize import canonicalize


def verify_audit_entry_signature(
    key_manager: KeyManager, entry: dict, signature: str
) -> dict:
    """Verify an audit entry's signature using the audit public key.

    Returns the decoded JWT claims on success, raises on failure.
    """
    claims = pyjwt.decode(
        signature,
        key_manager.audit_public_key,
        algorithms=["ES256"],
    )
    canonical = canonicalize(entry, exclude={"signature", "id"})
    expected_hash = hashlib.sha256(canonical).hexdigest()
    if claims.get("audit_hash") != expected_hash:
        raise ValueError("Audit hash mismatch")
    return claims
```

Also add `sign_audit_entry` method to `KeyManager` in `keys.py`.

**Step 4: Write facade __init__.py**

```python
"""ANIP Crypto — key management, JWT, JWS, JWKS, verification."""
from .keys import KeyManager
from .jwt import sign_jwt, verify_jwt
from .jws import (
    sign_jws_detached,
    verify_jws_detached,
    sign_jws_detached_audit,
    verify_jws_detached_audit,
)
from .jwks import build_jwks
from .canonicalize import canonicalize
from .verify import verify_audit_entry_signature

__all__ = [
    "KeyManager",
    "sign_jwt",
    "verify_jwt",
    "sign_jws_detached",
    "verify_jws_detached",
    "sign_jws_detached_audit",
    "verify_jws_detached_audit",
    "build_jwks",
    "canonicalize",
    "verify_audit_entry_signature",
]
```

**Step 5: Run tests — expected PASS**

```bash
pytest tests/ -v
```

**Step 6: Commit**

```bash
git add packages/python/anip-crypto/
git commit -m "feat(anip-crypto): add JWT, JWS, JWKS, and verification helpers"
```

---

### Task 7: TypeScript @anip/crypto — full crypto package

Extract `KeyManager` from `examples/anip-ts/src/crypto.ts` and split into modules.

**Files:**
- Create: `packages/typescript/crypto/src/keys.ts`
- Create: `packages/typescript/crypto/src/jwt.ts`
- Create: `packages/typescript/crypto/src/jws.ts`
- Create: `packages/typescript/crypto/src/jwks.ts`
- Create: `packages/typescript/crypto/src/canonicalize.ts`
- Create: `packages/typescript/crypto/src/verify.ts`
- Modify: `packages/typescript/crypto/src/index.ts`

**Step 1: Write test**

Create `packages/typescript/crypto/tests/crypto.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import {
  KeyManager,
  signJWT,
  verifyJWT,
  signJWSDetached,
  verifyJWSDetached,
  signJWSDetachedAudit,
  verifyJWSDetachedAudit,
  buildJWKS,
  canonicalize,
} from "../src/index.js";

describe("KeyManager", () => {
  it("generates two key pairs", async () => {
    const km = new KeyManager();
    await km.ready();
    const jwks = await buildJWKS(km);
    expect(jwks.keys).toHaveLength(2);
    expect(jwks.keys[0].use).toBe("sig");
    expect(jwks.keys[1].use).toBe("audit");
  });

  it("has distinct delegation and audit KIDs", async () => {
    const km = new KeyManager();
    await km.ready();
    const jwks = await buildJWKS(km);
    expect(jwks.keys[0].kid).not.toBe(jwks.keys[1].kid);
  });
});

describe("JWT", () => {
  it("signs and verifies", async () => {
    const km = new KeyManager();
    await km.ready();
    const token = await signJWT(km, { sub: "agent" });
    const claims = await verifyJWT(km, token);
    expect(claims.sub).toBe("agent");
  });
});

describe("JWS Detached", () => {
  it("signs and verifies with delegation key", async () => {
    const km = new KeyManager();
    await km.ready();
    const payload = new TextEncoder().encode("manifest");
    const jws = await signJWSDetached(km, payload);
    const parts = jws.split(".");
    expect(parts).toHaveLength(3);
    expect(parts[1]).toBe("");
    await verifyJWSDetached(km, jws, payload);
  });

  it("signs and verifies with audit key", async () => {
    const km = new KeyManager();
    await km.ready();
    const payload = new TextEncoder().encode("checkpoint");
    const jws = await signJWSDetachedAudit(km, payload);
    await verifyJWSDetachedAudit(km, jws, payload);
  });

  it("delegation key cannot verify audit signature", async () => {
    const km = new KeyManager();
    await km.ready();
    const payload = new TextEncoder().encode("data");
    const jws = await signJWSDetachedAudit(km, payload);
    await expect(verifyJWSDetached(km, jws, payload)).rejects.toThrow();
  });
});

describe("canonicalize", () => {
  it("sorts keys and excludes specified fields", () => {
    const result = canonicalize(
      { b: 2, a: 1, signature: "skip" },
      new Set(["signature"])
    );
    const parsed = JSON.parse(result);
    expect(Object.keys(parsed)).toEqual(["a", "b"]);
  });
});
```

**Step 2: Run test — expected FAIL**

```bash
cd packages/typescript && npx vitest run --project crypto
```

**Step 3: Implement**

Extract from `examples/anip-ts/src/crypto.ts`:

`keys.ts` — `KeyManager` class with:
- Constructor, `init()`, `ready()`, key persistence
- Expose delegation and audit key/kid via getters (not private)
- `signAuditEntry(entryData)` method
- Remove `signJWSDetached` from class — move to standalone functions

`jwt.ts` — Standalone async functions:
- `signJWT(km, payload)` — wraps `jose.SignJWT`
- `verifyJWT(km, token)` — wraps `jose.jwtVerify`

`jws.ts` — Standalone async functions:
- `signJWSDetached(km, payload)` — uses delegation key
- `verifyJWSDetached(km, jws, payload)`
- `signJWSDetachedAudit(km, payload)` — uses audit key
- `verifyJWSDetachedAudit(km, jws, payload)`

`jwks.ts`:
```typescript
export async function buildJWKS(km: KeyManager): Promise<{ keys: JWK[] }> {
  return km.getJWKS();
}
```

`canonicalize.ts`:
```typescript
export function canonicalize(
  data: Record<string, unknown>,
  exclude?: Set<string>
): string {
  const filtered = Object.fromEntries(
    Object.entries(data)
      .filter(([k]) => !exclude?.has(k))
      .sort(([a], [b]) => a.localeCompare(b))
  );
  return JSON.stringify(filtered);
}
```

`verify.ts` — Verification helpers for audit entries.

**Step 4: Write facade index.ts**

```typescript
export { KeyManager } from "./keys.js";
export { signJWT, verifyJWT } from "./jwt.js";
export {
  signJWSDetached, verifyJWSDetached,
  signJWSDetachedAudit, verifyJWSDetachedAudit,
} from "./jws.js";
export { buildJWKS } from "./jwks.js";
export { canonicalize } from "./canonicalize.js";
export { verifyAuditEntrySignature } from "./verify.js";
```

**Step 5: Run tests — expected PASS**

```bash
cd packages/typescript && npx vitest run --project crypto
```

**Step 6: Commit**

```bash
git add packages/typescript/crypto/
git commit -m "feat(@anip/crypto): extract TypeScript crypto package"
```

---

## Phase 4: anip-server

### Task 8: Python anip-server — storage abstraction

**Files:**
- Create: `packages/python/anip-server/src/anip_server/storage.py`

**Step 1: Write test**

Create `packages/python/anip-server/tests/test_storage.py`:

```python
"""Tests for storage abstraction and SQLite implementation."""
from anip_server.storage import SQLiteStorage


def test_sqlite_token_roundtrip():
    store = SQLiteStorage(":memory:")
    token_data = {
        "token_id": "tok-1",
        "issuer": "svc",
        "subject": "agent",
        "scope": ["travel.search"],
        "expires": "2026-12-31T23:59:59Z",
    }
    store.store_token(token_data)
    loaded = store.load_token("tok-1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-1"


def test_sqlite_audit_roundtrip():
    store = SQLiteStorage(":memory:")
    entry = {
        "sequence_number": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "capability": "test",
        "token_id": "tok-1",
        "root_principal": "human:test@example.com",
        "success": True,
        "result_summary": None,
        "failure_type": None,
        "cost_actual": None,
        "delegation_chain": [],
        "previous_hash": "sha256:0000",
        "signature": None,
    }
    store.store_audit_entry(entry)
    entries = store.query_audit_entries(capability="test")
    assert len(entries) == 1
    assert entries[0]["capability"] == "test"


def test_sqlite_checkpoint_roundtrip():
    store = SQLiteStorage(":memory:")
    body = {"checkpoint_id": "ckpt-001", "merkle_root": "sha256:abc"}
    store.store_checkpoint(body, "header..sig")
    ckpt = store.get_checkpoint_by_id("ckpt-001")
    assert ckpt is not None
    assert ckpt["signature"] == "header..sig"


def test_load_nonexistent_token():
    store = SQLiteStorage(":memory:")
    assert store.load_token("nonexistent") is None
```

**Step 2: Run test — expected FAIL**

```bash
cd packages/python/anip-server && pip install -e ".[dev]" && pip install -e ../anip-core -e ../anip-crypto && pytest tests/test_storage.py -v
```

**Step 3: Implement storage abstraction**

`packages/python/anip-server/src/anip_server/storage.py`:

```python
"""Storage abstraction for ANIP server primitives.

Defines the StorageBackend protocol and provides a SQLite default implementation.
"""
from __future__ import annotations
import json
import sqlite3
from typing import Any, Protocol


class StorageBackend(Protocol):
    """Abstract storage interface for ANIP server data."""

    def store_token(self, token_data: dict[str, Any]) -> None: ...
    def load_token(self, token_id: str) -> dict[str, Any] | None: ...
    def store_audit_entry(self, entry: dict[str, Any]) -> None: ...
    def query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...
    def get_last_audit_entry(self) -> dict[str, Any] | None: ...
    def get_audit_entries_range(self, first: int, last: int) -> list[dict[str, Any]]: ...
    def store_checkpoint(self, body: dict[str, Any], signature: str) -> None: ...
    def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]: ...
    def get_checkpoint_by_id(self, checkpoint_id: str) -> dict[str, Any] | None: ...


class SQLiteStorage:
    """SQLite implementation of StorageBackend."""

    def __init__(self, db_path: str = "anip.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        # delegation_tokens, audit_log, checkpoints tables
        # Extracted from examples/anip/anip_server/data/database.py
        ...

    # Implement all StorageBackend methods
    # Extract logic from examples/anip/anip_server/data/database.py
```

Extract the table creation DDL and CRUD methods from `examples/anip/anip_server/data/database.py`. Key changes:
- No global state — storage is an instance, not module-level
- JSON fields serialized/deserialized transparently
- No `set_audit_signer` — signing is handled by the audit module, not storage

**Step 4: Run tests — expected PASS**

```bash
pytest tests/test_storage.py -v
```

**Step 5: Commit**

```bash
git add packages/python/anip-server/
git commit -m "feat(anip-server): add storage abstraction with SQLite implementation"
```

---

### Task 9: Python anip-server — Merkle tree

**Files:**
- Create: `packages/python/anip-server/src/anip_server/merkle.py`

**Step 1: Write test**

Create `packages/python/anip-server/tests/test_merkle.py`:

```python
"""Tests for RFC 6962 Merkle tree."""
from anip_server.merkle import MerkleTree


def test_single_leaf():
    tree = MerkleTree()
    tree.add_leaf(b"hello")
    assert tree.leaf_count == 1
    assert tree.root.startswith("sha256:")


def test_root_changes_with_new_leaf():
    tree = MerkleTree()
    tree.add_leaf(b"a")
    root1 = tree.root
    tree.add_leaf(b"b")
    assert tree.root != root1


def test_inclusion_proof():
    tree = MerkleTree()
    for i in range(8):
        tree.add_leaf(f"leaf-{i}".encode())
    proof = tree.inclusion_proof(3)
    assert len(proof) > 0
    assert tree.verify_inclusion(3, b"leaf-3", proof, tree.root)


def test_inclusion_proof_wrong_data_fails():
    tree = MerkleTree()
    for i in range(4):
        tree.add_leaf(f"leaf-{i}".encode())
    proof = tree.inclusion_proof(0)
    assert not tree.verify_inclusion(0, b"wrong", proof, tree.root)


def test_consistency_proof():
    tree = MerkleTree()
    for i in range(4):
        tree.add_leaf(f"leaf-{i}".encode())
    old_root = tree.root
    old_size = tree.leaf_count
    for i in range(4, 8):
        tree.add_leaf(f"leaf-{i}".encode())
    proof = tree.consistency_proof(old_size)
    assert MerkleTree.verify_consistency_static(
        old_root, old_size, tree.root, tree.leaf_count, proof
    )


def test_snapshot():
    tree = MerkleTree()
    tree.add_leaf(b"data")
    snap = tree.snapshot()
    assert "root" in snap
    assert snap["leaf_count"] == 1
```

**Step 2: Run test — expected FAIL**

**Step 3: Extract MerkleTree from `examples/anip/anip_server/primitives/merkle.py`**

Copy the full `MerkleTree` class and helper functions. This module is already self-contained with no ANIP-specific imports, so it can be extracted as-is.

**Step 4: Run tests — expected PASS**

**Step 5: Commit**

```bash
git add packages/python/anip-server/src/anip_server/merkle.py packages/python/anip-server/tests/test_merkle.py
git commit -m "feat(anip-server): add RFC 6962 Merkle tree implementation"
```

---

### Task 10: Python anip-server — delegation engine

**Files:**
- Create: `packages/python/anip-server/src/anip_server/delegation.py`

**Step 1: Write test**

Create `packages/python/anip-server/tests/test_delegation.py`:

```python
"""Tests for delegation engine."""
from anip_server.delegation import DelegationEngine
from anip_server.storage import SQLiteStorage
from anip_core import DelegationToken, ANIPFailure


def make_engine():
    storage = SQLiteStorage(":memory:")
    return DelegationEngine(storage)


def test_issue_and_validate():
    engine = make_engine()
    token, token_id = engine.issue_token(
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
        issuer_id="svc",
        root_principal="human:alice@example.com",
    )
    result = engine.validate_delegation(token, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


def test_expired_token_rejected():
    engine = make_engine()
    token, _ = engine.issue_token(
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
        issuer_id="svc",
        root_principal="human:alice@example.com",
        ttl_hours=-1,  # already expired
    )
    result = engine.validate_delegation(token, ["travel.search"], "search_flights")
    assert isinstance(result, ANIPFailure)
    assert result.type == "token_expired"


def test_scope_insufficient():
    engine = make_engine()
    token, _ = engine.issue_token(
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
        issuer_id="svc",
        root_principal="human:alice@example.com",
    )
    result = engine.validate_delegation(token, ["travel.book"], "book_flight")
    assert isinstance(result, ANIPFailure)
    assert result.type == "scope_insufficient"


def test_child_scope_narrowing():
    engine = make_engine()
    parent, parent_id = engine.issue_token(
        subject="agent",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
        issuer_id="svc",
        root_principal="human:alice@example.com",
    )
    child, _ = engine.issue_token(
        subject="sub-agent",
        scope=["travel.search"],
        capability="search_flights",
        issuer_id="agent",
        parent_token=parent,
        root_principal="human:alice@example.com",
    )
    result = engine.validate_delegation(child, ["travel.search"], "search_flights")
    assert isinstance(result, DelegationToken)


def test_child_scope_widening_rejected():
    engine = make_engine()
    parent, _ = engine.issue_token(
        subject="agent",
        scope=["travel.search"],
        capability="search_flights",
        issuer_id="svc",
        root_principal="human:alice@example.com",
    )
    result = engine.issue_token(
        subject="sub-agent",
        scope=["travel.search", "travel.book"],
        capability="search_flights",
        issuer_id="agent",
        parent_token=parent,
        root_principal="human:alice@example.com",
    )
    # Should return ANIPFailure for scope escalation
    assert isinstance(result, ANIPFailure) or (
        isinstance(result, tuple) and isinstance(
            engine.validate_scope_narrowing(result[0]), ANIPFailure
        )
    )
```

**Step 2: Run test — expected FAIL**

**Step 3: Implement delegation engine**

Extract from `examples/anip/anip_server/primitives/delegation.py`. Key change: wrap in a `DelegationEngine` class that takes a `StorageBackend` instead of using module-level state:

```python
class DelegationEngine:
    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage
        self._active_requests: set[str] = set()
        self._lock = threading.Lock()

    def issue_token(self, ...) -> tuple[DelegationToken, str] | ANIPFailure: ...
    def validate_delegation(self, ...) -> DelegationToken | ANIPFailure: ...
    def validate_scope_narrowing(self, ...) -> ANIPFailure | None: ...
    def validate_constraints_narrowing(self, ...) -> ANIPFailure | None: ...
    def check_budget_authority(self, ...) -> ANIPFailure | None: ...
    def get_chain(self, ...) -> list[DelegationToken]: ...
    def get_root_principal(self, ...) -> str: ...
    def acquire_exclusive_lock(self, ...) -> ANIPFailure | None: ...
    def release_exclusive_lock(self, ...) -> None: ...
```

**Step 4: Run tests — expected PASS**

**Step 5: Commit**

```bash
git add packages/python/anip-server/
git commit -m "feat(anip-server): add delegation engine"
```

---

### Task 11: Python anip-server — permissions, manifest, audit, checkpoint, sinks

**Files:**
- Create: `packages/python/anip-server/src/anip_server/permissions.py`
- Create: `packages/python/anip-server/src/anip_server/manifest.py`
- Create: `packages/python/anip-server/src/anip_server/audit.py`
- Create: `packages/python/anip-server/src/anip_server/checkpoint.py`
- Create: `packages/python/anip-server/src/anip_server/sinks.py`
- Modify: `packages/python/anip-server/src/anip_server/__init__.py`

**Step 1: Write tests**

Create `packages/python/anip-server/tests/test_permissions.py`:

```python
"""Tests for permission discovery."""
from anip_core import DelegationToken, CapabilityDeclaration
from anip_server.permissions import discover_permissions


def test_available_capability():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"], purpose={"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        parent=None, expires="2099-12-31T23:59:59Z",
        constraints={"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    )
    caps = {
        "search_flights": CapabilityDeclaration(
            name="search_flights", description="Search", contract_version="1.0",
            inputs=[], output={"type": "object", "fields": []},
            side_effect={"type": "read", "rollback_window": None},
            minimum_scope=["travel.search"],
        ),
    }
    result = discover_permissions(token, caps)
    assert len(result.available) == 1
    assert result.available[0].capability == "search_flights"


def test_denied_capability():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"], purpose={"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        parent=None, expires="2099-12-31T23:59:59Z",
        constraints={"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    )
    caps = {
        "book_flight": CapabilityDeclaration(
            name="book_flight", description="Book", contract_version="1.0",
            inputs=[], output={"type": "object", "fields": []},
            side_effect={"type": "irreversible", "rollback_window": None},
            minimum_scope=["travel.book"],
        ),
    }
    result = discover_permissions(token, caps)
    assert len(result.denied) == 1
```

Create `packages/python/anip-server/tests/test_manifest.py`:

```python
"""Tests for manifest builder."""
from anip_core import CapabilityDeclaration, TrustPosture, ServiceIdentity
from anip_server.manifest import build_manifest


def test_build_manifest():
    caps = {
        "test_cap": CapabilityDeclaration(
            name="test_cap", description="Test", contract_version="1.0",
            inputs=[], output={"type": "object", "fields": []},
            side_effect={"type": "read", "rollback_window": None},
            minimum_scope=["test.read"],
        ),
    }
    trust = TrustPosture(level="signed")
    identity = ServiceIdentity(id="test-svc", jwks_uri="/.well-known/jwks.json", issuer_mode="first-party")
    manifest = build_manifest(capabilities=caps, trust=trust, service_identity=identity)
    assert manifest.protocol == "anip/0.3"
    assert manifest.manifest_metadata is not None
    assert manifest.manifest_metadata.sha256 is not None
    assert "test_cap" in manifest.capabilities
```

Create `packages/python/anip-server/tests/test_checkpoint.py`:

```python
"""Tests for checkpoints and sinks."""
import tempfile
import os
from anip_server.merkle import MerkleTree
from anip_server.checkpoint import create_checkpoint, CheckpointPolicy, CheckpointScheduler
from anip_server.sinks import LocalFileSink, CheckpointSink


def test_checkpoint_policy_entry_count():
    policy = CheckpointPolicy(entry_count=5)
    assert not policy.should_checkpoint(4)
    assert policy.should_checkpoint(5)


def test_checkpoint_policy_no_threshold():
    policy = CheckpointPolicy()
    assert not policy.should_checkpoint(1000)


def test_local_file_sink():
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = LocalFileSink(tmpdir)
        sink.publish({
            "body": {"checkpoint_id": "ckpt-001", "merkle_root": "sha256:abc"},
            "signature": "header..sig",
        })
        files = os.listdir(tmpdir)
        assert len(files) == 1
        assert files[0] == "ckpt-001.json"
```

**Step 2: Run tests — expected FAIL**

**Step 3: Implement all remaining modules**

`permissions.py` — Extract from `examples/anip/anip_server/primitives/permissions.py`. Change to standalone function (not dependent on module state).

`manifest.py` — Extract from `examples/anip/anip_server/primitives/manifest.py`. Key change: takes `capabilities`, `trust`, `service_identity` as parameters instead of importing capability modules and reading env vars.

```python
def build_manifest(
    *,
    capabilities: dict[str, CapabilityDeclaration],
    trust: TrustPosture,
    service_identity: ServiceIdentity,
    expires_days: int = 30,
) -> ANIPManifest:
    ...
```

`audit.py` — Audit log manager that uses `StorageBackend`:

```python
class AuditLog:
    def __init__(self, storage: StorageBackend, signer=None):
        self._storage = storage
        self._signer = signer
        self._merkle = MerkleTree()

    def log_entry(self, entry_data: dict) -> dict: ...
    def query(self, **filters) -> list[dict]: ...
    def get_merkle_snapshot(self) -> dict: ...
```

`checkpoint.py` — Extract `CheckpointPolicy`, `CheckpointScheduler`, `create_checkpoint` from `examples/anip/anip_server/primitives/checkpoint.py` and `examples/anip/anip_server/data/database.py`.

`sinks.py` — Extract `CheckpointSink` (ABC) and `LocalFileSink` from `examples/anip/anip_server/primitives/sinks.py`.

**Step 4: Write facade __init__.py**

```python
"""ANIP Server — delegation, audit, checkpoints, Merkle trees, sinks."""
from .delegation import DelegationEngine
from .permissions import discover_permissions
from .manifest import build_manifest
from .audit import AuditLog
from .merkle import MerkleTree
from .checkpoint import create_checkpoint, CheckpointPolicy, CheckpointScheduler
from .sinks import CheckpointSink, LocalFileSink
from .storage import StorageBackend, SQLiteStorage

__all__ = [
    "DelegationEngine",
    "discover_permissions",
    "build_manifest",
    "AuditLog",
    "MerkleTree",
    "create_checkpoint",
    "CheckpointPolicy",
    "CheckpointScheduler",
    "CheckpointSink",
    "LocalFileSink",
    "StorageBackend",
    "SQLiteStorage",
]
```

**Step 5: Run all tests**

```bash
cd packages/python/anip-server && pytest tests/ -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add packages/python/anip-server/
git commit -m "feat(anip-server): add permissions, manifest, audit, checkpoint, and sinks"
```

---

### Task 12: TypeScript @anip/server — full server package

Mirror the Python server package structure for TypeScript.

**Files:**
- Create: `packages/typescript/server/src/storage.ts`
- Create: `packages/typescript/server/src/merkle.ts`
- Create: `packages/typescript/server/src/delegation.ts`
- Create: `packages/typescript/server/src/permissions.ts`
- Create: `packages/typescript/server/src/manifest.ts`
- Create: `packages/typescript/server/src/audit.ts`
- Create: `packages/typescript/server/src/checkpoint.ts`
- Create: `packages/typescript/server/src/sinks.ts`
- Modify: `packages/typescript/server/src/index.ts`

**Step 1: Write tests**

Create `packages/typescript/server/tests/merkle.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { MerkleTree } from "../src/merkle.js";

describe("MerkleTree", () => {
  it("computes root for single leaf", () => {
    const tree = new MerkleTree();
    tree.addLeaf(Buffer.from("hello"));
    expect(tree.leafCount).toBe(1);
    expect(tree.root).toMatch(/^sha256:/);
  });

  it("root changes with new leaf", () => {
    const tree = new MerkleTree();
    tree.addLeaf(Buffer.from("a"));
    const root1 = tree.root;
    tree.addLeaf(Buffer.from("b"));
    expect(tree.root).not.toBe(root1);
  });

  it("produces valid inclusion proof", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 8; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const proof = tree.inclusionProof(3);
    expect(proof.length).toBeGreaterThan(0);
    expect(tree.verifyInclusion(3, Buffer.from("leaf-3"), proof)).toBe(true);
  });

  it("rejects wrong data in inclusion proof", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 4; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const proof = tree.inclusionProof(0);
    expect(tree.verifyInclusion(0, Buffer.from("wrong"), proof)).toBe(false);
  });

  it("produces valid consistency proof", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 4; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const oldRoot = tree.root;
    const oldSize = tree.leafCount;
    for (let i = 4; i < 8; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const proof = tree.consistencyProof(oldSize);
    expect(
      MerkleTree.verifyConsistencyStatic(oldRoot, oldSize, tree.root, tree.leafCount, proof)
    ).toBe(true);
  });
});
```

Create `packages/typescript/server/tests/delegation.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { DelegationEngine } from "../src/delegation.js";
import { SQLiteStorage } from "../src/storage.js";

function makeEngine() {
  return new DelegationEngine(new SQLiteStorage(":memory:"));
}

describe("DelegationEngine", () => {
  it("issues and validates token", () => {
    const engine = makeEngine();
    const { token } = engine.issueToken({
      subject: "agent",
      scope: ["travel.search"],
      capability: "search_flights",
      issuerId: "svc",
      rootPrincipal: "human:alice@example.com",
    });
    const result = engine.validateDelegation(token, ["travel.search"], "search_flights");
    expect(result).not.toHaveProperty("type"); // not an ANIPFailure
    expect(result).toHaveProperty("token_id");
  });

  it("rejects insufficient scope", () => {
    const engine = makeEngine();
    const { token } = engine.issueToken({
      subject: "agent",
      scope: ["travel.search"],
      capability: "search_flights",
      issuerId: "svc",
      rootPrincipal: "human:alice@example.com",
    });
    const result = engine.validateDelegation(token, ["travel.book"], "book_flight");
    expect(result).toHaveProperty("type", "scope_insufficient");
  });
});
```

Create `packages/typescript/server/tests/checkpoint.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { CheckpointPolicy } from "../src/checkpoint.js";
import { LocalFileSink } from "../src/sinks.js";
import { mkdtempSync, readdirSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

describe("CheckpointPolicy", () => {
  it("triggers on entry count", () => {
    const policy = new CheckpointPolicy({ entryCount: 5 });
    expect(policy.shouldCheckpoint(4)).toBe(false);
    expect(policy.shouldCheckpoint(5)).toBe(true);
  });

  it("never triggers without policy", () => {
    const policy = new CheckpointPolicy({});
    expect(policy.shouldCheckpoint(1000)).toBe(false);
  });
});

describe("LocalFileSink", () => {
  it("writes checkpoint file", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    sink.publish({
      body: { checkpoint_id: "ckpt-001", merkle_root: "sha256:abc" },
      signature: "header..sig",
    });
    const files = readdirSync(dir);
    expect(files).toHaveLength(1);
    expect(files[0]).toBe("ckpt-001.json");
  });
});
```

**Step 2: Extract all modules from TypeScript reference implementation**

Source files and their SDK targets:
- `examples/anip-ts/src/primitives/delegation.ts` → `server/src/delegation.ts` (wrap in `DelegationEngine` class with storage)
- `examples/anip-ts/src/primitives/permissions.ts` → `server/src/permissions.ts`
- `examples/anip-ts/src/primitives/manifest.ts` → `server/src/manifest.ts` (parameterize)
- `examples/anip-ts/src/data/database.ts` (audit portions) → `server/src/audit.ts`
- `examples/anip-ts/src/merkle.ts` → `server/src/merkle.ts` (copy as-is, self-contained)
- `examples/anip-ts/src/checkpoint.ts` → `server/src/checkpoint.ts`
- `examples/anip-ts/src/sinks.ts` → `server/src/sinks.ts`
- New: `server/src/storage.ts` (abstract interface + SQLite impl using better-sqlite3)

Key changes:
- `DelegationEngine` wraps delegation logic with instance-level storage + locks
- `buildManifest()` takes parameters instead of importing flight capabilities
- `AuditLog` class wraps audit operations with storage + Merkle tree
- Storage abstraction mirrors Python `StorageBackend`

**Step 3: Write facade index.ts**

```typescript
export { DelegationEngine } from "./delegation.js";
export { discoverPermissions } from "./permissions.js";
export { buildManifest } from "./manifest.js";
export { AuditLog } from "./audit.js";
export { MerkleTree } from "./merkle.js";
export { createCheckpoint, CheckpointPolicy, CheckpointScheduler } from "./checkpoint.js";
export { CheckpointSink, LocalFileSink } from "./sinks.js";
export { StorageBackend, SQLiteStorage } from "./storage.js";
```

**Step 4: Run tests**

```bash
cd packages/typescript && npx vitest run --project server
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add packages/typescript/server/
git commit -m "feat(@anip/server): extract TypeScript server package"
```

---

## Phase 5: Example Refactoring

### Task 13: Rename Python example package

**Files:**
- Modify: `examples/anip/pyproject.toml`
- Rename: `examples/anip/anip_server/` → `examples/anip/anip_flight_demo/`
- Update all internal imports

**Step 1: Update pyproject.toml**

Change name from `anip-demo` to `anip-flight-demo` and update entry points.
Add SDK packages as dependencies:
```toml
dependencies = [
    "anip-core>=0.3.0",
    "anip-crypto>=0.3.0",
    "anip-server>=0.3.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
]
```

**Step 2: Rename package directory**

```bash
cd examples/anip && mv anip_server anip_flight_demo
```

**Step 3: Update all imports**

Find and replace `anip_server` → `anip_flight_demo` in all files under `examples/anip/`.
Then replace SDK-extractable imports with package imports:

```python
# Before (in main.py):
from anip_server.primitives.models import ANIPManifest, DelegationToken
from anip_server.primitives.crypto import KeyManager
from anip_server.primitives.delegation import validate_delegation

# After:
from anip_core import ANIPManifest, DelegationToken
from anip_crypto import KeyManager
from anip_server import DelegationEngine, discover_permissions, build_manifest
```

**Step 4: Run existing tests**

```bash
cd examples/anip && pytest tests/ -v
```

Expected: All existing tests PASS with new imports.

**Step 5: Commit**

```bash
git add examples/anip/
git commit -m "refactor: rename Python example to anip-flight-demo and consume SDK packages"
```

---

### Task 14: Refactor TypeScript example to consume SDK packages

**Files:**
- Modify: `examples/anip-ts/package.json`
- Modify: `examples/anip-ts/src/server.ts`
- Modify: `examples/anip-ts/src/primitives/manifest.ts`
- Update all internal imports

**Step 1: Add SDK dependencies to package.json**

```json
{
  "dependencies": {
    "@anip/core": "0.3.0",
    "@anip/crypto": "0.3.0",
    "@anip/server": "0.3.0",
    "@hono/node-server": "^1.11.0",
    "hono": "^4.4.0"
  }
}
```

Remove `better-sqlite3`, `jose`, `zod` from direct dependencies (now transitive through SDK packages).

**Step 2: Update imports throughout**

Replace local primitive imports with SDK package imports:

```typescript
// Before:
import type { ANIPManifest, DelegationToken } from "../types.js";
import { KeyManager } from "../crypto.js";
import { validateDelegation } from "../primitives/delegation.js";

// After:
import type { ANIPManifest, DelegationToken } from "@anip/core";
import { KeyManager } from "@anip/crypto";
import { DelegationEngine, discoverPermissions, buildManifest } from "@anip/server";
```

**Step 3: Run existing tests**

```bash
cd examples/anip-ts && npx vitest run
```

Expected: All existing tests PASS.

**Step 4: Commit**

```bash
git add examples/anip-ts/
git commit -m "refactor: update TypeScript example to consume SDK packages"
```

---

### Task 15: Final verification and cleanup

**Step 1: Run all package tests**

```bash
cd packages/python/anip-core && pytest tests/ -v
cd packages/python/anip-crypto && pytest tests/ -v
cd packages/python/anip-server && pytest tests/ -v
cd packages/typescript && npx vitest run
```

**Step 2: Run all example tests**

```bash
cd examples/anip && pytest tests/ -v
cd examples/anip-ts && npx vitest run
```

**Step 3: Verify builds**

```bash
cd packages/typescript && npm run build --workspaces
cd packages/python/anip-core && pip install -e .
cd packages/python/anip-crypto && pip install -e .
cd packages/python/anip-server && pip install -e .
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: verify all SDK packages and examples pass"
```

**Step 5: Create PR**

```bash
git push -u origin feature/sdk-packages
gh pr create --title "feat: ANIP SDK packages extraction" --body "$(cat <<'EOF'
## Summary

- Extracts reusable SDK packages from the v0.3 reference implementations
- Three packages per language: core (types), crypto (signing/verification), server (delegation, audit, checkpoints)
- Python: anip-core, anip-crypto, anip-server (standalone PyPI packages)
- TypeScript: @anip/core, @anip/crypto, @anip/server (npm workspace)
- Examples refactored to consume SDK packages
- Fresh public-API-focused tests for all packages
- Existing example tests preserved as integration coverage

## Test plan

- [ ] All Python package tests pass
- [ ] All TypeScript package tests pass
- [ ] Python example tests pass with SDK imports
- [ ] TypeScript example tests pass with SDK imports
- [ ] Packages install cleanly via pip/npm

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
