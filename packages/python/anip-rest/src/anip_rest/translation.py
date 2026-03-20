"""ANIP -> REST translation layer.

Generates OpenAPI 3.1 specs and route mappings from ANIP capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anip_core.models import CapabilityDeclaration

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "airport_code": "string",
}


@dataclass
class RouteOverride:
    path: str
    method: str


@dataclass
class RESTRoute:
    capability_name: str
    path: str
    method: str  # "GET" or "POST"
    declaration: CapabilityDeclaration


def generate_routes(
    capabilities: dict[str, CapabilityDeclaration],
    overrides: dict[str, RouteOverride] | None = None,
) -> list[RESTRoute]:
    """Generate REST routes from service capabilities."""
    routes = []
    for name, decl in capabilities.items():
        override = (overrides or {}).get(name)
        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        routes.append(RESTRoute(
            capability_name=name,
            path=override.path if override else f"/api/{name}",
            method=(override.method if override else ("GET" if se_type == "read" else "POST")).upper(),
            declaration=decl,
        ))
    return routes


def generate_openapi_spec(
    service_id: str,
    routes: list[RESTRoute],
) -> dict[str, Any]:
    """Generate a complete OpenAPI 3.1 spec from routes."""
    paths: dict[str, Any] = {}
    for route in routes:
        method = route.method.lower()
        decl = route.declaration
        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        financial = decl.cost is not None and decl.cost.financial is not None

        operation: dict[str, Any] = {
            "summary": decl.description,
            "operationId": route.capability_name,
            "responses": {
                "200": {"description": "Success"},
                "401": {"description": "Authentication required"},
                "403": {"description": "Authorization failed"},
                "404": {"description": "Unknown capability"},
            },
            "x-anip-side-effect": se_type,
            "x-anip-minimum-scope": decl.minimum_scope,
            "x-anip-financial": financial,
        }

        if method == "get":
            operation["parameters"] = _build_query_parameters(decl)
        else:
            operation["requestBody"] = _build_request_body(decl)

        paths[route.path] = {method: operation}

    return {
        "openapi": "3.1.0",
        "info": {"title": f"ANIP REST — {service_id}", "version": "1.0"},
        "paths": paths,
    }


def _build_query_parameters(decl: CapabilityDeclaration) -> list[dict]:
    return [
        {
            "name": inp.name,
            "in": "query",
            "required": inp.required,
            "schema": {
                "type": _TYPE_MAP.get(inp.type, "string"),
                **({"format": "date"} if inp.type == "date" else {}),
            },
            "description": inp.description,
        }
        for inp in decl.inputs
    ]


def _build_request_body(decl: CapabilityDeclaration) -> dict:
    properties = {}
    required = []
    for inp in decl.inputs:
        properties[inp.name] = {
            "type": _TYPE_MAP.get(inp.type, "string"),
            "description": inp.description,
        }
        if inp.required:
            required.append(inp.name)
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"type": "object", "properties": properties, **({"required": required} if required else {})},
            },
        },
    }
