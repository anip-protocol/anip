"""Shared CheckResult dataclass used by all checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single contract check."""

    check_name: str
    capability: str
    result: str  # "PASS", "FAIL", "WARN", "SKIP"
    confidence: str  # "medium", "elevated"
    detail: str
