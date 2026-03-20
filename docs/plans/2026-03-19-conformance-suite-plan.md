# ANIP Conformance Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone, HTTP-based pytest conformance suite that validates ANIP protocol compliance against any service by URL.

**Architecture:** Flat Python test suite under `conformance/` at the project root. Uses httpx for async HTTP, pytest-asyncio for async test support. Tests are pure wire-level protocol checks — no SDK imports. A thin `conftest.py` provides the `--base-url` option, an httpx client, and a token-issuing helper.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, httpx, PyJWT, cryptography

---

### Task 1: Project Scaffolding

**Files:**
- Create: `conformance/pyproject.toml`
- Create: `conformance/conftest.py`

**Step 1: Create pyproject.toml**

```python
# conformance/pyproject.toml
```

```toml
[project]
name = "anip-conformance"
version = "0.1.0"
description = "ANIP protocol conformance test suite"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "PyJWT[crypto]>=2.8",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.4",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["."]
```

**Step 2: Create conftest.py**

```python
"""Shared fixtures for ANIP conformance tests.

Provides:
- --base-url CLI option
- base_url, client, discovery fixtures
- issue_token() helper for getting JWTs
"""
from __future__ import annotations

import pytest
import httpx


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        required=True,
        help="Base URL of the ANIP service to test (e.g. http://localhost:8090)",
    )
    parser.addoption(
        "--bootstrap-bearer",
        required=True,
        help="Bearer credential for bootstrap token issuance (API key, OIDC token, etc.)",
    )
    parser.addoption(
        "--sample-inputs",
        default=None,
        help="Path to JSON file mapping capability names to sample parameters",
    )


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def bootstrap_bearer(request):
    return request.config.getoption("--bootstrap-bearer")


@pytest.fixture(scope="session")
def sample_inputs(request):
    """Load sample capability inputs from JSON file, or return empty dict."""
    path = request.config.getoption("--sample-inputs")
    if path is None:
        return {}
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text())


@pytest.fixture(scope="session")
def client(base_url):
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
def discovery(client):
    resp = client.get("/.well-known/anip")
    assert resp.status_code == 200, f"Discovery failed: {resp.status_code}"
    return resp.json()["anip_discovery"]


def _first_capability_with_scope(discovery: dict, scope_prefix: str) -> tuple[str, list[str]]:
    """Find the first capability whose minimum_scope starts with the given prefix."""
    for name, meta in discovery["capabilities"].items():
        min_scope = meta.get("minimum_scope", [])
        if any(s.startswith(scope_prefix) for s in min_scope):
            return name, min_scope
    raise LookupError(f"No capability with scope prefix '{scope_prefix}'")


@pytest.fixture(scope="session")
def read_capability(discovery):
    """Return (name, scope) for a read-only capability."""
    for name, meta in discovery["capabilities"].items():
        se = meta.get("side_effect", {})
        se_type = se.get("type") if isinstance(se, dict) else se
        if se_type == "read":
            return name, meta.get("minimum_scope", [])
    raise LookupError("No read capability found on this service")


@pytest.fixture(scope="session")
def write_capability(discovery):
    """Return (name, scope) for an irreversible/financial capability."""
    for name, meta in discovery["capabilities"].items():
        se = meta.get("side_effect", {})
        se_type = se.get("type") if isinstance(se, dict) else se
        if se_type in ("irreversible", "write", "transactional"):
            return name, meta.get("minimum_scope", [])
    raise LookupError("No write/irreversible capability found on this service")


@pytest.fixture(scope="session")
def all_scopes(discovery):
    """Collect all unique scopes across all capabilities."""
    scopes = set()
    for meta in discovery["capabilities"].values():
        for s in meta.get("minimum_scope", []):
            scopes.add(s)
    return list(scopes)


def issue_token(
    client: httpx.Client,
    scope: list[str],
    capability: str,
    bootstrap_bearer: str,
) -> str:
    """Issue a delegation token via API key. Returns the JWT string."""
    resp = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        json={
            "scope": scope,
            "capability": capability,
            "purpose_parameters": {"task_id": "conformance-test"},
        },
    )
    assert resp.status_code == 200, f"Token issuance failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["issued"] is True, f"Token not issued: {data}"
    return data["token"]
```

