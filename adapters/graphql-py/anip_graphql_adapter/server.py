"""ANIP GraphQL Adapter Server.

A generic adapter that discovers any ANIP-compliant service and
exposes its capabilities as a GraphQL endpoint with custom @anip*
directives. Point it at any ANIP service URL — zero per-service
code required.

Usage:
    # With config file
    anip-graphql-adapter --config adapter.yaml

    # With environment variables
    ANIP_SERVICE_URL=http://localhost:8000 anip-graphql-adapter

    # Direct
    anip-graphql-adapter --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from typing import Any

import uvicorn
from ariadne import (
    MutationType,
    QueryType,
    ScalarType,
    make_executable_schema,
)
from ariadne.asgi import GraphQL
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from .config import AdapterConfig, load_config
from .discovery import discover_service
from .invocation import ANIPInvoker
from .translation import generate_schema, _to_camel_case

logger = logging.getLogger("anip-graphql-adapter")


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub(r"([A-Z])", r"_\1", name)
    return s1.lower().lstrip("_")


def _build_anip_response(result: dict[str, Any]) -> dict[str, Any]:
    """Build a GraphQL-friendly response dict from an ANIP invocation result."""
    response: dict[str, Any] = {
        "success": result.get("success", False),
        "result": result.get("result"),
        "costActual": None,
        "failure": None,
    }

    # Map cost_actual -> costActual
    cost_actual = result.get("cost_actual")
    if cost_actual:
        financial = cost_actual.get("financial")
        response["costActual"] = {
            "financial": financial,
            "varianceFromEstimate": cost_actual.get("variance_from_estimate"),
        }

    # Map failure with resolution
    failure = result.get("failure")
    if failure:
        resolution = failure.get("resolution")
        mapped_resolution = None
        if resolution:
            mapped_resolution = {
                "action": resolution.get("action", ""),
                "requires": resolution.get("requires"),
                "grantableBy": resolution.get("grantable_by"),
            }
        response["failure"] = {
            "type": failure.get("type", "unknown"),
            "detail": failure.get("detail", ""),
            "resolution": mapped_resolution,
            "retry": failure.get("retry", False),
        }

    return response


def _make_resolver(capability_name: str, invoker: ANIPInvoker):
    """Create a resolver function for a given capability."""

    async def resolver(_obj: Any, _info: Any, **kwargs: Any) -> dict[str, Any]:
        # Convert camelCase args back to snake_case for ANIP
        arguments = {_camel_to_snake(k): v for k, v in kwargs.items()}
        try:
            result = await invoker.invoke(capability_name, arguments)
        except Exception as e:
            logger.exception("ANIP invocation failed for %s", capability_name)
            return {
                "success": False,
                "result": None,
                "costActual": None,
                "failure": {
                    "type": "adapter_error",
                    "detail": str(e),
                    "resolution": None,
                    "retry": True,
                },
            }
        return _build_anip_response(result)

    return resolver


async def build_app(config: AdapterConfig) -> FastAPI:
    """Build a FastAPI app with GraphQL endpoint from an ANIP service.

    Discovers the service, sets up the invoker, generates the schema,
    and registers resolvers dynamically.
    """
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
        issuer=config.delegation.issuer,
        scope=config.delegation.scope,
        token_ttl_minutes=config.delegation.token_ttl_minutes,
    )
    await invoker.setup()
    logger.info("Delegation token registered")

    # Step 3: Generate GraphQL schema SDL
    schema_sdl = generate_schema(service)

    # Step 4: Build Ariadne resolvers
    query = QueryType()
    mutation = MutationType()

    # Custom JSON scalar
    json_scalar = ScalarType("JSON")

    @json_scalar.serializer
    def serialize_json(value: Any) -> Any:
        return value

    @json_scalar.value_parser
    def parse_json_value(value: Any) -> Any:
        return value

    # Register resolvers for each capability
    for name, cap in service.capabilities.items():
        camel_name = _to_camel_case(name)
        resolver_fn = _make_resolver(name, invoker)

        if cap.side_effect == "read":
            query.field(camel_name)(resolver_fn)
        else:
            mutation.field(camel_name)(resolver_fn)

    # Step 5: Build executable schema
    bindables = [query, mutation, json_scalar]
    schema = make_executable_schema(schema_sdl, *bindables)

    # Step 6: Build FastAPI app
    app = FastAPI(
        title="ANIP GraphQL Adapter",
        docs_url=None,
        openapi_url=None,
    )

    # Mount the GraphQL endpoint
    graphql_app = GraphQL(
        schema,
        debug=True,
        introspection=config.graphql.introspection,
    )
    app.mount(config.graphql.path, graphql_app)

    # Schema endpoint for downloading the SDL
    @app.get("/schema.graphql")
    async def get_schema() -> PlainTextResponse:
        return PlainTextResponse(schema_sdl, media_type="text/plain")

    # Store schema SDL on app for testing
    app.state.schema_sdl = schema_sdl

    return app


def main() -> None:
    """Entry point for the adapter CLI."""
    import asyncio

    parser = argparse.ArgumentParser(
        description="ANIP GraphQL Adapter: expose any ANIP service as a GraphQL endpoint"
    )
    parser.add_argument(
        "--config", "-c", help="Path to adapter.yaml config file"
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
        stream=sys.stderr,
    )

    config = load_config(args.config)
    if args.url:
        config.anip_service_url = args.url

    app = asyncio.run(build_app(config))
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
