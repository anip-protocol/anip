"""cost_presence check — verifies cost_actual is returned when declared."""

from __future__ import annotations

from ..probes.audit_probe import AuditProbe
from .check_result import CheckResult


class CostPresenceCheck:
    """Only applies when the manifest declares ``cost.financial``."""

    name = "cost_presence"

    @staticmethod
    def applies(declaration: dict) -> bool:
        cost = declaration.get("cost") or {}
        return cost.get("financial") is not None

    @staticmethod
    def run(
        capability: str,
        invoke_response: dict,
    ) -> CheckResult:
        result, confidence, detail = AuditProbe.check_cost_actual(invoke_response)
        return CheckResult(
            check_name="cost_presence",
            capability=capability,
            result=result,
            confidence=confidence,
            detail=detail,
        )
