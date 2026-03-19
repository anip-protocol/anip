"""Retention enforcer -- background cleanup of expired audit entries (v0.8)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
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
        skip_audit_retention: bool = False,
        on_sweep: Callable[[int, float], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._storage = storage
        self._interval = interval_seconds
        self._skip_audit_retention = skip_audit_retention
        self._on_sweep = on_sweep
        self._on_error = on_error
        self._task: asyncio.Task[None] | None = None
        self._last_run_at: str | None = None
        self._last_deleted_count: int = 0
        self._last_error: str | None = None

    @property
    def last_run_at(self) -> str | None:
        return self._last_run_at

    @property
    def last_deleted_count(self) -> int:
        return self._last_deleted_count

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def sweep(self) -> int:
        """Run one cleanup sweep. Returns number of deleted entries."""
        if self._skip_audit_retention:
            return 0  # Cluster mode: audit retention disabled
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
            start = time.monotonic()
            try:
                count = await self.sweep()
                duration_ms = (time.monotonic() - start) * 1000
                self._last_run_at = datetime.now(timezone.utc).isoformat()
                self._last_deleted_count = count
                self._last_error = None
                if self._on_sweep:
                    try:
                        self._on_sweep(count, duration_ms)
                    except Exception:
                        pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._last_error = str(e)
                if self._on_error:
                    try:
                        self._on_error(str(e))
                    except Exception:
                        pass
