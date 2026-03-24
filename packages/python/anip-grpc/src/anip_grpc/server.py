"""ANIP gRPC transport server — maps gRPC RPCs to ANIPService methods."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Ensure generated stubs can resolve `from anip.v1 import anip_pb2`
_generated_dir = str(Path(__file__).parent / "generated")
if _generated_dir not in sys.path:
    sys.path.insert(0, _generated_dir)

import grpc  # noqa: E402
from concurrent import futures  # noqa: E402

from anip_service import ANIPService  # noqa: E402
from anip_service.types import ANIPError  # noqa: E402

from anip_grpc.generated.anip.v1 import anip_pb2  # noqa: E402
from anip_grpc.generated.anip.v1 import anip_pb2_grpc  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_bearer(context: grpc.ServicerContext) -> str | None:
    """Extract a bearer token from gRPC call metadata."""
    for key, value in context.invocation_metadata():
        if key == "authorization" and value.startswith("Bearer "):
            return value[7:].strip()
    return None


def _make_anip_failure(failure: dict[str, Any]) -> anip_pb2.AnipFailure:
    """Build a protobuf AnipFailure from a dict."""
    resolution = failure.get("resolution")
    resolution_json = ""
    if resolution is not None:
        resolution_json = json.dumps(resolution) if not isinstance(resolution, str) else resolution
    return anip_pb2.AnipFailure(
        type=failure.get("type", ""),
        detail=failure.get("detail", ""),
        resolution_json=resolution_json,
        retry=failure.get("retry", False),
    )


def _run_async(coro):
    """Run an async coroutine from a sync gRPC servicer method."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside a running loop — create a new one in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Servicer
# ---------------------------------------------------------------------------