**Step 3: Verify scaffolding**

Run: `cd conformance && pip install -e . && cd ..`
Expected: Install succeeds

**Step 4: Commit**

```bash
git add conformance/pyproject.toml conformance/conftest.py
git commit -m "feat(conformance): scaffold project with fixtures and helpers"
```

---

### Task 2: Discovery Tests

**Files:**
- Create: `conformance/test_discovery.py`

**Step 1: Write the tests**

```python
"""Conformance tests for ANIP discovery, manifest, and JWKS.

Spec references: §6.1 (discovery), §6.2 (manifest signing), Conformance Category 1.
"""
import re


class TestDiscovery:
    def test_discovery_returns_200(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200

    def test_discovery_required_fields(self, discovery):
        required = ["protocol", "compliance", "base_url", "profile", "auth",
                     "capabilities", "endpoints", "trust_level"]
        for field in required:
            assert field in discovery, f"Missing required field: {field}"

    def test_compliance_value(self, discovery):
        assert discovery["compliance"] in ("anip-compliant", "anip-complete")

    def test_endpoints_required_keys(self, discovery):
        required_endpoints = ["manifest", "invoke", "tokens", "permissions"]
        for ep in required_endpoints:
            assert ep in discovery["endpoints"], f"Missing endpoint: {ep}"

    def test_endpoint_urls_consistent_with_base_url(self, discovery):
        base = discovery["base_url"].rstrip("/")
        for name, url in discovery["endpoints"].items():
            if url.startswith("/"):
                continue  # relative URLs are fine
            assert url.startswith(base), (
                f"Endpoint '{name}' URL '{url}' not consistent with base_url '{base}'"
            )

    def test_capabilities_non_empty(self, discovery):
        assert len(discovery["capabilities"]) > 0

    def test_protocol_version_format(self, discovery):
        assert re.match(r"^anip/\d+\.\d+", discovery["protocol"])


class TestManifest:
    def test_manifest_returns_200(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200

    def test_manifest_has_signature(self, client):
        resp = client.get("/anip/manifest")
        assert "x-anip-signature" in resp.headers, "Manifest missing X-ANIP-Signature header"

    def test_manifest_contains_capabilities(self, client, discovery):
        resp = client.get("/anip/manifest")
        data = resp.json()
        # Manifest should declare the same capabilities as discovery
        assert "capabilities" in data


class TestJWKS:
    def test_jwks_returns_200(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200

    def test_jwks_has_keys(self, client):
        resp = client.get("/.well-known/jwks.json")
        data = resp.json()
        assert "keys" in data
        assert len(data["keys"]) > 0

    def test_jwks_keys_are_ec(self, client):
        resp = client.get("/.well-known/jwks.json")
        for key in resp.json()["keys"]:
            assert key.get("kty") == "EC", f"Expected EC key, got {key.get('kty')}"
            assert key.get("crv") == "P-256", f"Expected P-256 curve, got {key.get('crv')}"
```

**Step 2: Run tests to verify they pass**

Run: `cd conformance && pytest test_discovery.py -v --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key`
Expected: All pass (run against the Python example app)

**Step 3: Commit**

```bash
git add conformance/test_discovery.py
git commit -m "feat(conformance): add discovery, manifest, and JWKS tests"
```

---

### Task 3: Token Tests

**Files:**
- Create: `conformance/test_tokens.py`

**Step 1: Write the tests**

