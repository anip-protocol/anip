"""Mount ANIP routes onto a FastAPI application."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from pydantic import ValidationError

from anip_core import IssueApprovalGrantRequest, failure_status_code
from anip_service import ANIPService, ANIPError, invalid_parameters_failure


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
            return _failure_response({
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
            })
        return graph

    # --- Tokens ---

    @app.post(f"{prefix}/anip/tokens")
    async def issue_token(request: Request):
        issuer = await _extract_issuer(request, service)
        if issuer is None:
            return _auth_failure_token_endpoint()

        # The credential is checked first; a body that is not a JSON object
        # is then invalid_parameters (SPEC.md §6.3).
        body, malformed = await _read_json_object(request)
        if malformed is not None:
            return malformed
        try:
            result = await service.issue_token_as(issuer, body)
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

        # The credential is checked first; a body that is not a JSON object
        # is then invalid_parameters (SPEC.md §6.3).
        body, malformed = await _read_json_object(request)
        if malformed is not None:
            return malformed
        params = body.get("parameters", body)
        client_reference_id = body.get("client_reference_id")
        task_id = body.get("task_id")
        parent_invocation_id = body.get("parent_invocation_id")
        upstream_service = body.get("upstream_service")
        stream = body.get("stream", False)
        approval_grant = body.get("approval_grant")  # v0.23
        requested_effects = body.get("requested_effects")
        if requested_effects is not None and not isinstance(requested_effects, list):
            return _failure_response(invalid_parameters_failure(
                "requested_effects must be an array of canonical effect ids",
                requires="requested_effects as an array of strings",
            ))
        # SPEC.md §4.8 line 1035: session_id for session_bound grants is read
        # from the signed delegation token, NOT from caller-supplied body.

        # One set of arguments for the unary and the streaming call, so the
        # two reach the service's pre-handler checks with the same request.
        invoke_args = dict(
            client_reference_id=client_reference_id,
            task_id=task_id,
            parent_invocation_id=parent_invocation_id,
            upstream_service=upstream_service,
            approval_grant=approval_grant,
            requested_effects=requested_effects,
        )

        if not stream:
            # Unary mode — existing behavior
            result = await service.invoke(capability, token, params, **invoke_args)
            if not result.get("success"):
                status = failure_status_code(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)
            return result

        # Streaming mode — pre-validate streaming support (return JSON 400, not SSE)
        decl = service.get_capability_declaration(capability)
        if decl is not None:
            modes = [m.value if hasattr(m, 'value') else m for m in (decl.response_modes or ["unary"])]  # pyright: ignore[reportAttributeAccessIssue]
            if "streaming" not in modes:
                result = await service.invoke(
                    capability, token, params, stream=True, **invoke_args)
                status = failure_status_code(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)

        # True streaming: asyncio.Queue bridges sink -> SSE generator
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def progress_sink(event: dict) -> None:
            await queue.put({"type": "progress", **event})

        async def run_invoke():
            try:
                result = await service.invoke(
                    capability, token, params,
                    stream=True, _progress_sink=progress_sink, **invoke_args)
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

    # --- Approval grant issuance (v0.23) ---

    @app.post(f"{prefix}/anip/approval_grants")
    async def issue_approval_grant(request: Request):
        # Phase 7.2a — canonical wire surface for grant issuance.
        # Validation order matters: parse + load request first, then enforce
        # approver-scope-for-this-capability. See SPEC.md §4.9.
        result = await _resolve_token(request, service)
        if result is None:
            return _auth_failure_jwt_endpoint()
        if isinstance(result, ANIPError):
            return _error_response(result)
        token = result

        try:
            body = await request.json()
        except Exception:
            return _failure_response(invalid_parameters_failure(
                "request body must be JSON", requires=_JSON_BODY_REQUIRES))

        # Step 2: the body must match the IssueApprovalGrantRequest schema
        # (session_id iff session_bound, one_time max_uses 1, positive
        # expires_in_seconds and max_uses).
        try:
            parsed = IssueApprovalGrantRequest.model_validate(body, strict=True)
        except ValidationError as exc:
            detail = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'body'}: {err['msg']}"
                for err in exc.errors()
            )
            return _failure_response(invalid_parameters_failure(
                detail, requires="a body that matches the IssueApprovalGrantRequest schema"))
        approval_request_id = parsed.approval_request_id
        grant_type = parsed.grant_type

        # Load the approval_request first so we can check approver authority
        # against the right capability.
        approval_request = await service._storage.get_approval_request(approval_request_id)
        if approval_request is None:
            return _failure_response({
                "type": "approval_request_not_found",
                "detail": f"unknown approval_request_id={approval_request_id!r}",
                "resolution": {
                    "action": "check_manifest",
                    "recovery_class": "revalidate_then_retry",
                },
            })

        # Step 4: request state is checked BEFORE approver authority, so a
        # decided or expired request answers the same to every caller.
        if approval_request["status"] != "pending":
            return _error_response(ANIPError(
                "approval_request_already_decided",
                f"approval_request_id={approval_request_id!r} "
                f"status={approval_request['status']!r}",
            ))
        if approval_request["expires_at"] <= datetime.now(timezone.utc).isoformat():
            return _error_response(ANIPError(
                "approval_request_expired",
                f"approval_request_id={approval_request_id!r} "
                f"expired at {approval_request['expires_at']}",
            ))

        # Step 5: approver authority. Token scope must contain
        # approver:<capability> OR a service-defined approver scope covering
        # that capability. The reference implementation accepts any of:
        # - "approver:*" (all capabilities)
        # - "approver:<request.capability>" (specific)
        target_capability = approval_request["capability"]
        token_scopes = list(token.scope)
        approver_scopes = {f"approver:*", f"approver:{target_capability}"}
        if not any(s in approver_scopes for s in token_scopes):
            return _failure_response({
                "type": "approver_not_authorized",
                "detail": f"token lacks approver scope for capability {target_capability!r}",
                "resolution": {
                    "action": "request_broader_scope",
                    "recovery_class": "redelegation_then_retry",
                    "requires": f"scope += approver:{target_capability}",
                },
            })

        approver_principal = {
            "subject": token.subject,
            "root_principal": token.root_principal,
        }
        try:
            grant = await service.issue_approval_grant(
                approval_request_id,
                grant_type=grant_type,
                approver_principal=approver_principal,
                expires_in_seconds=parsed.expires_in_seconds,
                max_uses=parsed.max_uses,
                session_id=parsed.session_id,
            )
        except ANIPError as e:
            return _error_response(e)

        return grant

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
            return _failure_response({
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
            })
        return result

    # --- Health ---
    if health_endpoint:
        @app.get("/-/health")
        def health():
            return service.get_health()


async def _extract_issuer(request: Request, service: ANIPService):
    """Authenticate the caller of the token endpoint.

    Accepts the bootstrap credential, or a delegation token issued by this
    service. A token authenticates as its *subject* (the holder), which is
    what allows legitimate sub-delegation via ``parent_token``; the service
    refuses root issuance for such callers.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return await service.authenticate_issuer(auth[7:].strip())


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


