"""ANIP capability invocation from GraphQL requests.

Passes caller-provided credentials (delegation token or API key)
through to the ANIP service. The adapter holds no tokens of its own.
"""

from __future__ import annotations

from typing import Any

import httpx

from .discovery import ANIPService


class CredentialError(Exception):
    """Raised when no valid credentials are provided."""


class IssuanceError(Exception):
    """Raised when API-key token issuance is denied."""

    def __init__(self, error: str):
        self.error = error
        super().__init__(f"Token issuance denied: {error}")


class ANIPInvoker:
    """Invokes ANIP capabilities by forwarding caller credentials.

    Supports two credential modes:
    1. Delegation token (preferred): caller provides a signed ANIP token
    2. API key (convenience): caller provides an API key, adapter requests
       a short-lived token scoped to the specific capability
    """

    def __init__(self, service: ANIPService):
        self.service = service

    async def invoke(
        self,
        capability_name: str,
        arguments: dict[str, Any],
        *,
        token: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Invoke an ANIP capability using caller-provided credentials."""
        if token is not None:
            return await self._invoke_with_token(capability_name, arguments, token)
        elif api_key is not None:
            return await self._invoke_with_api_key(capability_name, arguments, api_key)
        else:
            raise CredentialError(
                "No credentials provided. Include either "
                "'X-ANIP-Token: <anip-token>' or "
                "'X-ANIP-API-Key: <key>' header."
            )

    async def _invoke_with_token(
        self,
        capability_name: str,
        arguments: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        """Invoke directly with a caller-provided signed token."""
        invoke_url = self.service.endpoints["invoke"].replace(
            "{capability}", capability_name
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                invoke_url,
                json={"parameters": arguments},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def _invoke_with_api_key(
        self,
        capability_name: str,
        arguments: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Request a capability token via API key, then invoke."""
        capability = self.service.capabilities.get(capability_name)
        cap_scope = ["*"]
        if capability and capability.minimum_scope:
            cap_scope = capability.minimum_scope

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Request a signed token
            token_resp = await client.post(
                self.service.endpoints["tokens"],
                json={
                    "subject": "adapter:anip-graphql-adapter",
                    "scope": cap_scope,
                    "capability": capability_name,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            if not token_data.get("issued"):
                raise IssuanceError(token_data.get("error", "unknown error"))

            jwt_str = token_data["token"]

            # Step 2: Invoke with the signed token
            invoke_url = self.service.endpoints["invoke"].replace(
                "{capability}", capability_name
            )
            resp = await client.post(
                invoke_url,
                json={"parameters": arguments},
                headers={"Authorization": f"Bearer {jwt_str}"},
            )
            resp.raise_for_status()
            return resp.json()
