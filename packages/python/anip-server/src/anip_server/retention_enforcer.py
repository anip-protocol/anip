"""Retention enforcer -- background cleanup of expired audit entries (v0.8)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import StorageBackend


class RetentionEnforcer:
    """Background sweep that deletes expired audit entries."""

    def __init__(
        self,
        storage: StorageBackend,
        *,
        interval_seconds: int = 60,
    ) -> None:
        self._storage = storage
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def sweep(self) -> int:
        """Run one cleanup sweep. Returns number of deleted entries."""
        now = datetime.now(timezone.utc).isoformat()
        return await self._storage.delete_expired_audit_entries(now)

    def start(self) -> None:
        """Start background cleanup as an asyncio task.

        Must be called from within a running event loop.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError(
                "RetentionEnforcer.start() requires a running event loop. "
                "Call from an async context (e.g., ASGI startup hook)."
            )
        self._task = loop.create_task(self._run())

    def stop(self) -> None:
        """Cancel the background cleanup task."""
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Sweep failures are non-fatal
