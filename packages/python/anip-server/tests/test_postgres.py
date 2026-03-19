"""Tests for PostgresStorage backend.

These tests require a running PostgreSQL instance. Set the
``ANIP_TEST_POSTGRES_DSN`` environment variable to a valid DSN
(e.g. ``postgresql://user:pass@localhost/anip_test``) to run them.
"""

import os

import pytest

POSTGRES_DSN: str = os.environ.get("ANIP_TEST_POSTGRES_DSN", "")
pytestmark = pytest.mark.skipif(
    not POSTGRES_DSN, reason="ANIP_TEST_POSTGRES_DSN not set"
)


@pytest.fixture
async def store():
    from anip_server.postgres import PostgresStorage

    s = PostgresStorage(POSTGRES_DSN)
    await s.initialize()

    # Clean tables before each test for isolation
    pool = s._get_pool()
    await pool.execute("DELETE FROM audit_log")
    await pool.execute("DELETE FROM delegation_tokens")
    await pool.execute("DELETE FROM checkpoints")
    await pool.execute("DELETE FROM exclusive_leases")
    await pool.execute("DELETE FROM leader_leases")
    await pool.execute(
        "UPDATE audit_append_head SET last_sequence_number = 0, last_hash = 'sha256:0' WHERE id = 1"
    )

    yield s
    await s.close()


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------


class TestTokenStorage:
    async def test_store_and_load(self, store):
        token = {
            "token_id": "tok-1",
            "issuer": "alice",
            "subject": "bob",
            "scope": ["read"],
            "purpose": {"task": "test"},
            "parent": None,
            "expires": "2099-01-01T00:00:00Z",
            "constraints": {"max_calls": 10},
            "root_principal": "alice",
            "caller_class": "human",
        }
        await store.store_token(token)
        loaded = await store.load_token("tok-1")
        assert loaded is not None
        assert loaded["token_id"] == "tok-1"
        assert loaded["scope"] == ["read"]
        assert loaded["purpose"] == {"task": "test"}
        assert loaded["constraints"] == {"max_calls": 10}

    async def test_load_missing_returns_none(self, store):
        assert await store.load_token("nonexistent") is None


# ---------------------------------------------------------------------------
# Audit append tests
# ---------------------------------------------------------------------------


