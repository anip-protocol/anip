"""Storage tests for v0.23 approval requests + grants.

Covers both InMemoryStorage and SQLiteStorage implementations of:
- store_approval_request / get_approval_request
- store_grant / get_grant
- approve_request_and_store_grant (atomic, per Decision 0.9a)
- try_reserve_grant (atomic, per Phase 7.3 Phase B)

Plus concurrent reservation/issuance tests for the security boundary.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from anip_server.storage import InMemoryStorage, SQLiteStorage


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(seconds: int = 900) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past_iso(seconds: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _approval_request(
    *,
    request_id: str = "apr_test",
    capability: str = "finance.transfer_funds",
    expires_at: str | None = None,
) -> dict:
    return {
        "approval_request_id": request_id,
        "capability": capability,
        "scope": ["finance.write"],
        "requester": {"principal": "user_123"},
        "parent_invocation_id": None,
        "preview": {"amount": 50000},
        "preview_digest": "sha256:preview",
        "requested_parameters": {"amount": 50000},
        "requested_parameters_digest": "sha256:params",
        "grant_policy": {
            "allowed_grant_types": ["one_time"],
            "default_grant_type": "one_time",
            "expires_in_seconds": 900,
            "max_uses": 1,
        },
        "status": "pending",
        "approver": None,
        "decided_at": None,
        "created_at": _now_iso(),
        "expires_at": expires_at or _future_iso(),
    }


def _grant(
    *,
    grant_id: str = "grant_test",
    request_id: str = "apr_test",
    grant_type: str = "one_time",
    max_uses: int = 1,
    session_id: str | None = None,
    expires_at: str | None = None,
) -> dict:
    return {
        "grant_id": grant_id,
        "approval_request_id": request_id,
        "grant_type": grant_type,
        "capability": "finance.transfer_funds",
        "scope": ["finance.write"],
        "approved_parameters_digest": "sha256:params",
        "preview_digest": "sha256:preview",
        "requester": {"principal": "user_123"},
        "approver": {"principal": "manager_456"},
        "issued_at": _now_iso(),
        "expires_at": expires_at or _future_iso(),
        "max_uses": max_uses,
        "use_count": 0,
        "session_id": session_id,
        "signature": "sig_test",
    }


@pytest.fixture(params=["inmem", "sqlite"])
def store(request):
    if request.param == "inmem":
        return InMemoryStorage()
    return SQLiteStorage(":memory:")


async def _ensure_approval_request_for(store, request_id: str = "apr_test") -> None:
    """Helper for tests that store a grant directly via the test-only
    store_grant primitive. SQLite enforces a FK on approval_request_id; we
    seed a parent row so the FK is satisfied. InMemoryStorage tolerates
    missing parents (test-only path)."""
    if isinstance(store, SQLiteStorage):
        await store.store_approval_request(_approval_request(request_id=request_id))


# --- store / get round-trips ------------------------------------------------


@pytest.mark.asyncio
async def test_store_and_get_approval_request_round_trip(store):
    req = _approval_request()
    await store.store_approval_request(req)
    loaded = await store.get_approval_request("apr_test")
    assert loaded is not None
    assert loaded["approval_request_id"] == "apr_test"
    assert loaded["capability"] == "finance.transfer_funds"
    assert loaded["status"] == "pending"
    assert loaded["scope"] == ["finance.write"]
    assert loaded["grant_policy"]["expires_in_seconds"] == 900


@pytest.mark.asyncio
async def test_get_approval_request_missing_returns_none(store):
    assert await store.get_approval_request("nope") is None


@pytest.mark.asyncio
async def test_store_approval_request_idempotent_same_content(store):
    """SPEC.md §4.7: re-storing identical content under same id is a no-op."""
    req = _approval_request()
    await store.store_approval_request(req)
    # Second store with the exact same dict must not raise.
    await store.store_approval_request(dict(req))
    loaded = await store.get_approval_request("apr_test")
    assert loaded is not None
    assert loaded["approval_request_id"] == "apr_test"


@pytest.mark.asyncio
async def test_store_approval_request_conflict_raises(store):
    """SPEC.md §4.7: re-storing different content under same id is an error.
    Prevents silent mutation of an already-persisted ApprovalRequest."""
    req = _approval_request()
    await store.store_approval_request(req)
    mutated = dict(req)
    mutated["preview"] = {"amount": 99999}  # different content, same id
    with pytest.raises(ValueError, match="already stored with different content"):
        await store.store_approval_request(mutated)
    # Original content preserved.
    loaded = await store.get_approval_request("apr_test")
    assert loaded["preview"] == {"amount": 50000}


@pytest.mark.asyncio
async def test_store_and_get_grant_round_trip(store):
    await _ensure_approval_request_for(store)
    g = _grant()
    await store.store_grant(g)
    loaded = await store.get_grant("grant_test")
    assert loaded is not None
    assert loaded["grant_id"] == "grant_test"
    assert loaded["approval_request_id"] == "apr_test"
    assert loaded["use_count"] == 0


# --- approve_request_and_store_grant ---------------------------------------


@pytest.mark.asyncio
async def test_approve_request_and_store_grant_happy_path(store):
    req = _approval_request()
    await store.store_approval_request(req)
    result = await store.approve_request_and_store_grant(
        "apr_test",
        _grant(),
        approver={"principal": "manager_456"},
        decided_at_iso=_now_iso(),
        now_iso=_now_iso(),
    )
    assert result["ok"] is True
    assert result["grant"]["grant_id"] == "grant_test"
    # Approval request transitioned
    loaded_req = await store.get_approval_request("apr_test")
    assert loaded_req["status"] == "approved"
    assert loaded_req["approver"] == {"principal": "manager_456"}
    # Grant persisted
    loaded_grant = await store.get_grant("grant_test")
    assert loaded_grant is not None


@pytest.mark.asyncio
async def test_approve_request_not_found(store):
    result = await store.approve_request_and_store_grant(
        "nope", _grant(), {}, _now_iso(), _now_iso()
    )
    assert result["ok"] is False
    assert result["reason"] == "approval_request_not_found"


@pytest.mark.asyncio
async def test_approve_already_decided(store):
    req = _approval_request()
    await store.store_approval_request(req)
    await store.approve_request_and_store_grant(
        "apr_test", _grant(grant_id="g1"), {"principal": "u2"}, _now_iso(), _now_iso()
    )
    # Second attempt fails.
    result = await store.approve_request_and_store_grant(
        "apr_test",
        _grant(grant_id="g2"),
        {"principal": "u3"},
        _now_iso(),
        _now_iso(),
    )
    assert result["ok"] is False
    assert result["reason"] == "approval_request_already_decided"


@pytest.mark.asyncio
async def test_approve_request_expired(store):
    req = _approval_request(expires_at=_past_iso())
    await store.store_approval_request(req)
    result = await store.approve_request_and_store_grant(
        "apr_test", _grant(), {"principal": "u2"}, _now_iso(), _now_iso()
    )
    assert result["ok"] is False
    assert result["reason"] == "approval_request_expired"


@pytest.mark.asyncio
async def test_concurrent_approve_request_and_store_grant(store):
    """Concurrent approval attempts: exactly 1 succeeds, N-1 receive
    approval_request_already_decided.
    """
    req = _approval_request()
    await store.store_approval_request(req)
    n = 10
    grants = [_grant(grant_id=f"g{i}") for i in range(n)]
    coros = [
        store.approve_request_and_store_grant(
            "apr_test",
            grants[i],
            {"principal": f"u{i}"},
            _now_iso(),
            _now_iso(),
        )
        for i in range(n)
    ]
    results = await asyncio.gather(*coros)
    successes = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]
    assert len(successes) == 1
    assert len(failures) == n - 1
    for f in failures:
        assert f["reason"] == "approval_request_already_decided"
    # Exactly one approval_request approved.
    loaded_req = await store.get_approval_request("apr_test")
    assert loaded_req["status"] == "approved"


# --- try_reserve_grant -----------------------------------------------------


@pytest.mark.asyncio
async def test_try_reserve_grant_happy_path(store):
    await _ensure_approval_request_for(store)
    g = _grant()
    await store.store_grant(g)
    result = await store.try_reserve_grant("grant_test", _now_iso())
    assert result["ok"] is True
    assert result["grant"]["use_count"] == 1


@pytest.mark.asyncio
async def test_try_reserve_grant_not_found(store):
    result = await store.try_reserve_grant("nope", _now_iso())
    assert result["ok"] is False
    assert result["reason"] == "grant_not_found"


@pytest.mark.asyncio
async def test_try_reserve_grant_expired(store):
    await _ensure_approval_request_for(store)
    g = _grant(expires_at=_past_iso())
    await store.store_grant(g)
    result = await store.try_reserve_grant("grant_test", _now_iso())
    assert result["ok"] is False
    assert result["reason"] == "grant_expired"


@pytest.mark.asyncio
async def test_try_reserve_grant_one_time_consumed(store):
    await _ensure_approval_request_for(store)
    g = _grant(max_uses=1)
    await store.store_grant(g)
    first = await store.try_reserve_grant("grant_test", _now_iso())
    assert first["ok"] is True
    second = await store.try_reserve_grant("grant_test", _now_iso())
    assert second["ok"] is False
    assert second["reason"] == "grant_consumed"


@pytest.mark.asyncio
async def test_try_reserve_grant_session_bound_max_uses(store):
    await _ensure_approval_request_for(store)
    g = _grant(grant_type="session_bound", max_uses=3, session_id="sess_1")
    await store.store_grant(g)
    for _ in range(3):
        r = await store.try_reserve_grant("grant_test", _now_iso())
        assert r["ok"] is True
    fourth = await store.try_reserve_grant("grant_test", _now_iso())
    assert fourth["ok"] is False
    assert fourth["reason"] == "grant_consumed"


@pytest.mark.asyncio
async def test_concurrent_try_reserve_grant_one_time(store):
    """N parallel reservations: exactly 1 succeeds, N-1 receive grant_consumed.

    This is the security-critical atomicity test for §4.8.
    """
    await _ensure_approval_request_for(store)
    g = _grant(max_uses=1)
    await store.store_grant(g)
    n = 10
    coros = [store.try_reserve_grant("grant_test", _now_iso()) for _ in range(n)]
    results = await asyncio.gather(*coros)
    successes = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]
    assert len(successes) == 1
    assert len(failures) == n - 1
    for f in failures:
        assert f["reason"] == "grant_consumed"


@pytest.mark.asyncio
async def test_concurrent_try_reserve_session_bound_respects_max_uses(store):
    """Session-bound grant with max_uses=3 and N=10 parallel reservations:
    exactly 3 succeed, 7 receive grant_consumed.
    """
    await _ensure_approval_request_for(store)
    g = _grant(grant_type="session_bound", max_uses=3, session_id="sess_1")
    await store.store_grant(g)
    n = 10
    coros = [store.try_reserve_grant("grant_test", _now_iso()) for _ in range(n)]
    results = await asyncio.gather(*coros)
    successes = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]
    assert len(successes) == 3
    assert len(failures) == 7


# --- defense-in-depth ------------------------------------------------------


@pytest.mark.asyncio
async def test_grants_unique_approval_request_id_constraint_sqlite():
    """Defense-in-depth: even if a flawed implementation bypassed the
    conditional UPDATE in approve_request_and_store_grant, the grants table's
    UNIQUE constraint on approval_request_id prevents two grants from
    coexisting for one approval request.

    Verified by attempting two raw INSERTs (bypassing the test-only
    INSERT OR REPLACE store_grant)."""
    import json
    import sqlite3
    store = SQLiteStorage(":memory:")
    await store.store_approval_request(_approval_request(request_id="apr_x"))
    g1 = _grant(grant_id="g1", request_id="apr_x")
    g2 = _grant(grant_id="g2", request_id="apr_x")
    await store.store_grant(g1)
    # Direct INSERT (not REPLACE) — must trigger UNIQUE violation.
    with store._lock:
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(
                """INSERT INTO approval_grants
                   (grant_id, approval_request_id, grant_type, capability, scope,
                    approved_parameters_digest, preview_digest, requester, approver,
                    issued_at, expires_at, max_uses, use_count, session_id, signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    g2["grant_id"], g2["approval_request_id"], g2["grant_type"],
                    g2["capability"], json.dumps(g2["scope"]),
                    g2["approved_parameters_digest"], g2["preview_digest"],
                    json.dumps(g2["requester"]), json.dumps(g2["approver"]),
                    g2["issued_at"], g2["expires_at"], g2["max_uses"],
                    g2["use_count"], g2["session_id"], g2["signature"],
                ),
            )
