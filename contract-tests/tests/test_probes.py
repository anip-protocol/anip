"""Tests for audit and storage probes."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from anip_contract_tests.probes.audit_probe import AuditProbe
from anip_contract_tests.probes.storage_probe import StorageProbe, TableSnapshot


# ── Audit probe: event_class mapping ──────────────────────────────────────


class TestAuditEventClassMapping:
    def test_read_maps_to_low_risk(self):
        entry = {"event_class": "low_risk_success"}
        result, confidence, detail = AuditProbe.check_event_class(entry, "read")
        assert result == "PASS"
        assert confidence == "elevated"

    def test_write_maps_to_high_risk(self):
        entry = {"event_class": "high_risk_success"}
        result, confidence, detail = AuditProbe.check_event_class(entry, "write")
        assert result == "PASS"

    def test_irreversible_maps_to_high_risk(self):
        entry = {"event_class": "high_risk_success"}
        result, confidence, detail = AuditProbe.check_event_class(entry, "irreversible")
        assert result == "PASS"

    def test_transactional_maps_to_high_risk(self):
        entry = {"event_class": "high_risk_success"}
        result, confidence, detail = AuditProbe.check_event_class(entry, "transactional")
        assert result == "PASS"

    def test_mismatched_class_fails(self):
        entry = {"event_class": "low_risk_success"}
        result, confidence, detail = AuditProbe.check_event_class(entry, "write")
        assert result == "FAIL"
        assert "low_risk_success" in detail
        assert "high_risk_success" in detail

    def test_missing_event_class_fails(self):
        entry = {}
        result, confidence, detail = AuditProbe.check_event_class(entry, "read")
        assert result == "FAIL"
        assert "missing" in detail.lower()

    def test_unknown_side_effect_warns(self):
        entry = {"event_class": "low_risk_success"}
        result, confidence, detail = AuditProbe.check_event_class(entry, "unknown_type")
        assert result == "WARN"

    def test_cost_actual_present(self):
        resp = {"cost_actual": {"financial": {"amount": 300, "currency": "USD"}}}
        result, confidence, detail = AuditProbe.check_cost_actual(resp)
        assert result == "PASS"

    def test_cost_actual_missing(self):
        resp = {"result": "ok"}
        result, confidence, detail = AuditProbe.check_cost_actual(resp)
        assert result == "FAIL"

    def test_cost_actual_empty(self):
        resp = {"cost_actual": {}}
        result, confidence, detail = AuditProbe.check_cost_actual(resp)
        assert result == "FAIL"


# ── Storage probe: snapshot + compare ─────────────────────────────────────


def _create_test_db(path: str) -> None:
    """Create a small SQLite DB with known tables and rows."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, event TEXT)")
    conn.execute("CREATE TABLE exclusive_leases (id INTEGER PRIMARY KEY, ts TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'alice')")
    conn.execute("INSERT INTO users VALUES (2, 'bob')")
    conn.execute("INSERT INTO audit_log VALUES (1, 'login')")
    conn.execute("INSERT INTO exclusive_leases VALUES (1, '2026-01-01')")
    conn.commit()
    conn.close()


class TestStorageSnapshot:
    def test_snapshot_returns_all_tables(self, tmp_path: Path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        probe = StorageProbe(db_path)
        snap = probe.snapshot()
        assert "users" in snap
        assert "audit_log" in snap
        assert "exclusive_leases" in snap
        assert snap["users"].row_count == 2
        assert snap["audit_log"].row_count == 1

    def test_snapshot_with_sqlite_dsn(self, tmp_path: Path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        probe = StorageProbe(f"sqlite:///{db_path}")
        snap = probe.snapshot()
        assert "users" in snap


class TestStorageCompare:
    def test_no_changes_no_findings(self):
        before = {
            "users": TableSnapshot("users", 2),
            "audit_log": TableSnapshot("audit_log", 1),
        }
        findings = StorageProbe.compare(before, before)
        assert findings == []

    def test_expected_audit_delta_allowed(self):
        before = {
            "users": TableSnapshot("users", 2),
            "audit_log": TableSnapshot("audit_log", 1),
        }
        after = {
            "users": TableSnapshot("users", 2),
            "audit_log": TableSnapshot("audit_log", 2),
        }
        findings = StorageProbe.compare(before, after, expected_audit_delta=1)
        assert findings == []

    def test_unexpected_audit_delta_warns(self):
        before = {
            "audit_log": TableSnapshot("audit_log", 1),
        }
        after = {
            "audit_log": TableSnapshot("audit_log", 5),
        }
        findings = StorageProbe.compare(before, after, expected_audit_delta=1)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].change_type == "unexpected_audit_delta"

    def test_allowlisted_lease_tables_ignored(self):
        before = {
            "exclusive_leases": TableSnapshot("exclusive_leases", 1),
        }
        after = {
            "exclusive_leases": TableSnapshot("exclusive_leases", 5),
        }
        findings = StorageProbe.compare(before, after)
        assert findings == []

    def test_unexpected_mutation_is_violation(self):
        before = {
            "users": TableSnapshot("users", 2),
            "audit_log": TableSnapshot("audit_log", 1),
        }
        after = {
            "users": TableSnapshot("users", 5),
            "audit_log": TableSnapshot("audit_log", 2),
        }
        findings = StorageProbe.compare(before, after, expected_audit_delta=1)
        assert len(findings) == 1
        assert findings[0].table == "users"
        assert findings[0].severity == "violation"
        assert findings[0].change_type == "row_count_increased"

    def test_new_table_is_violation(self):
        before = {"users": TableSnapshot("users", 2)}
        after = {
            "users": TableSnapshot("users", 2),
            "new_table": TableSnapshot("new_table", 3),
        }
        findings = StorageProbe.compare(before, after)
        assert len(findings) == 1
        assert findings[0].change_type == "table_created"
        assert findings[0].severity == "violation"

    def test_row_count_decreased(self):
        before = {"users": TableSnapshot("users", 5)}
        after = {"users": TableSnapshot("users", 2)}
        findings = StorageProbe.compare(before, after)
        assert len(findings) == 1
        assert findings[0].change_type == "row_count_decreased"
