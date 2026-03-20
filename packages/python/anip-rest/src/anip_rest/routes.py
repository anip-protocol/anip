"""ANIP REST bindings — mount RESTful API endpoints on a FastAPI app."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from anip_service import ANIPService, ANIPError
from .translation import generate_routes, generate_openapi_spec, RouteOverride, RESTRoute

_FAILURE_STATUS = {
    "authentication_required": 401,
    "invalid_token": 401,
    "scope_insufficient": 403,
    "budget_exceeded": 403,
    "purpose_mismatch": 403,
    "unknown_capability": 404,
    "invalid_parameters": 400,
    "unavailable": 409,
    "internal_error": 500,
}


async def _resolve_auth(
    request: Request,
    service: ANIPService,
    capability_name: str,
):
    """Resolve auth from Authorization header.

    Order: try JWT first, then API key. authenticate_bearer() also
    accepts valid JWTs internally, so calling it first would misidentify
    a caller-supplied JWT as an API key and issue a synthetic token.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer = auth[7:].strip()

    # Try as JWT first — preserves original delegation chain
    jwt_error = None
    try:
        return await service.resolve_bearer_token(bearer)
    except ANIPError as e:
        jwt_error = e  # Stash the structured error

    # Try as API key — only if JWT failed
    principal = await service.authenticate_bearer(bearer)
    if principal:
        cap_decl = service.get_capability_declaration(capability_name)
        min_scope = cap_decl.minimum_scope if cap_decl else []
        token_result = await service.issue_token(principal, {
            "subject": "adapter:anip-rest",
            "scope": min_scope if min_scope else ["*"],
            "capability": capability_name,
            "purpose_parameters": {"source": "rest"},
        })
        jwt_str = token_result["token"]
        return await service.resolve_bearer_token(jwt_str)

    # Neither JWT nor API key — surface the original JWT error
    if jwt_error:
        raise jwt_error
    return None


def _error_response(error: ANIPError) -> JSONResponse:
    status = _FAILURE_STATUS.get(error.error_type, 400)
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": error.error_type,
                "detail": error.detail,
                "resolution": error.resolution,
                "retry": error.retry,
            },
        },
        status_code=status,
    )


def _convert_query_params(query: dict[str, str], decl) -> dict[str, Any]:
    """Convert query string values to appropriate types."""
    type_map = {inp.name: inp.type for inp in decl.inputs}
    result = {}
    for key, value in query.items():
        t = type_map.get(key)
        if t == "integer":
            result[key] = int(value)
        elif t == "number":
            result[key] = float(value)
        elif t == "boolean":
            result[key] = value.lower() == "true"
        else:
            result[key] = value
    return result


def mount_anip_rest(
    app: FastAPI,
    service: ANIPService,
    *,
    routes: dict[str, RouteOverride] | None = None,
    prefix: str = "",
) -> None:
    """Mount RESTful API endpoints on a FastAPI app.

    Args:
        app: FastAPI app instance.
        service: ANIPService to expose.
        routes: Optional route overrides per capability.
        prefix: URL prefix for all REST routes.
    """
    manifest = service.get_manifest()
    capabilities = {}
    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if decl:
            capabilities[name] = decl

    rest_routes = generate_routes(capabilities, routes)
    service_id = (
        getattr(manifest.service_identity, "id", None)
        if manifest.service_identity
        else None
    ) or "anip-service"
    openapi_spec = generate_openapi_spec(service_id, rest_routes)

    @app.get(f"{prefix}/rest/openapi.json")
    async def get_rest_openapi():
        return openapi_spec

    @app.get(f"{prefix}/rest/docs", response_class=HTMLResponse)
    async def get_rest_docs():
        return f"""<!DOCTYPE html>
<html><head><title>ANIP REST API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({{ url: "{prefix}/rest/openapi.json", dom_id: "#swagger-ui" }});</script>
</body></html>"""

    for route in rest_routes:
        _register_route(app, service, route, prefix)


def _register_route(app: FastAPI, service: ANIPService, route: RESTRoute, prefix: str) -> None:
    """Register a single capability as a REST endpoint."""
    path = f"{prefix}{route.path}"

    async def handler(request: Request) -> JSONResponse:
        try:
            token = await _resolve_auth(request, service, route.capability_name)
        except ANIPError as e:
            return _error_response(e)

        if token is None:
            return JSONResponse(
                {
                    "success": False,
                    "failure": {
                        "type": "authentication_required",
                        "detail": "Authorization header with Bearer token or API key required",
                        "resolution": {"action": "provide_credentials"},
                        "retry": True,
                    },
                },
                status_code=401,
            )

        if route.method == "GET":
            params = _convert_query_params(dict(request.query_params), route.declaration)
        else:
            body = await request.json()
            params = body.get("parameters", body)

        client_reference_id = request.headers.get("x-client-reference-id")

        try:
            result = await service.invoke(
                route.capability_name, token, params,
                client_reference_id=client_reference_id,
            )
            return JSONResponse(result)
        except ANIPError as e:
            return _error_response(e)

    if route.method == "GET":
        app.get(path)(handler)
    else:
        app.post(path)(handler)
