"""Mount ANIP routes onto a FastAPI application."""
from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from anip_service import ANIPService, ANIPError


def mount_anip(
    app: FastAPI,
    service: ANIPService,
    prefix: str = "",
) -> None:
    """Mount all ANIP protocol routes onto a FastAPI app.

    Routes:
        GET  {prefix}/.well-known/anip          → discovery
        GET  {prefix}/.well-known/jwks.json     → JWKS
        GET  {prefix}/anip/manifest             → full manifest (signed)
        POST {prefix}/anip/tokens               → issue token
        POST {prefix}/anip/permissions           → discover permissions
        POST {prefix}/anip/invoke/{capability}   → invoke capability
        POST {prefix}/anip/audit                → query audit log
        GET  {prefix}/anip/checkpoints          → list checkpoints
        GET  {prefix}/anip/checkpoints/{id}     → get checkpoint
    """

    # --- Lifecycle: wire start/stop into FastAPI events ---

    @app.on_event("startup")
    async def _anip_startup():
        service.start()

    @app.on_event("shutdown")
    async def _anip_shutdown():
        service.stop()

    # --- Discovery & Identity ---

    @app.get(f"{prefix}/.well-known/anip")
    async def discovery():
        return service.get_discovery()

    @app.get(f"{prefix}/.well-known/jwks.json")
    async def jwks():
        return service.get_jwks()

    @app.get(f"{prefix}/anip/manifest")
    async def manifest():
        body_bytes, signature = service.get_signed_manifest()
        return Response(
            content=body_bytes,
            media_type="application/json",
            headers={"X-ANIP-Signature": signature},
        )

    # --- Tokens ---

    @app.post(f"{prefix}/anip/tokens")
    async def issue_token(request: Request):
        principal = _extract_principal(request, service)
        if principal is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        body = await request.json()
        try:
            result = service.issue_token(principal, body)
            return result
        except ANIPError as e:
            return _error_response(e)

    # --- Permissions ---

    @app.post(f"{prefix}/anip/permissions")
    async def permissions(request: Request):
        token = _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        return service.discover_permissions(token)

    # --- Invoke ---

    @app.post(f"{prefix}/anip/invoke/{{capability}}")
    async def invoke(capability: str, request: Request):
        token = _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        body = await request.json()
        params = body.get("parameters", body)
        client_reference_id = body.get("client_reference_id")
        result = service.invoke(
            capability, token, params,
            client_reference_id=client_reference_id,
        )

        if not result.get("success"):
            status = _failure_status(result.get("failure", {}).get("type"))
            return JSONResponse(result, status_code=status)

        return result

    # --- Audit ---

    @app.post(f"{prefix}/anip/audit")
    async def audit(request: Request):
        token = _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        filters = {
            "capability": request.query_params.get("capability"),
            "since": request.query_params.get("since"),
            "invocation_id": request.query_params.get("invocation_id"),
            "client_reference_id": request.query_params.get("client_reference_id"),
            "limit": int(request.query_params.get("limit", "50")),
        }
        return service.query_audit(token, filters)

    # --- Checkpoints ---

    @app.get(f"{prefix}/anip/checkpoints")
    async def list_checkpoints(request: Request):
        limit = int(request.query_params.get("limit", "10"))
        return service.get_checkpoints(limit)

    @app.get(f"{prefix}/anip/checkpoints/{{checkpoint_id}}")
    async def get_checkpoint(checkpoint_id: str, request: Request):
        options = {
            "include_proof": request.query_params.get("include_proof") == "true",
            "leaf_index": request.query_params.get("leaf_index"),
            "consistency_from": request.query_params.get("consistency_from"),
        }
        result = service.get_checkpoint(checkpoint_id, options)
        if result is None:
            return JSONResponse({"error": "Checkpoint not found"}, status_code=404)
        return result


def _extract_principal(request: Request, service: ANIPService) -> str | None:
    """Extract authenticated principal from the request.

    Uses service.authenticate_bearer() which tries bootstrap auth (API keys,
    external auth) first, then ANIP JWT verification. This is critical for
    first-token issuance before any ANIP tokens exist.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer_value = auth[7:].strip()
    return service.authenticate_bearer(bearer_value)


def _resolve_token(request: Request, service: ANIPService):
    """Resolve a bearer token from the Authorization header."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_str = auth[7:].strip()
    try:
        return service.resolve_bearer_token(jwt_str)
    except ANIPError:
        return None


def _failure_status(failure_type: str | None) -> int:
    """Map ANIP failure types to HTTP status codes."""
    mapping = {
        "invalid_token": 401,
        "token_expired": 401,
        "scope_insufficient": 403,
        "insufficient_authority": 403,
        "purpose_mismatch": 403,
        "unknown_capability": 404,
        "not_found": 404,
        "unavailable": 409,
        "concurrent_lock": 409,
        "internal_error": 500,
    }
    return mapping.get(failure_type or "", 400)


def _error_response(error: ANIPError) -> JSONResponse:
    """Map an ANIPError to a JSONResponse."""
    status = _failure_status(error.error_type)
    return JSONResponse(
        {"success": False, "failure": {"type": error.error_type, "detail": error.detail}},
        status_code=status,
    )
