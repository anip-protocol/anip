"""Thin HTTP client for ANIP service endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


class ANIPClient:
    """Stateless client for an ANIP-compliant service."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.get(path)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post(path, json=json)
            resp.raise_for_status()
            return resp.json()

    def discover(self) -> dict[str, Any]:
        """Fetch the ANIP discovery document."""
        return self._get("/.well-known/anip")

    def get_manifest(self) -> dict[str, Any]:
        """Fetch the full ANIP manifest."""
        return self._get("/anip/manifest")

    def register_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Register a delegation token with the service."""
        return self._post("/anip/tokens", token)

    def check_permissions(self, token: dict[str, Any]) -> dict[str, Any]:
        """Query what the agent can do given its delegation token."""
        return self._post("/anip/permissions", token)

    def get_graph(self, capability: str) -> dict[str, Any]:
        """Get prerequisite and composition graph for a capability."""
        return self._get(f"/anip/graph/{capability}")

    def invoke(
        self, capability: str, token: dict[str, Any], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke an ANIP capability."""
        return self._post(
            f"/anip/invoke/{capability}",
            {"delegation_token": token, "parameters": parameters},
        )

    def query_audit(
        self, token: dict[str, Any], capability: str | None = None
    ) -> dict[str, Any]:
        """Query the audit log."""
        params = ""
        if capability:
            params = f"?capability={capability}"
        return self._post(f"/anip/audit{params}", token)


def make_token(
    issuer: str,
    subject: str,
    scope: list[str],
    capability: str,
    parent: str | None = None,
    max_delegation_depth: int = 2,
    concurrent_branches: str = "allowed",
    ttl_hours: int = 2,
) -> dict[str, Any]:
    """Build a delegation token dict with a unique runtime ID."""
    token_id = f"demo-{uuid.uuid4().hex[:8]}"
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    return {
        "token_id": token_id,
        "issuer": issuer,
        "subject": subject,
        "scope": scope,
        "purpose": {"capability": capability, "parameters": {}, "task_id": f"task-{token_id}"},
        "parent": parent,
        "expires": expires,
        "constraints": {
            "max_delegation_depth": max_delegation_depth,
            "concurrent_branches": concurrent_branches,
        },
    }
