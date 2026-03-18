"""Caller-class-aware disclosure resolution.

Two modes:
- Fixed mode (disclosure_level != "policy"): returns the fixed level for all callers.
- Policy mode (disclosure_level == "policy"): resolves from token claims via disclosure_policy.
"""
from __future__ import annotations

from typing import Any

_SCOPE_TO_CLASS = {
    "audit:full": "audit_full",
}


def _resolve_caller_class(token_claims: dict[str, Any] | None) -> str:
    """Extract caller class from token claims."""
    if token_claims is None:
        return "default"

    # 1. Explicit claim
    caller_class = token_claims.get("anip:caller_class")
    if caller_class is not None:
        return str(caller_class)

    # 2. Scope-derived
    scopes = token_claims.get("scope", [])
    if isinstance(scopes, list):
        for scope in scopes:
            if scope in _SCOPE_TO_CLASS:
                return _SCOPE_TO_CLASS[scope]

    return "default"


def resolve_disclosure_level(
    disclosure_level: str,
    *,
    token_claims: dict[str, Any] | None = None,
    disclosure_policy: dict[str, str] | None = None,
) -> str:
    """Resolve the effective disclosure level for a caller.

    If disclosure_level is not "policy", returns that fixed level (v0.8 behavior).
    If "policy", resolves from caller class via disclosure_policy.
    """
    if disclosure_level != "policy":
        return disclosure_level

    caller_class = _resolve_caller_class(token_claims)

    if disclosure_policy is None:
        return "redacted"

    level = disclosure_policy.get(caller_class)
    if level is not None:
        return level

    return disclosure_policy.get("default", "redacted")
