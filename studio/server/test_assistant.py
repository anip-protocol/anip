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
    assert caps["interpret_project_intent"]["cross_service_contract"] is not None
    assert caps["explain_evaluation"]["cross_service_contract"] is not None


def test_assistant_discovery_exposes_round2_posture(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round2")
    monkeypatch.setattr(assistant_service, "get_pool", lambda: _DummyPool())

    app = FastAPI()
    mount_anip(app, assistant_service.create_studio_assistant_service(), prefix="/studio-assistant")

    with TestClient(app) as client:
        resp = client.get("/studio-assistant/.well-known/anip")
        assert resp.status_code == 200, resp.text
        doc = resp.json()["anip_discovery"]
        assert doc["protocol"] == "anip/0.22"
        assert doc["trust_level"] == "signed"
        assert doc["posture"]["failure_disclosure"]["detail_level"] == "redacted"
        assert doc["posture"]["anchoring"]["enabled"] is False


def test_assistant_manifest_exposes_round3_streaming_and_session(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round3")
    monkeypatch.setattr(assistant_service, "get_pool", lambda: _DummyPool())

    app = FastAPI()
    mount_anip(app, assistant_service.create_studio_assistant_service(), prefix="/studio-assistant")

    with TestClient(app) as client:
        resp = client.get("/studio-assistant/anip/manifest")
        assert resp.status_code == 200, resp.text
        caps = resp.json()["capabilities"]
        assert caps["start_design_review_session"]["session"]["type"] == "continuation"
        assert caps["stream_design_review"]["session"]["type"] == "continuation"
        assert "streaming" in caps["stream_design_review"]["response_modes"]


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


def test_assistant_can_stream_design_review(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round3")
    monkeypatch.setattr(assistant_service, "get_pool", lambda: _DummyPool())
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Streaming Project"},
    )

    app = FastAPI()
    mount_anip(app, assistant_service.create_studio_assistant_service(), prefix="/studio-assistant")

    with TestClient(app) as client:
        start_token = _issue_token(client, "start_design_review_session")
        start_resp = client.post(
            "/studio-assistant/anip/invoke/start_design_review_session",
            headers={"Authorization": f"Bearer {start_token}"},
            json={"parameters": {"project_id": "proj-stream"}},
        )
        assert start_resp.status_code == 200, start_resp.text
        session_id = start_resp.json()["result"]["session_id"]

        stream_token = _issue_token(client, "stream_design_review")
        stream_resp = client.post(
            "/studio-assistant/anip/invoke/stream_design_review",
            headers={"Authorization": f"Bearer {stream_token}"},
            json={
                "parameters": {"project_id": "proj-stream", "session_id": session_id},
                "stream": True,
                "client_reference_id": "stream-review-test",
            },
        )
        assert stream_resp.status_code == 200, stream_resp.text
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")
        text = stream_resp.text
        assert "event: progress" in text
        assert "event: completed" in text


def test_assistant_can_use_configured_model_result_for_intent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Travel Project", "domain": "travel"},
    )

    async def _fake_model_response(capability: str, payload: dict):
        assert capability == "interpret_project_intent"
        assert payload["project"]["name"] == "Travel Project"
        return {
            "title": "AI Draft: Travel Booking",
            "summary": "A concise AI-backed draft for the travel booking brief.",
            "recommended_shape_type": "multi_service",
            "recommended_shape_reason": "Approval and booking lifecycles are distinct enough to separate.",
            "requirements_focus": ["Make approval policy explicit."],
            "scenario_starters": ["Add a scenario where approval is required before booking."],
            "domain_concepts": ["Booking", "Approval"],
            "service_suggestions": ["Split booking and approval into separate responsibilities."],
            "next_steps": ["Review the first draft before accepting it."],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _fake_model_response)

    token = _issue_token(client, "interpret_project_intent")
    resp = client.post(
        "/studio-assistant/anip/invoke/interpret_project_intent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-assistant-intent",
                "intent": "We need a travel booking service with approvals.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["title"] == "AI Draft: Travel Booking"
    assert result["recommended_shape_type"] == "multi_service"
    assert result["domain_concepts"] == ["Booking", "Approval"]


def test_assistant_falls_back_when_model_result_is_missing_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Travel Project"},
    )

    async def _partial_model_response(capability: str, payload: dict):
        assert capability == "interpret_project_intent"
        return {
            "title": "AI Draft: Travel Booking",
            "recommended_shape_type": "not-a-valid-shape",
            "requirements_focus": [],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _partial_model_response)

    token = _issue_token(client, "interpret_project_intent")
    resp = client.post(
        "/studio-assistant/anip/invoke/interpret_project_intent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-assistant-intent",
                "intent": (
                    "We need a travel booking service that can search flights, "
                    "book travel, and escalate exceptions for approval."
                ),
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["title"] == "AI Draft: Travel Booking"
    assert result["recommended_shape_type"] in {"single_service", "multi_service"}
    assert len(result["requirements_focus"]) > 0
    assert len(result["scenario_starters"]) > 0
