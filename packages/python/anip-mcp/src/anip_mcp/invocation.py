"""Shared ANIP MCP invocation core.

Used by both stdio (routes.py) and HTTP (http.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from anip_service import ANIPService, ANIPError


@dataclass
class InvokeResult:
    text: str
    is_error: bool


async def resolve_auth(
    bearer: str,
    service: ANIPService,
    capability_name: str,
):
    """Resolve auth from a bearer token. JWT-first, API-key fallback."""
    jwt_error = None
    try:
        return await service.resolve_bearer_token(bearer)
    except ANIPError as e:
        jwt_error = e

    principal = await service.authenticate_bearer(bearer)
    if principal:
        cap_decl = service.get_capability_declaration(capability_name)
        min_scope = cap_decl.minimum_scope if cap_decl else []
        token_result = await service.issue_token(principal, {
            "subject": "adapter:anip-mcp",
            "scope": min_scope if min_scope else ["*"],
            "capability": capability_name,
            "purpose_parameters": {"source": "mcp"},
        })
        jwt_str = token_result["token"]
        return await service.resolve_bearer_token(jwt_str)

    if jwt_error:
        raise jwt_error
    raise ANIPError("authentication_required", "No valid bearer credential provided")


async def invoke_with_token(
    service: ANIPService,
    capability_name: str,
    args: dict[str, Any],
    token,
) -> InvokeResult:
    """Invoke a capability with an already-resolved delegation token."""
    try:
        result = await service.invoke(capability_name, token, args)
        return translate_response(result)
    except ANIPError as e:
        return InvokeResult(
            text=f"FAILED: {e.error_type}\nDetail: {e.detail}\nRetryable: no",
            is_error=True,
        )


def translate_response(response: dict[str, Any]) -> InvokeResult:
    """Translate an ANIP invoke response to MCP text format."""
    if response.get("success"):
        result = response.get("result", {})
        parts = [json.dumps(result, indent=2, default=str)]
        cost_actual = response.get("cost_actual")
        if cost_actual:
            financial = cost_actual.get("financial", {})
            amount = financial.get("amount")
            currency = financial.get("currency", "USD")
            if amount is not None:
                parts.append(f"\n[Cost: {currency} {amount}]")
        return InvokeResult(text="".join(parts), is_error=False)

    failure = response.get("failure", {})
    parts = [
        f"FAILED: {failure.get('type', 'unknown')}",
        f"Detail: {failure.get('detail', 'no detail')}",
    ]
    resolution = failure.get("resolution", {})
    if resolution:
        parts.append(f"Resolution: {resolution.get('action', '')}")
        if resolution.get("requires"):
            parts.append(f"Requires: {resolution['requires']}")
    parts.append(f"Retryable: {'yes' if failure.get('retry') else 'no'}")
    return InvokeResult(text="\n".join(parts), is_error=True)
