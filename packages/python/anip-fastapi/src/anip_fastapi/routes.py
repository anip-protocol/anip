"""Mount ANIP routes onto a FastAPI application."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from anip_service import ANIPService, ANIPError


def mount_anip(
    app: FastAPI,
    service: ANIPService,
    prefix: str = "",
    *,
    health_endpoint: bool = False,
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
    app.router.on_startup.append(service.start)
    app.router.on_shutdown.append(service.shutdown)  # async flush first
    app.router.on_shutdown.append(service.stop)       # sync timer cleanup

    # --- Discovery & Identity ---

    @app.get(f"{prefix}/.well-known/anip")
    async def discovery(request: Request):
        base_url = str(request.base_url).rstrip("/")
        return service.get_discovery(base_url=base_url)

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

    # --- Graph ---

    @app.get(f"{prefix}/anip/graph/{{capability}}")
    async def get_graph(capability: str):
        graph = service.get_capability_graph(capability)
        if graph is None:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "failure": {
                        "type": "not_found",
                        "detail": f"Capability '{capability}' not found",
                        "resolution": {
                            "action": "check_manifest",
                            "recovery_class": "revalidate_then_retry",
                            "requires": "Valid capability name from GET /anip/manifest",
                            "grantable_by": None,
                            "estimated_availability": None,
                        },
                        "retry": False,
                    },
                },
            )
        return graph

    # --- Tokens ---

    @app.post(f"{prefix}/anip/tokens")
    async def issue_token(request: Request):
        principal = await _extract_principal(request, service)
        if principal is None:
            return _auth_failure_token_endpoint()

        body = await request.json()
        try:
            result = await service.issue_token(principal, body)
            return result
        except ANIPError as e:
            return _error_response(e)

    # --- Permissions ---

    @app.post(f"{prefix}/anip/permissions")
    async def permissions(request: Request):
        result = await _resolve_token(request, service)
        if result is None:
            return _auth_failure_jwt_endpoint()
        if isinstance(result, ANIPError):
            return _error_response(result)
        token = result
        return service.discover_permissions(token)

    # --- Invoke ---

    @app.post(f"{prefix}/anip/invoke/{{capability}}")
    async def invoke(capability: str, request: Request):
        result = await _resolve_token(request, service)
        if result is None:
            return _auth_failure_jwt_endpoint()
        if isinstance(result, ANIPError):
            return _error_response(result)
        token = result

        body = await request.json()
        params = body.get("parameters", body)
        client_reference_id = body.get("client_reference_id")
        task_id = body.get("task_id")
        parent_invocation_id = body.get("parent_invocation_id")
        upstream_service = body.get("upstream_service")
        stream = body.get("stream", False)

        if not stream:
            # Unary mode — existing behavior
            result = await service.invoke(
                capability, token, params,
                client_reference_id=client_reference_id,
                task_id=task_id,
                parent_invocation_id=parent_invocation_id,
                upstream_service=upstream_service,
            )
            if not result.get("success"):
                status = _failure_status(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)
            return result

        # Streaming mode — pre-validate streaming support (return JSON 400, not SSE)
        decl = service.get_capability_declaration(capability)
        if decl is not None:
            modes = [m.value if hasattr(m, 'value') else m for m in (decl.response_modes or ["unary"])]  # pyright: ignore[reportAttributeAccessIssue]
            if "streaming" not in modes:
                result = await service.invoke(
                    capability, token, params,
                    client_reference_id=client_reference_id,
                    task_id=task_id,
                    parent_invocation_id=parent_invocation_id,
                    upstream_service=upstream_service,
                    stream=True,
                )
                status = _failure_status(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)

        # True streaming: asyncio.Queue bridges sink -> SSE generator
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def progress_sink(event: dict) -> None:
            await queue.put({"type": "progress", **event})

        async def run_invoke():
            try:
                result = await service.invoke(
                    capability, token, params,
                    client_reference_id=client_reference_id,
                    task_id=task_id,
                    parent_invocation_id=parent_invocation_id,
                    upstream_service=upstream_service,
                    stream=True,
                    _progress_sink=progress_sink,
                )
                await queue.put({"type": "terminal", "result": result})
            except Exception as e:
                await queue.put({"type": "error", "detail": "Internal error"})

        async def sse_generator():
            task = asyncio.create_task(run_invoke())
            try:
                while True:
                    event = await queue.get()
                    ts = datetime.now(timezone.utc).isoformat()

                    if event["type"] == "progress":
                        event_data = {
                            "invocation_id": event["invocation_id"],
                            "client_reference_id": event.get("client_reference_id"),
                            "timestamp": ts,
                            "payload": event["payload"],
                        }
                        yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

                    elif event["type"] == "terminal":
                        result = event["result"]
                        if result.get("success"):
                            event_data = {
                                "invocation_id": result["invocation_id"],
                                "client_reference_id": result.get("client_reference_id"),
                                "timestamp": ts,
                                "success": True,
                                "result": result.get("result"),
                                "cost_actual": result.get("cost_actual"),
                            }
                            if "stream_summary" in result:
                                event_data["stream_summary"] = result["stream_summary"]
                            yield f"event: completed\ndata: {json.dumps(event_data)}\n\n"
                        else:
                            event_data = {
                                "invocation_id": result.get("invocation_id"),
                                "client_reference_id": result.get("client_reference_id"),
                                "timestamp": ts,
                                "success": False,
                                "failure": result.get("failure"),
                            }
                            if "stream_summary" in result:
                                event_data["stream_summary"] = result["stream_summary"]
                            yield f"event: failed\ndata: {json.dumps(event_data)}\n\n"
                        break

                    elif event["type"] == "error":
                        event_data = {
                            "timestamp": ts,
                            "success": False,
                            "failure": {"type": "internal_error", "detail": event["detail"]},
                        }
                        yield f"event: failed\ndata: {json.dumps(event_data)}\n\n"
                        break
            finally:
                await task

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # --- Audit ---

    @app.post(f"{prefix}/anip/audit")
    async def audit(request: Request):
        result = await _resolve_token(request, service)
        if result is None:
            return _auth_failure_jwt_endpoint()
        if isinstance(result, ANIPError):
            return _error_response(result)
        token = result

        filters = {
            "capability": request.query_params.get("capability"),
            "since": request.query_params.get("since"),
            "invocation_id": request.query_params.get("invocation_id"),
            "client_reference_id": request.query_params.get("client_reference_id"),
            "task_id": request.query_params.get("task_id"),
            "parent_invocation_id": request.query_params.get("parent_invocation_id"),
            "event_class": request.query_params.get("event_class"),
            "limit": int(request.query_params.get("limit", "50")),
        }
        return await service.query_audit(token, filters)

    # --- Checkpoints ---

    @app.get(f"{prefix}/anip/checkpoints")
    async def list_checkpoints(request: Request):
        limit = int(request.query_params.get("limit", "10"))
        return await service.get_checkpoints(limit)

    @app.get(f"{prefix}/anip/checkpoints/{{checkpoint_id}}")
    async def get_checkpoint(checkpoint_id: str, request: Request):
        options = {
            "include_proof": request.query_params.get("include_proof") == "true",
            "leaf_index": request.query_params.get("leaf_index"),
            "consistency_from": request.query_params.get("consistency_from"),
        }
        result = await service.get_checkpoint(checkpoint_id, options)
        if result is None:
            return JSONResponse(
                {
                    "success": False,
                    "failure": {
                        "type": "not_found",
                        "detail": f"Checkpoint {checkpoint_id} not found",
                        "resolution": {
                            "action": "revalidate_state",
                            "recovery_class": "revalidate_then_retry",
                            "requires": "GET /anip/checkpoints to find valid checkpoint IDs",
                            "grantable_by": None,
                            "estimated_availability": None,
                        },
                        "retry": False,
                    },
                },
                status_code=404,
            )
        return result

    # --- Health ---
    if health_endpoint:
        @app.get("/-/health")
        def health():
            return service.get_health()


async def _extract_principal(request: Request, service: ANIPService) -> str | None:
    """Extract authenticated principal from the request.

    For token issuance, JWT delegation must authenticate as the *current token
    subject*, not the chain root principal. That is what allows legitimate
    sub-delegation via ``parent_token``.

    Order:
    1. Try ANIP JWT first and return ``token.subject``.
    2. Fall back to bootstrap auth (API keys, external auth) for first-token
       issuance before any ANIP tokens exist.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer_value = auth[7:].strip()
    try:
        token = await service.resolve_bearer_token(bearer_value)
        return token.subject
    except ANIPError:
        return await service.authenticate_bearer(bearer_value)


