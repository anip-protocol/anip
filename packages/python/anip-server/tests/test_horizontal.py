"""Tests for v0.10 horizontal-scaling StorageBackend methods."""
import pytest
from anip_server import InMemoryStorage, SQLiteStorage


@pytest.fixture
def memory_store():
    return InMemoryStorage()


@pytest.fixture
def sqlite_store(tmp_path):
    return SQLiteStorage(str(tmp_path / "test.db"))


@pytest.fixture(params=["memory", "sqlite"])
def store(request, memory_store, sqlite_store):
    return memory_store if request.param == "memory" else sqlite_store


class TestAppendAuditEntry:
    async def test_first_entry_gets_sequence_1(self, store):
        entry = await store.append_audit_entry({
            "capability": "test", "success": True, "timestamp": "2026-01-01T00:00:00Z",
        })
        assert entry["sequence_number"] == 1
        assert entry["previous_hash"] == "sha256:0"

    async def test_sequential_entries_increment(self, store):
        e1 = await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
        e2 = await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
        assert e2["sequence_number"] == 2
        assert e2["previous_hash"] != "sha256:0"

    async def test_previous_hash_chains(self, store):
        e1 = await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
        e2 = await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
        assert e2["previous_hash"].startswith("sha256:")
        assert len(e2["previous_hash"]) > 10


class TestUpdateAuditSignature:
    async def test_update_signature(self, store):
        entry = await store.append_audit_entry({
            "capability": "test", "success": True, "timestamp": "2026-01-01T00:00:00Z",
        })
        await store.update_audit_signature(entry["sequence_number"], "sig-abc")
        last = await store.get_last_audit_entry()
        assert last is not None
        assert last["signature"] == "sig-abc"


class TestGetMaxAuditSequence:
    async def test_empty_returns_none(self, store):
        assert await store.get_max_audit_sequence() is None

    async def test_returns_highest(self, store):
        await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
        await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
        assert await store.get_max_audit_sequence() == 2


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


class TestLeaderLeases:
    async def test_acquire_leader(self, store):
        assert await store.try_acquire_leader("checkpoint", "replica-1", 60) is True
        assert await store.try_acquire_leader("checkpoint", "replica-2", 60) is False

    async def test_release_and_reacquire(self, store):
        await store.try_acquire_leader("checkpoint", "replica-1", 60)
        await store.release_leader("checkpoint", "replica-1")
        assert await store.try_acquire_leader("checkpoint", "replica-2", 60) is True
