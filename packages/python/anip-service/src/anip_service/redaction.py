"""Failure detail redaction for v0.8 security hardening.

Shapes failure responses based on disclosure level before they reach the caller.
Storage always records the full unredacted failure.
"""

from __future__ import annotations

from typing import Any

_GENERIC_MESSAGES: dict[str, str] = {
    "scope_insufficient": "Insufficient scope for this capability",
    "invalid_token": "Authentication failed",
    "token_expired": "Token has expired",
    "purpose_mismatch": "Token purpose does not match this capability",
    "insufficient_authority": "Insufficient authority for this action",
    "unknown_capability": "Capability not found",
    "not_found": "Resource not found",
    "unavailable": "Service temporarily unavailable",
    "concurrent_lock": "Operation conflict",
    "internal_error": "Internal error",
    "streaming_not_supported": "Streaming not supported for this capability",
    "scope_escalation": "Scope escalation not permitted",
}

_DEFAULT_GENERIC = "Request failed"


def redact_failure(
    failure: dict[str, Any],
    disclosure_level: str,
) -> dict[str, Any]:
    """Apply disclosure-level redaction to a failure response.

    Args:
        failure: The failure dict (type, detail, retry, resolution).
        disclosure_level: One of "full", "reduced", "redacted", "policy".
            "policy" is treated as "redacted" in v0.8.

    Returns:
        A new failure dict with appropriate redaction applied.
    """
    if disclosure_level == "policy":
        disclosure_level = "redacted"

    if disclosure_level == "full":
        return failure

    result = {**failure}
    resolution = {**(failure.get("resolution") or {})}

    if disclosure_level == "reduced":
        resolution["grantable_by"] = None
        detail = result.get("detail", "")
        if len(detail) > 200:
            result["detail"] = detail[:200]

    elif disclosure_level == "redacted":
        failure_type = result.get("type", "")
        result["detail"] = _GENERIC_MESSAGES.get(failure_type, _DEFAULT_GENERIC)
        resolution["requires"] = None
        resolution["grantable_by"] = None
        resolution["estimated_availability"] = None

    if resolution:
        result["resolution"] = resolution

    return result
