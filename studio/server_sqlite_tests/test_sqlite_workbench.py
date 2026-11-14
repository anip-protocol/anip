"""SQLite coverage for the Studio workbench and the timestamp serialisers.

The desktop app runs on SQLite, where ``created_at`` / ``updated_at`` come
back as ISO strings; under Postgres they are ``datetime`` objects. These tests
drive the real app against a real SQLite file, with no repository mocks, so a
serialiser that only works for one backend fails here.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from studio.server import db, repository
from studio.server.app import app
from studio.server.workbench_service import BOOTSTRAP_BEARER

WORKBENCH = "/studio-workbench/anip"

INTERPRETATION = {
    "title": "Intent Interpretation",
    "summary": "Travel needs a first design.",
    "recommended_shape_type": "single_service",
    "recommended_shape_reason": "Keep the main action together.",
    "requirements_focus": ["Make over-budget behavior explicit."],
    "scenario_starters": ["Add a scenario where the booking is over budget."],
    "domain_concepts": ["Booking", "Budget"],
    "service_suggestions": ["Start with one primary service."],
    "next_steps": ["Run evaluation."],
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    monkeypatch.delenv("STUDIO_SEED_SHOWCASES", raising=False)
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        db.close_pool()


def _invoke(client: TestClient, capability: str, parameters: dict) -> dict:
    issued = client.post(
        f"{WORKBENCH}/tokens",
        headers={"Authorization": f"Bearer {BOOTSTRAP_BEARER}"},
        json={
            "subject": "studio-agent",
            "scope": [f"studio.workbench.{capability}"],
            "capability": capability,
            "ttl_hours": 1,
        },
    )
    assert issued.status_code == 200, issued.text
    response = client.post(
        f"{WORKBENCH}/invoke/{capability}",
        headers={"Authorization": f"Bearer {issued.json()['token']}"},
        json={"parameters": parameters},
    )
    body = response.json()
    assert response.status_code == 200 and body.get("success"), response.text
    return body["result"]


def _assert_iso_timestamp(value) -> None:
    assert isinstance(value, str), f"expected an ISO string, got {value!r}"
    datetime.fromisoformat(value)


def test_sqlite_workbench_creates_project_and_initial_setup(client):
    """The "Create Initial Project Setup" flow, end to end on SQLite."""
    workspace = _invoke(client, "create_workspace", {"name": "Desktop Workspace"})["workspace"]
    project = _invoke(
        client,
        "create_project",
        {
            "name": "Travel Project",
            "workspace_id": workspace["id"],
            "summary": "Travel booking stress test",
            "domain": "travel",
        },
    )["project"]
    assert project["workspace_id"] == workspace["id"]

    setup = _invoke(
        client,
        "accept_first_design",
        {
            "project_id": project["id"],
            "source_intent": "Book travel and block over-budget booking.",
            "interpretation": INTERPRETATION,
        },
    )
    assert setup["shape"]["requirements_id"] == setup["requirements"]["id"]
    assert len(setup["scenarios"]) >= 1
    for artifact in [setup["requirements"], setup["shape"], *setup["scenarios"]]:
        _assert_iso_timestamp(artifact["created_at"])
        _assert_iso_timestamp(artifact["updated_at"])

    state = _invoke(client, "read_project_state", {"project_id": project["id"]})
    assert state["project"]["counts"] == {
        "requirements": 1,
        "scenarios": len(setup["scenarios"]),
        "shapes": 1,
        "evaluations": 0,
    }
    assert [item["id"] for item in state["requirements"]] == [setup["requirements"]["id"]]
    for artifact in [*state["requirements"], *state["scenarios"], *state["shapes"]]:
        _assert_iso_timestamp(artifact["created_at"])
        _assert_iso_timestamp(artifact["updated_at"])


def test_sqlite_workbench_lists_evaluation_timestamps(client):
    """read_project_state also serialises evaluation rows."""
    project = _invoke(client, "create_project", {"name": "Evaluated Project"})["project"]
    setup = _invoke(
        client,
        "accept_first_design",
        {
            "project_id": project["id"],
            "source_intent": "Book travel and block over-budget booking.",
            "interpretation": INTERPRETATION,
        },
    )
    evaluated = _invoke(
        client,
        "evaluate_service_design",
        {
            "project_id": project["id"],
            "requirements_id": setup["requirements"]["id"],
            "scenario_id": setup["scenarios"][0]["id"],
            "shape_id": setup["shape"]["id"],
        },
    )

    state = _invoke(client, "read_project_state", {"project_id": project["id"]})
    assert [item["id"] for item in state["evaluations"]] == [evaluated["evaluation_id"]]
    _assert_iso_timestamp(state["evaluations"][0]["created_at"])


@pytest.mark.parametrize(
    ("path", "create", "state"),
    [
        (
            "/api/data-access-projects",
            repository.create_data_access_project,
            {"name": "Orders Data Access"},
        ),
        (
            "/api/application-integration-projects",
            repository.create_application_integration_project,
            {"title": "CRM Integration"},
        ),
    ],
)
def test_sqlite_draft_project_lists_serialise_timestamps(client, path, create, state):
    with db.get_pool().connection() as conn:
        create(conn, "draft-1", state)

    response = client.get(path)

    assert response.status_code == 200, response.text
    [summary] = response.json()
    assert summary["id"] == "draft-1"
    _assert_iso_timestamp(summary["created_at"])
    _assert_iso_timestamp(summary["updated_at"])
