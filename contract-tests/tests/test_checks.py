"""Tests for contract checks with mock probe results."""

from __future__ import annotations

import pytest

from anip_contract_tests.checks.classification import ClassificationCheck
from anip_contract_tests.checks.compensation import CompensationCheck
from anip_contract_tests.checks.cost_presence import CostPresenceCheck
from anip_contract_tests.checks.read_purity import ReadPurityCheck
from anip_contract_tests.probes.storage_probe import Finding


# ── ReadPurityCheck ───────────────────────────────────────────────────────


class TestReadPurityCheck:
    def test_applies_only_to_read(self):
        assert ReadPurityCheck.applies({"side_effect": {"type": "read"}})
        assert not ReadPurityCheck.applies({"side_effect": {"type": "write"}})
        assert not ReadPurityCheck.applies({"side_effect": {"type": "irreversible"}})
        assert not ReadPurityCheck.applies({})

    def test_pass_with_correct_audit_and_no_mutations(self):
        entry = {"event_class": "low_risk_success"}
        result = ReadPurityCheck.run("search", entry, storage_findings=[])
        assert result.result == "PASS"
        assert result.confidence == "elevated"

    def test_fail_with_wrong_event_class(self):
        entry = {"event_class": "high_risk_success"}
        result = ReadPurityCheck.run("search", entry, storage_findings=[])
        assert result.result == "FAIL"

    def test_fail_with_storage_mutations(self):
        entry = {"event_class": "low_risk_success"}
        findings = [
            Finding(
                table="users",
                change_type="row_count_increased",
                detail="users changed",
                severity="violation",
            )
        ]
        result = ReadPurityCheck.run("search", entry, storage_findings=findings)
        assert result.result == "FAIL"
        assert "mutated" in result.detail.lower()

    def test_pass_without_storage_probe(self):
        entry = {"event_class": "low_risk_success"}
        result = ReadPurityCheck.run("search", entry, storage_findings=None)
        assert result.result == "PASS"
        assert result.confidence == "medium"

    def test_pass_without_audit_or_storage(self):
        result = ReadPurityCheck.run("search", None, storage_findings=None)
        assert result.result == "PASS"
        assert result.confidence == "medium"

    def test_storage_warnings_do_not_cause_failure(self):
        entry = {"event_class": "low_risk_success"}
        findings = [
            Finding(
                table="audit_log",
                change_type="unexpected_audit_delta",
                detail="extra audit entries",
                severity="warning",
            )
        ]
        result = ReadPurityCheck.run("search", entry, storage_findings=findings)
        assert result.result == "PASS"


# ── ClassificationCheck ───────────────────────────────────────────────────


class TestClassificationCheck:
    def test_applies_when_side_effect_present(self):
        assert ClassificationCheck.applies({"side_effect": {"type": "read"}})
        assert ClassificationCheck.applies({"side_effect": {"type": "write"}})
        assert not ClassificationCheck.applies({})
        assert not ClassificationCheck.applies({"side_effect": {}})

    def test_pass_read_low_risk(self):
        decl = {"side_effect": {"type": "read"}}
        entry = {"event_class": "low_risk_success"}
        result = ClassificationCheck.run("search", decl, entry)
        assert result.result == "PASS"

    def test_pass_write_high_risk(self):
        decl = {"side_effect": {"type": "write"}}
        entry = {"event_class": "high_risk_success"}
        result = ClassificationCheck.run("update_user", decl, entry)
        assert result.result == "PASS"

    def test_fail_mismatch(self):
        decl = {"side_effect": {"type": "write"}}
        entry = {"event_class": "low_risk_success"}
        result = ClassificationCheck.run("update_user", decl, entry)
        assert result.result == "FAIL"

    def test_skip_no_audit_entry(self):
        decl = {"side_effect": {"type": "read"}}
        result = ClassificationCheck.run("search", decl, None)
        assert result.result == "SKIP"


# ── CostPresenceCheck ────────────────────────────────────────────────────


class TestCostPresenceCheck:
    def test_applies_when_financial_cost_present(self):
        assert CostPresenceCheck.applies(
            {"cost": {"financial": {"range_min": 100, "currency": "USD"}}}
        )
        assert not CostPresenceCheck.applies({"cost": {"financial": None}})
        assert not CostPresenceCheck.applies({"cost": {}})
        assert not CostPresenceCheck.applies({})

    def test_pass_when_cost_actual_present(self):
        resp = {"cost_actual": {"financial": {"amount": 300, "currency": "USD"}}}
        result = CostPresenceCheck.run("book_flight", resp)
        assert result.result == "PASS"

    def test_fail_when_cost_actual_missing(self):
        resp = {"result": "ok"}
        result = CostPresenceCheck.run("book_flight", resp)
        assert result.result == "FAIL"


# ── CompensationCheck ────────────────────────────────────────────────────


class TestCompensationCheck:
    def test_applies_with_scenario(self):
        assert CompensationCheck.applies({"setup_capability": "book"})
        assert not CompensationCheck.applies(None)