```python
"""Conformance tests for ANIP token issuance and delegation.

Spec references: §4.3 (delegation chain), Conformance Category 4.
"""
from datetime import datetime, timezone

import jwt as pyjwt


class TestTokenIssuance:
    def test_issue_token_success(self, client, bootstrap_bearer, read_capability):
        cap_name, cap_scope = read_capability
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={
                "scope": cap_scope,
                "capability": cap_name,
                "purpose_parameters": {"task_id": "conformance"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["issued"] is True
        assert "token" in data
        assert "token_id" in data
        assert "expires" in data

    def test_token_expires_in_future(self, client, bootstrap_bearer, read_capability):
        cap_name, cap_scope = read_capability
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={
                "scope": cap_scope,
                "capability": cap_name,
                "purpose_parameters": {"task_id": "conformance"},
            },
        )
        data = resp.json()
        expires = datetime.fromisoformat(data["expires"].replace("Z", "+00:00"))
        assert expires > datetime.now(timezone.utc)

    def test_token_verifiable_against_jwks(self, client, bootstrap_bearer, read_capability):
        cap_name, cap_scope = read_capability
        # Get JWKS
        jwks_resp = client.get("/.well-known/jwks.json")
        jwks_data = jwks_resp.json()

        # Issue token
        token_resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={
                "scope": cap_scope,
                "capability": cap_name,
                "purpose_parameters": {"task_id": "conformance"},
            },
        )
        token_str = token_resp.json()["token"]

        # Verify — resolve the matching key by kid from the JWT header
        from jwt import PyJWKSet, get_unverified_header
        header = get_unverified_header(token_str)
        keyset = PyJWKSet.from_dict(jwks_data)
        kid = header.get("kid")
        signing_key = None
        for jwk in keyset.keys:
            if jwk.key_id == kid:
                signing_key = jwk.key
                break
        if signing_key is None:
            # Fall back to first key if no kid match (single-key services)
            signing_key = keyset.keys[0].key
        # Should not raise
        decoded = pyjwt.decode(
            token_str,
            signing_key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
        assert decoded is not None


class TestTokenDenial:
    def test_unauthenticated_returns_401(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["anything"]},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert "resolution" in data["failure"]
        assert "retry" in data["failure"]

    def test_unauthenticated_failure_has_required_fields(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["anything"]},
        )
        failure = resp.json()["failure"]
        assert "type" in failure
        assert "detail" in failure
        assert "resolution" in failure
        assert "retry" in failure
        assert isinstance(failure["retry"], bool)
```

**Step 2: Run tests**

Run: `cd conformance && pytest test_tokens.py -v --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key`
Expected: All pass

**Step 3: Commit**

```bash
git add conformance/test_tokens.py
git commit -m "feat(conformance): add token issuance and denial tests"
```

---

### Task 4: Invocation Tests

**Files:**
- Create: `conformance/test_invoke.py`

**Step 1: Write the tests**

