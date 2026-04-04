"""Tests for the ANIP-backed Studio assistant service.

These tests intentionally mount the assistant as a real ANIP service while
stubbing Studio's repository layer. That keeps the dogfooding slice honest
without depending on the Studio Postgres lifecycle.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio.server.app import mount_anip
import studio.server.assistant_service as assistant_service

BOOTSTRAP = "studio-assistant-bootstrap"


@contextmanager
def _dummy_connection():
    yield object()


class _DummyPool:
    def connection(self):
        return _dummy_connection()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(assistant_service, "get_pool", lambda: _DummyPool())

    app = FastAPI()
    mount_anip(app, assistant_service.create_studio_assistant_service(), prefix="/studio-assistant")

    with TestClient(app) as c:
        yield c


def _issue_token(client: TestClient, capability: str) -> str:
    resp = client.post(
        "/studio-assistant/anip/tokens",
        headers={"Authorization": f"Bearer {BOOTSTRAP}"},
        json={
            "subject": "studio-ui",
            "scope": [f"studio.assistant.{capability}"],
            "capability": capability,
            "ttl_hours": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["issued"] is True
    return data["token"]


def test_assistant_manifest_exposes_explanation_capabilities(client: TestClient):
    resp = client.get("/studio-assistant/anip/manifest")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    caps = body["capabilities"]
    assert "explain_shape" in caps
    assert "explain_evaluation" in caps
    assert "interpret_project_intent" in caps


def test_assistant_can_explain_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Travel Project"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Travel Shape",
            "requirements_id": "req-travel",
            "data": {
                "shape": {
                    "id": "travel-shape",
                    "name": "Travel Booking Service",
                    "type": "single_service",
                    "notes": ["Keep booking and authority checks together initially."],
                    "services": [
                        {
                            "id": "svc-booking",
                            "name": "Booking Service",
                            "role": "books travel",
                            "capabilities": ["search flight", "book flight"],
                        }
                    ],
                    "domain_concepts": [
                        {
                            "id": "booking",
                            "name": "Booking",
                            "meaning": "Travel reservation",
                            "owner": "svc-booking",
                            "sensitivity": "medium",
                        }
                    ],
                }
            },
        },
    )
    monkeypatch.setattr(
        assistant_service,
        "get_requirements",
        lambda _conn, _pid, _rid: {
            "id": "req-travel",
            "data": {
                "system": {"name": "Travel Booking"},
                "business_constraints": {
                    "spending_possible": True,
                    "cost_visibility_required": True,
                },
            },
        },
    )
    monkeypatch.setattr(
        assistant_service,
        "derive_contract_expectations",
        lambda _shape, _requirements: [
            {
                "surface": "budget_enforcement",
                "reason": "booking can spend money and requirements require budget controls",
            },
            {
                "surface": "authority_posture",
                "reason": "high-impact booking decisions need clear authority semantics",
            },
        ],
    )

    token = _issue_token(client, "explain_shape")
    resp = client.post(
        "/studio-assistant/anip/invoke/explain_shape",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-assistant-shape",
                "shape_id": "shp-proj-assistant-shape",
                "question": "Why this service boundary?",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "Travel Booking Service" in result["title"]
    assert "single-service" in result["summary"]
    assert "authority checks together" in result["focused_answer"]
    assert len(result["highlights"]) > 0


def test_assistant_can_explain_evaluation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Travel Project"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_scenario",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Scenario",
            "data": {
                "scenario": {
                    "name": "book_flight_over_budget",
                    "narrative": "Booking is over budget.",
                }
            },
        },
    )
    monkeypatch.setattr(
        assistant_service,
        "get_evaluation",
        lambda _conn, _pid, eid: {
            "id": eid,
            "scenario_id": "scn-travel",
            "is_stale": False,
            "stale_artifacts": [],
            "data": {
                "evaluation": {
                    "result": "PARTIAL",
                    "handled_by_anip": ["budget visibility", "structured failure"],
                    "glue_you_will_still_write": ["approval routing"],
                    "why": [
                        "The shape expresses spending and blocking, but approval workflow is not explicit."
                    ],
                    "what_would_improve": ["Add an explicit approval path."],
                }
            },
        },
    )

    token = _issue_token(client, "explain_evaluation")
    resp = client.post(
        "/studio-assistant/anip/invoke/explain_evaluation",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-assistant-eval",
                "evaluation_id": "eval-assistant",
                "question": "What should change next?",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "PARTIAL" in result["summary"]
    assert result["next_steps"] == ["Add an explicit approval path."]


def test_assistant_can_interpret_project_intent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Travel Project"},
    )

    token = _issue_token(client, "interpret_project_intent")
    resp = client.post(
        "/studio-assistant/anip/invoke/interpret_project_intent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-assistant-intent",
                "intent": (
                    "We need a travel booking service that can search flights, "
                    "book travel, block bookings over budget, and escalate exceptions for approval."
                ),
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["recommended_shape_type"] in {"single_service", "multi_service"}
    assert any("budget" in item.lower() for item in result["requirements_focus"])
    assert any("approval" in item.lower() for item in result["scenario_starters"] + result["service_suggestions"])
