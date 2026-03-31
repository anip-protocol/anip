"""ANIP stdio transport server — JSON-RPC 2.0 over stdin/stdout."""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from anip_service import ANIPService
from anip_service.types import ANIPError

from .framing import read_message, write_message
from .protocol import (
    AUTH_ERROR,
    FAILURE_TYPE_TO_CODE,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    NOT_FOUND,
    PARSE_ERROR,
    VALID_METHODS,
    extract_auth,
    make_error,
    make_notification,
    make_response,
    validate_request,
)


class AnipStdioServer:
    """JSON-RPC 2.0 server wrapping an ANIPService for stdio transport."""

    def __init__(self, service: ANIPService) -> None:
        self._service = service

    # --- Public dispatch ---

    async def handle_request(self, msg: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
        """Validate and dispatch a JSON-RPC request to the appropriate handler.

        Returns a single JSON-RPC response dict, or for streaming invocations
        a list of [notification..., response].
        """
        error_desc = validate_request(msg)
        if error_desc is not None:
            return make_error(msg.get("id"), INVALID_REQUEST, error_desc)

        request_id = msg["id"]
        method = msg["method"]
        params = msg.get("params") or {}

        if method not in VALID_METHODS:
            return make_error(request_id, METHOD_NOT_FOUND, f"Unknown method: {method}")

        handler = self._DISPATCH.get(method)
        if handler is None:
            return make_error(request_id, INTERNAL_ERROR, f"No handler for {method}")

        try:
            result = await handler(self, params)
        except ANIPError as exc:
            code = FAILURE_TYPE_TO_CODE.get(exc.error_type, INTERNAL_ERROR)
            return make_error(request_id, code, exc.detail, {
                "type": exc.error_type,
                "detail": exc.detail,
                "retry": exc.retry,
            })
        except Exception as exc:
            return make_error(request_id, INTERNAL_ERROR, str(exc))

        # Streaming invoke returns (notifications, result)
        if isinstance(result, tuple) and len(result) == 2:
            notifications, final_result = result
            messages: list[dict[str, Any]] = list(notifications)
            messages.append(make_response(request_id, final_result))
            return messages

        return make_response(request_id, result)

    # --- Method handlers ---

    async def _handle_anip_discovery(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._service.get_discovery()

    async def _handle_anip_manifest(self, params: dict[str, Any]) -> dict[str, Any]:
        body_bytes, signature = self._service.get_signed_manifest()
        return {"manifest": json.loads(body_bytes), "signature": signature}

    async def _handle_anip_jwks(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._service.get_jwks()

    async def _handle_anip_tokens_issue(self, params: dict[str, Any]) -> dict[str, Any]:
        bearer = extract_auth(params)
        if bearer is None:
            raise ANIPError("authentication_required", "This method requires auth.bearer")

        # Try bootstrap auth (API key) first, then ANIP JWT
        principal = await self._service.authenticate_bearer(bearer)
        if principal is None:
            raise ANIPError("invalid_token", "Bearer token not recognized")

        # Build the token request body from params
        body: dict[str, Any] = {}
        for key in ("subject", "scope", "capability", "purpose_parameters",
                     "parent_token", "ttl_hours", "caller_class"):
            if key in params:
                body[key] = params[key]

        return await self._service.issue_token(principal, body)

    async def _handle_anip_permissions(self, params: dict[str, Any]) -> dict[str, Any]:
        token = await self._resolve_jwt(params)
        perm = self._service.discover_permissions(token)
        return perm.model_dump() if hasattr(perm, "model_dump") else perm

    async def _handle_anip_invoke(
        self, params: dict[str, Any],
    ) -> dict[str, Any] | tuple[list[dict[str, Any]], dict[str, Any]]:
        token = await self._resolve_jwt(params)

        capability = params.get("capability")
        if not capability:
            raise ANIPError("unknown_capability", "Missing 'capability' in params")

        parameters = params.get("parameters", {})
        client_reference_id = params.get("client_reference_id")
        task_id = params.get("task_id")
        parent_invocation_id = params.get("parent_invocation_id")
        stream = params.get("stream", False)

        if stream:
            notifications: list[dict[str, Any]] = []

            async def _progress_sink(payload: dict[str, Any]) -> None:
                notifications.append(
                    make_notification("anip.invoke.progress", payload)
                )

            result = await self._service.invoke(
                capability, token, parameters,
                client_reference_id=client_reference_id,
                task_id=task_id,
                parent_invocation_id=parent_invocation_id,
                stream=True,
                _progress_sink=_progress_sink,
            )
            return (notifications, result)

        result = await self._service.invoke(
            capability, token, parameters,
            client_reference_id=client_reference_id,
            task_id=task_id,
            parent_invocation_id=parent_invocation_id,
        )
        return result

    async def _handle_anip_audit_query(self, params: dict[str, Any]) -> dict[str, Any]:
        token = await self._resolve_jwt(params)

        filters: dict[str, Any] = {}
        for key in ("capability", "since", "invocation_id",
                     "client_reference_id", "task_id",
                     "parent_invocation_id", "event_class", "limit"):
            if key in params:
                filters[key] = params[key]

        return await self._service.query_audit(token, filters)

    async def _handle_anip_checkpoints_list(self, params: dict[str, Any]) -> dict[str, Any]:
        limit = params.get("limit", 10)
        return await self._service.get_checkpoints(limit)

    async def _handle_anip_checkpoints_get(self, params: dict[str, Any]) -> dict[str, Any]:
        checkpoint_id = params.get("id")
        if not checkpoint_id:
            raise ANIPError("not_found", "Missing 'id' in params")

        options: dict[str, Any] = {}
        for key in ("include_proof", "leaf_index", "consistency_from"):
            if key in params:
                options[key] = params[key]

        result = await self._service.get_checkpoint(checkpoint_id, options)
        if result is None:
            raise ANIPError("not_found", f"Checkpoint not found: {checkpoint_id}")
        return result

    # --- Internal helpers ---

    async def _resolve_jwt(self, params: dict[str, Any]) -> Any:
        """Extract and verify a JWT bearer token from params.

        Returns the resolved DelegationToken.
        Raises ANIPError if auth is missing or invalid.
        """
        bearer = extract_auth(params)
        if bearer is None:
            raise ANIPError("authentication_required", "This method requires auth.bearer")
        return await self._service.resolve_bearer_token(bearer)

    # --- Dispatch table ---

    _DISPATCH: dict[str, Any] = {
        "anip.discovery": _handle_anip_discovery,
        "anip.manifest": _handle_anip_manifest,
        "anip.jwks": _handle_anip_jwks,
        "anip.tokens.issue": _handle_anip_tokens_issue,
        "anip.permissions": _handle_anip_permissions,
        "anip.invoke": _handle_anip_invoke,
        "anip.audit.query": _handle_anip_audit_query,
        "anip.checkpoints.list": _handle_anip_checkpoints_list,
        "anip.checkpoints.get": _handle_anip_checkpoints_get,
    }


class _StdioWriter:
    """Minimal async writer wrapping sys.stdout.buffer."""

    def __init__(self):
        self._out = sys.stdout.buffer

    def write(self, data: bytes) -> None:
        self._out.write(data)

    async def drain(self) -> None:
        self._out.flush()

    def close(self) -> None:
        pass


def _make_stdio_streams():
    """Create async reader/writer for stdin/stdout without connect_*_pipe."""
    reader = asyncio.StreamReader()

    async def _feed_stdin():
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.buffer.readline)
            if not line:
                reader.feed_eof()
                break
            reader.feed_data(line)

    asyncio.get_event_loop().create_task(_feed_stdin())
    writer = _StdioWriter()
    return reader, writer


async def serve_stdio(
    service: ANIPService,
    reader: asyncio.StreamReader | None = None,
    writer: asyncio.StreamWriter | None = None,
) -> None:
    """Run the ANIP stdio server, reading JSON-RPC from reader and writing to writer.

    If reader/writer are not provided, connects stdin/stdout as asyncio streams.
    """
    if reader is None or writer is None:
        # Use a simple sync wrapper for stdin/stdout.
        # This avoids connect_read_pipe/connect_write_pipe which fail
        # when stdin/stdout are not real pipes (e.g., terminals, redirected files).
        reader, writer = _make_stdio_streams()

    server = AnipStdioServer(service)
    await service.start()

    try:
        while True:
            try:
                msg = await read_message(reader)
            except json.JSONDecodeError as exc:
                error_resp = make_error(None, PARSE_ERROR, f"Parse error: {exc}")
                await write_message(writer, error_resp)
                continue

            if msg is None:
                break  # EOF

            response = await server.handle_request(msg)

            if isinstance(response, list):
                for item in response:
                    await write_message(writer, item)
            else:
                await write_message(writer, response)
    finally:
        await service.shutdown()
        service.stop()