```python
"""Conformance tests for ANIP capability invocation.

Spec references: §4.1-4.5 (invocation, failure semantics),
Conformance Categories 3 and 5.
"""
import re

import pytest
from conftest import issue_token


class TestInvocationSuccess:
    def test_invoke_with_sample_inputs(self, client, bootstrap_bearer, discovery, read_capability, all_scopes, sample_inputs):
        """Test successful invocation using sample inputs if provided."""
        cap_name, _ = read_capability
        params = sample_inputs.get(cap_name)
        if params is None:
            pytest.skip(f"No sample inputs for '{cap_name}' — provide via --sample-inputs")
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "invocation_id" in data
        assert re.match(r"^inv-[0-9a-f]{12}$", data["invocation_id"])

    def test_invocation_id_format(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        # invocation_id must be present even on failure (spec §6.3)
        assert "invocation_id" in data
        assert re.match(r"^inv-[0-9a-f]{12}$", data["invocation_id"])

    def test_client_reference_id_echoed(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        ref_id = "conformance-test-ref-001"
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "parameters": {},
                "client_reference_id": ref_id,
            },
        )
        data = resp.json()
        assert data.get("client_reference_id") == ref_id


class TestInvocationFailures:
    def test_unknown_capability_returns_404(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/invoke/nonexistent_capability_xyz",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "unknown_capability"

    def test_missing_auth_returns_401(self, client, read_capability):
        cap_name, _ = read_capability
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            json={"parameters": {}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"

    def test_invalid_token_returns_401(self, client, read_capability):
        cap_name, _ = read_capability
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
            json={"parameters": {}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

    def test_missing_auth_vs_invalid_token_distinct(self, client, read_capability):
        """Missing auth and invalid token must produce different failure.type values."""
        cap_name, _ = read_capability

        # Missing auth
        resp_missing = client.post(
            f"/anip/invoke/{cap_name}",
            json={"parameters": {}},
        )
        # Invalid token
        resp_invalid = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
            json={"parameters": {}},
        )
        type_missing = resp_missing.json()["failure"]["type"]
        type_invalid = resp_invalid.json()["failure"]["type"]
        assert type_missing != type_invalid, (
            f"Missing auth and invalid token should have different failure types, "
            f"both returned '{type_missing}'"
        )

    def test_failure_has_required_fields(self, client, read_capability):
        """Every failure response must include type, detail, resolution, retry."""
        cap_name, _ = read_capability
        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
            json={"parameters": {}},
        )
        failure = resp.json()["failure"]
        assert "type" in failure
        assert "detail" in failure
        assert "resolution" in failure
        assert "retry" in failure
        assert isinstance(failure["retry"], bool)

    def test_scope_mismatch(self, client, bootstrap_bearer, write_capability, read_capability):
        """Token scoped for read should be denied for write capability."""
        write_name, _ = write_capability
        read_name, read_scope = read_capability
        # Issue token with only read scope
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            f"/anip/invoke/{write_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )
        data = resp.json()
        assert data["success"] is False


class TestCostSignaling:
    def test_financial_capability_includes_cost_actual(self, client, bootstrap_bearer, discovery, all_scopes, sample_inputs):
        """If a capability declares financial=true and sample inputs are provided,
        successful invoke should include cost_actual."""
        for name, meta in discovery["capabilities"].items():
            if meta.get("financial") is True:
                params = sample_inputs.get(name)
                if params is None:
                    pytest.skip(f"No sample inputs for financial capability '{name}' — provide via --sample-inputs")
                token = issue_token(client, all_scopes, name, bootstrap_bearer)
                resp = client.post(
                    f"/anip/invoke/{name}",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"parameters": params},
                )
                assert resp.status_code == 200, (
                    f"Financial capability '{name}' invocation failed: {resp.status_code}"
                )
                data = resp.json()
                assert data["success"] is True
                assert "cost_actual" in data, (
                    f"Financial capability '{name}' should include cost_actual"
                )
                break  # only need to test one
```

**Step 2: Run tests**

Run: `cd conformance && pytest test_invoke.py -v --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key --sample-inputs=samples/flight-service.json`
Expected: All pass

**Step 3: Commit**

```bash
git add conformance/test_invoke.py
git commit -m "feat(conformance): add invocation, failure semantics, and cost tests"
```

---

### Task 5: Permissions Tests

**Files:**
- Create: `conformance/test_permissions.py`

**Step 1: Write the tests**

```python
"""Conformance tests for ANIP permission discovery.

Spec references: §4.4 (permission discovery), Conformance Category 4.
"""
from conftest import issue_token


class TestPermissions:
    def test_permissions_response_shape(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "restricted" in data
        assert "denied" in data
        assert isinstance(data["available"], list)
        assert isinstance(data["restricted"], list)
        assert isinstance(data["denied"], list)

    def test_full_scope_shows_available(self, client, bootstrap_bearer, discovery, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        available_names = [c["capability"] for c in data["available"]]
        # At least one capability should be available with full scope
        assert len(available_names) > 0

    def test_narrow_scope_restricts_capabilities(self, client, bootstrap_bearer, discovery, read_capability, write_capability):
        read_name, read_scope = read_capability
        write_name, write_scope = write_capability
        # Issue token with only read scope
        token = issue_token(client, read_scope, read_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        restricted_names = [c["capability"] for c in data["restricted"]]
        # The write capability should be restricted when we only have read scope
        assert write_name in restricted_names, (
            f"Expected '{write_name}' in restricted with scope {read_scope}, "
            f"got restricted: {restricted_names}"
        )

    def test_available_entry_has_capability_field(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        for entry in resp.json()["available"]:
            assert "capability" in entry

    def test_restricted_entry_has_reason(self, client, bootstrap_bearer, read_capability):
        cap_name, read_scope = read_capability
        token = issue_token(client, read_scope, cap_name, bootstrap_bearer)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        for entry in resp.json()["restricted"]:
            assert "capability" in entry
            assert "reason" in entry

    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/anip/permissions")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert "failure" in data
```

