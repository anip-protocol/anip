"""ANIP-MCP Bridge Server.

A generic bridge that discovers any ANIP-compliant service and
exposes its capabilities as MCP tools. Point it at any ANIP service
URL — zero per-service code required.

Usage:
    # With config file
    anip-mcp-bridge --config bridge.yaml

    # With environment variables
    ANIP_SERVICE_URL=http://localhost:8000 anip-mcp-bridge

    # Direct
    anip-mcp-bridge --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from .config import BridgeConfig, load_config
from .discovery import ANIPService, discover_service
from .invocation import ANIPInvoker
from .translation import capability_to_input_schema, enrich_description

logger = logging.getLogger("anip-mcp-bridge")


def build_server(
    service: ANIPService, invoker: ANIPInvoker, config: BridgeConfig
) -> Server:
    """Build an MCP server with tools generated from ANIP capabilities."""

    server = Server("anip-mcp-bridge")

    # Build MCP tools from ANIP capabilities
    mcp_tools: dict[str, types.Tool] = {}
    for name, capability in service.capabilities.items():
        description = (
            enrich_description(capability)
            if config.enrich_descriptions
            else capability.description
        )
        mcp_tools[name] = types.Tool(
            name=name,
            description=description,
            inputSchema=capability_to_input_schema(capability),
        )

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return list(mcp_tools.values())

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent]:
        if name not in mcp_tools:
            return [
                types.TextContent(
                    type="text",
                    text=f"Unknown tool: {name}. Available: {list(mcp_tools.keys())}",
                )
            ]

        try:
            result = await invoker.invoke(name, arguments or {})
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            logger.exception("ANIP invocation failed for %s", name)
            return [
                types.TextContent(
                    type="text",
                    text=f"ANIP invocation error: {e}",
                )
            ]

    return server


async def run_bridge(config: BridgeConfig) -> None:
    """Discover ANIP service, build MCP server, and run."""
    # Step 1: Discover the ANIP service
    logger.info("Discovering ANIP service at %s", config.anip_service_url)
    service = await discover_service(config.anip_service_url)
    logger.info(
        "Discovered %s (%s) with %d capabilities",
        service.base_url,
        service.compliance,
        len(service.capabilities),
    )
    for name, cap in service.capabilities.items():
        logger.info(
            "  %s: %s [%s]%s",
            name,
            cap.side_effect,
            cap.contract_version,
            " (financial)" if cap.financial else "",
        )

    # Step 2: Set up the invoker with delegation tokens
    invoker = ANIPInvoker(
        service=service,
        scope=config.delegation.scope,
        api_key=config.delegation.api_key,
    )
    logger.info("Invoker ready")

    # Step 3: Build and run MCP server
    server = build_server(service, invoker, config)

    logger.info("Starting MCP server (transport: %s)", config.transport)

    if config.transport == "stdio":
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="anip-mcp-bridge",
                    server_version="0.2.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    else:
        raise ValueError(
            f"Unsupported transport: {config.transport}. "
            f"Currently supported: stdio"
        )


def main() -> None:
    """Entry point for the bridge CLI."""
    parser = argparse.ArgumentParser(
        description="ANIP-MCP Bridge: expose any ANIP service as MCP tools"
    )
    parser.add_argument(
        "--config", "-c", help="Path to bridge.yaml config file"
    )
    parser.add_argument(
        "--url", "-u", help="ANIP service URL (overrides config)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol; logs go to stderr
    )

    config = load_config(args.config)
    if args.url:
        config.anip_service_url = args.url

    asyncio.run(run_bridge(config))


if __name__ == "__main__":
    main()
