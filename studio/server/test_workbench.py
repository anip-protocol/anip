"""Tests for the ANIP-backed Studio workbench service."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio.server.app import mount_anip
import studio.server.workbench_service as workbench_service

BOOTSTRAP = "studio-workbench-bootstrap"


@contextmanager
def _dummy_connection():
    yield object()


class _DummyPool:
    def connection(self):
        return _dummy_connection()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(workbench_service, "get_pool", lambda: _DummyPool())
    app = FastAPI()
    mount_anip(app, workbench_service.create_studio_workbench_service(), prefix="/studio-workbench")
    with TestClient(app) as c:
        yield c


def _issue_token(client: TestClient, capability: str) -> str:
    resp = client.post(
        "/studio-workbench/anip/tokens",
        headers={"Authorization": f"Bearer {BOOTSTRAP}"},
        json={
            "subject": "studio-agent",
            "scope": [f"studio.workbench.{capability}"],
            "capability": capability,
            "ttl_hours": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_workbench_manifest_exposes_core_capabilities(client: TestClient):
    resp = client.get("/studio-workbench/anip/manifest")
    assert resp.status_code == 200, resp.text
    caps = resp.json()["capabilities"]
    assert "create_project" in caps
    assert "accept_first_design" in caps
    assert "evaluate_service_design" in caps
    assert "generate_business_brief" in caps


def test_workbench_can_accept_first_design(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Travel Project",
            "summary": "Travel booking stress test",
            "domain": "travel",
            "requirements_count": 0,
            "scenarios_count": 0,
            "shapes_count": 0,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "create_requirements",
        lambda _conn, **kwargs: {
            "id": kwargs["req_id"],
            "title": kwargs["title"],
            "role": "primary",
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "create_scenario",
        lambda _conn, **kwargs: {
            "id": kwargs["scenario_id"],
            "title": kwargs["title"],
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "create_shape",
        lambda _conn, **kwargs: {
            "id": kwargs["shape_id"],
            "title": kwargs["title"],
            "requirements_id": kwargs["requirements_id"],
        },
    )

    token = _issue_token(client, "accept_first_design")
    resp = client.post(
        "/studio-workbench/anip/invoke/accept_first_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-stress",
                "source_intent": "Book travel and block over-budget booking.",
                "interpretation": {
                    "title": "Intent Interpretation",
                    "summary": "Travel needs a first design.",
                    "recommended_shape_type": "single_service",
                    "recommended_shape_reason": "Keep the main action together.",
                    "requirements_focus": ["Make over-budget behavior explicit."],
                    "scenario_starters": ["Add a scenario where the booking is over budget."],
                    "domain_concepts": ["Booking", "Budget"],
                    "service_suggestions": ["Start with one primary service."],
                    "next_steps": ["Run evaluation."],
                },
            }
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["requirements"]["role"] == "primary"
    assert len(result["scenarios"]) == 1
    assert result["shape"]["requirements_id"] == result["requirements"]["id"]


def test_workbench_can_evaluate_service_design(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_requirements",
        lambda _conn, _pid, _rid: {"id": "req-1", "data": {"system": {"name": "travel"}}},
    )
    monkeypatch.setattr(
        workbench_service,
        "get_scenario",
        lambda _conn, _pid, _sid: {"id": "scn-1", "data": {"scenario": {"name": "book_over_budget"}}},
    )
    monkeypatch.setattr(
        workbench_service,
        "get_shape",
        lambda _conn, _pid, _shid: {"id": "shape-1", "data": {"shape": {"type": "single_service"}}},
    )
    monkeypatch.setattr(workbench_service, "validate_payload", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workbench_service, "build_shape_backed_proposal", lambda *_args, **_kwargs: {"proposal": {"shape_backed": True}})
    monkeypatch.setattr(
        workbench_service,
        "evaluate",
        lambda *_args, **_kwargs: {
            "evaluation": {
                "result": "PARTIAL",
                "handled_by_anip": ["budget visibility"],
                "what_would_improve": ["Add explicit approval routing."],
            }
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "create_evaluation",
        lambda _conn, **kwargs: {
            "id": kwargs["eval_id"],
            "result": kwargs["data"]["evaluation"]["result"],
        },
    )

    token = _issue_token(client, "evaluate_service_design")
    resp = client.post(
        "/studio-workbench/anip/invoke/evaluate_service_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-stress",
                "requirements_id": "req-1",
                "scenario_id": "scn-1",
                "shape_id": "shape-1",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["result"] == "PARTIAL"
    assert result["evaluation"]["what_would_improve"] == ["Add explicit approval routing."]
