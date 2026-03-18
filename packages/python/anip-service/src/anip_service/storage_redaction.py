"""Storage-side redaction — strips parameters from low-value audit entries before persistence."""
from __future__ import annotations

from typing import Any

_LOW_VALUE_CLASSES = frozenset({
    "low_risk_success",
    "malformed_or_spam",
    "repeated_low_value_denial",
})


def storage_redact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the audit entry with parameters stripped for low-value events.

    High-risk events are returned unchanged (with storage_redacted=False).
    The persisted redacted entry is the canonical hashed form for checkpointing.
    """
    result = {**entry}
    event_class = result.get("event_class")

    if event_class in _LOW_VALUE_CLASSES:
        result["parameters"] = None
        result["storage_redacted"] = True
    else:
        result["storage_redacted"] = False

    return result
