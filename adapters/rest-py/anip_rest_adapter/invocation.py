"""ANIP capability invocation from REST requests.

Handles delegation token construction and ANIP invocation,
returning raw dicts for FastAPI JSON serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .discovery import ANIPService


class ANIPInvoker:
    """Invokes ANIP capabilities on behalf of REST requests.

    Manages delegation tokens and translates between REST's simple
    request/response model and ANIP's delegation-aware invocation.
    """

    def __init__(
        self,
        service: ANIPService,
        issuer: str,
        scope: list[str],
        token_ttl_minutes: int = 60,
    ):
        self.service = service
        self.issuer = issuer
        self.scope = scope
        self.token_ttl_minutes = token_ttl_minutes
        self._root_token_id: str | None = None

    async def setup(self) -> None:
        """Register the root delegation token with the ANIP service."""
        self._root_token_id = f"rest-adapter-{uuid.uuid4().hex[:12]}"
        root_token = {
            "token_id": self._root_token_id,
            "issuer": self.issuer,
            "subject": "adapter:anip-rest-adapter",
            "scope": self.scope,
            "purpose": {
                "capability": "*",
                "parameters": {},
                "task_id": f"rest-session-{uuid.uuid4().hex[:8]}",
            },
            "parent": None,
            "expires": (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.token_ttl_minutes)
            ).isoformat(),
            "constraints": {
                "max_delegation_depth": 2,
                "concurrent_branches": "allowed",
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.service.endpoints["tokens"], json=root_token
            )
            resp.raise_for_status()

    async def invoke(
        self, capability_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke an ANIP capability and return the raw response dict.

        Creates a per-invocation delegation token with proper purpose
        binding, invokes the capability, and returns the ANIP response
        directly as a dict for JSON serialization.
        """
        # Build a capability-specific token
        cap_token_id = f"rest-{capability_name}-{uuid.uuid4().hex[:8]}"

        # Determine scope for this capability
        capability = self.service.capabilities.get(capability_name)
        cap_scope = self.scope  # default to full scope
        if capability and capability.minimum_scope:
            if "*" in self.scope:
                # Wildcard scope — use the capability's required scopes directly
                cap_scope = capability.minimum_scope
            else:
                # Narrow scope to what the capability needs
                needed = capability.minimum_scope
                cap_scope = [
                    s
                    for s in self.scope
                    if s.split(":")[0] in needed or s in needed
                ]
                if not cap_scope:
                    cap_scope = self.scope  # fall back if no match

        cap_token = {
            "token_id": cap_token_id,
            "issuer": "adapter:anip-rest-adapter",
            "subject": "adapter:anip-rest-adapter",
            "scope": cap_scope,
            "purpose": {
                "capability": capability_name,
                "parameters": arguments,
                "task_id": f"rest-invoke-{uuid.uuid4().hex[:8]}",
            },
            "parent": self._root_token_id,
            "expires": (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.token_ttl_minutes)
            ).isoformat(),
            "constraints": {
                "max_delegation_depth": 2,
                "concurrent_branches": "allowed",
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # Register the capability token
            resp = await client.post(
                self.service.endpoints["tokens"], json=cap_token
            )
            resp.raise_for_status()

            # Invoke the capability
            invoke_url = self.service.endpoints["invoke"].replace(
                "{capability}", capability_name
            )
            resp = await client.post(
                invoke_url,
                json={
                    "delegation_token": cap_token,
                    "parameters": arguments,
                },
            )
            resp.raise_for_status()
            return resp.json()
