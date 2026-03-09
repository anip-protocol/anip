"""ANIP -> REST/OpenAPI translation layer.

Converts ANIP capability declarations into REST routes and
generates an OpenAPI 3.1 specification with ANIP metadata
preserved as x-anip-* extensions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .discovery import ANIPCapability, ANIPService


# Map ANIP input types to JSON Schema types
_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "airport_code": "string",
}


@dataclass
class RESTRoute:
    """A REST route generated from an ANIP capability."""

    capability_name: str
    path: str
    method: str  # "GET" or "POST"
    capability: ANIPCapability


def generate_routes(
    service: ANIPService,
    route_overrides: dict[str, Any] | None = None,
) -> dict[str, RESTRoute]:
    """Generate REST routes from ANIP capabilities.

    Default: GET /api/{name} for read, POST /api/{name} for everything else.
    Overridable via route_overrides dict.
    """
    routes: dict[str, RESTRoute] = {}
    overrides = route_overrides or {}

    for name, cap in service.capabilities.items():
        if name in overrides:
            override = overrides[name]
            path = override.path
            method = override.method.upper()
        else:
            path = f"/api/{name}"
            method = "GET" if cap.side_effect == "read" else "POST"

        routes[name] = RESTRoute(
            capability_name=name,
            path=path,
            method=method,
            capability=cap,
        )

    return routes


def generate_openapi_spec(
    service: ANIPService,
    routes: dict[str, RESTRoute],
) -> dict[str, Any]:
    """Generate an OpenAPI 3.1 specification from ANIP service metadata.

    Preserves ANIP metadata as x-anip-* extensions on each operation.
    """
    paths: dict[str, Any] = {}

    for name, route in routes.items():
        operation = _build_operation(name, route)
        method_key = route.method.lower()
        paths[route.path] = {method_key: operation}

    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": f"ANIP REST Adapter — {service.base_url}",
            "version": service.compliance,
            "description": (
                "Auto-generated REST API from an ANIP service. "
                "x-anip-* extensions preserve ANIP metadata."
            ),
        },
        "paths": paths,
        "components": {
            "schemas": {
                "ANIPResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "result": {"type": "object"},
                        "failure": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "type": {"type": "string"},
                                "detail": {"type": "string"},
                                "retry": {"type": "boolean"},
                                "resolution": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "requires": {"type": "string"},
                                        "grantable_by": {"type": "string"},
                                    },
                                },
                            },
                        },
                        "cost_actual": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "financial": {
                                    "type": "object",
                                    "properties": {
                                        "amount": {"type": "number"},
                                        "currency": {"type": "string"},
                                    },
                                },
                                "variance_from_estimate": {"type": "string"},
                            },
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["success"],
                },
            },
        },
    }

    return spec


def _build_operation(name: str, route: RESTRoute) -> dict[str, Any]:
    """Build an OpenAPI operation object for a capability."""
    cap = route.capability

    operation: dict[str, Any] = {
        "operationId": name,
        "summary": cap.description,
        "tags": ["ANIP Capabilities"],
        "x-anip-side-effect": cap.side_effect,
        "x-anip-minimum-scope": cap.minimum_scope,
        "x-anip-financial": cap.financial,
        "x-anip-contract-version": cap.contract_version,
    }

    if cap.cost:
        operation["x-anip-cost"] = cap.cost
    if cap.requires:
        operation["x-anip-requires"] = [
            r.get("capability", r) if isinstance(r, dict) else r
            for r in cap.requires
        ]
    if cap.rollback_window:
        operation["x-anip-rollback-window"] = cap.rollback_window

    # Parameters / request body
    if route.method == "GET":
        operation["parameters"] = _build_query_parameters(cap)
    else:
        operation["requestBody"] = _build_request_body(cap)

    # Responses
    operation["responses"] = {
        "200": {
            "description": "Successful ANIP response",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ANIPResponse"},
                },
            },
        },
        "400": {"description": "Invalid parameters"},
        "401": {"description": "Delegation expired or invalid"},
        "403": {"description": "Insufficient authority, budget exceeded, or purpose mismatch"},
        "404": {"description": "Unknown capability"},
    }

    return operation


def _build_query_parameters(cap: ANIPCapability) -> list[dict[str, Any]]:
    """Build OpenAPI query parameters from ANIP capability inputs."""
    params = []
    for inp in cap.inputs:
        json_type = _TYPE_MAP.get(inp.get("type", "string"), "string")
        param: dict[str, Any] = {
            "name": inp["name"],
            "in": "query",
            "required": inp.get("required", True),
            "schema": {
                "type": json_type,
            },
            "description": inp.get("description", ""),
        }
        if inp.get("type") == "date":
            param["schema"]["format"] = "date"
        if "default" in inp and inp["default"] is not None:
            param["schema"]["default"] = inp["default"]
        params.append(param)
    return params


def _build_request_body(cap: ANIPCapability) -> dict[str, Any]:
    """Build OpenAPI requestBody from ANIP capability inputs."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for inp in cap.inputs:
        json_type = _TYPE_MAP.get(inp.get("type", "string"), "string")
        prop: dict[str, Any] = {
            "type": json_type,
            "description": inp.get("description", ""),
        }
        if inp.get("type") == "date":
            prop["format"] = "date"
        if "default" in inp and inp["default"] is not None:
            prop["default"] = inp["default"]
        properties[inp["name"]] = prop
        if inp.get("required", True):
            required.append(inp["name"])

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required

    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": schema,
            },
        },
    }
