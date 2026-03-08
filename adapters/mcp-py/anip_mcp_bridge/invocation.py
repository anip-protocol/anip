"""ANIP capability invocation from MCP tool calls.

Handles delegation token construction and ANIP invocation,
translating ANIP responses back into MCP-compatible results.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .discovery import ANIPService


class ANIPInvoker:
    """Invokes ANIP capabilities on behalf of MCP tool calls.

    Manages delegation tokens and translates between MCP's simple
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
        self._root_token_id = f"mcp-bridge-{uuid.uuid4().hex[:12]}"
        root_token = {
            "token_id": self._root_token_id,
            "issuer": self.issuer,
            "subject": "bridge:anip-mcp-bridge",
            "scope": self.scope,
            "purpose": {
                "capability": "*",
                "parameters": {},
                "task_id": f"mcp-session-{uuid.uuid4().hex[:8]}",
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
    ) -> str:
        """Invoke an ANIP capability and return an MCP-friendly result string.

        Creates a per-invocation delegation token with proper purpose
        binding, invokes the capability, and translates the ANIP response.
        """
        # Build a capability-specific token
        cap_token_id = f"mcp-{capability_name}-{uuid.uuid4().hex[:8]}"

        # Determine scope for this capability
        capability = self.service.capabilities.get(capability_name)
        cap_scope = self.scope  # default to full scope
        if capability:
            # Narrow scope to what the capability needs
            needed = capability.minimum_scope
            cap_scope = [
                s for s in self.scope if s.split(":")[0] in needed or s in needed
            ]
            if not cap_scope:
                cap_scope = self.scope  # fall back if no match

        cap_token = {
            "token_id": cap_token_id,
            "issuer": "bridge:anip-mcp-bridge",
            "subject": "bridge:anip-mcp-bridge",
            "scope": cap_scope,
            "purpose": {
                "capability": capability_name,
                "parameters": arguments,
                "task_id": f"mcp-invoke-{uuid.uuid4().hex[:8]}",
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
            result = resp.json()

        return self._translate_response(capability_name, result)

    def _translate_response(
        self, capability_name: str, response: dict[str, Any]
    ) -> str:
        """Translate an ANIP InvokeResponse into an MCP result string.

        ANIP responses are structured with success/failure semantics,
        cost actuals, and session state. MCP tools return plain text.
        This translation preserves as much signal as possible.
        """
        if response.get("success"):
            result = response.get("result", {})
            parts = [json.dumps(result, indent=2, default=str)]

            # Surface cost actual if present
            cost_actual = response.get("cost_actual")
            if cost_actual:
                financial = cost_actual.get("financial", {})
                amount = financial.get("amount")
                currency = financial.get("currency", "USD")
                if amount is not None:
                    parts.append(f"\n[Cost: {currency} {amount}]")
                variance = cost_actual.get("variance_from_estimate")
                if variance:
                    parts.append(f"[Variance from estimate: {variance}]")

            return "".join(parts)

        # Failure — translate ANIP failure semantics into readable text
        failure = response.get("failure", {})
        parts = [
            f"FAILED: {failure.get('type', 'unknown')}",
            f"Detail: {failure.get('detail', 'no detail')}",
        ]

        resolution = failure.get("resolution", {})
        if resolution:
            action = resolution.get("action", "")
            parts.append(f"Resolution: {action}")
            if resolution.get("requires"):
                parts.append(f"Requires: {resolution['requires']}")
            if resolution.get("grantable_by"):
                parts.append(f"Grantable by: {resolution['grantable_by']}")

        retry = failure.get("retry", False)
        parts.append(f"Retryable: {'yes' if retry else 'no'}")

        return "\n".join(parts)
