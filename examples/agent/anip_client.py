"""Thin HTTP client for ANIP service endpoints."""

from __future__ import annotations

from typing import Any

import httpx


class ANIPClient:
    """Stateless client for an ANIP-compliant service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.get(path)
            resp.raise_for_status()
            return resp.json()

    def _post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post(path, json=json, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def discover(self) -> dict[str, Any]:
        """Fetch the ANIP discovery document."""
        return self._get("/.well-known/anip")

    def get_manifest(self) -> dict[str, Any]:
        """Fetch the full ANIP manifest."""
        return self._get("/anip/manifest")

    def request_token(
        self,
        subject: str,
        scope: list[str],
        capability: str,
        api_key: str,
        parent_token: str | None = None,
        purpose_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request a JWT delegation token from the service.

        Calls POST /anip/tokens with Bearer auth. Returns the response dict
        which includes ``{"issued": True, "token_id": ..., "token": jwt_str,
        "expires": ...}``.
        """
        body: dict[str, Any] = {
            "subject": subject,
            "scope": scope,
            "capability": capability,
        }
        if parent_token is not None:
            body["parent_token"] = parent_token
        if purpose_parameters is not None:
            body["purpose_parameters"] = purpose_parameters
        return self._post(
            "/anip/tokens",
            body,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def check_permissions(self, token_jwt: str) -> dict[str, Any]:
        """Query what the agent can do given its delegation token JWT."""
        return self._post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token_jwt}"},
        )

    def get_graph(self, capability: str) -> dict[str, Any]:
        """Get prerequisite and composition graph for a capability."""
        return self._get(f"/anip/graph/{capability}")

    def invoke(
        self,
        capability: str,
        token_jwt: str,
        parameters: dict[str, Any],
        client_reference_id: str | None = None,
    ) -> dict[str, Any]:
        """Invoke an ANIP capability."""
        body: dict[str, Any] = {"parameters": parameters}
        if client_reference_id is not None:
            body["client_reference_id"] = client_reference_id
        return self._post(
            f"/anip/invoke/{capability}",
            json=body,
            headers={"Authorization": f"Bearer {token_jwt}"},
        )

    def query_audit(
        self,
        token_jwt: str,
        capability: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
    ) -> dict[str, Any]:
        """Query the audit log."""
        query_params: dict[str, str] = {}
        if capability:
            query_params["capability"] = capability
        if invocation_id:
            query_params["invocation_id"] = invocation_id
        if client_reference_id:
            query_params["client_reference_id"] = client_reference_id
        return self._post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token_jwt}"},
            params=query_params or None,
        )