async def _resolve_token(request: Request, service: ANIPService):
    """Resolve a bearer token from the Authorization header.

    Returns:
        DelegationToken if valid, ANIPError if invalid/expired, None if no header.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_str = auth[7:].strip()
    try:
        return await service.resolve_bearer_token(jwt_str)
    except ANIPError as e:
        return e


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
        "concurrent_request_rejected": 409,
        "internal_error": 500,
    }
    return mapping.get(failure_type or "", 400)


_DEFAULT_RESOLUTIONS: dict[str, dict] = {
    "invalid_token": {
        "action": "request_new_delegation",
        "recovery_class": "redelegation_then_retry",
        "requires": "Valid JWT from POST /anip/tokens",
        "grantable_by": None,
        "estimated_availability": None,
    },
    "scope_insufficient": {
        "action": "request_broader_scope",
        "recovery_class": "redelegation_then_retry",
        "requires": "Token with required scope",
        "grantable_by": None,
        "estimated_availability": None,
    },
    "unknown_capability": {
        "action": "check_manifest",
        "recovery_class": "revalidate_then_retry",
        "requires": "Valid capability name from GET /anip/manifest",
        "grantable_by": None,
        "estimated_availability": None,
    },
}


def _error_response(error: ANIPError) -> JSONResponse:
    """Map an ANIPError to a JSONResponse."""
    status = _failure_status(error.error_type)
    resolution = error.resolution or _DEFAULT_RESOLUTIONS.get(
        error.error_type,
        {"action": "contact_service_owner", "recovery_class": "terminal", "requires": None, "grantable_by": None, "estimated_availability": None},
    )
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": error.error_type,
                "detail": error.detail,
                "resolution": resolution,
                "retry": error.retry,
            },
        },
        status_code=status,
    )


def _auth_failure_token_endpoint() -> JSONResponse:
    """Structured auth failure for POST /anip/tokens (credentials required)."""
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": "authentication_required",
                "detail": "A valid API key is required to issue delegation tokens",
                "resolution": {
                    "action": "provide_credentials",
                    "recovery_class": "retry_now",
                    "requires": "API key in Authorization header",
                    "grantable_by": None,
                    "estimated_availability": None,
                },
                "retry": True,
            },
        },
        status_code=401,
    )


def _auth_failure_jwt_endpoint() -> JSONResponse:
    """Structured auth failure for JWT-authenticated endpoints (no header)."""
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": "authentication_required",
                "detail": "A valid delegation token (JWT) is required in the Authorization header",
                "resolution": {
                    "action": "request_new_delegation",
                    "recovery_class": "redelegation_then_retry",
                    "requires": "Bearer token from POST /anip/tokens",
                    "grantable_by": None,
                    "estimated_availability": None,
                },
                "retry": True,
            },
        },
        status_code=401,
    )
