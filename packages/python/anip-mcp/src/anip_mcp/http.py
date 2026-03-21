"""ANIP MCP Streamable HTTP transport for FastAPI.

Mounts an MCP server on a FastAPI application using the mcp library's
StreamableHTTPSessionManager in stateless mode. Each request gets its own
transport instance, so no session state is shared between requests.

Auth is per-request: the call_tool handler reads Authorization from
server.request_context.request (the Starlette Request provided by the
transport's request_context metadata).
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from fastapi import FastAPI
from starlette.requests import Request
from starlette.routing import Mount

from anip_service import ANIPService, ANIPError
from .invocation import resolve_auth, invoke_with_token
from .translation import capability_to_input_schema, enrich_description

logger = logging.getLogger(__name__)


def mount_anip_mcp_http(
    app: FastAPI,
    service: ANIPService,
    *,
    path: str = "/mcp",
    enrich_descriptions: bool = True,
) -> None:
    """Mount MCP Streamable HTTP transport on a FastAPI app.

    Does not own the service lifecycle — call service.start() before
    the app starts (e.g. in an outer lifespan or mount_anip).

    Creates an MCP Server with tools registered from the ANIPService,
    wraps it in a StreamableHTTPSessionManager (stateless mode), adds a
    startup/shutdown lifespan handler to the FastAPI app, and mounts the
    ASGI handler at the given path.

    Auth is per-request from the Authorization: Bearer header.
    JWT-first, API-key fallback — same as the REST/GraphQL transports.
    """
    # Build tool map from service manifest
    manifest = service.get_manifest()
    mcp_tools: dict[str, mcp_types.Tool] = {}

    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if not decl:
            continue
        decl_dict = decl.model_dump()
        description = enrich_description(decl_dict) if enrich_descriptions else decl.description
        mcp_tools[name] = mcp_types.Tool(
            name=name,
            description=description,
            inputSchema=capability_to_input_schema(decl_dict),
        )

    # Create the MCP lowlevel server
    mcp_server = Server("anip-mcp-http")

    @mcp_server.list_tools()
    async def handle_list_tools() -> list[mcp_types.Tool]:
        return list(mcp_tools.values())

    @mcp_server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict,
    ) -> list[mcp_types.TextContent]:
        # The mcp server wraps the return into CallToolResult(isError=False).
        # To signal errors, raise an exception — the server catches it and
        # creates CallToolResult(isError=True, content=[TextContent(str(e))]).
        if name not in mcp_tools:
            raise ValueError(f"Unknown tool: {name}. Available: {list(mcp_tools.keys())}")

        # Extract Authorization header from the per-request Starlette Request.
        bearer: str | None = None
        try:
            ctx = mcp_server.request_context
            request: Request | None = getattr(ctx, "request", None)
            if request is not None:
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    bearer = auth_header[7:].strip()
        except LookupError:
            pass

        if not bearer:
            raise ValueError("FAILED: authentication_required\nDetail: No Authorization header\nRetryable: yes")

        token = await resolve_auth(bearer, service, name)
        result = await invoke_with_token(service, name, arguments or {}, token)
        if result.is_error:
            raise ValueError(result.text)
        return [mcp_types.TextContent(type="text", text=result.text)]

    # Use the session manager in stateless mode: each request gets its own
    # transport, so no shared state between HTTP requests.
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=False,   # Use SSE responses (standard MCP)
        stateless=True,        # Per-request transport
    )

    # Integrate the session manager's lifecycle into the FastAPI app.
    # We wrap the existing lifespan (if any) so we don't clobber it.
    existing_lifespan = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def combined_lifespan(app_: Any):
        async with existing_lifespan(app_):
            async with session_manager.run():
                yield

    app.router.lifespan_context = combined_lifespan

    # Mount the ASGI handler. FastAPI's app.mount() adds a route to the
    # router, but calling it after routes have been added can cause ordering
    # issues. We append a Mount route directly.
    app.routes.append(
        Mount(path, app=session_manager.handle_request)
    )
