"""Tests for audit log lineage fields (invocation_id, client_reference_id)."""
from anip_server.audit import AuditLog
from anip_server.storage import SQLiteStorage


def _make_entry(**overrides):
    """Helper to create a minimal audit entry_data dict."""
    base = {
        "capability": "test.action",
        "token_id": "tok-1",
        "root_principal": "human:user@example.com",
        "success": True,
    }
    base.update(overrides)
    return base


def test_audit_entry_includes_lineage_fields():
    """Log entry with both IDs, verify they're in the returned entry."""
    store = SQLiteStorage(":memory:")
    audit = AuditLog(store)

    entry = audit.log_entry(_make_entry(
        invocation_id="inv-001",
        client_reference_id="cref-001",
    ))

    assert entry["invocation_id"] == "inv-001"
    assert entry["client_reference_id"] == "cref-001"


def test_audit_entry_lineage_fields_optional():
    """Log entry without IDs, verify both are None."""
    store = SQLiteStorage(":memory:")
    audit = AuditLog(store)

    entry = audit.log_entry(_make_entry())

    assert entry["invocation_id"] is None
    assert entry["client_reference_id"] is None


def test_audit_entry_persisted_with_lineage():
    """Log then query, verify IDs are in the stored entry."""
    store = SQLiteStorage(":memory:")
    audit = AuditLog(store)

    audit.log_entry(_make_entry(
        invocation_id="inv-persist",
        client_reference_id="cref-persist",
    ))

    entries = audit.query(capability="test.action")
    assert len(entries) == 1
    assert entries[0]["invocation_id"] == "inv-persist"
    assert entries[0]["client_reference_id"] == "cref-persist"


def test_query_audit_by_invocation_id():
    """Log 2 entries with different invocation_ids, query by one, get only that one."""
    store = SQLiteStorage(":memory:")
    audit = AuditLog(store)

    audit.log_entry(_make_entry(invocation_id="inv-aaa"))
    audit.log_entry(_make_entry(invocation_id="inv-bbb"))

    results = audit.query(invocation_id="inv-aaa")
    assert len(results) == 1
    assert results[0]["invocation_id"] == "inv-aaa"


def test_query_audit_by_client_reference_id():
    """Log 3 entries (2 with same client_reference_id, 1 different), query by the shared one, get exactly 2."""
    store = SQLiteStorage(":memory:")
    audit = AuditLog(store)

    audit.log_entry(_make_entry(client_reference_id="cref-shared"))
    audit.log_entry(_make_entry(client_reference_id="cref-shared"))
    audit.log_entry(_make_entry(client_reference_id="cref-other"))

    results = audit.query(client_reference_id="cref-shared")
    assert len(results) == 2
    assert all(r["client_reference_id"] == "cref-shared" for r in results)
