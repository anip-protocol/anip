"""ANIP stdio client — spawns a subprocess and communicates via JSON-RPC 2.0."""
from __future__ import annotations

import asyncio
import itertools
from typing import Any

from .framing import read_message, write_message


class InvokeStream:
    """Async iterator for streaming invoke progress. Terminal result in .result."""

    def __init__(self, reader: asyncio.StreamReader, req_id: int) -> None:
        self._reader = reader
        self._req_id = req_id
        self.result: dict[str, Any] | None = None

    def __aiter__(self) -> InvokeStream:
        return self

    async def __anext__(self) -> dict[str, Any]:
        while True:
            msg = await read_message(self._reader)
            if msg is None:
                raise StopAsyncIteration

            # Notification (progress)
            if "method" in msg and msg["method"] == "anip.invoke.progress":
                return msg["params"]

            # Final response for our request
            if "id" in msg and msg["id"] == self._req_id:
                if "error" in msg:
                    raise Exception(f"Invoke failed: {msg['error']}")
                self.result = msg["result"]
                raise StopAsyncIteration


class AnipStdioClient:
    """Async context manager that spawns an ANIP service subprocess and talks JSON-RPC 2.0.

    IMPORTANT: This client is single-request-at-a-time. Do not issue concurrent
    calls or overlap a streaming invoke with other requests — there is no response
    demultiplexer. Concurrent request support is a future enhancement.
    """

    def __init__(self, *cmd: str) -> None:
        self._cmd = cmd
        self._proc: asyncio.subprocess.Process | None = None
        self._id_counter = itertools.count(1)
        self._stderr_task: asyncio.Task | None = None

    async def __aenter__(self) -> AnipStdioClient:
        self._proc = await asyncio.create_subprocess_exec(
            *self._cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Drain stderr in background to prevent pipe buffer deadlock.
        # The stdio spec reserves stderr for logs/diagnostics — a chatty service
        # can fill the pipe buffer and block if nobody reads it.
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        return self

    async def _drain_stderr(self) -> None:
        """Read and discard stderr to prevent pipe buffer deadlock."""
        assert self._proc is not None and self._proc.stderr is not None
        try:
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    break
        except Exception:
            pass

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._proc is not None:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
            await self._proc.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass

    # --- Core RPC plumbing ---

    async def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and return the result, skipping interleaved notifications."""
        assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None

        req_id = next(self._id_counter)
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        await write_message(self._proc.stdin, request)

        # Read messages until we get the response matching our request id
        while True:
            msg = await read_message(self._proc.stdout)
            if msg is None:
                raise ConnectionError("Subprocess closed stdout before responding")

            # Skip notifications (no "id" field)
            if "id" not in msg:
                continue

            if msg["id"] == req_id:
                if "error" in msg:
                    err = msg["error"]
                    raise Exception(f"JSON-RPC error {err.get('code')}: {err.get('message')}")
                return msg["result"]

    # --- Typed public methods ---

    async def discovery(self) -> dict[str, Any]:
        """Call anip.discovery."""
        return await self._call("anip.discovery")

    async def manifest(self) -> dict[str, Any]:
        """Call anip.manifest — returns {manifest, signature}."""
        return await self._call("anip.manifest")

    async def jwks(self) -> dict[str, Any]:
        """Call anip.jwks — returns {keys: [...]}."""
        return await self._call("anip.jwks")

    async def issue_token(
        self,
        bearer: str,
        *,
        subject: str | None = None,
        scope: list[str] | None = None,
        capability: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call anip.tokens.issue."""
        params: dict[str, Any] = {"auth": {"bearer": bearer}}
        if subject is not None:
            params["subject"] = subject
        if scope is not None:
            params["scope"] = scope
        if capability is not None:
            params["capability"] = capability
        params.update(kwargs)
        return await self._call("anip.tokens.issue", params)

    async def permissions(self, bearer: str) -> dict[str, Any]:
        """Call anip.permissions."""
        return await self._call("anip.permissions", {"auth": {"bearer": bearer}})

    async def invoke(
        self,
        bearer: str,
        capability: str,
        parameters: dict[str, Any] | None = None,
        *,
        client_reference_id: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | InvokeStream:
        """Call anip.invoke. Returns result dict, or InvokeStream if stream=True."""
        assert self._proc is not None and self._proc.stdin is not None and self._proc.stdout is not None

        params: dict[str, Any] = {
            "auth": {"bearer": bearer},
            "capability": capability,
        }
        if parameters is not None:
            params["parameters"] = parameters
        if client_reference_id is not None:
            params["client_reference_id"] = client_reference_id
        if stream:
            params["stream"] = True

        req_id = next(self._id_counter)
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "anip.invoke",
            "params": params,
        }
        await write_message(self._proc.stdin, request)

        if stream:
            return InvokeStream(self._proc.stdout, req_id)

        # Non-streaming: read until we get the matching response
        while True:
            msg = await read_message(self._proc.stdout)
            if msg is None:
                raise ConnectionError("Subprocess closed stdout before responding")
            if "id" not in msg:
                continue
            if msg["id"] == req_id:
                if "error" in msg:
                    err = msg["error"]
                    raise Exception(f"JSON-RPC error {err.get('code')}: {err.get('message')}")
                return msg["result"]

    async def audit_query(
        self,
        bearer: str,
        *,
        capability: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        event_class: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Call anip.audit.query."""
        params: dict[str, Any] = {"auth": {"bearer": bearer}}
        if capability is not None:
            params["capability"] = capability
        if since is not None:
            params["since"] = since
        if invocation_id is not None:
            params["invocation_id"] = invocation_id
        if client_reference_id is not None:
            params["client_reference_id"] = client_reference_id
        if event_class is not None:
            params["event_class"] = event_class
        if limit is not None:
            params["limit"] = limit
        return await self._call("anip.audit.query", params)

    async def checkpoints_list(self, limit: int = 10) -> dict[str, Any]:
        """Call anip.checkpoints.list."""
        return await self._call("anip.checkpoints.list", {"limit": limit})

    async def checkpoints_get(
        self,
        id: str,
        *,
        include_proof: bool = False,
        leaf_index: int | None = None,
        consistency_from: str | None = None,
    ) -> dict[str, Any]:
        """Call anip.checkpoints.get."""
        params: dict[str, Any] = {"id": id, "include_proof": include_proof}
        if leaf_index is not None:
            params["leaf_index"] = leaf_index
        if consistency_from is not None:
            params["consistency_from"] = consistency_from
        return await self._call("anip.checkpoints.get", params)
