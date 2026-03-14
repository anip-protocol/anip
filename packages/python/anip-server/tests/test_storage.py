"""Tests for storage abstraction and SQLite implementation."""
from anip_server.storage import SQLiteStorage


def test_sqlite_token_roundtrip():
    store = SQLiteStorage(":memory:")
    token_data = {
        "token_id": "tok-1",
        "issuer": "svc",
        "subject": "agent",
        "scope": ["travel.search"],
        "expires": "2026-12-31T23:59:59Z",
    }
    store.store_token(token_data)
    loaded = store.load_token("tok-1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-1"


def test_sqlite_audit_roundtrip():
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
    store.store_audit_entry(entry)
    entries = store.query_audit_entries(capability="test")
    assert len(entries) == 1
    assert entries[0]["capability"] == "test"


def test_sqlite_checkpoint_roundtrip():
    store = SQLiteStorage(":memory:")
    body = {"checkpoint_id": "ckpt-001", "merkle_root": "sha256:abc"}
    store.store_checkpoint(body, "header..sig")
    ckpt = store.get_checkpoint_by_id("ckpt-001")
    assert ckpt is not None
    assert ckpt["signature"] == "header..sig"


def test_load_nonexistent_token():
    store = SQLiteStorage(":memory:")
    assert store.load_token("nonexistent") is None
