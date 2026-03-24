"""classification check — verifies event_class matches declared side_effect."""

from __future__ import annotations

from ..probes.audit_probe import AuditProbe
from .check_result import CheckResult


class ClassificationCheck:
    """Applies to all capabilities that have a side_effect declaration."""

    name = "classification"

    @staticmethod
    def applies(declaration: dict) -> bool:
        se = declaration.get("side_effect") or {}
        return se.get("type") is not None

    @staticmethod
    def run(
        capability: str,
        declaration: dict,
        audit_entry: dict | None,
    ) -> CheckResult:
        se = declaration.get("side_effect") or {}
        se_type = se.get("type")

        if audit_entry is None:
            return CheckResult(
                check_name="classification",
                capability=capability,
                result="SKIP",
                confidence="medium",
                detail="No audit entry available",
            )

        result, confidence, detail = AuditProbe.check_event_class(
            audit_entry, se_type
        )
        return CheckResult(
            check_name="classification",
            capability=capability,
            result=result,
            confidence=confidence,
            detail=detail,
        )
