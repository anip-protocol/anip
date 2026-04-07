"""Thin HTTP client for ANIP service endpoints."""

from __future__ import annotations

import json
from typing import Any

import httpx


class ANIPClient:
    """Stateless client for an ANIP-compliant service."""

    def __init__(self, base_url: str = "http://127.0.0.1:9100", timeout: float = 10):
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

    def request_capability_token(
        self,
        principal: str,
        capability: str,
        scope: list[str],
        api_key: str,
        purpose_parameters: dict[str, Any] | None = None,
        ttl_hours: int = 2,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request a root token pre-bound to a specific capability.

        This mirrors the v0.20 runtime helper semantics at the protocol-client
        edge: scope stays explicit, and delegation fields are intentionally
        absent from this convenience path.
        """
        body: dict[str, Any] = {
            "subject": principal,
            "scope": scope,
            "capability": capability,
            "ttl_hours": ttl_hours,
        }
        if purpose_parameters is not None:
            body["purpose_parameters"] = purpose_parameters
        if budget is not None:
            body["budget"] = budget
        return self._post(
            "/anip/tokens",
            body,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def request_delegated_capability_token(
        self,
        principal: str,
        parent_token: str,
        capability: str,
        scope: list[str],
        subject: str,
        auth_bearer: str,
        caller_class: str | None = None,
        purpose_parameters: dict[str, Any] | None = None,
        ttl_hours: int = 2,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request a delegated token pre-bound to a specific capability.

        This mirrors the v0.22 delegated runtime helper semantics at the
        protocol-client edge: ``parent_token`` is a token ID string, scope
        remains explicit, and the delegated subject is explicit too.
        """
        body: dict[str, Any] = {
            "subject": subject,
            "scope": scope,
            "capability": capability,
            "parent_token": parent_token,
            "ttl_hours": ttl_hours,
        }
        if caller_class is not None:
            body["caller_class"] = caller_class
        if purpose_parameters is not None:
            body["purpose_parameters"] = purpose_parameters
        if budget is not None:
            body["budget"] = budget
        return self._post(
            "/anip/tokens",
            body,
            headers={"Authorization": f"Bearer {auth_bearer}"},
        )

    def check_permissions(self, token_jwt: str) -> dict[str, Any]:
        """Query what the agent can do given its delegation token JWT."""
        return self._post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token_jwt}"},
        )

    @staticmethod
    def match_permission(permissions: dict[str, Any], capability: str) -> dict[str, Any]:
        """Return the available/restricted/denied entry for a capability."""
        for bucket in ("available", "restricted", "denied"):
            for item in permissions.get(bucket, []):
                if item.get("capability") == capability:
                    return {"status": bucket, **item}
        return {"status": "unknown", "capability": capability}

    def get_graph(self, capability: str) -> dict[str, Any]:
        """Get prerequisite and composition graph for a capability."""
        return self._get(f"/anip/graph/{capability}")

    def invoke(
        self,
        capability: str,
        token_jwt: str,
        parameters: dict[str, Any],
        client_reference_id: str | None = None,
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
        upstream_service: str | None = None,
    ) -> dict[str, Any]:
        """Invoke an ANIP capability."""
        body: dict[str, Any] = {"parameters": parameters}
        if client_reference_id is not None:
            body["client_reference_id"] = client_reference_id
        if task_id is not None:
            body["task_id"] = task_id
        if parent_invocation_id is not None:
            body["parent_invocation_id"] = parent_invocation_id
        if upstream_service is not None:
            body["upstream_service"] = upstream_service
        return self._post(
            f"/anip/invoke/{capability}",
            json=body,
            headers={"Authorization": f"Bearer {token_jwt}"},
        )

    def invoke_stream(
        self,
        capability: str,
        token_jwt: str,
        parameters: dict[str, Any],
        client_reference_id: str | None = None,
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
        upstream_service: str | None = None,
    ) -> list[dict[str, Any]]:
        """Invoke an ANIP capability in streaming mode and parse SSE events."""
        body: dict[str, Any] = {"parameters": parameters, "stream": True}
        if client_reference_id is not None:
            body["client_reference_id"] = client_reference_id
        if task_id is not None:
            body["task_id"] = task_id
        if parent_invocation_id is not None:
            body["parent_invocation_id"] = parent_invocation_id
        if upstream_service is not None:
            body["upstream_service"] = upstream_service

        events: list[dict[str, Any]] = []
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"/anip/invoke/{capability}",
                json=body,
                headers={"Authorization": f"Bearer {token_jwt}"},
            ) as resp:
                resp.raise_for_status()
                current_event: str | None = None
                current_data: list[str] = []
                for line in resp.iter_lines():
                    if line == "":
                        if current_event is not None:
                            payload = "\n".join(current_data) if current_data else "{}"
                            events.append({"event": current_event, "data": json.loads(payload)})
                        current_event = None
                        current_data = []
                        continue
                    if line.startswith("event: "):
                        current_event = line[len("event: "):]
                    elif line.startswith("data: "):
                        current_data.append(line[len("data: "):])
        return events

    def query_audit(
        self,
        token_jwt: str,
        capability: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
        event_class: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Query the audit log."""
        query_params: dict[str, str] = {}
        if capability:
            query_params["capability"] = capability
        if invocation_id:
            query_params["invocation_id"] = invocation_id
        if client_reference_id:
            query_params["client_reference_id"] = client_reference_id
        if task_id:
            query_params["task_id"] = task_id
        if parent_invocation_id:
            query_params["parent_invocation_id"] = parent_invocation_id
        if event_class:
            query_params["event_class"] = event_class
        if limit is not None:
            query_params["limit"] = str(limit)
        return self._post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token_jwt}"},
            params=query_params or None,
        )

    def list_checkpoints(self, limit: int = 10) -> dict[str, Any]:
        """List recent anchored checkpoints for the service."""
        return self._get(f"/anip/checkpoints?limit={int(limit)}")

    def get_checkpoint(
        self,
        checkpoint_id: str,
        *,
        include_proof: bool = False,
        leaf_index: int | None = None,
        consistency_from: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a checkpoint and optional inclusion/consistency proof data."""
        params: list[str] = []
        if include_proof:
            params.append("include_proof=true")
        if leaf_index is not None:
            params.append(f"leaf_index={int(leaf_index)}")
        if consistency_from is not None:
            params.append(f"consistency_from={consistency_from}")
        query = f"?{'&'.join(params)}" if params else ""
        return self._get(f"/anip/checkpoints/{checkpoint_id}{query}")
