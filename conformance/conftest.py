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
