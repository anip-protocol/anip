"""Checkpoint policy for the ANIP audit log."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable

from anip_flight_demo.primitives.sinks import CheckpointSink

_sink: CheckpointSink | None = None
_sink_queue: queue.Queue = queue.Queue()
_sink_thread: threading.Thread | None = None


def set_sink(sink: CheckpointSink) -> None:
    global _sink, _sink_thread
    _sink = sink
    if _sink_thread is None or not _sink_thread.is_alive():
        _sink_thread = threading.Thread(target=_drain_sink_queue, daemon=True)
        _sink_thread.start()


def enqueue_for_sink(checkpoint: dict[str, Any]) -> None:
    if _sink is not None:
        _sink_queue.put(checkpoint)


def get_pending_sink_count() -> int:
    return _sink_queue.qsize()


def _drain_sink_queue() -> None:
    while True:
        ckpt = _sink_queue.get()
        if _sink:
            try:
                _sink.publish(ckpt)
            except Exception:
                # Re-queue on failure for retry
                _sink_queue.put(ckpt)
        _sink_queue.task_done()


@dataclass
class CheckpointPolicy:
    """Defines when a checkpoint should be created.

    At least one trigger must be set for ``should_checkpoint`` to ever
    return ``True``.
    """

    entry_count: int | None = None
    interval_seconds: int | None = None

    def should_checkpoint(
        self, entries_since_last: int, seconds_since_last: float = 0
    ) -> bool:
        """Return ``True`` when any configured threshold is met."""
        if self.entry_count is not None and entries_since_last >= self.entry_count:
            return True
        if (
            self.interval_seconds is not None
            and seconds_since_last >= self.interval_seconds
        ):
            return True
        return False


class CheckpointScheduler:
    """Background timer that triggers checkpoints on a time interval."""

    def __init__(
        self,
        interval_seconds: int,
        create_fn: Callable[[], object],
        has_new_entries_fn: Callable[[], bool],
    ):
        self._interval = interval_seconds
        self._create_fn = create_fn
        self._has_new_entries = has_new_entries_fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            if self._has_new_entries():
                self._create_fn()
