"""Tests for requirements set role enforcement (primary / alternative).

Verifies that:
1. The first requirements set in a project gets role='primary' automatically
2. The second requirements set defaults to role='alternative'
3. The DB partial unique index prevents two primary sets in the same project
4. Promoting an alternative to primary demotes the current primary (repository level)
5. Deleting a primary requirements set is still blocked by proposal refs (409)
"""

import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")

import uuid
import pytest

from studio.server.db import get_pool
from studio.server.repository import set_requirements_role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pid():
    return f"role-{uuid.uuid4().hex[:8]}"


def _create_project(client, pid):
    r = client.post("/api/projects", json={"id": pid, "name": f"Project {pid}"})
    assert r.status_code == 201, r.text
    return pid


def _create_req(client, pid, req_id, title="Requirements", data=None):
    if data is None:
        data = {"system": {"name": title}}
    r = client.post(f"/api/projects/{pid}/requirements", json={
        "id": req_id,
        "title": title,
        "data": data,
    })
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test 1: First requirements set gets role='primary'
# ---------------------------------------------------------------------------

def test_first_requirements_set_is_primary(client):
    pid = _pid()
    _create_project(client, pid)
    req = _create_req(client, pid, f"req1-{pid}", "First Requirements")
    assert req["role"] == "primary"


# ---------------------------------------------------------------------------
# Test 2: Second requirements set defaults to role='alternative'
# ---------------------------------------------------------------------------

def test_second_requirements_set_is_alternative(client):
    pid = _pid()
    _create_project(client, pid)
    req1 = _create_req(client, pid, f"req1-{pid}", "First")
    req2 = _create_req(client, pid, f"req2-{pid}", "Second")
    assert req1["role"] == "primary"
    assert req2["role"] == "alternative"


# ---------------------------------------------------------------------------
# Test 3: DB unique index prevents two primary sets in the same project
# ---------------------------------------------------------------------------

def test_cannot_insert_two_primary_sets_directly(client):
    """Direct INSERT of a second primary must be rejected by the partial unique index."""
    pid = _pid()
    _create_project(client, pid)
    _create_req(client, pid, f"req1-{pid}", "First")

    # Attempt a raw INSERT bypassing the repository role logic
    with get_pool().connection() as conn:
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO requirements_sets"
                " (id, project_id, title, data, content_hash, role)"
                " VALUES (%s, %s, %s, '{}'::jsonb, '', 'primary')",
                (f"req-dup-{pid}", pid, "Duplicate Primary"),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Test 4: Promoting alternative to primary demotes the current primary
# ---------------------------------------------------------------------------

def test_promote_alternative_to_primary_demotes_old_primary(client):
    pid = _pid()
    _create_project(client, pid)
    req1 = _create_req(client, pid, f"req1-{pid}", "First")
    req2 = _create_req(client, pid, f"req2-{pid}", "Second")

    assert req1["role"] == "primary"
    assert req2["role"] == "alternative"

    # Promote req2 to primary via repository function
    with get_pool().connection() as conn:
        updated = set_requirements_role(conn, pid, f"req2-{pid}", "primary")

    assert updated["role"] == "primary"

    # req1 should now be alternative — verify via API
    r = client.get(f"/api/projects/{pid}/requirements/{req1['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "alternative"

    # req2 should be primary
    r = client.get(f"/api/projects/{pid}/requirements/{req2['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "primary"


# ---------------------------------------------------------------------------
# Test 5: Delete primary requirements set blocked by proposal refs
# ---------------------------------------------------------------------------

def test_delete_primary_requirements_blocked_by_proposal(client):
    """Even though it's the primary set, deleting it is blocked if proposals reference it."""
    pid = _pid()
    _create_project(client, pid)
    req = _create_req(client, pid, f"req1-{pid}", "Primary Requirements")
    assert req["role"] == "primary"

    # Create a proposal referencing the primary requirements set
    prop_id = f"prop-{pid}"
    r = client.post(f"/api/projects/{pid}/proposals", json={
        "id": prop_id,
        "title": "Proposal",
        "requirements_id": req["id"],
        "data": {"proposal": {"name": "test"}},
    })
    assert r.status_code == 201, r.text

    # Attempt to delete the primary requirements set — must be blocked with 409
    r = client.delete(f"/api/projects/{pid}/requirements/{req['id']}")
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["blocked_by"] == "proposals"
    assert prop_id in detail["refs"]
