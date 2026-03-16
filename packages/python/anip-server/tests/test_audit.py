"""Tests for AuditLog."""
from anip_server.audit import AuditLog
from anip_server.storage import InMemoryStorage


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


async def test_audit_entry_includes_lineage_fields():
    """Log entry with both IDs, verify they're in the returned entry."""
    store = InMemoryStorage()
    audit = AuditLog(store)

    entry = await audit.log_entry(_make_entry(
        invocation_id="inv-001",
        client_reference_id="cref-001",
    ))

    assert entry["invocation_id"] == "inv-001"
    assert entry["client_reference_id"] == "cref-001"


async def test_audit_entry_lineage_fields_optional():
    """Log entry without IDs, verify both are None."""
    store = InMemoryStorage()
    audit = AuditLog(store)

    entry = await audit.log_entry(_make_entry())

    assert entry["invocation_id"] is None
    assert entry["client_reference_id"] is None


async def test_audit_entry_persisted_with_lineage():
    """Log then query, verify IDs are in the stored entry."""
    store = InMemoryStorage()
    audit = AuditLog(store)

    await audit.log_entry(_make_entry(
        invocation_id="inv-persist",
        client_reference_id="cref-persist",
    ))

    entries = await audit.query(capability="test.action")
    assert len(entries) == 1
    assert entries[0]["invocation_id"] == "inv-persist"
    assert entries[0]["client_reference_id"] == "cref-persist"


async def test_query_audit_by_invocation_id():
    """Log 2 entries with different invocation_ids, query by one, get only that one."""
    store = InMemoryStorage()
    audit = AuditLog(store)

    await audit.log_entry(_make_entry(invocation_id="inv-aaa"))
    await audit.log_entry(_make_entry(invocation_id="inv-bbb"))

    results = await audit.query(invocation_id="inv-aaa")
    assert len(results) == 1
    assert results[0]["invocation_id"] == "inv-aaa"


async def test_query_audit_by_client_reference_id():
    """Log 3 entries (2 with same client_reference_id, 1 different), query by the shared one, get exactly 2."""
    store = InMemoryStorage()
    audit = AuditLog(store)

    await audit.log_entry(_make_entry(client_reference_id="cref-shared"))
    await audit.log_entry(_make_entry(client_reference_id="cref-shared"))
    await audit.log_entry(_make_entry(client_reference_id="cref-other"))

    results = await audit.query(client_reference_id="cref-shared")
    assert len(results) == 2
    assert all(r["client_reference_id"] == "cref-shared" for r in results)


async def test_audit_entry_includes_stream_summary():
    """Audit entries should persist stream_summary when provided."""
    store = InMemoryStorage()
    audit = AuditLog(store)

    await audit.log_entry(_make_entry(
        invocation_id="inv-000000000001",
        stream_summary={
            "response_mode": "streaming",
            "events_emitted": 5,
            "events_delivered": 3,
            "duration_ms": 1200,
            "client_disconnected": True,
        },
    ))

    entries = await audit.query(capability="test.action")
    assert entries[0]["stream_summary"]["events_emitted"] == 5
    assert entries[0]["stream_summary"]["client_disconnected"] is True


async def test_audit_entry_with_sync_signer():
    """Sync signer callback produces a signature."""
    store = InMemoryStorage()
    audit = AuditLog(store, signer=lambda entry: "sync-sig")
    entry = await audit.log_entry(_make_entry())
    assert entry["signature"] == "sync-sig"


async def test_audit_entry_with_async_signer():
    """Async signer callback produces a signature."""
    store = InMemoryStorage()

    async def async_signer(entry):
        return "async-sig"

    audit = AuditLog(store, signer=async_signer)
    entry = await audit.log_entry(_make_entry())
    assert entry["signature"] == "async-sig"
