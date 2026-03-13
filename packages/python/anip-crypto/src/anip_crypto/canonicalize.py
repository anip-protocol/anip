"""Canonical JSON helpers for verifiable ANIP artifacts."""

import json
from typing import Any


def canonicalize(data: dict[str, Any], *, exclude: set[str] | None = None) -> bytes:
    """Produce canonical JSON bytes for signing/hashing.

    Sorts keys, uses compact separators, optionally excludes fields.
    """
    filtered = {k: v for k, v in sorted(data.items()) if k not in (exclude or set())}
    return json.dumps(filtered, separators=(",", ":"), sort_keys=True).encode()
