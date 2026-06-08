"""Tests for the ANIP-backed Studio workbench service."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio.server.app import mount_anip
from studio.server.business_developer_bridge import generate_drift_analysis_from_context
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
    assert "generate_business_packet" in caps
    assert "generate_drift_analysis" in caps
    assert "generate_glue_analysis" in caps
    assert caps["evaluate_service_design"]["cross_service_contract"] is not None






def test_workbench_can_generate_business_packet(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Enterprise Deal Desk",
            "summary": "Sales needs a governed workflow for non-standard enterprise renewals.",
            "domain": "sales",
            "labels": ["consumer:hybrid"],
            "requirements_count": 1,
            "scenarios_count": 1,
            "shapes_count": 1,
            "evaluations_count": 1,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "list_requirements",
        lambda _conn, _pid: [{
            "id": "req-1",
            "data": {
                "requirements": {
                    "goals": ["Keep common renewals self-serve."],
                    "shape_preference": "multi_service_estate",
                }
            },
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_scenarios",
        lambda _conn, _pid: [{
            "id": "scn-1",
            "title": "Primary Renewal Scenario",
            "data": {
                "scenario": {
                    "name": "renewal_discount_and_terms_exception",
                    "narrative": "A seller requests a non-standard renewal with margin and terms pressure.",
                    "expected_behavior": ["Clarify missing authority before proceeding."],
                }
            },
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_shapes",
        lambda _conn, _pid: [{"id": "shape-1", "data": {"shape": {"type": "multi_service_estate"}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_evaluations",
        lambda _conn, _pid: [{
            "id": "eval-1",
            "created_at": "2026-04-09T10:00:00Z",
            "data": {
                "evaluation": {
                    "result": "PARTIAL",
                    "handled_by_anip": ["purpose binding"],
                    "what_would_improve": ["Add explicit approval routing."],
                }
            },
        }],
    )

    token = _issue_token(client, "generate_business_packet")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/generate_business_packet",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-bridge"}},
    )
    assert resp.status_code == 200, resp.text
    packet = resp.json()["result"]["packet"]
    assert packet["packet_kind"] == "business_packet"
    assert packet["source"]["project_id"] == "proj-bridge"
    assert packet["payload"]["intent"]["intended_consumers"] == ["people", "agents"]
    assert packet["payload"]["current_posture"]["recommended_shape"] == "multi_service_estate"
    assert packet["payload"]["current_posture"]["needs_change"] == ["Add explicit approval routing."]




def test_workbench_can_generate_glue_analysis(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Enterprise Deal Desk",
            "summary": "Sales needs a governed workflow for non-standard enterprise renewals.",
            "domain": "sales",
            "labels": ["consumer:hybrid"],
            "requirements_count": 1,
            "scenarios_count": 1,
            "shapes_count": 1,
            "evaluations_count": 1,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "list_requirements",
        lambda _conn, _pid: [{
            "id": "req-1",
            "data": {
                "requirements": {
                    "goals": ["Keep common renewals self-serve."],
                    "business_constraints": ["Require approval before write actions."],
                }
            },
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_scenarios",
        lambda _conn, _pid: [{
            "id": "scn-1",
            "title": "Primary Renewal Scenario",
            "data": {
                "scenario": {
                    "name": "renewal_followup_task",
                    "narrative": "A seller wants follow-up tasks created for stalled renewals.",
                    "expected_behavior": ["Stop for approval before any write executes."],
                }
            },
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_shapes",
        lambda _conn, _pid: [{"id": "shape-1", "data": {"shape": {"type": "single_service"}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_evaluations",
        lambda _conn, _pid: [{
            "id": "eval-1",
            "created_at": "2026-04-09T10:00:00Z",
            "data": {
                "evaluation": {
                    "result": "PARTIAL",
                    "handled_by_anip": ["purpose binding"],
                    "what_would_improve": ["Add explicit approval routing."],
                }
            },
        }],
    )

    token = _issue_token(client, "generate_glue_analysis")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/generate_glue_analysis",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-bridge"}},
    )
    assert resp.status_code == 200, resp.text
    analysis = resp.json()["result"]["analysis"]
    assert analysis["scenario_id"] == "scn-1"
    assert analysis["expected_outcome"] == "approval_required"
    assert analysis["observed_outcome"] == "approval_required"
    assert analysis["gap_category"] == "approval_control_missing"
    assert analysis["likely_owner"] == "developer_design"
    assert analysis["fix_priority"] == "high"


def test_workbench_glue_analysis_prefers_runtime_observations(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "GTM Runtime Drift",
            "summary": "Review real runtime drift for a governed GTM capability.",
            "domain": "sales",
            "labels": ["consumer:agent"],
            "requirements_count": 1,
            "scenarios_count": 1,
            "shapes_count": 1,
            "evaluations_count": 1,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "list_requirements",
        lambda _conn, _pid: [{
            "id": "req-1",
            "data": {
                "requirements": {
                    "goals": ["Flag risky enterprise renewals."],
                    "business_constraints": ["Clarify missing GTM inputs before recommendation."],
                }
            },
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_scenarios",
        lambda _conn, _pid: [{
            "id": "scn-1",
            "title": "Account Risk Review",
            "data": {
                "scenario": {
                    "name": "account_risk_review",
                    "narrative": "The GTM agent should ask for the missing risk cohort before continuing.",
                    "expected_behavior": ["Ask for the minimum missing input before retrying."],
                }
            },
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_shapes",
        lambda _conn, _pid: [{"id": "shape-1", "data": {"shape": {"type": "single_service"}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_evaluations",
        lambda _conn, _pid: [{
            "id": "eval-runtime-1",
            "created_at": "2026-04-11T10:00:00Z",
            "data": {
                "evaluation": {
                    "result": "REQUIRES_GLUE",
                    "runtime_observations": {
                        "source": "audit",
                        "observed_at": "2026-04-11T10:05:00Z",
                        "observed_outcome": "clarification_required",
                        "reason_code": "clarification_loop_detected",
                        "invoked_capability": "gtm.account_risk_summary",
                        "unresolved_inputs": ["risk_cohort"],
                        "retry_without_progress": True,
                        "agent_behavior": "retried same capability without resolving inputs",
                        "backend_context": "cube_semantic_context",
                    },
                }
            },
        }],
    )

    token = _issue_token(client, "generate_glue_analysis")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/generate_glue_analysis",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-runtime"}},
    )
    assert resp.status_code == 200, resp.text
    analysis = resp.json()["result"]["analysis"]
    assert analysis["scenario_id"] == "scn-1"
    assert analysis["observed_outcome"] == "clarification_required"
    assert analysis["gap_category"] == "clarification_loop_detected"
    assert analysis["likely_owner"] == "consuming_agent"
    assert analysis["fix_priority"] == "high"
    assert analysis["diagnostic_evidence"]["capability_id"] == "gtm.account_risk_summary"
    assert analysis["diagnostic_evidence"]["reason_code"] == "clarification_loop_detected"
    assert analysis["diagnostic_evidence"]["backend_context"] == "cube_semantic_context"
    assert analysis["diagnostic_evidence"]["observation_source"] == "audit"
    assert analysis["diagnostic_evidence"]["observed_at"] == "2026-04-11T10:05:00Z"


def test_workbench_uses_selected_service_metadata_in_drift_analysis(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "GTM Capability",
            "summary": "Validate the governed GTM capability against the implemented service surface.",
            "domain": "sales",
            "labels": ["consumer:agent_anip"],
            "requirements_count": 1,
            "scenarios_count": 1,
            "shapes_count": 1,
            "evaluations_count": 1,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "list_requirements",
        lambda _conn, _pid: [{
            "id": "req-1",
            "data": {"requirements": {"goals": ["Review account risk safely."]}},
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_scenarios",
        lambda _conn, _pid: [{
            "id": "scn-1",
            "title": "Account Risk Review",
            "data": {"scenario": {"name": "account_risk_review"}},
        }],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_shapes",
        lambda _conn, _pid: [{"id": "shape-1", "data": {"shape": {"type": "single_service"}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_evaluations",
        lambda _conn, _pid: [{
            "id": "eval-1",
            "data": {"evaluation": {"result": "HANDLED"}},
        }],
    )

    token = _issue_token(client, "generate_drift_analysis")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/generate_drift_analysis",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-metadata",
                "service_metadata_artifact_id": "service-metadata-svc-b",
                "metadata_comparison": {
                    "missing_capabilities": ["gtm.account_risk_summary"],
                    "extra_capabilities": ["gtm.pipeline_summary"],
                    "observed": {
                        "source": "inspect_discovery",
                        "observed_at": "2026-04-11T12:05:00Z",
                        "service_id": "svc-b",
                    },
                },
            }
        },
    )
    assert resp.status_code == 200, resp.text
    analysis = resp.json()["result"]["analysis"]
    assert analysis["gap_category"] == "service_metadata_insufficient"
    assert analysis["likely_owner"] == "service_implementation"
    assert analysis["fix_priority"] == "high"
    assert analysis["diagnostic_evidence"]["capability_id"] == "gtm.account_risk_summary"
    assert analysis["diagnostic_evidence"]["reason_code"] == "service_metadata_missing_capability"
    assert analysis["diagnostic_evidence"]["observation_source"] == "inspect_discovery"
    assert analysis["diagnostic_evidence"]["observed_at"] == "2026-04-11T12:05:00Z"
    assert analysis["diagnostic_evidence"]["service_metadata_artifact_id"] == "service-metadata-svc-b"
    assert analysis["diagnostic_evidence"]["service_metadata_mismatch"] == (
        "missing intended capabilities: gtm.account_risk_summary; "
        "extra observed capabilities: gtm.pipeline_summary"
    )


def test_workbench_manifest_exposes_public_capabilities(monkeypatch: pytest.MonkeyPatch):
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/anip/manifest")
        assert resp.status_code == 200, resp.text
        caps = resp.json()["capabilities"]
        assert "create_project" in caps
        assert "evaluate_service_design" in caps
        assert "generate_engineering_contract" in caps
        assert caps["create_project"]["control_requirements"] == []
        assert caps["evaluate_service_design"]["control_requirements"] == []
        assert caps["generate_engineering_contract"]["control_requirements"] == []


def test_generate_drift_analysis_prioritizes_conformance_failures():
    analysis = generate_drift_analysis_from_context(
        {
            "evaluation": {
                "evaluation": {
                    "scenario_name": "account_risk_review",
                    "result": "HANDLED",
                    "handled_by_anip": ["summary generation"],
                    "glue_you_will_still_write": [],
                    "glue_category": [],
                    "why": [],
                    "what_would_improve": [],
                }
            },
            "scenario": {
                "scenario": {
                    "name": "account_risk_review",
                    "context": {"capability": "gtm.account_risk_summary"},
                }
            },
            "shape": {
                "shape": {
                    "type": "single_service",
                    "services": [{"name": "gtm-core", "capabilities": ["gtm.account_risk_summary"]}],
                }
            },
            "metadata_comparison": {
                "missing_capabilities": [],
                "extra_capabilities": [],
                "observed": {
                    "source": "inspect_discovery_manifest",
                    "observed_at": "2026-04-11T12:05:00Z",
                    "service_id": "svc-b",
                },
                "conformance_checks": [
                    {
                        "id": "jwks_uri_declared",
                        "label": "JWKS URI declared",
                        "status": "non_conformant",
                        "detail": "Manifest service identity did not include a JWKS URI.",
                    }
                ],
            },
        }
    )
    assert analysis.gap_category == "service_metadata_insufficient"
    assert analysis.likely_owner == "service_implementation"
    assert analysis.fix_priority == "high"
    assert analysis.diagnostic_evidence.reason_code == "anip_conformance_check_failed"


def test_workbench_discovery_exposes_public_posture(monkeypatch: pytest.MonkeyPatch):
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/.well-known/anip")
        assert resp.status_code == 200, resp.text
        doc = resp.json()["anip_discovery"]
        assert doc["protocol"] == "anip/0.24"
        assert doc["trust_level"] == "signed"
        assert doc["posture"]["anchoring"]["enabled"] is False
        assert doc["posture"]["anchoring"]["proofs_available"] is False
        assert doc["posture"]["failure_disclosure"]["detail_level"] == "full"


def test_workbench_manifest_exposes_public_graph_relationships(monkeypatch: pytest.MonkeyPatch):
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/anip/manifest")
        assert resp.status_code == 200, resp.text
        caps = resp.json()["capabilities"]
        assert caps["create_project"]["composes_with"] == []
        assert caps["accept_first_design"]["composes_with"] == []
        assert caps["draft_fix_from_change"]["composes_with"] == []
        assert caps["generate_business_brief"]["requires"] == []


def test_workbench_graph_route_exposes_public_relationships(monkeypatch: pytest.MonkeyPatch):
    with _mounted_client(monkeypatch) as client:
        resp = client.get("/studio-workbench/anip/graph/create_project")
        assert resp.status_code == 200, resp.text
        graph = resp.json()
        assert graph["capability"] == "create_project"
        assert graph["composes_with"] == []


def test_workbench_permissions_use_public_capability_set(monkeypatch: pytest.MonkeyPatch):
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
        create_project = _permission_entry(data, "available", "create_project")
        evaluate = _permission_entry(data, "available", "evaluate_service_design")
        engineering = _permission_entry(data, "available", "generate_engineering_contract")

        assert create_workspace["scope_match"] == "studio.workbench.create_workspace"
        assert create_project["scope_match"] == "studio.workbench.create_project"
        assert evaluate["scope_match"] == "studio.workbench.evaluate_service_design"
        assert engineering["scope_match"] == "studio.workbench.generate_engineering_contract"


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
    assert len(result["scenarios"]) >= 1
    assert result["shape"]["requirements_id"] == result["requirements"]["id"]


def test_workbench_accept_first_design_uses_project_consumer_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    recorded: dict[str, str] = {}

    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Studio Project",
            "summary": "PM brief",
            "domain": "ops",
            "labels": ["consumer:human_app"],
            "requirements_count": 0,
            "scenarios_count": 0,
            "shapes_count": 0,
        },
    )

    def _record_requirements(_interpretation, _source_intent, _project_name, _project_domain, consumer_mode):
        recorded["requirements"] = consumer_mode
        return {"system": {"name": "studio-project", "domain": "ops", "deployment_intent": "public_http_service"}}

    def _record_scenarios(_interpretation, consumer_mode):
        recorded["scenarios"] = consumer_mode
        return [{"title": "Scenario", "data": {"scenario": {"name": "scenario"}}}]

    def _record_shape(_interpretation, _project_name, consumer_mode):
        recorded["shape"] = consumer_mode
        return {"shape": {"type": "single_service", "services": [{"id": "svc-a", "name": "Service", "role": "primary service"}], "domain_concepts": []}}

    monkeypatch.setattr(workbench_service, "make_requirements_template_from_intent", _record_requirements)
    monkeypatch.setattr(workbench_service, "make_scenario_templates_from_intent", _record_scenarios)
    monkeypatch.setattr(workbench_service, "make_shape_template_from_intent", _record_shape)
    monkeypatch.setattr(
        workbench_service,
        "create_requirements",
        lambda _conn, **kwargs: {"id": kwargs["req_id"], "title": kwargs["title"], "role": "primary"},
    )
    monkeypatch.setattr(
        workbench_service,
        "create_scenario",
        lambda _conn, **kwargs: {"id": kwargs["scenario_id"], "title": kwargs["title"]},
    )
    monkeypatch.setattr(
        workbench_service,
        "create_shape",
        lambda _conn, **kwargs: {"id": kwargs["shape_id"], "title": kwargs["title"], "requirements_id": kwargs["requirements_id"]},
    )

    token = _issue_token(client, "accept_first_design")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/accept_first_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-consumer",
                "source_intent": "People need an internal operations workflow.",
                "interpretation": {
                    "title": "Intent Interpretation",
                    "summary": "Ops needs a first design.",
                    "recommended_shape_type": "single_service",
                    "recommended_shape_reason": "Keep the main action together.",
                    "requirements_focus": ["Keep the operator flow understandable."],
                    "scenario_starters": ["Add a scenario where an operator needs a clear explanation."],
                    "domain_concepts": ["Request"],
                    "service_suggestions": ["Start with one primary service."],
                    "next_steps": ["Run evaluation."],
                },
            }
        },
    )
    assert resp.status_code == 200, resp.text
    assert recorded == {
        "requirements": "human_app",
        "scenarios": "human_app",
        "shape": "human_app",
    }


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


def test_workbench_can_generate_llm_assisted_business_brief(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Deal Desk",
            "summary": "A realistic PM brief.",
            "requirements_count": 1,
            "scenarios_count": 1,
            "shapes_count": 1,
            "evaluations_count": 1,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "list_requirements",
        lambda _conn, _pid: [{"id": "req-1", "title": "Requirements", "data": {"requirements": {"business_constraints": {"approval_required": True}}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_scenarios",
        lambda _conn, _pid: [{"id": "scn-1", "title": "Scenario", "data": {"scenario": {"narrative": "A risky approval flow."}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_shapes",
        lambda _conn, _pid: [{"id": "shape-1", "title": "Shape", "data": {"shape": {"type": "multi_service", "services": [{"id": "svc-a"}], "domain_concepts": []}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_evaluations",
        lambda _conn, _pid: [{"id": "eval-1", "result": "HANDLED", "data": {"evaluation": {"handled_by_anip": ["audit"], "what_would_improve": ["None"]}}}],
    )

    async def _fake_model_response(capability: str, payload: dict[str, object]) -> dict[str, str] | None:
        assert capability == "rewrite_business_brief"
        assert "deterministic_draft" in payload
        return {"document": "# Readable Business Brief\n\nThis is the narrative version."}

    monkeypatch.setattr(workbench_service, "try_model_assistant_response", _fake_model_response)

    token = _issue_token(client, "generate_business_brief")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/generate_business_brief",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-1", "llm_assisted": True}},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["assisted"] is True
    assert "Readable Business Brief" in result["document"]
    assert "Canonical source of truth: Business Brief" in result["document"]
    assert "Artifact role: Business Narrative" in result["document"]


def test_workbench_readable_business_brief_falls_back_when_model_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        workbench_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Deal Desk",
            "summary": "A realistic PM brief.",
            "requirements_count": 1,
            "scenarios_count": 1,
            "shapes_count": 1,
            "evaluations_count": 1,
        },
    )
    monkeypatch.setattr(
        workbench_service,
        "list_requirements",
        lambda _conn, _pid: [{"id": "req-1", "title": "Requirements", "data": {"requirements": {"business_constraints": {"approval_required": True}}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_scenarios",
        lambda _conn, _pid: [{"id": "scn-1", "title": "Scenario", "data": {"scenario": {"narrative": "A risky approval flow."}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_shapes",
        lambda _conn, _pid: [{"id": "shape-1", "title": "Shape", "data": {"shape": {"type": "multi_service", "services": [{"id": "svc-a"}], "domain_concepts": []}}}],
    )
    monkeypatch.setattr(
        workbench_service,
        "list_evaluations",
        lambda _conn, _pid: [{"id": "eval-1", "result": "HANDLED", "data": {"evaluation": {"handled_by_anip": ["audit"], "what_would_improve": ["None"]}}}],
    )
    async def _no_model_response(*_args, **_kwargs):
        return None

    monkeypatch.setattr(workbench_service, "try_model_assistant_response", _no_model_response)

    token = _issue_token(client, "generate_business_brief")["token"]
    resp = client.post(
        "/studio-workbench/anip/invoke/generate_business_brief",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-1", "llm_assisted": True}},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["assisted"] is False
    assert "Business Brief: Deal Desk" in result["document"]
    assert "Artifact role: Canonical Business Brief" in result["document"]