**Step 2: Run tests**

Run: `cd conformance && pytest test_permissions.py -v --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key`
Expected: All pass

**Step 3: Commit**

```bash
git add conformance/test_permissions.py
git commit -m "feat(conformance): add permission discovery tests"
```

---

### Task 6: Audit Tests

**Files:**
- Create: `conformance/test_audit.py`

**Step 1: Write the tests**

```python
"""Conformance tests for ANIP audit log queries.

Spec references: §5.4 (observability), Conformance Category 6.
"""
from conftest import issue_token


class TestAudit:
    def test_audit_response_shape(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Make an invocation so there's at least one audit entry
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_audit_entry_required_fields(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Ensure at least one entry
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["count"] >= 1
        entry = data["entries"][0]
        assert "invocation_id" in entry
        assert "capability" in entry
        assert "timestamp" in entry
        assert "success" in entry

    def test_audit_filter_by_capability(self, client, bootstrap_bearer, read_capability, all_scopes):
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        # Make an invocation
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {}},
        )

        resp = client.post(
            f"/anip/audit?capability={cap_name}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("capability_filter") == cap_name
        # All returned entries should match the filter
        for entry in data["entries"]:
            assert entry["capability"] == cap_name

    def test_audit_filter_combination(self, client, bootstrap_bearer, read_capability, all_scopes):
        """Combined filters (capability + since) should work together."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)

        resp = client.post(
            f"/anip/audit?capability={cap_name}&since=2020-01-01T00:00:00Z",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "entries" in data

    def test_audit_unauthenticated_returns_401(self, client):
        resp = client.post("/anip/audit")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert "failure" in data
```

**Step 2: Run tests**

Run: `cd conformance && pytest test_audit.py -v --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key`
Expected: All pass

**Step 3: Commit**

```bash
git add conformance/test_audit.py
git commit -m "feat(conformance): add audit log query tests"
```

---

### Task 7: Checkpoint Tests

**Files:**
- Create: `conformance/test_checkpoints.py`

**Step 1: Write the tests**

```python
"""Conformance tests for ANIP checkpoint and proof behavior.

Spec references: §6.5 (checkpoints).

Checkpoint endpoints are only required for services with trust_level
'anchored' or 'attested'. Tests are skipped if the service does not
advertise checkpoint support in its discovery document.
"""
import pytest


def _has_checkpoints(discovery: dict) -> bool:
    """Check if the service advertises checkpoint support."""
    return "checkpoints" in discovery.get("endpoints", {})


class TestCheckpoints:
    def test_list_checkpoints_returns_200(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200

    def test_list_checkpoints_shape(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        data = resp.json()
        assert "checkpoints" in data
        assert isinstance(data["checkpoints"], list)

    def test_checkpoint_entry_fields(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        data = resp.json()
        if len(data["checkpoints"]) > 0:
            cp = data["checkpoints"][0]
            assert "checkpoint_id" in cp
            assert "merkle_root" in cp
            assert "timestamp" in cp

    def test_checkpoint_not_found(self, client, discovery):
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints/nonexistent_cp_id_xyz")
        assert resp.status_code == 404

    def test_checkpoint_proof_request(self, client, discovery):
        """If checkpoints exist, test proof request behavior."""
        if not _has_checkpoints(discovery):
            pytest.skip("Service does not advertise checkpoint endpoint")
        resp = client.get("/anip/checkpoints")
        data = resp.json()
        if len(data["checkpoints"]) == 0:
            pytest.skip("No checkpoints available to test proof behavior")

        cp_id = data["checkpoints"][0]["checkpoint_id"]
        resp = client.get(f"/anip/checkpoints/{cp_id}?include_proof=true&leaf_index=0")
        assert resp.status_code == 200
        detail = resp.json()
        # Should have either inclusion_proof or proof_unavailable
        has_proof = "inclusion_proof" in detail
        has_unavailable = "proof_unavailable" in detail
        assert has_proof or has_unavailable, (
            "Checkpoint detail with include_proof=true should have "
            "'inclusion_proof' or 'proof_unavailable'"
        )
```

