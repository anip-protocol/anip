"""Canonical hashing utilities for ANIP audit entries."""
import hashlib
import json
from typing import Any


def compute_entry_hash(entry: dict[str, Any]) -> str:
    """Compute the canonical hash of an audit entry for hash-chain linking."""
    canonical = json.dumps(
        {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def canonical_bytes(entry: dict[str, Any]) -> bytes:
    """Return canonical JSON bytes of an audit entry for Merkle leaf hashing."""
    return json.dumps(
        {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
