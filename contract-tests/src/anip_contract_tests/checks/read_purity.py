"""read_purity check — verifies read-declared capabilities cause no mutations."""

from __future__ import annotations

from ..probes.audit_probe import AuditProbe
from ..probes.storage_probe import Finding, StorageProbe, TableSnapshot
from .check_result import CheckResult


class ReadPurityCheck:
    """Applicable only when ``side_effect.type == "read"``."""

    name = "read_purity"

    @staticmethod
    def applies(declaration: dict) -> bool:
        se = declaration.get("side_effect") or {}
        return se.get("type") == "read"

    @staticmethod
    def run(
        capability: str,
        audit_entry: dict | None,
        storage_findings: list[Finding] | None,
    ) -> CheckResult:
        """Run the read-purity check.

        *audit_entry* should be the latest audit entry for this invocation.
        *storage_findings* should be the findings from a before/after
        storage snapshot comparison (may be ``None`` if no storage probe).
        """
        # Audit: event_class should be low_risk_success
        if audit_entry is not None:
            result, confidence, detail = AuditProbe.check_event_class(
                audit_entry, "read"
            )
            if result == "FAIL":
                return CheckResult(
                    check_name="read_purity",
                    capability=capability,
                    result="FAIL",
                    confidence=confidence,
                    detail=f"Audit: {detail}",
                )

        # Storage: no unexpected mutations
        if storage_findings is not None:
            violations = [f for f in storage_findings if f.severity == "violation"]
            if violations:
                tables = ", ".join(f.table for f in violations)
                return CheckResult(
                    check_name="read_purity",
                    capability=capability,
                    result="FAIL",
                    confidence="elevated",
                    detail=f"Read capability mutated storage: {tables}",
                )

        # Determine confidence from what we checked.
        if audit_entry is not None and storage_findings is not None:
            confidence = "elevated"
        else:
            confidence = "medium"

        return CheckResult(
            check_name="read_purity",
            capability=capability,
            result="PASS",
            confidence=confidence,
            detail="No mutations detected for read capability",
        )
