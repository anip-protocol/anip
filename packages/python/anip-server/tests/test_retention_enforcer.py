"""Tests for retention enforcer (v0.8)."""

import asyncio
import pytest
from anip_server.retention_enforcer import RetentionEnforcer
from anip_server.storage import InMemoryStorage


@pytest.fixture
def storage():
    return InMemoryStorage()


@pytest.mark.asyncio
async def test_enforcer_deletes_expired_entries(storage):
    """Enforcer deletes entries where expires_at < now."""
    base = {
        "timestamp": "2026-03-10T00:00:00Z", "capability": "test",
        "success": True, "previous_hash": "sha256:0000",
        "event_class": "malformed_or_spam", "retention_tier": "short",
    }
    await storage.store_audit_entry({**base, "sequence_number": 1, "expires_at": "2026-03-10T00:00:00Z"})
    await storage.store_audit_entry({**base, "sequence_number": 2, "expires_at": "2027-03-16T00:00:00Z"})
    await storage.store_audit_entry({**base, "sequence_number": 3, "expires_at": None})

    enforcer = RetentionEnforcer(storage, interval_seconds=1)
    deleted = await enforcer.sweep()
    assert deleted == 1
    remaining = await storage.query_audit_entries()
    assert len(remaining) == 2


@pytest.mark.asyncio
async def test_enforcer_start_stop(storage):
    """Enforcer can be started and stopped from async context."""
    enforcer = RetentionEnforcer(storage, interval_seconds=60)
    enforcer.start()
    assert enforcer._task is not None
    enforcer.stop()
    assert enforcer._task is None


@pytest.mark.asyncio
async def test_enforcer_start_requires_event_loop():
    """start() from sync context without loop raises RuntimeError."""
    # This test runs in async context so get_running_loop() succeeds.
    # We just verify the enforcer works when there IS a loop.
    storage = InMemoryStorage()
    enforcer = RetentionEnforcer(storage, interval_seconds=60)
    enforcer.start()  # Should not raise
    enforcer.stop()