class AnipGrpcServicer(anip_pb2_grpc.AnipServiceServicer):
    """gRPC servicer that delegates to an ANIPService instance."""

    def __init__(self, service: ANIPService) -> None:
        self._service = service

    # --- Public RPCs (no auth) ---

    def Discovery(self, request, context):
        result = self._service.get_discovery()
        return anip_pb2.DiscoveryResponse(json=json.dumps(result))

    def Manifest(self, request, context):
        body_bytes, signature = self._service.get_signed_manifest()
        return anip_pb2.ManifestResponse(
            manifest_json=body_bytes.decode("utf-8"),
            signature=signature,
        )

    def Jwks(self, request, context):
        result = self._service.get_jwks()
        return anip_pb2.JwksResponse(json=json.dumps(result))

    def ListCheckpoints(self, request, context):
        limit = request.limit or 10
        result = _run_async(self._service.get_checkpoints(limit))
        return anip_pb2.ListCheckpointsResponse(json=json.dumps(result))

    def GetCheckpoint(self, request, context):
        checkpoint_id = request.id
        if not checkpoint_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Missing checkpoint id")

        options: dict[str, Any] = {}
        if request.include_proof:
            options["include_proof"] = True
        if request.leaf_index:
            options["leaf_index"] = request.leaf_index
        if request.consistency_from:
            options["consistency_from"] = request.consistency_from

        result = _run_async(self._service.get_checkpoint(checkpoint_id, options))
        if result is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Checkpoint not found: {checkpoint_id}")

        return anip_pb2.GetCheckpointResponse(json=json.dumps(result))

    # --- Bootstrap or JWT auth ---

    def IssueToken(self, request, context):
        bearer = _extract_bearer(context)
        if bearer is None:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization bearer token")

        # Try bootstrap auth (API key) first, then ANIP JWT for sub-delegation
        principal = _run_async(self._service.authenticate_bearer(bearer))
        if principal is None:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Bearer token not recognized")

        # Build the token request body from protobuf fields
        body: dict[str, Any] = {}
        if request.subject:
            body["subject"] = request.subject
        if request.scope:
            body["scope"] = list(request.scope)
        if request.capability:
            body["capability"] = request.capability
        if request.purpose_parameters_json:
            body["purpose_parameters"] = json.loads(request.purpose_parameters_json)
        if request.parent_token:
            body["parent_token"] = request.parent_token
        if request.ttl_hours:
            body["ttl_hours"] = request.ttl_hours
        if request.caller_class:
            body["caller_class"] = request.caller_class

        try:
            result = _run_async(self._service.issue_token(principal, body))
        except ANIPError as exc:
            return anip_pb2.IssueTokenResponse(
                issued=False,
                failure=anip_pb2.AnipFailure(
                    type=exc.error_type,
                    detail=exc.detail,
                    retry=exc.retry,
                ),
            )

        return anip_pb2.IssueTokenResponse(
            issued=result.get("issued", True),
            token_id=result.get("token_id", ""),
            token=result.get("token", ""),
            expires=result.get("expires", ""),
        )

    # --- JWT auth ---

    def _resolve_jwt(self, context):
        """Extract and verify a JWT bearer token. Aborts if missing/invalid."""
        bearer = _extract_bearer(context)
        if bearer is None:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Missing authorization bearer token")
        try:
            return _run_async(self._service.resolve_bearer_token(bearer))
        except ANIPError as exc:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, exc.detail)

    def Permissions(self, request, context):
        token = self._resolve_jwt(context)
        perm = self._service.discover_permissions(token)
        perm_dict = perm.model_dump() if hasattr(perm, "model_dump") else perm
        return anip_pb2.PermissionsResponse(
            success=True,
            json=json.dumps(perm_dict),
        )

    def Invoke(self, request, context):
        token = self._resolve_jwt(context)

        capability = request.capability
        parameters = json.loads(request.parameters_json) if request.parameters_json else {}
        client_reference_id = request.client_reference_id or None

        try:
            result = _run_async(self._service.invoke(
                capability, token, parameters,
                client_reference_id=client_reference_id,
            ))
        except ANIPError as exc:
            return anip_pb2.InvokeResponse(
                success=False,
                client_reference_id=client_reference_id or "",
                failure=anip_pb2.AnipFailure(
                    type=exc.error_type,
                    detail=exc.detail,
                    retry=exc.retry,
                ),
            )

        # The service returns a dict with success, result, invocation_id, etc.
        success = result.get("success", True)
        resp = anip_pb2.InvokeResponse(
            success=success,
            invocation_id=result.get("invocation_id", ""),
            client_reference_id=result.get("client_reference_id", "") or "",
        )

        if success:
            result_data = result.get("result")
            if result_data is not None:
                resp.result_json = json.dumps(result_data)
            cost_actual = result.get("cost_actual")
            if cost_actual is not None:
                resp.cost_actual_json = json.dumps(cost_actual)
        else:
            failure = result.get("failure")
            if failure:
                resp.failure.CopyFrom(_make_anip_failure(failure))

        return resp

    def InvokeStream(self, request, context):
        token = self._resolve_jwt(context)

        capability = request.capability
        parameters = json.loads(request.parameters_json) if request.parameters_json else {}
        client_reference_id = request.client_reference_id or None

        # Collect progress events, then yield them followed by the final event
        progress_events: list[dict[str, Any]] = []

        async def _do_stream_invoke():
            async def _progress_sink(payload: dict[str, Any]) -> None:
                progress_events.append(payload)

            return await self._service.invoke(
                capability, token, parameters,
                client_reference_id=client_reference_id,
                stream=True,
                _progress_sink=_progress_sink,
            )

        try:
            result = _run_async(_do_stream_invoke())
        except ANIPError as exc:
            yield anip_pb2.InvokeEvent(
                failed=anip_pb2.FailedEvent(
                    invocation_id="",
                    client_reference_id=client_reference_id or "",
                    failure=anip_pb2.AnipFailure(
                        type=exc.error_type,
                        detail=exc.detail,
                        retry=exc.retry,
                    ),
                ),
            )
            return

        # Yield progress events
        invocation_id = result.get("invocation_id", "")
        for evt in progress_events:
            payload = evt.get("payload", evt)
            yield anip_pb2.InvokeEvent(
                progress=anip_pb2.ProgressEvent(
                    invocation_id=evt.get("invocation_id", invocation_id),
                    payload_json=json.dumps(payload),
                ),
            )

        # Yield final completed or failed event
        success = result.get("success", True)
        if success:
            result_data = result.get("result")
            cost_actual = result.get("cost_actual")
            yield anip_pb2.InvokeEvent(
                completed=anip_pb2.CompletedEvent(
                    invocation_id=invocation_id,
                    client_reference_id=result.get("client_reference_id", "") or "",
                    result_json=json.dumps(result_data) if result_data is not None else "",
                    cost_actual_json=json.dumps(cost_actual) if cost_actual is not None else "",
                ),
            )
        else:
            failure = result.get("failure", {})
            yield anip_pb2.InvokeEvent(
                failed=anip_pb2.FailedEvent(
                    invocation_id=invocation_id,
                    client_reference_id=result.get("client_reference_id", "") or "",
                    failure=_make_anip_failure(failure),
                ),
            )

    def QueryAudit(self, request, context):
        token = self._resolve_jwt(context)

        filters: dict[str, Any] = {}
        if request.capability:
            filters["capability"] = request.capability
        if request.since:
            filters["since"] = request.since
        if request.invocation_id:
            filters["invocation_id"] = request.invocation_id
        if request.client_reference_id:
            filters["client_reference_id"] = request.client_reference_id
        if request.event_class:
            filters["event_class"] = request.event_class
        if request.limit:
            filters["limit"] = request.limit

        try:
            result = _run_async(self._service.query_audit(token, filters))
        except ANIPError as exc:
            return anip_pb2.QueryAuditResponse(
                success=False,
                failure=anip_pb2.AnipFailure(
                    type=exc.error_type,
                    detail=exc.detail,
                    retry=exc.retry,
                ),
            )

        return anip_pb2.QueryAuditResponse(
            success=True,
            json=json.dumps(result),
        )


# ---------------------------------------------------------------------------
# serve_grpc entry point
# ---------------------------------------------------------------------------

def serve_grpc(service: ANIPService, port: int = 50051) -> None:
    """Start a gRPC server wrapping an ANIPService.

    Blocks until the server is terminated. Runs the ANIP service's
    async event loop in a background thread so background tasks
    (retention, checkpoints, aggregation) stay alive alongside the
    blocking gRPC server.
    """
    import threading

    # Create a persistent event loop for the ANIP service's async tasks.
    loop = asyncio.new_event_loop()

    def _run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    loop_thread = threading.Thread(target=_run_loop, daemon=True)
    loop_thread.start()

    # Start the ANIP service on the persistent loop.
    future = asyncio.run_coroutine_threadsafe(service.start(), loop)
    future.result()  # Wait for start to complete

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    anip_pb2_grpc.add_AnipServiceServicer_to_server(
        AnipGrpcServicer(service), grpc_server,
    )
    grpc_server.add_insecure_port(f"[::]:{port}")
    grpc_server.start()

    try:
        grpc_server.wait_for_termination()
    finally:
        fut = asyncio.run_coroutine_threadsafe(service.shutdown(), loop)
        fut.result()
        service.stop()
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=5)