**Step 2: Run tests**

Run: `cd conformance && pytest test_checkpoints.py -v --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key`
Expected: All pass

**Step 3: Commit**

```bash
git add conformance/test_checkpoints.py
git commit -m "feat(conformance): add checkpoint and proof tests"
```

---

### Task 8: Run Full Suite Against Both Implementations

A sample inputs file for the example apps should be created at `conformance/samples/flight-service.json`:

```json
{
  "search_flights": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
  "book_flight": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1}
}
```

**Step 1: Start Python example app and run suite**

```bash
cd examples/anip && python3 -m uvicorn app:app --port 8090 &
sleep 2
cd conformance && pytest --base-url=http://localhost:8090 --bootstrap-bearer=demo-human-key --sample-inputs=samples/flight-service.json -v
kill %1
```

Expected: All tests pass

**Step 2: Start TypeScript example app and run suite**

```bash
cd examples/anip-ts && npm start &
sleep 2
cd conformance && pytest --base-url=http://localhost:4100 --bootstrap-bearer=demo-human-key --sample-inputs=samples/flight-service.json -v
kill %1
```

Expected: All tests pass

**Step 3: Fix any failures**

If any test fails against one implementation but passes against the other, the failure is likely:
- A missing protocol feature in one implementation
- A conformance test that accidentally relies on implementation-specific behavior

Fix the conformance test or the implementation as appropriate.

**Step 4: Commit any fixes**

```bash
git add -A conformance/
git commit -m "fix(conformance): adjust tests for cross-implementation compatibility"
```

---

### Task 9: CI Integration

**Files:**
- Create: `.github/workflows/ci-conformance.yml`

**Step 1: Create the workflow**

```yaml
name: Conformance Suite

on:
  push:
    branches: [main]
    paths:
      - "conformance/**"
      - "packages/**"
      - "examples/**"
      - ".github/workflows/ci-conformance.yml"
  pull_request:
    paths:
      - "conformance/**"
      - "packages/**"
      - "examples/**"
      - ".github/workflows/ci-conformance.yml"

jobs:
  conformance:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        target:
          - name: python
            setup: |
              pip install -e "packages/python/anip-core[dev]"
              pip install -e "packages/python/anip-crypto[dev]"
              pip install -e "packages/python/anip-server[dev]"
              pip install -e "packages/python/anip-service[dev]"
              pip install -e "packages/python/anip-fastapi[dev]"
              pip install -e "examples/anip"
            start: "cd examples/anip && python -m uvicorn app:app --port 8090 &"
            url: "http://localhost:8090"
          - name: typescript
            setup: |
              cd packages/typescript && npm ci && npm run build
              cd ../../examples/anip-ts && npm ci && npm run build
            start: "cd examples/anip-ts && node dist/index.js &"
            url: "http://localhost:4100"

    name: "conformance (${{ matrix.target.name }})"
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - uses: actions/setup-node@v4
        if: matrix.target.name == 'typescript'
        with:
          node-version: "22"

      - name: Install target service
        run: ${{ matrix.target.setup }}

      - name: Install conformance suite
        run: pip install -e "./conformance"

      - name: Start service
        run: |
          ${{ matrix.target.start }}
          sleep 3

      - name: Run conformance suite
        run: >
          pytest conformance/
          --base-url=${{ matrix.target.url }}
          --bootstrap-bearer=demo-human-key
          --sample-inputs=conformance/samples/flight-service.json
          -v
```

**Step 2: Commit**

```bash
git add .github/workflows/ci-conformance.yml
git commit -m "ci: add conformance suite workflow for Python and TypeScript"
```
