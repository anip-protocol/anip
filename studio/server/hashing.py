"""Deterministic content hashing for artifact staleness detection."""

import hashlib
import json


def canonical_json(data: dict) -> str:
    """Produce a deterministic JSON string for hashing.
    Keys are sorted, separators are compact, no trailing whitespace.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def content_hash(data: dict) -> str:
    """SHA-256 hex digest of the canonical JSON representation."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
