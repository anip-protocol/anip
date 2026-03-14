"""Example-specific sink queue functions.

CheckpointPolicy and CheckpointScheduler are imported from anip_server SDK.
This module retains only the background sink-publish queue, which is specific
to the example's wiring.
"""

from __future__ import annotations

import queue
import threading
from typing import Any

from anip_server import CheckpointSink

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
