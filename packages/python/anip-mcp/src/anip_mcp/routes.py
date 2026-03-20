"""ANIP MCP bindings — mount ANIPService capabilities as MCP tools.

Supports stdio transport via the mcp library.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server

from anip_service import ANIPService, ANIPError
from .translation import capability_to_input_schema, enrich_description


@dataclass
class McpCredentials:
    """Mount-time credentials for stdio transport."""
    api_key: str
    scope: list[str]
    subject: str


async def _invoke_capability(
    service: ANIPService,
    capability_name: str,
    args: dict[str, Any],
    credentials: McpCredentials,
) -> str:
    """Invoke an ANIP capability directly via the service instance."""
    principal = await service.authenticate_bearer(credentials.api_key)
    if not principal:
        return "FAILED: authentication_required\nDetail: Invalid bootstrap credential\nRetryable: no"

    # Narrow scope to what the capability needs
    cap_decl = service.get_capability_declaration(capability_name)
    min_scope = cap_decl.minimum_scope if cap_decl else []
    cap_scope = credentials.scope
    if min_scope:
        needed = set(min_scope)
        narrowed = [s for s in credentials.scope if s.split(":")[0] in needed or s in needed]
        if narrowed:
            cap_scope = narrowed

    # Issue a synthetic token
    try:
        token_result = await service.issue_token(principal, {
            "subject": credentials.subject,
            "scope": cap_scope,
            "capability": capability_name,
            "purpose_parameters": {"source": "mcp"},
        })
    except ANIPError as e:
        return f"FAILED: {e.error_type}\nDetail: {e.detail}\nRetryable: no"

    jwt_str = token_result["token"]
    token = await service.resolve_bearer_token(jwt_str)

    result = await service.invoke(capability_name, token, args)
    return _translate_response(result)


def _translate_response(response: dict[str, Any]) -> str:
    """Translate an ANIP InvokeResponse into an MCP result string."""
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
        return "".join(parts)

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
    return "\n".join(parts)


@dataclass
class McpLifecycle:
    """Lifecycle handle returned by mount_anip_mcp."""
    _service: ANIPService

    def stop(self) -> None:
        self._service.stop()

    async def shutdown(self) -> None:
        self._service.stop()
        await self._service.shutdown()


async def mount_anip_mcp(
    server: Server,
    service: ANIPService,
    *,
    credentials: McpCredentials,
    enrich_descriptions: bool = True,
) -> McpLifecycle:
    """Mount ANIP capabilities as MCP tools on an MCP Server.

    Starts the service lifecycle (storage init, background workers).
    Caller must call the returned lifecycle.stop() / lifecycle.shutdown()
    on teardown.
    """
    await service.start()

    # Build tool map from service manifest
    manifest = service.get_manifest()
    mcp_tools: dict[str, types.Tool] = {}

    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if not decl:
            continue
        decl_dict = decl.model_dump()
        description = enrich_description(decl_dict) if enrich_descriptions else decl.description
        mcp_tools[name] = types.Tool(
            name=name,
            description=description,
            inputSchema=capability_to_input_schema(decl_dict),
        )

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return list(mcp_tools.values())

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict,
    ) -> list[types.TextContent]:
        if name not in mcp_tools:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}. Available: {list(mcp_tools.keys())}",
            )]

        try:
            result = await _invoke_capability(service, name, arguments or {}, credentials)
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"ANIP invocation error: {e}",
            )]

    return McpLifecycle(_service=service)
