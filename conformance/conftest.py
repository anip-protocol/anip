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
    """Load sample capability inputs from JSON file, or return empty dict.

    Any ``issued_at`` fields inside parameter objects are refreshed to the
    current epoch time so that binding freshness checks (max_age) pass.
    """
    path = request.config.getoption("--sample-inputs")
    if path is None:
        return {}
    import json
    import time
    from pathlib import Path

    data = json.loads(Path(path).read_text())

    # Refresh issued_at timestamps so bindings are not stale
    now = int(time.time())
    for _cap, params in data.items():
        if isinstance(params, dict):
            for _key, val in params.items():
                if isinstance(val, dict) and "issued_at" in val:
                    val["issued_at"] = now

    return data


@pytest.fixture(scope="session")
def client(base_url):
    with httpx.Client(base_url=base_url, timeout=30) as c:
        yield c


@pytest.fixture(scope="session")
def discovery(client):
    resp = client.get("/.well-known/anip")
    assert resp.status_code == 200, f"Discovery failed: {resp.status_code}"
    return resp.json()["anip_discovery"]



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
    *,
    task_id: str | None = "conformance-test",
    budget: dict | None = None,
) -> str:
    """Issue a delegation token via API key. Returns the JWT string.

    Args:
        task_id: If provided, binds the token to this task_id via
            purpose_parameters. Pass None to issue a token without
            task binding (needed for tests that set task_id per invocation).
        budget: If provided, attaches budget constraints to the token.
            Expected shape: {"currency": "USD", "max_amount": 100}.
    """
    purpose_parameters: dict = {}
    if task_id is not None:
        purpose_parameters["task_id"] = task_id

    body: dict = {
        "scope": scope,
        "capability": capability,
        "purpose_parameters": purpose_parameters,
    }
    if budget is not None:
        body["budget"] = budget

    resp = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        json=body,
    )
    assert resp.status_code == 200, f"Token issuance failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["issued"] is True, f"Token not issued: {data}"
    return data["token"]


def issue_token_full(
    client: httpx.Client,
    scope: list[str],
    capability: str,
    bootstrap_bearer: str,
    *,
    task_id: str | None = "conformance-test",
    budget: dict | None = None,
    parent_token: str | None = None,
) -> tuple[int, dict]:
    """Issue a delegation token and return the full response dict.

    Unlike issue_token() which returns just the JWT string, this returns the
    entire response including token_id, token, expires, and budget fields.
    Useful for delegation and budget echo tests.

    Args:
        parent_token: Token ID of the parent token for delegation (child issuance).
        budget: Budget constraints for the token.
    """
    purpose_parameters: dict = {}
    if task_id is not None:
        purpose_parameters["task_id"] = task_id

    body: dict = {
        "scope": scope,
        "capability": capability,
        "purpose_parameters": purpose_parameters,
    }
    if budget is not None:
        body["budget"] = budget
    if parent_token is not None:
        body["parent_token"] = parent_token

    resp = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        json=body,
    )
    return resp.status_code, resp.json()


# --- Manifest fixture (v0.14: full capability details) ---
# The discovery document (/.well-known/anip) only includes a summary per
# capability (description, side_effect, minimum_scope, financial, contract).
# Budget, binding, and control requirement tests need the full capability
# declarations from the manifest (/anip/manifest).


@pytest.fixture(scope="session")
def manifest_capabilities(client):
    """Return full capability declarations from the manifest endpoint.

    The manifest contains cost, requires_binding, control_requirements, etc.
    which are not present in the discovery summary.
    """
    resp = client.get("/anip/manifest")
    assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
    data = resp.json()
    return data.get("capabilities", {})


# --- Capability lookup fixtures (v0.14: budget, binding, control) ---


@pytest.fixture(scope="session")
def fixed_cost_capability(manifest_capabilities):
    """Return (name, scope, financial) for a capability with fixed financial cost.

    Only matches capabilities where cost.certainty == "fixed" AND
    cost.financial.amount is a positive number (not None or zero).
    """
    for name, meta in manifest_capabilities.items():
        cost = meta.get("cost")
        if not cost or cost.get("certainty") != "fixed":
            continue
        financial = cost.get("financial")
        if not financial:
            continue
        amount = financial.get("amount")
        if amount is not None and amount > 0:
            return name, meta.get("minimum_scope", []), financial
    return None


@pytest.fixture(scope="session")
def binding_capability(manifest_capabilities):
    """Return (name, scope, requires_binding) for a capability with binding requirements."""
    for name, meta in manifest_capabilities.items():
        bindings = meta.get("requires_binding", [])
        if bindings:
            return name, meta.get("minimum_scope", []), bindings
    return None


@pytest.fixture(scope="session")
def control_requirement_capability(manifest_capabilities):
    """Return (name, scope, control_requirements) for a capability with control requirements."""
    for name, meta in manifest_capabilities.items():
        controls = meta.get("control_requirements", [])
        if controls:
            return name, meta.get("minimum_scope", []), controls
    return None


@pytest.fixture(scope="session")
def cost_ceiling_capability(manifest_capabilities):
    """Return (name, scope) for a capability that requires cost_ceiling control requirement."""
    for name, meta in manifest_capabilities.items():
        controls = meta.get("control_requirements", [])
        for ctrl in controls:
            if ctrl.get("type") == "cost_ceiling":
                return name, meta.get("minimum_scope", [])
    return None
