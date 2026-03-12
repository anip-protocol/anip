"""ANIP REST Adapter Server.

A generic adapter that discovers any ANIP-compliant service and
exposes its capabilities as REST endpoints with an auto-generated
OpenAPI specification. Point it at any ANIP service URL — zero
per-service code required.

Usage:
    # With config file
    anip-rest-adapter --config adapter.yaml

    # With environment variables
    ANIP_SERVICE_URL=http://localhost:8000 anip-rest-adapter

    # Direct
    anip-rest-adapter --url http://localhost:8000
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import AdapterConfig, load_config
from .discovery import discover_service
from .invocation import ANIPInvoker, CredentialError, IssuanceError
from .translation import RESTRoute, generate_openapi_spec, generate_routes

logger = logging.getLogger("anip-rest-adapter")

# ANIP failure type -> HTTP status code mapping
_FAILURE_STATUS_MAP = {
    "unknown_capability": 404,
    "insufficient_authority": 403,
    "budget_exceeded": 403,
    "purpose_mismatch": 403,
    "invalid_parameters": 400,
    "delegation_expired": 401,
}


async def build_app(config: AdapterConfig) -> FastAPI:
    """Build a FastAPI app from an ANIP service.

    Discovers the service, sets up the invoker, generates routes,
    and registers all endpoints dynamically.
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

    # Step 2: Set up the invoker (stateless — no token registration)
    invoker = ANIPInvoker(service=service)
    logger.info("Invoker ready (pass-through mode)")

    # Step 3: Generate routes and OpenAPI spec
    routes = generate_routes(service, config.routes)
    openapi_spec = generate_openapi_spec(service, routes)

    # Step 4: Build FastAPI app
    app = FastAPI(
        title="ANIP REST Adapter",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Override the default OpenAPI schema with our generated one
    app.openapi = lambda: openapi_spec

    # Register dynamic routes
    for name, route in routes.items():
        _register_route(app, route, invoker)

    return app


def _extract_credentials(request: Request) -> tuple[str | None, str | None]:
    """Extract ANIP credentials from request headers."""
    token = request.headers.get("x-anip-token")
    api_key = request.headers.get("x-anip-api-key")
    return token, api_key


def _register_route(
    app: FastAPI,
    route: RESTRoute,
    invoker: ANIPInvoker,
) -> None:
    """Register a single REST route for an ANIP capability."""
    cap = route.capability

    if route.method == "GET":

        @app.get(route.path, name=route.capability_name)
        async def handle_get(
            request: Request,
            _cap_name: str = route.capability_name,
            _cap: Any = cap,
        ) -> JSONResponse:
            # Extract query parameters and convert types
            arguments = dict(request.query_params)
            arguments = _convert_param_types(arguments, _cap)
            token, api_key = _extract_credentials(request)
            return await _invoke_and_respond(
                invoker, _cap_name, arguments, _cap, token=token, api_key=api_key
            )

    else:

        @app.post(route.path, name=route.capability_name)
        async def handle_post(
            request: Request,
            _cap_name: str = route.capability_name,
            _cap: Any = cap,
        ) -> JSONResponse:
            body = await request.json()
            token, api_key = _extract_credentials(request)
            return await _invoke_and_respond(
                invoker, _cap_name, body, _cap, token=token, api_key=api_key
            )


def _convert_param_types(
    arguments: dict[str, str],
    cap: Any,
) -> dict[str, Any]:
    """Convert GET query parameter strings to proper types based on capability inputs."""
    converted: dict[str, Any] = {}
    input_types: dict[str, str] = {}
    for inp in cap.inputs:
        input_types[inp["name"]] = inp.get("type", "string")

    for key, value in arguments.items():
        inp_type = input_types.get(key, "string")
        if inp_type == "integer":
            try:
                converted[key] = int(value)
            except (ValueError, TypeError):
                converted[key] = value
        elif inp_type == "number":
            try:
                converted[key] = float(value)
            except (ValueError, TypeError):
                converted[key] = value
        elif inp_type == "boolean":
            converted[key] = value.lower() in ("true", "1", "yes")
        else:
            converted[key] = value

    return converted


async def _invoke_and_respond(
    invoker: ANIPInvoker,
    capability_name: str,
    arguments: dict[str, Any],
    cap: Any,
    *,
    token: str | None = None,
    api_key: str | None = None,
) -> JSONResponse:
    """Invoke an ANIP capability and map the response to HTTP status codes."""
    try:
        result = await invoker.invoke(
            capability_name, arguments, token=token, api_key=api_key
        )
    except CredentialError as e:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "failure": {
                    "type": "missing_credentials",
                    "detail": str(e),
                    "retry": False,
                },
            },
        )
    except IssuanceError as e:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "failure": {
                    "type": "token_issuance_denied",
                    "detail": str(e),
                    "retry": False,
                },
            },
        )
    except Exception as e:
        logger.exception("ANIP invocation failed for %s", capability_name)
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "failure": {
                    "type": "adapter_error",
                    "detail": str(e),
                    "retry": True,
                },
            },
        )

    # Build response with warnings
    response: dict[str, Any] = {
        "success": result.get("success", False),
        "result": result.get("result"),
    }

    if result.get("cost_actual"):
        response["cost_actual"] = result["cost_actual"]

    # Add warnings for irreversible/financial operations
    warnings: list[str] = []
    if cap.side_effect == "irreversible":
        warnings.append("IRREVERSIBLE: this action cannot be undone")
    if cap.financial:
        warnings.append("FINANCIAL: this action involves real charges")
    if warnings:
        response["warnings"] = warnings

    if result.get("success"):
        return JSONResponse(status_code=200, content=response)

    # Map ANIP failure to HTTP status
    failure = result.get("failure", {})
    response["failure"] = failure
    status_code = _FAILURE_STATUS_MAP.get(failure.get("type", ""), 500)
    return JSONResponse(status_code=status_code, content=response)


def main() -> None:
    """Entry point for the adapter CLI."""
    import asyncio

    parser = argparse.ArgumentParser(
        description="ANIP REST Adapter: expose any ANIP service as REST endpoints"
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
