"""ANIP capability invocation from MCP tool calls.

Handles delegation token construction and ANIP invocation,
translating ANIP responses back into MCP-compatible results.
"""

from __future__ import annotations

import json
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
        scope: list[str],
        api_key: str = "demo-human-key",
    ):
        self.service = service
        self.scope = scope
        self.api_key = api_key

    async def setup(self) -> None:
        """No-op — v0.2 issues per-capability tokens, no root token needed."""

    async def invoke(
        self, capability_name: str, arguments: dict[str, Any]
    ) -> str:
        """Invoke an ANIP capability and return an MCP-friendly result string.

        Creates a per-invocation delegation token with proper purpose
        binding, invokes the capability, and translates the ANIP response.
        """
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

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Request a signed JWT token
            token_resp = await client.post(
                self.service.endpoints["tokens"],
                json={
                    "subject": "bridge:anip-mcp-bridge",
                    "scope": cap_scope,
                    "capability": capability_name,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            if not token_data.get("issued"):
                error = token_data.get("error", "unknown error")
                return f"FAILED: token_issuance\nDetail: {error}\nRetryable: no"
            jwt_str = token_data["token"]

            # Step 2: Invoke with the JWT
            invoke_url = self.service.endpoints["invoke"].replace(
                "{capability}", capability_name
            )
            resp = await client.post(
                invoke_url,
                json={
                    "token": jwt_str,
                    "parameters": arguments,
                },
            )
            resp.raise_for_status()
            result = resp.json()

        return self._translate_response(result)

    def _translate_response(
        self, response: dict[str, Any]
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