class TestAppendAuditEntry:
    async def test_first_entry_gets_sequence_1(self, store):
        entry = await store.append_audit_entry(
            {
                "capability": "test",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        assert entry["sequence_number"] == 1
        assert entry["previous_hash"] == "sha256:0"

    async def test_sequential_entries_increment(self, store):
        await store.append_audit_entry(
            {
                "capability": "a",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        e2 = await store.append_audit_entry(
            {
                "capability": "b",
                "success": True,
                "timestamp": "2026-01-01T00:00:01Z",
            }
        )
        assert e2["sequence_number"] == 2
        assert e2["previous_hash"] != "sha256:0"

    async def test_previous_hash_chains(self, store):
        await store.append_audit_entry(
            {
                "capability": "a",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        e2 = await store.append_audit_entry(
            {
                "capability": "b",
                "success": True,
                "timestamp": "2026-01-01T00:00:01Z",
            }
        )
        assert e2["previous_hash"].startswith("sha256:")
        assert len(e2["previous_hash"]) > 10


# ---------------------------------------------------------------------------
# Signature update tests
# ---------------------------------------------------------------------------


class TestUpdateAuditSignature:
    async def test_update_signature(self, store):
        entry = await store.append_audit_entry(
            {
                "capability": "test",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        await store.update_audit_signature(entry["sequence_number"], "sig-abc")
        last = await store.get_last_audit_entry()
        assert last is not None
        assert last["signature"] == "sig-abc"


# ---------------------------------------------------------------------------
# Max sequence tests
# ---------------------------------------------------------------------------


class TestGetMaxAuditSequence:
    async def test_empty_returns_none(self, store):
        assert await store.get_max_audit_sequence() is None

    async def test_returns_highest(self, store):
        await store.append_audit_entry(
            {
                "capability": "a",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        await store.append_audit_entry(
            {
                "capability": "b",
                "success": True,
                "timestamp": "2026-01-01T00:00:01Z",
            }
        )
        assert await store.get_max_audit_sequence() == 2


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------


class TestQueryAuditEntries:
    async def test_query_by_capability(self, store):
        await store.append_audit_entry(
            {
                "capability": "read",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        await store.append_audit_entry(
            {
                "capability": "write",
                "success": True,
                "timestamp": "2026-01-01T00:00:01Z",
            }
        )
        results = await store.query_audit_entries(capability="read")
        assert len(results) == 1
        assert results[0]["capability"] == "read"

    async def test_query_all(self, store):
        await store.append_audit_entry(
            {
                "capability": "a",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        await store.append_audit_entry(
            {
                "capability": "b",
                "success": True,
                "timestamp": "2026-01-01T00:00:01Z",
            }
        )
        results = await store.query_audit_entries()
        assert len(results) == 2

    async def test_query_with_limit(self, store):
        for i in range(5):
            await store.append_audit_entry(
                {
                    "capability": "op",
                    "success": True,
                    "timestamp": f"2026-01-01T00:00:0{i}Z",
                }
            )
        results = await store.query_audit_entries(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Range queries and expiry
# ---------------------------------------------------------------------------


class TestAuditEntriesRange:
    async def test_get_range(self, store):
        for i in range(5):
            await store.append_audit_entry(
                {
                    "capability": f"op-{i}",
                    "success": True,
                    "timestamp": f"2026-01-01T00:00:0{i}Z",
                }
            )
        entries = await store.get_audit_entries_range(2, 4)
        assert len(entries) == 3
        assert entries[0]["sequence_number"] == 2
        assert entries[-1]["sequence_number"] == 4


class TestDeleteExpiredEntries:
    async def test_delete_expired(self, store):
        await store.append_audit_entry(
            {
                "capability": "old",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
                "expires_at": "2026-01-01T00:00:00Z",
            }
        )
        await store.append_audit_entry(
            {
                "capability": "new",
                "success": True,
                "timestamp": "2026-06-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
            }
        )
        deleted = await store.delete_expired_audit_entries("2026-06-01T00:00:00Z")
        assert deleted == 1


class TestEarliestExpiry:
    async def test_earliest_expiry(self, store):
        await store.append_audit_entry(
            {
                "capability": "a",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
                "expires_at": "2026-06-01T00:00:00Z",
            }
        )
        await store.append_audit_entry(
            {
                "capability": "b",
                "success": True,
                "timestamp": "2026-01-01T00:00:01Z",
                "expires_at": "2026-03-01T00:00:00Z",
            }
        )
        earliest = await store.get_earliest_expiry_in_range(1, 2)
        assert earliest == "2026-03-01T00:00:00Z"

    async def test_no_expiry_returns_none(self, store):
        await store.append_audit_entry(
            {
                "capability": "a",
                "success": True,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        earliest = await store.get_earliest_expiry_in_range(1, 1)
        assert earliest is None


# ---------------------------------------------------------------------------
# Checkpoint tests
# ---------------------------------------------------------------------------


class TestCheckpoints:
    async def test_store_and_get(self, store):
        body = {
            "checkpoint_id": "ckpt-1",
            "range": {"first_sequence": 1, "last_sequence": 10},
            "merkle_root": "sha256:abc",
            "previous_checkpoint": None,
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_count": 10,
        }
        await store.store_checkpoint(body, "sig-1")
        checkpoints = await store.get_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0]["checkpoint_id"] == "ckpt-1"
        assert checkpoints[0]["signature"] == "sig-1"

    async def test_get_by_id(self, store):
        body = {
            "checkpoint_id": "ckpt-2",
            "range": {"first_sequence": 1, "last_sequence": 5},
            "merkle_root": "sha256:def",
            "previous_checkpoint": None,
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_count": 5,
        }
        await store.store_checkpoint(body, "sig-2")
        ckpt = await store.get_checkpoint_by_id("ckpt-2")
        assert ckpt is not None
        assert ckpt["merkle_root"] == "sha256:def"

    async def test_missing_checkpoint_returns_none(self, store):
        assert await store.get_checkpoint_by_id("nonexistent") is None


# ---------------------------------------------------------------------------
# Exclusive lease tests
# ---------------------------------------------------------------------------


class TestExclusiveLeases:
    async def test_acquire_and_release(self, store):
        assert await store.try_acquire_exclusive("key1", "holder-a", 30) is True
        assert await store.try_acquire_exclusive("key1", "holder-b", 30) is False
        await store.release_exclusive("key1", "holder-a")
        assert await store.try_acquire_exclusive("key1", "holder-b", 30) is True

    async def test_same_holder_can_reacquire(self, store):
        assert await store.try_acquire_exclusive("key1", "holder-a", 30) is True
        assert await store.try_acquire_exclusive("key1", "holder-a", 30) is True

    async def test_wrong_holder_cannot_release(self, store):
        await store.try_acquire_exclusive("key1", "holder-a", 30)
        await store.release_exclusive("key1", "holder-b")  # wrong holder
        assert await store.try_acquire_exclusive("key1", "holder-b", 30) is False


# ---------------------------------------------------------------------------
# Leader lease tests
# ---------------------------------------------------------------------------


class TestLeaderLeases:
    async def test_acquire_leader(self, store):
        assert await store.try_acquire_leader("checkpoint", "replica-1", 60) is True
        assert await store.try_acquire_leader("checkpoint", "replica-2", 60) is False

    async def test_release_and_reacquire(self, store):
        await store.try_acquire_leader("checkpoint", "replica-1", 60)
        await store.release_leader("checkpoint", "replica-1")
        assert await store.try_acquire_leader("checkpoint", "replica-2", 60) is True


# ---------------------------------------------------------------------------
# store_audit_entry (direct, non-appending)
# ---------------------------------------------------------------------------


class TestStoreAuditEntry:
    async def test_store_and_query(self, store):
        entry = {
            "sequence_number": 1,
            "timestamp": "2026-01-01T00:00:00Z",
            "capability": "test",
            "success": True,
            "previous_hash": "sha256:0",
            "parameters": {"key": "value"},
        }
        await store.store_audit_entry(entry)
        last = await store.get_last_audit_entry()
        assert last is not None
        assert last["capability"] == "test"
        assert last["parameters"] == {"key": "value"}
        assert last["success"] is True
