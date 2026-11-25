"""ANIP REST bindings — mount RESTful API endpoints on a FastAPI app."""
from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from anip_core import failure_status_code
from anip_service import ANIPService, ANIPError, INVALID_PARAMETERS_RESOLUTION, invalid_parameters_failure
from .translation import generate_routes, generate_openapi_spec, RouteOverride, RESTRoute

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


def _failure_response(body: dict[str, Any]) -> JSONResponse:
    """A failed response with the HTTP status of its failure type (SPEC.md §6.3)."""
    failure = body.get("failure") or {}
    return JSONResponse(body, status_code=failure_status_code(failure.get("type")))


def _error_response(error: ANIPError) -> JSONResponse:
    resolution = error.resolution
    retry = error.retry
    if error.error_type == "invalid_parameters":
        resolution = resolution or dict(INVALID_PARAMETERS_RESOLUTION)
        retry = False
    return _failure_response({
        "success": False,
        "failure": {
            "type": error.error_type,
            "detail": error.detail,
            "resolution": resolution,
            "retry": retry,
        },
    })


_JSON_BODY_REQUIRES = "a JSON object as the request body"


def _convert_query_value(value: str, declared_type: str | None) -> Any:
    """Read a query-string value as the declared primitive type.

    A value that cannot be read as that type is passed on as the string it
    is, so the service refuses it as ``invalid_parameters`` (SPEC.md §6.3).
    """
    if declared_type in ("integer", "number"):
        try:
            if declared_type == "integer":
                try:
                    return int(value)
                except ValueError:
                    pass
            number = float(value)
        except ValueError:
            return value
        return number if math.isfinite(number) else value
    if declared_type == "boolean":
        return {"true": True, "false": False}.get(value.lower(), value)
    return value


def _convert_query_params(query: dict[str, str], decl) -> dict[str, Any]:
    """Convert query string values to appropriate types."""
    type_map = {inp.name: inp.type for inp in decl.inputs}
    return {key: _convert_query_value(value, type_map.get(key)) for key, value in query.items()}


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
            return _failure_response({
                "success": False,
                "failure": {
                    "type": "authentication_required",
                    "detail": "Authorization header with Bearer token or API key required",
                    "resolution": {"action": "provide_credentials", "recovery_class": "retry_now"},
                    "retry": True,
                },
            })

        if route.method == "GET":
            params = _convert_query_params(dict(request.query_params), route.declaration)
        else:
            # The credential is checked first; a body that is not a JSON
            # object is then invalid_parameters (SPEC.md §6.3).
            try:
                body = await request.json()
            except Exception:
                body = None
                detail = "request body must be JSON"
            else:
                detail = "request body must be a JSON object"
            if not isinstance(body, dict):
                return _failure_response({
                    "success": False,
                    "failure": invalid_parameters_failure(detail, requires=_JSON_BODY_REQUIRES),
                })
            params = body.get("parameters", body)

        client_reference_id = request.headers.get("x-client-reference-id")

        try:
            result = await service.invoke(
                route.capability_name, token, params,
                client_reference_id=client_reference_id,
            )
            if not result.get("success"):
                return _failure_response(result)
            return JSONResponse(result)
        except ANIPError as e:
            return _error_response(e)

    if route.method == "GET":
        app.get(path)(handler)
    else:
        app.post(path)(handler)
