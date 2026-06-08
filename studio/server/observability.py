"""Small observability primitives for Studio.

The hosted and self-hosted Studio deployments need stable health, readiness,
and Prometheus scrape output without pulling in a full metrics dependency.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Mapping
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
        }
        event = getattr(record, "event", None)
        if event:
            payload["event"] = event
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _RESERVED_LOG_RECORD_KEYS:
                continue
            try:
                json.dumps(value)
            except TypeError:
                payload[key] = str(value)
            else:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


_RESERVED_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def configure_json_logging() -> logging.Logger:
    logger = logging.getLogger("anip.studio")
    if not any(getattr(handler, "_anip_json_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler._anip_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class StudioMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_total: defaultdict[str, int] = defaultdict(int)
        self._request_duration_sum: defaultdict[str, float] = defaultdict(float)
        self._request_duration_count: defaultdict[str, int] = defaultdict(int)
        self._readiness_total: defaultdict[str, int] = defaultdict(int)
        self._last_migration_applied = False
        self._last_migration_expected = 0
        self._last_migration_applied_count = 0

    def record_request(self, method: str, route: str, status: int, duration_seconds: float) -> None:
        key = f'method="{method}",route="{route}",status="{status}"'
        with self._lock:
            self._request_total[key] += 1
            self._request_duration_sum[key] += duration_seconds
            self._request_duration_count[key] += 1

    def record_readiness(self, status: str, migration: Mapping[str, Any]) -> None:
        key = f'status="{status}"'
        with self._lock:
            self._readiness_total[key] += 1
            self._last_migration_applied = bool(migration.get("applied"))
            self._last_migration_expected = int(migration.get("expected_count") or 0)
            self._last_migration_applied_count = int(migration.get("applied_count") or 0)

    def prometheus_text(self) -> str:
        with self._lock:
            lines = [
                "# HELP anip_studio_http_requests_total Studio HTTP requests by method, route, and status.",
                "# TYPE anip_studio_http_requests_total counter",
            ]
            lines.extend(_format_counter_map("anip_studio_http_requests_total", self._request_total))
            lines.extend(
                [
                    "# HELP anip_studio_http_request_duration_seconds_sum Total Studio HTTP request duration seconds.",
                    "# TYPE anip_studio_http_request_duration_seconds_sum counter",
                ]
            )
            lines.extend(_format_float_map("anip_studio_http_request_duration_seconds_sum", self._request_duration_sum))
            lines.extend(
                [
                    "# HELP anip_studio_http_request_duration_seconds_count Studio HTTP request duration sample count.",
                    "# TYPE anip_studio_http_request_duration_seconds_count counter",
                ]
            )
            lines.extend(_format_counter_map("anip_studio_http_request_duration_seconds_count", self._request_duration_count))
            lines.extend(
                [
                    "# HELP anip_studio_readiness_checks_total Studio readiness checks by status.",
                    "# TYPE anip_studio_readiness_checks_total counter",
                ]
            )
            lines.extend(_format_counter_map("anip_studio_readiness_checks_total", self._readiness_total))
            migration_applied = 1 if self._last_migration_applied else 0
            lines.extend(
                [
                    "# HELP anip_studio_migrations_applied Whether all embedded Studio migrations were applied on the last readiness check.",
                    "# TYPE anip_studio_migrations_applied gauge",
                    f"anip_studio_migrations_applied {migration_applied}",
                    "# HELP anip_studio_migrations_expected Embedded Studio migration count on the last readiness check.",
                    "# TYPE anip_studio_migrations_expected gauge",
                    f"anip_studio_migrations_expected {self._last_migration_expected}",
                    "# HELP anip_studio_migrations_applied_count Applied Studio migration count on the last readiness check.",
                    "# TYPE anip_studio_migrations_applied_count gauge",
                    f"anip_studio_migrations_applied_count {self._last_migration_applied_count}",
                ]
            )
            return "\n".join(lines) + "\n"


def now() -> float:
    return time.perf_counter()


def _format_counter_map(name: str, values: Mapping[str, int]) -> list[str]:
    return [f"{name}{{{key}}} {values[key]}" for key in sorted(values)]


def _format_float_map(name: str, values: Mapping[str, float]) -> list[str]:
    return [f"{name}{{{key}}} {values[key]:.9f}" for key in sorted(values)]
