"""Tests for the ANIP-backed Studio workbench service."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import time

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


@contextmanager
def _mounted_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(workbench_service, "get_pool", lambda: _DummyPool())
    app = FastAPI()
    mount_anip(app, workbench_service.create_studio_workbench_service(), prefix="/studio-workbench")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    with _mounted_client(monkeypatch) as c:
        yield c


def _issue_token(
    client: TestClient,
    capability: str,
    *,
    scope: list[str] | None = None,
    auth_bearer: str = BOOTSTRAP,
    parent_token: str | None = None,
    budget: dict | None = None,
    concurrent_branches: str | None = None,
) -> dict:
    payload = {
        "subject": "studio-agent",
        "scope": scope or [f"studio.workbench.{capability}"],
        "capability": capability,
        "ttl_hours": 1,
    }
    if parent_token is not None:
        payload["parent_token"] = parent_token
    if budget is not None:
        payload["budget"] = budget
    if concurrent_branches is not None:
        payload["concurrent_branches"] = concurrent_branches
    resp = client.post(
        "/studio-workbench/anip/tokens",
        headers={"Authorization": f"Bearer {auth_bearer}"},
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _permission_entry(data: dict, bucket: str, capability: str) -> dict:
    for item in data.get(bucket, []):
        if item.get("capability") == capability:
            return item
    raise AssertionError(f"{capability} not found in {bucket}: {data}")


def test_workbench_manifest_exposes_core_capabilities(client: TestClient):
    resp = client.get("/studio-workbench/anip/manifest")
    assert resp.status_code == 200, resp.text
    caps = resp.json()["capabilities"]
    assert "create_project" in caps
    assert "accept_first_design" in caps
    assert "evaluate_service_design" in caps
    assert "generate_business_brief" in caps
    assert caps["evaluate_service_design"]["cross_service_contract"] is not None


def test_workbench_manifest_exposes_round1_dogfood_controls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round1")
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/anip/manifest")
        assert resp.status_code == 200, resp.text
        caps = resp.json()["capabilities"]
        create_project = caps["create_project"]
        evaluate = caps["evaluate_service_design"]

        assert any(item["type"] == "stronger_delegation_required" for item in create_project["control_requirements"])
        assert any(item["type"] == "stronger_delegation_required" for item in evaluate["control_requirements"])
        assert any(item["type"] == "cost_ceiling" for item in evaluate["control_requirements"])
        assert any(item["type"] == "non_delegable" for item in caps["generate_engineering_contract"]["control_requirements"])
        assert evaluate["cost"]["financial"]["amount"] == workbench_service.DOGFOOD_EVALUATION_COST_AMOUNT
        assert evaluate["cost"]["financial"]["currency"] == workbench_service.DOGFOOD_EVALUATION_CURRENCY


@pytest.mark.parametrize("profile", ["round2", "round4", "round5"])
def test_workbench_discovery_exposes_anchored_posture(
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", profile)
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/.well-known/anip")
        assert resp.status_code == 200, resp.text
        doc = resp.json()["anip_discovery"]
        assert doc["protocol"] == "anip/0.22"
        assert doc["trust_level"] == "anchored"
        assert doc["posture"]["anchoring"]["enabled"] is True
        assert doc["posture"]["anchoring"]["proofs_available"] is True
        assert doc["posture"]["failure_disclosure"]["detail_level"] == "full"


def test_workbench_manifest_exposes_round5_observability_controls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round5")
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/anip/manifest")
        assert resp.status_code == 200, resp.text
        caps = resp.json()["capabilities"]
        assert "hold_exclusive_probe" in caps
        assert "read_runtime_observability" in caps


def test_workbench_round5_exercises_exclusive_contention_and_observability(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round5")
    with _mounted_client(monkeypatch) as client:
        hold_token = _issue_token(
            client,
            "hold_exclusive_probe",
            concurrent_branches="exclusive",
        )["token"]
        read_token = _issue_token(client, "read_runtime_observability")["token"]

        def _invoke_hold(client_reference_id: str, hold_seconds: float) -> dict:
            resp = client.post(
                "/studio-workbench/anip/invoke/hold_exclusive_probe",
                headers={"Authorization": f"Bearer {hold_token}"},
                json={
                    "client_reference_id": client_reference_id,
                    "parameters": {
                        "hold_seconds": hold_seconds,
                        "label": client_reference_id,
                    },
                },
            )
            assert resp.status_code in (200, 400), resp.text
            return resp.json()

        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(_invoke_hold, "hold-primary", 1.0)
            time.sleep(0.2)
            second = _invoke_hold("hold-contender", 0.1)
            first_result = first.result(timeout=5)

        assert first_result["success"] is True
        assert second["success"] is False
        assert second["failure"]["type"] == "concurrent_request_rejected"

        obs_resp = client.post(
            "/studio-workbench/anip/invoke/read_runtime_observability",
            headers={"Authorization": f"Bearer {read_token}"},
            json={"parameters": {}},
        )
        assert obs_resp.status_code == 200, obs_resp.text
        obs = obs_resp.json()
        assert obs["success"] is True
        result = obs["result"]
        assert result["health"]["status"] == "healthy"
        counts = result["hooks"]["counts"]
        assert counts["logging.invocation_start"] >= 1
        assert counts["logging.invocation_end"] >= 1
        assert counts["metrics.invocation_duration"] >= 1


def test_workbench_permissions_support_round1_preflight_and_budget(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_DOGFOOD_PROFILE", "round1")
    with _mounted_client(monkeypatch) as client:
        parent = _issue_token(
            client,
            "create_workspace",
            scope=workbench_service.WORKBENCH_SCOPES,
        )

        perms_resp = client.post(
            "/studio-workbench/anip/permissions",
            headers={"Authorization": f"Bearer {parent['token']}"},
            json={},
        )
        assert perms_resp.status_code == 200, perms_resp.text
        data = perms_resp.json()

        create_workspace = _permission_entry(data, "available", "create_workspace")
        create_project = _permission_entry(data, "restricted", "create_project")
        evaluate = _permission_entry(data, "restricted", "evaluate_service_design")
        engineering = _permission_entry(data, "denied", "generate_engineering_contract")

        assert create_workspace["scope_match"] == "studio.workbench.create_workspace"
        assert create_project["reason_type"] == "unmet_control_requirement"
        assert create_project["resolution_hint"] == "request_capability_binding"
        assert "stronger_delegation_required" in create_project["unmet_token_requirements"]

        assert evaluate["reason_type"] == "unmet_control_requirement"
        assert evaluate["resolution_hint"] == "request_budget_bound_delegation"
        assert set(evaluate["unmet_token_requirements"]) == {"stronger_delegation_required", "cost_ceiling"}
        assert engineering["reason_type"] == "non_delegable"

        child = _issue_token(
            client,
            "evaluate_service_design",
            scope=["studio.workbench.evaluate_service_design"],
            auth_bearer=parent["token"],
            parent_token=parent["token_id"],
            budget={"currency": "USD", "max_amount": 8.0},
        )
        child_perms_resp = client.post(
            "/studio-workbench/anip/permissions",
            headers={"Authorization": f"Bearer {child['token']}"},
            json={},
        )
        assert child_perms_resp.status_code == 200, child_perms_resp.text
        child_data = child_perms_resp.json()
        evaluate_available = _permission_entry(child_data, "available", "evaluate_service_design")
        assert evaluate_available["constraints"]["budget_remaining"] == 8.0
        assert evaluate_available["constraints"]["currency"] == "USD"

        root_engineering = _issue_token(
            client,
            "generate_engineering_contract",
        )
        root_engineering_perms = client.post(
            "/studio-workbench/anip/permissions",
            headers={"Authorization": f"Bearer {root_engineering['token']}"},
            json={},
        )
        assert root_engineering_perms.status_code == 200, root_engineering_perms.text
        root_engineering_data = root_engineering_perms.json()
        engineering_available = _permission_entry(root_engineering_data, "available", "generate_engineering_contract")
        assert engineering_available["scope_match"] == "studio.workbench.generate_engineering_contract"


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

    token = _issue_token(client, "accept_first_design")["token"]
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

    token = _issue_token(client, "evaluate_service_design")["token"]
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
