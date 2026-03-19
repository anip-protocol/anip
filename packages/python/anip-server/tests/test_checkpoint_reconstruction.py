"""Tests for storage-derived checkpoint reconstruction."""
import pytest

from anip_server.checkpoint import reconstruct_and_create_checkpoint
from anip_server.storage import InMemoryStorage


@pytest.mark.asyncio
async def test_reconstruct_creates_correct_merkle_root():
    store = InMemoryStorage()
    await store.append_audit_entry(
        {"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"}
    )
    await store.append_audit_entry(
        {"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"}
    )

    result = await reconstruct_and_create_checkpoint(
        storage=store, service_id="test-svc"
    )
    assert result is not None
    body, sig = result
    assert body["merkle_root"].startswith("sha256:")
    assert body["entry_count"] == 2


@pytest.mark.asyncio
async def test_reconstruct_returns_none_if_no_entries():
    store = InMemoryStorage()
    result = await reconstruct_and_create_checkpoint(
        storage=store, service_id="test-svc"
    )
    assert result is None


@pytest.mark.asyncio
async def test_reconstruct_returns_none_if_no_new_entries():
    store = InMemoryStorage()
    await store.append_audit_entry(
        {"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"}
    )

    result = await reconstruct_and_create_checkpoint(
        storage=store, service_id="test-svc"
    )
    body, sig = result
    await store.store_checkpoint(body, sig)

    # No new entries -- should return None
    result2 = await reconstruct_and_create_checkpoint(
        storage=store, service_id="test-svc"
    )
    assert result2 is None


@pytest.mark.asyncio
async def test_cumulative_root_covers_all_entries():
    store = InMemoryStorage()
    await store.append_audit_entry(
        {"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"}
    )
    r1 = await reconstruct_and_create_checkpoint(
        storage=store, service_id="test-svc"
    )
    body1, _ = r1
    await store.store_checkpoint(body1, "")

    await store.append_audit_entry(
        {"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"}
    )
    r2 = await reconstruct_and_create_checkpoint(
        storage=store, service_id="test-svc"
    )
    body2, _ = r2

    # Second checkpoint root should cover entries 1+2, not just entry 2
    assert body2["entry_count"] == 2
    assert body2["merkle_root"] != body1["merkle_root"]
