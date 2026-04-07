"""Tests for storage abstraction, InMemoryStorage, and SQLiteStorage."""
import pytest
from anip_server.storage import InMemoryStorage, SQLiteStorage


# ---------------------------------------------------------------------------
# SQLiteStorage tests (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sqlite_token_roundtrip():
    store = SQLiteStorage(":memory:")
    token_data = {
        "token_id": "tok-1",
        "issuer": "svc",
        "subject": "agent",
        "scope": ["travel.search"],
        "expires": "2026-12-31T23:59:59Z",
    }
    await store.store_token(token_data)
    loaded = await store.load_token("tok-1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-1"


@pytest.mark.asyncio
async def test_sqlite_audit_roundtrip():
    store = SQLiteStorage(":memory:")
    entry = {
        "sequence_number": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "capability": "test",
        "token_id": "tok-1",
        "root_principal": "human:test@example.com",
        "success": True,
        "result_summary": None,
        "failure_type": None,
        "cost_actual": None,
        "delegation_chain": [],
        "previous_hash": "sha256:0000",
        "signature": None,
    }
    await store.store_audit_entry(entry)
    entries = await store.query_audit_entries(capability="test")
    assert len(entries) == 1
    assert entries[0]["capability"] == "test"


@pytest.mark.asyncio
async def test_sqlite_checkpoint_roundtrip():
    store = SQLiteStorage(":memory:")
    body = {"checkpoint_id": "ckpt-001", "merkle_root": "sha256:abc"}
    await store.store_checkpoint(body, "header..sig")
    ckpt = await store.get_checkpoint_by_id("ckpt-001")
    assert ckpt is not None
    assert ckpt["signature"] == "header..sig"


@pytest.mark.asyncio
async def test_load_nonexistent_token():
    store = SQLiteStorage(":memory:")
    assert await store.load_token("nonexistent") is None


# ---------------------------------------------------------------------------
# InMemoryStorage tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_roundtrip():
    s = InMemoryStorage()
    await s.store_token({"token_id": "tok-1", "issuer": "svc", "subject": "agent"})
    loaded = await s.load_token("tok-1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-1"


@pytest.mark.asyncio
async def test_token_not_found():
    s = InMemoryStorage()
    assert await s.load_token("nonexistent") is None


@pytest.mark.asyncio
async def test_audit_store_and_query():
    s = InMemoryStorage()
    await s.store_audit_entry({
        "sequence_number": 1,
        "capability": "search",
        "root_principal": "human:alice",
    })
    entries = await s.query_audit_entries(capability="search")
    assert len(entries) == 1
    assert entries[0]["capability"] == "search"


@pytest.mark.asyncio
async def test_audit_ordering():
    """Entries returned in descending sequence_number order."""
    s = InMemoryStorage()
    for i in range(1, 6):
        await s.store_audit_entry({
            "sequence_number": i,
            "capability": "action",
            "timestamp": f"2026-01-0{i}T00:00:00Z",
            "previous_hash": "sha256:0",
            "success": True,
        })
    entries = await s.query_audit_entries(capability="action")
    seq_numbers = [e["sequence_number"] for e in entries]
    assert seq_numbers == [5, 4, 3, 2, 1]


@pytest.mark.asyncio
async def test_audit_query_limit():
    """Limit parameter restricts number of returned entries."""
    s = InMemoryStorage()
    for i in range(1, 11):
        await s.store_audit_entry({
            "sequence_number": i,
            "capability": "action",
            "previous_hash": "sha256:0",
            "success": True,
        })
    entries = await s.query_audit_entries(capability="action", limit=3)
    assert len(entries) == 3
    # Should be the 3 highest sequence numbers
    assert entries[0]["sequence_number"] == 10
    assert entries[2]["sequence_number"] == 8


@pytest.mark.asyncio
async def test_audit_query_by_root_principal():
    s = InMemoryStorage()
    await s.store_audit_entry({
        "sequence_number": 1,
        "capability": "search",
        "root_principal": "human:alice",
    })
    await s.store_audit_entry({
        "sequence_number": 2,
        "capability": "search",
        "root_principal": "human:bob",
    })
    entries = await s.query_audit_entries(root_principal="human:alice")
    assert len(entries) == 1
    assert entries[0]["root_principal"] == "human:alice"


@pytest.mark.asyncio
async def test_audit_query_by_since():
    s = InMemoryStorage()
    await s.store_audit_entry({
        "sequence_number": 1,
        "capability": "search",
        "timestamp": "2026-01-01T00:00:00Z",
    })
    await s.store_audit_entry({
        "sequence_number": 2,
        "capability": "search",
        "timestamp": "2026-06-01T00:00:00Z",
    })
    entries = await s.query_audit_entries(since="2026-03-01T00:00:00Z")
    assert len(entries) == 1
    assert entries[0]["sequence_number"] == 2


@pytest.mark.asyncio
async def test_audit_query_by_invocation_id():
    s = InMemoryStorage()
    await s.store_audit_entry({
        "sequence_number": 1,
        "capability": "search",
        "invocation_id": "inv-001",
    })
    await s.store_audit_entry({
        "sequence_number": 2,
        "capability": "search",
        "invocation_id": "inv-002",
    })
    entries = await s.query_audit_entries(invocation_id="inv-001")
    assert len(entries) == 1
    assert entries[0]["invocation_id"] == "inv-001"


@pytest.mark.asyncio
async def test_audit_query_by_client_reference_id():
    s = InMemoryStorage()
    await s.store_audit_entry({
        "sequence_number": 1,
        "capability": "search",
        "client_reference_id": "cref-aaa",
    })
    await s.store_audit_entry({
        "sequence_number": 2,
        "capability": "search",
        "client_reference_id": "cref-bbb",
    })
    await s.store_audit_entry({
        "sequence_number": 3,
        "capability": "search",
        "client_reference_id": "cref-aaa",
    })
    entries = await s.query_audit_entries(client_reference_id="cref-aaa")
    assert len(entries) == 2
    assert all(e["client_reference_id"] == "cref-aaa" for e in entries)


@pytest.mark.asyncio
async def test_audit_combined_filters():
    """Multiple filters are ANDed together."""
    s = InMemoryStorage()
    await s.store_audit_entry({
        "sequence_number": 1,
        "capability": "search",
        "root_principal": "human:alice",
    })
    await s.store_audit_entry({
        "sequence_number": 2,
        "capability": "book",
        "root_principal": "human:alice",
    })
    await s.store_audit_entry({
        "sequence_number": 3,
        "capability": "search",
        "root_principal": "human:bob",
    })
    entries = await s.query_audit_entries(
        capability="search", root_principal="human:alice"
    )
    assert len(entries) == 1
    assert entries[0]["sequence_number"] == 1


@pytest.mark.asyncio
async def test_get_last_audit_entry():
    s = InMemoryStorage()
    assert await s.get_last_audit_entry() is None

    await s.store_audit_entry({"sequence_number": 1, "capability": "a"})
    await s.store_audit_entry({"sequence_number": 3, "capability": "c"})
    await s.store_audit_entry({"sequence_number": 2, "capability": "b"})

    last = await s.get_last_audit_entry()
    assert last is not None
    assert last["sequence_number"] == 3
    assert last["capability"] == "c"


@pytest.mark.asyncio
async def test_get_audit_entries_range():
    s = InMemoryStorage()
    for i in range(1, 6):
        await s.store_audit_entry({
            "sequence_number": i,
            "capability": f"cap-{i}",
        })

    entries = await s.get_audit_entries_range(2, 4)
    assert len(entries) == 3
    seq_numbers = [e["sequence_number"] for e in entries]
    # Ascending order
    assert seq_numbers == [2, 3, 4]


@pytest.mark.asyncio
async def test_get_audit_entries_range_empty():
    s = InMemoryStorage()
    await s.store_audit_entry({"sequence_number": 1, "capability": "a"})
    entries = await s.get_audit_entries_range(10, 20)
    assert entries == []


@pytest.mark.asyncio
async def test_checkpoint_roundtrip():
    s = InMemoryStorage()
    body = {"checkpoint_id": "ckpt-001", "merkle_root": "sha256:abc"}
    await s.store_checkpoint(body, "header..sig")
    ckpt = await s.get_checkpoint_by_id("ckpt-001")
    assert ckpt is not None
    assert ckpt["checkpoint_id"] == "ckpt-001"
    assert ckpt["merkle_root"] == "sha256:abc"
    assert ckpt["signature"] == "header..sig"


@pytest.mark.asyncio
async def test_checkpoint_not_found():
    s = InMemoryStorage()
    assert await s.get_checkpoint_by_id("nonexistent") is None


@pytest.mark.asyncio
async def test_checkpoint_listing():
    s = InMemoryStorage()
    for i in range(1, 6):
        await s.store_checkpoint(
            {"checkpoint_id": f"ckpt-{i:03d}", "merkle_root": f"sha256:{i}"},
            f"sig-{i}",
        )

    all_ckpts = await s.get_checkpoints(limit=10)
    assert len(all_ckpts) == 5

    limited = await s.get_checkpoints(limit=2)
    assert len(limited) == 2
    # Most recent 2, in chronological order
    assert limited[0]["checkpoint_id"] == "ckpt-004"
    assert limited[1]["checkpoint_id"] == "ckpt-005"


@pytest.mark.asyncio
async def test_checkpoint_stores_body_fields():
    """store_checkpoint merges body dict with signature."""
    s = InMemoryStorage()
    body = {
        "checkpoint_id": "ckpt-x",
        "merkle_root": "sha256:root",
        "entry_count": 42,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    await s.store_checkpoint(body, "my-sig")
    ckpt = await s.get_checkpoint_by_id("ckpt-x")
    assert ckpt is not None
    assert ckpt["entry_count"] == 42
    assert ckpt["timestamp"] == "2026-01-01T00:00:00Z"
    assert ckpt["signature"] == "my-sig"


@pytest.mark.asyncio
async def test_token_data_isolation():
    """Stored token data should be independent of the original dict."""
    s = InMemoryStorage()
    data = {"token_id": "tok-iso", "issuer": "svc", "subject": "agent"}
    await s.store_token(data)
    data["issuer"] = "MUTATED"
    loaded = await s.load_token("tok-iso")
    assert loaded is not None
    assert loaded["issuer"] == "svc"


@pytest.mark.asyncio
async def test_audit_no_filters_returns_all():
    """query_audit_entries with no filters returns all entries."""
    s = InMemoryStorage()
    for i in range(1, 4):
        await s.store_audit_entry({
            "sequence_number": i,
            "capability": f"cap-{i}",
        })
    entries = await s.query_audit_entries()
    assert len(entries) == 3


# ---------------------------------------------------------------------------
# Backend compliance suite (parametrized across both backends)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# v0.8: event_class, retention_tier, expires_at tests — SQLiteStorage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sqlite_store_and_query_audit_entry_with_event_class(tmp_path):
    """v0.8: audit entries include event_class, retention_tier, expires_at."""
    storage = SQLiteStorage(str(tmp_path / "test.db"))
    entry = {
        "sequence_number": 1, "timestamp": "2026-03-16T12:00:00Z",
        "capability": "test.cap", "token_id": "t1", "issuer": "svc",
        "subject": "agent", "root_principal": "human", "parameters": None,
        "success": True, "result_summary": None, "failure_type": None,
        "cost_actual": None, "delegation_chain": None, "invocation_id": "inv-1",
        "client_reference_id": None, "stream_summary": None,
        "previous_hash": "sha256:0000", "signature": None,
        "event_class": "high_risk_success", "retention_tier": "long",
        "expires_at": "2027-03-16T12:00:00Z",
    }
    await storage.store_audit_entry(entry)
    rows = await storage.query_audit_entries(capability="test.cap")
    assert len(rows) == 1
    assert rows[0]["event_class"] == "high_risk_success"
    assert rows[0]["retention_tier"] == "long"
    assert rows[0]["expires_at"] == "2027-03-16T12:00:00Z"


@pytest.mark.asyncio
async def test_sqlite_query_audit_entries_by_event_class(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "test.db"))
    base = {
        "timestamp": "2026-03-16T12:00:00Z", "capability": "test.cap",
        "token_id": "t1", "issuer": "svc", "subject": "agent",
        "root_principal": "human", "parameters": None, "success": True,
        "result_summary": None, "failure_type": None, "cost_actual": None,
        "delegation_chain": None, "invocation_id": None,
        "client_reference_id": None, "stream_summary": None,
        "previous_hash": "sha256:0000", "signature": None,
        "retention_tier": "short", "expires_at": "2026-03-23T12:00:00Z",
    }
    await storage.store_audit_entry({**base, "sequence_number": 1, "event_class": "high_risk_success"})
    await storage.store_audit_entry({**base, "sequence_number": 2, "event_class": "malformed_or_spam"})
    await storage.store_audit_entry({**base, "sequence_number": 3, "event_class": "high_risk_success"})
    rows = await storage.query_audit_entries(event_class="high_risk_success")
    assert len(rows) == 2
    assert all(r["event_class"] == "high_risk_success" for r in rows)


@pytest.mark.asyncio
async def test_sqlite_delete_expired_audit_entries(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "test.db"))
    base = {
        "timestamp": "2026-03-16T12:00:00Z", "capability": "test.cap",
        "token_id": "t1", "issuer": "svc", "subject": "agent",
        "root_principal": "human", "parameters": None, "success": True,
        "result_summary": None, "failure_type": None, "cost_actual": None,
        "delegation_chain": None, "invocation_id": None,
        "client_reference_id": None, "stream_summary": None,
        "previous_hash": "sha256:0000", "signature": None,
        "event_class": "malformed_or_spam", "retention_tier": "short",
    }
    await storage.store_audit_entry({**base, "sequence_number": 1, "expires_at": "2026-03-10T00:00:00Z"})
    await storage.store_audit_entry({**base, "sequence_number": 2, "expires_at": "2026-03-20T00:00:00Z"})
    await storage.store_audit_entry({**base, "sequence_number": 3, "expires_at": None})
    deleted = await storage.delete_expired_audit_entries("2026-03-16T12:00:00Z")
    assert deleted == 1
    remaining = await storage.query_audit_entries()
    assert len(remaining) == 2


# ---------------------------------------------------------------------------
# v0.8: event_class, retention_tier, expires_at tests — InMemoryStorage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inmemory_store_and_query_audit_entry_with_event_class():
    """v0.8: audit entries include event_class, retention_tier, expires_at."""
    storage = InMemoryStorage()
    entry = {
        "sequence_number": 1, "timestamp": "2026-03-16T12:00:00Z",
        "capability": "test.cap", "token_id": "t1", "issuer": "svc",
        "subject": "agent", "root_principal": "human", "parameters": None,
        "success": True, "result_summary": None, "failure_type": None,
        "cost_actual": None, "delegation_chain": None, "invocation_id": "inv-1",
        "client_reference_id": None, "stream_summary": None,
        "previous_hash": "sha256:0000", "signature": None,
        "event_class": "high_risk_success", "retention_tier": "long",
        "expires_at": "2027-03-16T12:00:00Z",
    }
    await storage.store_audit_entry(entry)
    rows = await storage.query_audit_entries(capability="test.cap")
    assert len(rows) == 1
    assert rows[0]["event_class"] == "high_risk_success"
    assert rows[0]["retention_tier"] == "long"
    assert rows[0]["expires_at"] == "2027-03-16T12:00:00Z"


@pytest.mark.asyncio
async def test_inmemory_query_audit_entries_by_event_class():
    storage = InMemoryStorage()
    base = {
        "timestamp": "2026-03-16T12:00:00Z", "capability": "test.cap",
        "token_id": "t1", "issuer": "svc", "subject": "agent",
        "root_principal": "human", "parameters": None, "success": True,
        "result_summary": None, "failure_type": None, "cost_actual": None,
        "delegation_chain": None, "invocation_id": None,
        "client_reference_id": None, "stream_summary": None,
        "previous_hash": "sha256:0000", "signature": None,
        "retention_tier": "short", "expires_at": "2026-03-23T12:00:00Z",
    }
    await storage.store_audit_entry({**base, "sequence_number": 1, "event_class": "high_risk_success"})
    await storage.store_audit_entry({**base, "sequence_number": 2, "event_class": "malformed_or_spam"})
    await storage.store_audit_entry({**base, "sequence_number": 3, "event_class": "high_risk_success"})
    rows = await storage.query_audit_entries(event_class="high_risk_success")
    assert len(rows) == 2
    assert all(r["event_class"] == "high_risk_success" for r in rows)


@pytest.mark.asyncio
async def test_inmemory_delete_expired_audit_entries():
    storage = InMemoryStorage()
    base = {
        "timestamp": "2026-03-16T12:00:00Z", "capability": "test.cap",
        "token_id": "t1", "issuer": "svc", "subject": "agent",
        "root_principal": "human", "parameters": None, "success": True,
        "result_summary": None, "failure_type": None, "cost_actual": None,
        "delegation_chain": None, "invocation_id": None,
        "client_reference_id": None, "stream_summary": None,
        "previous_hash": "sha256:0000", "signature": None,
        "event_class": "malformed_or_spam", "retention_tier": "short",
    }
    await storage.store_audit_entry({**base, "sequence_number": 1, "expires_at": "2026-03-10T00:00:00Z"})
    await storage.store_audit_entry({**base, "sequence_number": 2, "expires_at": "2026-03-20T00:00:00Z"})
    await storage.store_audit_entry({**base, "sequence_number": 3, "expires_at": None})
    deleted = await storage.delete_expired_audit_entries("2026-03-16T12:00:00Z")
    assert deleted == 1
    remaining = await storage.query_audit_entries()
    assert len(remaining) == 2


from compliance import ALL_COMPLIANCE_TESTS


@pytest.mark.parametrize("test_fn", ALL_COMPLIANCE_TESTS, ids=lambda f: f.__name__)
async def test_in_memory_compliance(test_fn):
    storage = InMemoryStorage()
    await test_fn(storage)


@pytest.mark.parametrize("test_fn", ALL_COMPLIANCE_TESTS, ids=lambda f: f.__name__)
async def test_sqlite_compliance(test_fn, tmp_path):
    storage = SQLiteStorage(str(tmp_path / "test.db"))
    await test_fn(storage)