_JSON_BODY_REQUIRES = "a JSON object as the request body"


def _failure_response(failure: dict) -> JSONResponse:
    """A failure object with the HTTP status of its type (SPEC.md §6.3)."""
    return JSONResponse(
        {"success": False, "failure": failure},
        status_code=failure_status_code(failure.get("type")),
    )


async def _read_json_object(request: Request) -> tuple[dict, JSONResponse | None]:
    """Read the request body as a JSON object.

    Returns ``(body, None)``, or ``({}, response)`` with an
    ``invalid_parameters`` failure when the body is not JSON or not an object.
    """
    try:
        body = await request.json()
    except Exception:
        return {}, _failure_response(invalid_parameters_failure(
            "request body must be JSON", requires=_JSON_BODY_REQUIRES))
    if not isinstance(body, dict):
        return {}, _failure_response(invalid_parameters_failure(
            "request body must be a JSON object", requires=_JSON_BODY_REQUIRES))
    return body, None


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
    "invalid_parameters": {
        "action": "retry_now",
        "recovery_class": "retry_now",
        "requires": "a request that matches the endpoint's schema",
        "grantable_by": None,
        "estimated_availability": None,
    },
}


def _error_response(error: ANIPError) -> JSONResponse:
    """Map an ANIPError to a JSONResponse."""
    resolution = error.resolution or _DEFAULT_RESOLUTIONS.get(
        error.error_type,
        {"action": "contact_service_owner", "recovery_class": "terminal", "requires": None, "grantable_by": None, "estimated_availability": None},
    )
    return _failure_response({
        "type": error.error_type,
        "detail": error.detail,
        "resolution": resolution,
        # The same invalid request cannot succeed (SPEC.md §6.3).
        "retry": False if error.error_type == "invalid_parameters" else error.retry,
    })


def _auth_failure_token_endpoint() -> JSONResponse:
    """Structured auth failure for POST /anip/tokens (credentials required)."""
    return _failure_response({
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
    })


def _auth_failure_jwt_endpoint() -> JSONResponse:
    """Structured auth failure for JWT-authenticated endpoints (no header)."""
    return _failure_response({
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
    })
