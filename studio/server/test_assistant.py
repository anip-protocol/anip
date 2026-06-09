"""Tests for the ANIP-backed Studio assistant service.

These tests intentionally mount the assistant as a real ANIP service while
stubbing Studio's repository layer. That keeps the service contract checks
independent from the Studio Postgres lifecycle.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from anip_service import ANIPError

from studio.server.app import mount_anip
import studio.server.assistant_provider as assistant_provider
import studio.server.assistant_service as assistant_service

BOOTSTRAP = "studio-assistant-bootstrap"
CANONICAL_EFFECT_IDS = {
    "content.draft",
    "content.summary",
    "content.recommendation",
    "data.read",
    "data.aggregate",
    "data.export",
    "raw_data_export",
    "raw_model_features",
    "system.preview_mutation",
    "system.mutation",
    "external_dispatch",
    "approval.request",
    "approval.execute",
}


@contextmanager
def _dummy_connection():
    yield object()


class _DummyPool:
    def connection(self):
        return _dummy_connection()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(assistant_service, "get_pool", lambda: _DummyPool())

    async def _no_model_response(_capability, _payload):
        return None

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _no_model_response)

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
    assert "propose_requirements" in caps
    assert "propose_scenarios" in caps
    assert "propose_business_summary" in caps
    assert "propose_actor_model" in caps
    assert "propose_business_areas" in caps
    assert "propose_permission_intent" in caps
    assert "propose_non_goals" in caps
    assert "propose_success_criteria" in caps
    assert "propose_service_design" in caps
    assert "propose_capability_formalization" in caps
    assert "propose_runtime_policy_bindings" in caps
    assert "propose_input_contracts" in caps
    assert "propose_verification_expectations" in caps
    assert "propose_backend_bindings" in caps
    assert "propose_governed_fronting_capabilities" in caps
    assert "identify_missing_business_info" in caps
    assert "clarify_design_section" in caps
    assert "suggest_next_step" in caps
    assert "explain_shape" in caps
    assert "explain_evaluation" in caps
    assert "interpret_project_intent" in caps
    assert caps["interpret_project_intent"]["cross_service_contract"] is not None
    assert caps["explain_evaluation"]["cross_service_contract"] is not None


def test_assistant_discovery_exposes_public_posture(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(assistant_service, "get_pool", lambda: _DummyPool())

    app = FastAPI()
    mount_anip(app, assistant_service.create_studio_assistant_service(), prefix="/studio-assistant")

    with TestClient(app) as client:
        resp = client.get("/studio-assistant/.well-known/anip")
        assert resp.status_code == 200, resp.text
        doc = resp.json()["anip_discovery"]
        assert doc["protocol"] == "anip/0.24"
        assert doc["trust_level"] == "signed"
        assert doc["posture"]["failure_disclosure"]["detail_level"] == "full"
        assert doc["posture"]["anchoring"]["enabled"] is False


def test_assistant_manifest_exposes_streaming_and_session(monkeypatch: pytest.MonkeyPatch):
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
        assert caps["start_design_review_session"]["composes_with"][0]["capability"] == "stream_design_review"


def test_canonical_inventory_accepts_capability_formalizations_json():
    source_text = """
    # Reviewed Developer Evidence

    ```json
    {
      "capability_formalizations": [
        {
          "capability_id": "jira.prepare_comment",
          "service_id": "jira-governance-service",
          "summary": "Prepare a governed Jira comment preview.",
          "operation_type": "approval_gated",
          "side_effect_level": "approval_required",
          "grant_policy": {"mode": "default_one_time"},
          "business_effects": {
            "produces": ["content.draft", "approval.request"],
            "does_not_produce": ["external_dispatch", "system.mutation"]
          },
          "backend_operation": "POST /rest/api/3/issue/{issueIdOrKey}/comment",
          "output_shape": "comment_preview_result",
          "inputs": [
            {"input_name": "issue_key", "input_type": "string", "required": true}
          ]
        }
      ]
    }
    ```
    """

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)
    proposal = assistant_service._capability_formalization_from_inventory("Jira", inventory, [])
    capability = proposal["proposal"]["items"][0]["structured_data"]["capabilities"][0]

    assert [entry["capability_id"] for entry in inventory] == ["jira.prepare_comment"]
    assert capability["grant_policy"]["default_grant_type"] == "one_time"
    assert capability["grant_policy"]["expires_in_seconds"] == 900
    assert capability["inputs"][0]["input_name"] == "issue_key"


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


def test_assistant_can_propose_requirements(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )

    token = _issue_token(client, "propose_requirements")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_requirements",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-req",
                "source_document_text": "Build an internal assistant for revenue operations. It should help managers review pipeline risk and require approval for high-impact operational changes.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "pm"
    assert result["capability"] == "propose_requirements"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "requirements"
    assert len(result["proposal"]["items"]) >= 3


def test_assistant_rejects_generic_model_draft_for_rich_source(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )

    async def _generic_model_response(_capability, _payload):
        return {
            "mode": "pm",
            "capability": "propose_requirements",
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "requirements",
                "items": [
                    {
                        "id": "generic-req",
                        "title": "Define the product purpose as a governed, bounded system outcome",
                        "body": "The system should define purpose outcome before users trust bounded responses.",
                        "rationale": "Generic fallback text.",
                        "confidence": "medium",
                    }
                ],
            },
            "questions_for_user": [],
            "source_refs": [],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _generic_model_response)

    rich_source = (
        "# Revenue Operations Planning Assistant\n\n"
        "## Pipeline Risk Review\n"
        + "- Regional sales leaders review pipeline health, renewal exposure, and high-risk accounts.\n" * 40
        + "## Account Planning\n"
        + "- Account executives need governed account plans, MEDDICC context, next-best actions, and approval gates.\n" * 40
    )

    token = _issue_token(client, "propose_requirements")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_requirements",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-generic-reject", "source_document_text": rich_source}},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "invalid_request"
    assert "generic draft" in body["failure"]["detail"]


def test_assistant_reports_provider_failure_for_draft_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )

    async def _provider_failure(_capability, _payload):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _provider_failure)

    token = _issue_token(client, "propose_requirements")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_requirements",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-provider-failure",
                "source_document_text": "Build an internal assistant for revenue operations with governed approval gates.",
            }
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "assistant_provider_failed"
    assert "provider unavailable" in body["failure"]["detail"]


def test_fallback_marker_terms_ignore_proposal_schema_tokens():
    deterministic = {
        "proposal": {
            "proposal_kind": "patch_candidates",
            "artifact_type": "non_goals",
            "patches": [
                {
                    "path": "/entries/-",
                    "op": "add",
                    "value": {"statement": "Do not treat external export as automatic."},
                    "rationale": "External delivery changes the product boundary.",
                }
            ],
        }
    }

    terms = assistant_service._fallback_marker_terms(
        deterministic,
        "# Jira Engineering Workflow Agent\n\nThe agent must deny raw export and require approval for workflow changes.",
    )

    assert "patch_candidates" not in terms
    assert "non_goals" not in terms
    assert any("external export" in term or "external delivery" in term for term in terms)


def test_assistant_can_propose_scenarios(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )

    token = _issue_token(client, "propose_scenarios")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_scenarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-scn",
                "source_document_text": "Build an internal assistant for revenue operations. It should help managers review pipeline risk, ask clarifying questions when inputs are incomplete, and stop for approval before high-impact operational changes.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "pm"
    assert result["capability"] == "propose_scenarios"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "scenarios"
    assert len(result["proposal"]["items"]) >= 3


def test_pm_actor_entries_preserve_source_declared_actor_ids():
    source_text = """
    Representative actor families:
    - `sales_leader`
    - `rev_ops_manager`
    - `account_manager_east`
    - `account_manager_west`
    - `sales_analyst`
    """

    actors = assistant_service._pm_actor_entries(source_text, set(assistant_service._normalized_words(source_text)))

    assert [actor["actor_id"] for actor in actors] == [
        "sales_leader",
        "rev_ops_manager",
        "account_manager_east",
        "account_manager_west",
        "sales_analyst",
    ]
    assert all(actor["actor_id"] != "primary_operator" for actor in actors)
    assert all(actor["actor_id"] != "reviewing_manager" for actor in actors)
    assert all("GTM" not in actor["summary"] for actor in actors)


def test_pm_actor_entries_derive_governed_fronting_actor_ids():
    source_text = """
    # Jira Governed Fronting Intent

    Create a governed ANIP fronting service for Jira. Agents should see bounded Jira business capabilities, not raw REST or MCP tools.

    ## Public governed capabilities

    - `jira.backlog.search_context`: Find bounded work context.
    - `jira.issue.get_context`: Inspect one issue.
    - `jira.workflow_transition.request`: Request a governed transition and stop for approval.
    """

    actors = assistant_service._pm_actor_entries(source_text, set(assistant_service._normalized_words(source_text)))

    assert [actor["actor_id"] for actor in actors] == ["jira_requester", "jira_approver"]
    assert all(actor["actor_id"] != "primary_operator" for actor in actors)
    assert all(actor["actor_id"] != "reviewing_manager" for actor in actors)


def test_pm_business_areas_derive_governed_fronting_responsibilities():
    source_text = """
    # Jira Governed Fronting Intent

    Create a governed ANIP fronting service for Jira. Missing inputs clarify, direct mutation is approval-gated, raw export is denied, and audit evidence is required.

    ## Public governed capabilities

    - `jira.backlog.search_context`: Find bounded work context.
    - `jira.issue.get_context`: Inspect one issue.
    - `jira.story.prepare`: Prepare a story preview.
    - `jira.workflow_transition.request`: Request a governed transition.
    """
    words = set(assistant_service._normalized_words(source_text))

    areas = assistant_service._fronting_business_area_entries(source_text, words)

    assert [area["business_area_id"] for area in areas] == [
        "jira_context_access",
        "jira_issue_preparation",
        "jira_governed_change_requests",
        "jira_policy_and_audit",
    ]


def test_permission_intent_derive_governed_fronting_rules():
    actor_ids = ["jira_requester", "jira_approver"]
    business_area_ids = [
        "jira_context_access",
        "jira_issue_preparation",
        "jira_governed_change_requests",
        "jira_policy_and_audit",
    ]

    rules = assistant_service._fronting_permission_rule_values(actor_ids, business_area_ids)

    assert len(rules) == 8
    assert [(rule["actor_id"], rule["business_area"], rule["access_posture"], rule["governed_outcome_type"]) for rule in rules] == [
        ("jira_requester", "jira_context_access", "bounded", "bounded_result"),
        ("jira_requester", "jira_issue_preparation", "bounded", "bounded_result"),
        ("jira_requester", "jira_governed_change_requests", "approval_required", "approval_stop"),
        ("jira_requester", "jira_governed_change_requests", "restricted", "clarification_required"),
        ("jira_requester", "jira_governed_change_requests", "denied", "deny_request"),
        ("jira_approver", "jira_governed_change_requests", "bounded", "bounded_result"),
        ("jira_requester", "jira_context_access", "denied", "deny_request"),
        ("jira_approver", "jira_policy_and_audit", "bounded", "bounded_result"),
    ]


def test_actor_model_complete_rejects_reserved_outcome_actor_ids():
    assert not assistant_service._actor_model_complete(
        {
            "actors": [
                {
                    "actor_id": "approval_required",
                    "title": "Approval Required",
                    "summary": "This is an outcome token, not a business actor.",
                }
            ]
        }
    )


def test_source_declared_business_area_ids_from_in_flight_context():
    source_text = """
    Source brief.

    ---
    In-flight Product Design Context

    ## Actor IDs
    - `sales_leader`

    ## Business Area IDs
    - `pipeline_health`
    - `follow_up_task_preparation`
    """

    assert assistant_service._source_declared_actor_ids(source_text) == ["sales_leader"]
    assert assistant_service._source_declared_business_area_ids(source_text) == [
        "pipeline_health",
        "follow_up_task_preparation",
    ]


def test_grounding_markers_treat_source_actor_id_variants_as_grounded():
    source_text = """
    Representative actor families:
    - `sales_leader`
    - `account_manager_east`
    """
    deterministic = {
        "proposal": {
            "items": [
                {
                    "actor_id": "sales_leader",
                    "title": "Sales Leader",
                    "summary": "Source-declared actor family: Sales Leader.",
                },
                {
                    "actor_id": "account_manager_east",
                    "title": "Account Manager East",
                    "summary": "Source-declared actor family: Account Manager East.",
                },
            ]
        }
    }
    proposal_text = "Source-declared Sales Leader and Account Manager East preserve actor-specific visibility."

    assert assistant_service._fallback_marker_hits(deterministic, source_text, proposal_text) == []


def test_source_anchor_hits_treat_source_actor_id_variants_as_grounded():
    source_text = """
    Representative actor families:
    - `sales_leader`
    - `account_manager_east`
    """
    proposal_text = "Preserve sales_leader and account_manager_east as distinct actor families."

    hits = assistant_service._source_anchor_hits(source_text, proposal_text)

    assert "sales leader" in hits
    assert "account manager east" in hits


def test_grounding_markers_ignore_studio_governance_terms():
    source_text = """
    Representative actor families:
    - `sales_leader`
    """
    deterministic = {
        "proposal": {
            "patches": [
                {
                    "value": {
                        "actor_id": "sales_leader",
                        "approval_expectations": "Stop for approval-sensitive outcomes.",
                    }
                }
            ]
        }
    }

    assert assistant_service._fallback_marker_hits(
        deterministic,
        source_text,
        "sales_leader stops for approval-sensitive outcomes.",
    ) == []


def test_markdown_runtime_input_contracts_merge_with_canonical_service_inventory():
    source_text = """
    The following capability inventory is canonical.

    ### Pipeline Service
    Service:
    - `gtm-pipeline-service`
    Capabilities:
    - `gtm.pipeline_summary`

    ## Capability: gtm.pipeline_summary
    | input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | quarter | string | yes | time_scope | no | clarify | clarify | clarify | clarify | | | | Quarter label like 2017-Q2 | |
    | detail_level | string | no | | no | closed_values | use_default | clarify | clarify | summary | summary, stage_breakdown | | Summary depth | |
    """

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert len(inventory) == 1
    assert inventory[0]["service_id"] == "gtm-pipeline-service"
    assert inventory[0]["capability_id"] == "gtm.pipeline_summary"
    assert inventory[0]["inputs"][0]["input_name"] == "quarter"
    assert inventory[0]["inputs"][0]["semantic_type"] == "time_scope"
    assert inventory[0]["inputs"][1]["default"] == "summary"
    assert inventory[0]["inputs"][1]["allowed_values"] == ["summary", "stage_breakdown"]


def test_canonical_inventory_ignores_non_capability_json_name_fields():
    source_text = """
    {
      "ui_table": {
        "columns": [
          {"name": "capability_id"},
          {"name": "service_id"}
        ]
      },
      "canonical_capability_inventory": [
        {
          "capability_id": "gtm.pipeline_summary",
          "service_id": "gtm-pipeline-service",
          "inputs": [
            {"input_name": "quarter", "input_type": "string", "required": true, "summary": "Quarter label."}
          ]
        }
      ]
    }
    """

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert [entry["capability_id"] for entry in inventory] == ["gtm.pipeline_summary"]


def test_markdown_capability_governance_merges_with_runtime_input_contracts():
    source_text = """
    The following capability inventory is canonical.

    ### Prioritization Service
    Service:
    - `gtm-prioritization-service`
    Capabilities:
    - `gtm.route_leads`

    ## Capability Runtime Governance
    | capability_id | side_effect_level | operation_type | grant_policy | produces | does_not_produce | summary |
    | --- | --- | --- | --- | --- | --- | --- |
    | gtm.route_leads | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation | approval.execute, raw_model_features | Prepare routing preview and stop at approval. |

    ## Capability: gtm.route_leads
    | input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify | | inbound_last_week | gtm.cohort_catalog | Lead cohort | Ask which cohort to route. |
    """

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert len(inventory) == 1
    capability = inventory[0]
    assert capability["service_id"] == "gtm-prioritization-service"
    assert capability["side_effect_level"] == "approval_required"
    assert capability["operation_type"] == "approval_gated"
    assert capability["grant_policy"]["default_grant_type"] == "one_time"
    assert capability["business_effects"]["produces"] == ["approval.request", "system.preview_mutation"]
    assert capability["business_effects"]["does_not_produce"] == ["approval.execute", "raw_model_features"]
    assert capability["inputs"][0]["resolution"]["mode"] == "closed_values"


def test_gtm_runtime_input_contracts_use_canonical_effect_ids():
    source_text = Path("docs/examples/gtm-showcase/gtm-runtime-input-contracts.md").read_text()
    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    unknown_effects: set[str] = set()
    for capability in inventory:
        business_effects = capability.get("business_effects")
        if not isinstance(business_effects, dict):
            continue
        for field in ("produces", "does_not_produce"):
            values = business_effects.get(field)
            if isinstance(values, list):
                unknown_effects.update(str(value) for value in values if value and value not in CANONICAL_EFFECT_IDS)

    assert unknown_effects == set()


def test_csv_runtime_evidence_builds_complete_gtm_inventory():
    source_text = "\n\n".join(
        [
            Path("docs/examples/gtm-showcase/anip-capability-runtime-governance.csv").read_text(),
            Path("docs/examples/gtm-showcase/anip-capability-input-contracts.csv").read_text(),
        ]
    )

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert len(inventory) == 23
    by_id = {item["capability_id"]: item for item in inventory}
    assert by_id["gtm.score_leads"]["service_id"] == "gtm-prioritization-service"
    assert by_id["gtm.score_leads"]["business_effects"]["produces"] == [
        "content.summary",
        "content.recommendation",
    ]
    bottleneck_target = next(
        item
        for item in by_id["gtm.bottleneck_account_outreach_draft"]["inputs"]
        if item["input_name"] == "target_ref"
    )
    assert bottleneck_target["required"] is False
    assert bottleneck_target["resolution"]["mode"] == "backend_resolved"
    assert bottleneck_target["resolution"]["on_missing"] == "omit"


def test_csv_runtime_evidence_is_document_bounded_when_input_csv_comes_first():
    source_text = "\n\n".join(
        [
            Path("docs/examples/gtm-showcase/anip-capability-input-contracts.csv").read_text(),
            Path("docs/examples/gtm-showcase/anip-capability-runtime-governance.csv").read_text(),
        ]
    )

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert len(inventory) == 23
    for capability in inventory:
        input_names = {
            item.get("input_name")
            for item in capability.get("inputs", [])
            if isinstance(item, dict)
        }
        assert capability.get("service_id") not in input_names


def test_csv_runtime_governance_rejects_unknown_effect_ids():
    source_text = """\
capability_id,service_id,operation_type,side_effect_level,produces,does_not_produce,summary
gtm.score_leads,gtm-prioritization-service,read,read,content.summary;content.rationale,raw_model_features,Score leads.
"""

    with pytest.raises(ANIPError) as exc:
        assistant_service._canonical_capability_inventory_from_source(source_text)

    assert "unknown business effect IDs" in str(exc.value)
    assert "content.rationale" in str(exc.value)


def test_csv_developer_evidence_rejects_unfilled_placeholder_rows():
    source_text = """\
capability_id,operation_type,side_effect_level,produces,does_not_produce,needs_developer_input
demo.pipeline_summary,read,read,content.summary,raw_data_export,true
"""

    with pytest.raises(ANIPError) as exc:
        assistant_service._canonical_capability_inventory_from_source(source_text)

    assert "placeholder row" in str(exc.value)
    assert "demo.pipeline_summary" in str(exc.value)


def test_csv_composition_evidence_builds_first_class_composition_metadata():
    source_text = """\
project_id,product_revision_artifact_id,product_revision_number,product_design_hash,capability_id,service_id,service_name,kind,operation_type,side_effect_level,grant_policy,produces,does_not_produce,minimum_scope,backend_operation,output_shape,output_intent,intent_type,subject_kind,context_type,summary,needs_developer_input,developer_notes
project-1,product-r1,1,hash,demo.composed,demo-service,Demo Service,composed,approval_gated,approval_required,default_one_time,approval.request;system.preview_mutation,approval.execute,demo.composed,demo.composed,governed_preview,approval_stop,business_action,account,quarter,Composed preview,false,

project_id,product_revision_artifact_id,product_revision_number,product_design_hash,capability_id,input_name,input_type,required,semantic_type,entity_reference,resolution_mode,on_missing,on_ambiguous,on_unresolved,default_value,allowed_values,catalog_ref,resolver_ref,summary,clarification_hint,needs_developer_input,developer_notes
project-1,product-r1,1,hash,demo.composed,quarter,string,true,time_scope,false,clarify,clarify,clarify,clarify,,,,,Quarter,Ask for quarter,false,

project_id,product_revision_artifact_id,product_revision_number,product_design_hash,capability_id,composition_required,authority_boundary,step_id,step_order,child_capability_id,input_mapping_json,output_mapping_json,failure_policy_json,audit_policy_json,needs_developer_input,developer_notes
project-1,product-r1,1,hash,demo.composed,true,same_service,select_target,1,demo.select_target,"{""quarter"":""$.input.quarter""}","{""result"":""$.steps.select_target.output.result""}","{""child_clarification"":""propagate"",""child_denial"":""propagate""}","{""record_steps"":true}",false,
"""

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert len(inventory) == 1
    capability = inventory[0]
    assert capability["kind"] == "composed"
    assert capability["composition"]["authority_boundary"] == "same_service"
    assert capability["composition"]["steps"] == [{"id": "select_target", "capability": "demo.select_target", "step_order": 1}]
    assert capability["composition"]["input_mapping"] == {"select_target": {"quarter": "$.input.quarter"}}
    assert capability["composition"]["output_mapping"] == {"result": "$.steps.select_target.output.result"}
    assert capability["composition"]["failure_policy"]["child_clarification"] == "propagate"


def test_markdown_capability_governance_overrides_json_inventory():
    source_text = """
    {
      "capabilities": [
        {
          "capability_id": "gtm.route_leads",
          "operation_type": "read",
          "side_effect_level": "read",
          "inputs": []
        }
      ]
    }

    ## Capability Runtime Governance
    | capability_id | side_effect_level | operation_type | grant_policy | produces | does_not_produce | summary |
    | --- | --- | --- | --- | --- | --- | --- |
    | gtm.route_leads | approval_required | approval_gated | default_one_time | approval.request, system.preview_mutation | approval.execute, raw_model_features | Prepare routing preview and stop at approval. |

    ## Capability: gtm.route_leads
    | input_name | input_type | required | semantic_type | entity_reference | resolution_mode | on_missing | on_ambiguous | on_unresolved | default_value | allowed_values | catalog_ref | summary | clarification_hint |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | cohort_ref | string | yes | cohort_reference | no | closed_values | clarify | clarify | clarify | | inbound_last_week | gtm.cohort_catalog | Lead cohort | Ask which cohort to route. |
    """

    inventory = assistant_service._canonical_capability_inventory_from_source(source_text)

    assert len(inventory) == 1
    capability = inventory[0]
    assert capability["operation_type"] == "approval_gated"
    assert capability["side_effect_level"] == "approval_required"
    assert capability["grant_policy"]["default_grant_type"] == "one_time"
    assert capability["inputs"][0]["input_name"] == "cohort_ref"


@pytest.mark.parametrize(
    ("capability", "artifact_type"),
    [
        ("propose_business_summary", "product_summary"),
        ("propose_actor_model", "actor_model"),
        ("propose_business_areas", "business_areas"),
        ("propose_permission_intent", "permission_intent"),
        ("propose_non_goals", "non_goals"),
        ("propose_success_criteria", "success_criteria"),
    ],
)
def test_assistant_can_propose_remaining_pm_design_artifacts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    capability: str,
    artifact_type: str,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_requirements",
        lambda _conn, _pid, _rid: {
            "id": "req-1",
            "data": {
                "business_spec": {
                    "summary": "Help operators review governed business questions, preserve actor-specific visibility, and stop for approval when needed.",
                    "business_goal": ["Answer recurring business questions with bounded results."],
                    "non_goals": ["Do not take high-impact action automatically."],
                }
            },
        },
    )

    token = _issue_token(client, capability)
    resp = client.post(
        f"/studio-assistant/anip/invoke/{capability}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-pm-design",
                "source_document_text": "Help operators review governed business questions, preserve actor-specific visibility, and stop for approval when needed.",
                "source_requirements_id": "req-1",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "pm"
    assert result["capability"] == capability
    assert result["proposal"]["proposal_kind"] == "patch_candidates"
    assert result["proposal"]["artifact_type"] == artifact_type
    assert len(result["proposal"]["patches"]) >= 1


def test_assistant_can_propose_service_design(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {
                "shape": {
                    "services": [
                        {"id": "svc-pipeline", "name": "Pipeline"},
                        {"id": "svc-prioritization", "name": "Prioritization"},
                    ]
                }
            },
        },
    )

    token = _issue_token(client, "propose_service_design")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_service_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-dev",
                "source_document_text": "Keep service ownership explicit and require approval before high-impact operational changes.",
                "source_shape_id": "shape-dev",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_service_design"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "service_design"
    assert len(result["proposal"]["items"]) >= 3
    shape = result["proposal"]["items"][0]["structured_data"]["shape"]
    assert len(shape["services"]) == 2


def test_service_design_uses_source_declared_service_capability_ownership(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )

    async def _model_should_not_run(_capability, _payload):
        raise AssertionError("explicit source ownership should compile deterministically")

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _model_should_not_run)

    source = (
        "# Revenue Operations Assistant\n\n"
        "The following capability inventory is canonical. Studio must preserve these exact capability IDs.\n\n"
        "### 1. Pipeline Service\n\n"
        "Service:\n\n"
        "- `gtm-pipeline-service`\n\n"
        "Capabilities:\n\n"
        "- `gtm.pipeline_summary`\n"
        "- `gtm.account_risk_summary`\n\n"
        "### 2. Outreach Service\n\n"
        "Service:\n\n"
        "- `gtm-outreach-service`\n\n"
        "Capabilities:\n\n"
        "- `gtm.draft_outreach_message`\n"
        "\n"
        "Representative composition families:\n\n"
        "- `pipeline -> outreach`\n"
    )

    token = _issue_token(client, "propose_service_design")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_service_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-source-ownership",
                "source_document_text": source,
            }
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    shape = body["result"]["proposal"]["items"][0]["structured_data"]["shape"]
    services = {service["id"]: service for service in shape["services"]}
    assert services["gtm-pipeline-service"]["capabilities"] == [
        "gtm.pipeline_summary",
        "gtm.account_risk_summary",
    ]
    assert services["gtm-outreach-service"]["capabilities"] == ["gtm.draft_outreach_message"]
    assert {
        "from": "gtm-pipeline-service",
        "to": "gtm-outreach-service",
    } in [{"from": edge["from"], "to": edge["to"]} for edge in shape["coordination"]]


def test_deterministic_service_shape_derives_bounded_coordination_without_reverse_noise():
    source = """
    Representative composition families:

    - `pipeline/risk -> enrichment`
    - `prioritization -> enrichment -> outreach`

    Cross-Service Capability Semantics

    - `gtm.bottleneck_account_outreach_draft` is owned by `gtm-outreach-service`.
      It drafts outreach for either an explicitly selected account from a
      bottleneck/risk review or a provider-selected bounded top candidate.
    - `gtm.prioritized_routing_preparation` is owned by
      `gtm-prioritization-service`. It composes lead scoring/prioritization into a
      routing preview and stops at approval_required.
    """
    inventory = [
        {"service_id": "gtm-pipeline-service", "capability_id": "gtm.account_risk_summary"},
        {"service_id": "gtm-pipeline-service", "capability_id": "gtm.stage_bottleneck_summary"},
        {"service_id": "gtm-enrichment-service", "capability_id": "gtm.account_enrichment_summary"},
        {"service_id": "gtm-prioritization-service", "capability_id": "gtm.prioritize_accounts"},
        {"service_id": "gtm-prioritization-service", "capability_id": "gtm.prioritized_routing_preparation"},
        {"service_id": "gtm-outreach-service", "capability_id": "gtm.draft_outreach_message"},
        {"service_id": "gtm-outreach-service", "capability_id": "gtm.prioritized_outreach_draft"},
        {"service_id": "gtm-outreach-service", "capability_id": "gtm.bottleneck_account_outreach_draft"},
    ]

    shape = assistant_service._deterministic_service_shape(
        "GTM",
        [],
        {"preserve_source_services": True},
        explicit_service_ids=[
            "gtm-pipeline-service",
            "gtm-enrichment-service",
            "gtm-prioritization-service",
            "gtm-outreach-service",
        ],
        explicit_capability_ids=[entry["capability_id"] for entry in inventory],
        source_capability_inventory=inventory,
        source_text=source,
    )

    edges = {(edge["from"], edge["to"]) for edge in shape["coordination"]}

    assert ("gtm-pipeline-service", "gtm-enrichment-service") in edges
    assert ("gtm-prioritization-service", "gtm-enrichment-service") in edges
    assert ("gtm-prioritization-service", "gtm-outreach-service") in edges
    assert ("gtm-enrichment-service", "gtm-outreach-service") in edges
    assert ("gtm-pipeline-service", "gtm-outreach-service") in edges
    assert ("gtm-outreach-service", "gtm-pipeline-service") not in edges
    assert ("gtm-outreach-service", "gtm-prioritization-service") not in edges


def test_assistant_rejects_service_design_that_ignores_topology_preference(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )

    async def _wrong_service_count(_capability, payload):
        assert payload["service_topology_preference"]["target_service_count"] == 4
        return {
            "title": "Service Design Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_service_design",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "service_design",
                "items": [
                    {
                        "client_id": "shape",
                        "title": "Over-split topology",
                        "body": "Pipeline, prioritization, outreach, governance, analytics, context, and audit are split separately.",
                        "confidence": "high",
                        "rationale": "Model ignored the requested deployable topology.",
                        "structured_data": {
                            "shape": {
                                "name": "Revenue Ops Assistant",
                                "type": "multi_service",
                                "services": [
                                    {"id": f"svc-{index}", "name": f"Service {index}", "role": "service", "responsibilities": [], "capabilities": [], "owns_concepts": []}
                                    for index in range(7)
                                ],
                                "coordination": [],
                                "domain_concepts": [],
                            }
                        },
                    }
                ],
            },
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _wrong_service_count)

    token = _issue_token(client, "propose_service_design")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_service_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-topology",
                "source_document_text": (
                    "# Revenue Operations Assistant\n\n"
                    "The assistant supports pipeline review, account context, routing, outreach drafting, approvals, audit, and governed denial."
                ),
                "service_topology_preference": {
                    "granularity": "balanced",
                    "target_service_count": 4,
                    "preserve_source_services": False,
                    "rationale": "Match the selected deployable service topology.",
                },
            }
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "invalid_request"
    assert "Expected 4 service(s), got 7" in body["failure"]["detail"]


def test_assistant_rejects_service_design_that_drops_source_declared_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )

    async def _missing_declared_capability(_capability, _payload):
        return {
            "title": "Service Design Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_service_design",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "service_design",
                "items": [
                    {
                        "client_id": "shape",
                        "title": "Incomplete topology",
                        "body": "Pipeline owns summary only.",
                        "confidence": "high",
                        "rationale": "Model omitted one source-declared ID.",
                        "structured_data": {
                            "shape": {
                                "name": "Revenue Ops Assistant",
                                "type": "multi_service",
                                "services": [
                                    {
                                        "id": "gtm-pipeline-service",
                                        "name": "GTM Pipeline Service",
                                        "role": "service",
                                        "responsibilities": [],
                                        "capabilities": ["gtm.pipeline_summary"],
                                        "owns_concepts": [],
                                    }
                                ],
                                "coordination": [],
                                "domain_concepts": [],
                            }
                        },
                    }
                ],
            },
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _missing_declared_capability)

    token = _issue_token(client, "propose_service_design")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_service_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-capability-preservation",
                "source_document_text": (
                    "# Revenue Operations Assistant\n\n"
                    "The canonical service exposes `gtm.pipeline_summary` and "
                    "`gtm.prepare_followup_tasks` as reviewed capability IDs."
                ),
            }
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "invalid_request"
    assert "dropped source-declared capability IDs" in body["failure"]["detail"]
    assert "gtm.prepare_followup_tasks" in body["failure"]["detail"]


def test_assistant_rejects_extra_capabilities_when_source_inventory_is_canonical(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )

    async def _extra_capability(_capability, _payload):
        return {
            "title": "Service Design Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_service_design",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "service_design",
                "items": [
                    {
                        "client_id": "shape",
                        "title": "Over-expanded topology",
                        "body": "Pipeline owns summary and an invented convenience capability.",
                        "confidence": "high",
                        "rationale": "Model added one capability outside source truth.",
                        "structured_data": {
                            "shape": {
                                "name": "Revenue Ops Assistant",
                                "type": "multi_service",
                                "services": [
                                    {
                                        "id": "gtm-pipeline-service",
                                        "name": "GTM Pipeline Service",
                                        "role": "service",
                                        "responsibilities": [],
                                        "capabilities": ["gtm.pipeline_summary", "gtm.pipeline_convenience_summary"],
                                        "owns_concepts": [],
                                    }
                                ],
                                "coordination": [],
                                "domain_concepts": [],
                            }
                        },
                    }
                ],
            },
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _extra_capability)

    token = _issue_token(client, "propose_service_design")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_service_design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-capability-inventory",
                "source_document_text": (
                    "# Canonical capability inventory\n\n"
                    "The capability inventory is canonical and Studio must preserve these exact capability IDs: "
                    "`gtm.pipeline_summary`."
                ),
            }
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "invalid_request"
    assert "outside the canonical source inventory" in body["failure"]["detail"]
    assert "gtm.pipeline_convenience_summary" in body["failure"]["detail"]


def test_assistant_rejects_capability_formalization_that_drops_canonical_inventory():
    source = (
        "# Canonical capability inventory\n\n"
        "The capability inventory is canonical and Studio must preserve these exact capability IDs.\n\n"
        "```json\n"
        '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary","inputs":[{"input_name":"quarter","input_type":"string","required":true}]},{"service_id":"gtm-pipeline-service","capability_id":"gtm.prepare_followup_tasks","inputs":[{"input_name":"quarter","input_type":"string","required":true}]}]}\n'
        "```"
    )
    model_result = {
            "title": "Capability Formalization Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_capability_formalization",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "capability_formalization",
                "items": [
                    {
                        "client_id": "capabilities",
                        "title": "Partial capability contracts",
                        "body": "Pipeline owns summary only.",
                        "confidence": "high",
                        "rationale": "Model omitted one canonical ID.",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.pipeline_summary",
                                    "summary": "Return a bounded pipeline summary.",
                                }
                            ]
                        },
                    }
                ],
            },
        }

    with pytest.raises(ANIPError) as exc:
        assistant_service._validate_source_grounded_model_result(
            "propose_capability_formalization",
            source,
            model_result,
            deterministic={},
        )
    assert exc.value.error_type == "invalid_request"
    assert "capability formalization that dropped source-declared canonical capability IDs" in exc.value.detail
    assert "gtm.prepare_followup_tasks" in exc.value.detail


def test_assistant_rejects_capability_formalization_that_drops_locked_shape_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Locked Shape",
            "data": {
                "shape": {
                    "services": [
                        {
                            "id": "gtm-pipeline-service",
                            "name": "GTM Pipeline Service",
                            "capabilities": ["gtm.pipeline_summary", "gtm.prepare_followup_tasks"],
                        }
                    ]
                }
            },
        },
    )

    async def _partial_capability_formalization(_capability, _payload):
        return {
            "title": "Capability Formalization Proposal",
            "summary": "Drafted from locked shape.",
            "mode": "dev",
            "capability": "propose_capability_formalization",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "capability_formalization",
                "items": [
                    {
                        "client_id": "capabilities",
                        "title": "Partial capability contracts",
                        "body": "Pipeline owns summary only.",
                        "confidence": "high",
                        "rationale": "Model omitted one locked shape ID.",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.pipeline_summary",
                                    "summary": "Return a bounded pipeline summary.",
                                }
                            ]
                        },
                    }
                ],
            },
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _partial_capability_formalization)

    token = _issue_token(client, "propose_capability_formalization")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_capability_formalization",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-capability-formalization-shape",
                "source_shape_id": "shape-with-capabilities",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["proposal"]["proposal_kind"] == "clarification_questions"
    assert "reviewed runtime input names" in body["result"]["questions_for_user"][0]


def test_assistant_rejects_placeholder_capability_formalization():
    source = (
        "# Canonical capability inventory\n\n"
        "The capability inventory is canonical and Studio must preserve these exact capability IDs.\n\n"
        "```json\n"
        '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary","inputs":[{"input_name":"quarter","input_type":"string","required":true}]},{"service_id":"gtm-pipeline-service","capability_id":"gtm.prepare_followup_tasks","inputs":[{"input_name":"quarter","input_type":"string","required":true}]}]}\n'
        "```"
    )
    model_result = {
            "title": "Capability Formalization Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_capability_formalization",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "capability_formalization",
                "items": [
                    {
                        "client_id": "capabilities",
                        "title": "Placeholder capability contracts",
                        "body": "Pipeline owns summary and follow-up.",
                        "confidence": "high",
                        "rationale": "Model filled one canonical ID with a placeholder.",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.pipeline_summary",
                                    "summary": "Return a bounded pipeline summary.",
                                },
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.prepare_followup_tasks",
                                    "summary": "Placeholder: follow-up task preparation needs explicit source context.",
                                    "backend_operation": "review_needed",
                                },
                            ]
                        },
                    }
                ],
            },
        }

    with pytest.raises(ANIPError) as exc:
        assistant_service._validate_source_grounded_model_result(
            "propose_capability_formalization",
            source,
            model_result,
            deterministic={},
        )
    assert exc.value.error_type == "invalid_request"
    assert "placeholder capability formalization" in exc.value.detail
    assert "gtm.prepare_followup_tasks" in exc.value.detail


def test_assistant_rejects_incomplete_capability_formalization():
    source = (
        "# Canonical capability inventory\n\n"
        "The capability inventory is canonical and Studio must preserve these exact capability IDs.\n\n"
        "```json\n"
        '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary","inputs":[{"input_name":"quarter","input_type":"string","required":true}]},{"service_id":"gtm-pipeline-service","capability_id":"gtm.prepare_followup_tasks","inputs":[{"input_name":"quarter","input_type":"string","required":true}]}]}\n'
        "```"
    )
    model_result = {
            "title": "Capability Formalization Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_capability_formalization",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "capability_formalization",
                "items": [
                    {
                        "client_id": "capabilities",
                        "title": "Incomplete capability contracts",
                        "body": "Pipeline owns summary and follow-up.",
                        "confidence": "high",
                        "rationale": "Model kept IDs but omitted input contract details.",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.pipeline_summary",
                                    "summary": "Return a bounded pipeline summary.",
                                    "backend_operation": "gtm.pipeline_summary",
                                    "output_shape": "gtm_pipeline_summary_result",
                                    "inputs": [],
                                },
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.prepare_followup_tasks",
                                    "summary": "Prepare follow-up task previews.",
                                    "backend_operation": "gtm.prepare_followup_tasks",
                                    "output_shape": "gtm_followup_task_preview",
                                    "inputs": [
                                        {
                                            "input_name": "quarter",
                                            "input_type": "string",
                                            "required": True,
                                            "summary": "Quarter to evaluate.",
                                        }
                                    ],
                                },
                            ]
                        },
                    }
                ],
            },
        }

    with pytest.raises(ANIPError) as exc:
        assistant_service._validate_source_grounded_model_result(
            "propose_capability_formalization",
            source,
            model_result,
            deterministic={},
        )
    assert exc.value.error_type == "invalid_request"
    assert "incomplete capability formalization" in exc.value.detail
    assert "gtm.pipeline_summary" in exc.value.detail


def test_canonical_capability_inventory_parser_preserves_markdown_input_contracts():
    source = (
        "# Canonical capability inventory\n\n"
        "The canonical capability inventory is source owned.\n\n"
        "```json\n"
        '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary",'
        '"inputs":[{"input_name":"quarter","input_type":"string","required":true,"semantic_type":"time_scope"},'
        '{"input_name":"owner_scope","input_type":"string","required":false,"semantic_type":"scope_reference",'
        '"default_value":"East","input_format":"business_scope","validation_pattern":"^[A-Za-z ]+$",'
        '"clarification_hint":"Ask for a region when the scope is ambiguous.",'
        '"resolution":{"mode":"actor_policy_or_explicit","on_missing":"use_actor_scope","on_ambiguous":"clarify","on_unresolved":"clarify"}}]}]}\n'
        "```"
    )

    inventory = assistant_service._canonical_capability_inventory_from_source(source)

    assert inventory == [
        {
            "service_id": "gtm-pipeline-service",
            "capability_id": "gtm.pipeline_summary",
            "inputs": [
                {
                    "input_name": "quarter",
                    "input_type": "string",
                    "required": True,
                    "semantic_type": "time_scope",
                },
                {
                    "input_name": "owner_scope",
                    "input_type": "string",
                    "required": False,
                    "semantic_type": "scope_reference",
                    "default": "East",
                    "input_format": "business_scope",
                    "validation_pattern": "^[A-Za-z ]+$",
                    "clarification_hint": "Ask for a region when the scope is ambiguous.",
                    "resolution": {
                        "mode": "actor_policy_or_explicit",
                        "on_missing": "use_actor_scope",
                        "on_ambiguous": "clarify",
                        "on_unresolved": "clarify",
                    },
                },
            ],
        }
    ]


def test_assistant_compiles_canonical_capability_inventory_without_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )

    async def _model_must_not_run(_capability, _payload):
        raise AssertionError("model should not run for reviewed canonical capability inventory")

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _model_must_not_run)

    token = _issue_token(client, "propose_capability_formalization")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_capability_formalization",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-capability-formalization-compiled",
                "source_document_text": (
                    "# Canonical capability inventory\n\n"
                    "The canonical capability inventory is source owned.\n\n"
                    "```json\n"
                    '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary",'
                    '"summary":"Return a bounded pipeline summary.","operation_type":"summary","side_effect_level":"read_only",'
                    '"output_shape":"gtm_pipeline_summary_result","backend_operation":"gtm.pipeline_summary",'
                    '"business_effects":{"produces":["content.summary"],"does_not_produce":["raw_data_export"]},'
                    '"inputs":[{"input_name":"quarter","input_type":"string","required":true,"semantic_type":"time_scope","summary":"Quarter label"},'
                    '{"input_name":"owner_scope","input_type":"string","required":false,"semantic_type":"scope_reference","summary":"Actor scope",'
                    '"default":"East","resolution":{"mode":"actor_policy_or_explicit","on_missing":"use_actor_scope"}}]}]}\n'
                    "```"
                ),
            }
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    capabilities = result["proposal"]["items"][0]["structured_data"]["capabilities"]
    assert len(capabilities) == 1
    assert capabilities[0]["capability_id"] == "gtm.pipeline_summary"
    assert capabilities[0]["backend_operation"] == "gtm.pipeline_summary"
    assert capabilities[0]["output_shape"] == "gtm_pipeline_summary_result"
    assert [item["input_name"] for item in capabilities[0]["inputs"]] == ["quarter", "owner_scope"]
    assert capabilities[0]["inputs"][1]["default"] == "East"
    assert capabilities[0]["inputs"][1]["default_value"] == "East"
    assert capabilities[0]["inputs"][1]["resolution"]["mode"] == "actor_policy_or_explicit"


def test_assistant_prefers_current_source_inventory_over_stale_capability_artifacts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "revenue", "summary": "Revenue design"},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [])
    monkeypatch.setattr(
        assistant_service,
        "list_pm_artifacts",
        lambda _conn, _pid: [
            {
                "id": "stale-capability-artifact",
                "data": {
                    "artifact_type": "assistant_capability_formalization_candidates",
                    "accepted_payload": [
                        {
                            "structured_data": {
                                "capabilities": [
                                    {
                                        "service_id": "gtm-pipeline-service",
                                        "capability_id": "gtm.at_risk_followup_preparation",
                                        "kind": "atomic",
                                        "summary": "Stale atomic artifact.",
                                        "operation_type": "approval_gated",
                                        "side_effect_level": "approval_required",
                                        "backend_operation": "stale_atomic",
                                        "output_shape": "stale_result",
                                        "business_effects": {
                                            "produces": ["approval.request"],
                                            "does_not_produce": ["raw_data_export"],
                                        },
                                        "inputs": [
                                            {
                                                "input_name": "quarter",
                                                "input_type": "string",
                                                "required": True,
                                                "summary": "Quarter label.",
                                            }
                                        ],
                                    }
                                ]
                            }
                        }
                    ],
                },
            }
        ],
    )

    async def _model_must_not_run(_capability, _payload):
        raise AssertionError("model should not run for reviewed canonical capability inventory")

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _model_must_not_run)

    token = _issue_token(client, "propose_capability_formalization")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_capability_formalization",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-current-source-wins",
                "source_document_text": (
                    "# Canonical capability inventory\n\n"
                    "The canonical capability inventory is source owned.\n\n"
                    "```json\n"
                    '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service",'
                    '"capability_id":"gtm.at_risk_followup_preparation","kind":"composed",'
                    '"summary":"Prepare a governed follow-up preview for at-risk accounts.",'
                    '"operation_type":"approval_gated","side_effect_level":"approval_required",'
                    '"backend_operation":"prepare_followup_preview","output_shape":"at_risk_followup_preview",'
                    '"grant_policy":{"allowed_grant_types":["one_time","session_bound"],"default_grant_type":"one_time","expires_in_seconds":900,"max_uses":1},'
                    '"business_effects":{"produces":["approval.request"],"does_not_produce":["raw_data_export"]},'
                    '"composition":{"authority_boundary":"same_service",'
                    '"steps":[{"id":"prepare_followup_preview","capability":"gtm.prepare_followup_tasks","step_order":1}],'
                    '"input_mapping":{"prepare_followup_preview":{"quarter":"$.input.quarter"}},'
                    '"output_mapping":{"result":"$.steps.prepare_followup_preview.output.result"},'
                    '"failure_policy":{"child_error":"fail_parent","child_denial":"propagate","child_clarification":"propagate","child_approval_required":"propagate"}},'
                    '"inputs":[{"input_name":"quarter","input_type":"string","required":true,"summary":"Quarter label."}]}]}\n'
                    "```"
                ),
            }
        },
    )

    assert resp.status_code == 200, resp.text
    capabilities = resp.json()["result"]["proposal"]["items"][0]["structured_data"]["capabilities"]
    assert len(capabilities) == 1
    assert capabilities[0]["capability_id"] == "gtm.at_risk_followup_preparation"
    assert capabilities[0]["kind"] == "composed"
    assert capabilities[0]["backend_operation"] == "prepare_followup_preview"
    assert capabilities[0]["composition"]["steps"] == [
        {"id": "prepare_followup_preview", "capability": "gtm.prepare_followup_tasks", "step_order": 1}
    ]


def test_input_only_inventory_is_not_full_capability_contract_detail():
    input_only = [
        {
            "service_id": "gtm-pipeline-service",
            "capability_id": "gtm.pipeline_summary",
            "inputs": [
                {"input_name": "quarter", "input_type": "string", "required": True},
            ],
        }
    ]
    detailed = [
        {
            **input_only[0],
            "summary": "Return a bounded pipeline summary.",
            "output_shape": "gtm_pipeline_summary_result",
        }
    ]

    assert assistant_service._inventory_has_capability_contract_detail(input_only) is False
    assert assistant_service._inventory_has_capability_contract_detail(detailed) is True


def test_canonical_inventory_csv_sources_are_strict_and_deduped():
    repo_root = Path(__file__).resolve().parents[2]
    governance = (repo_root / "docs/examples/gtm-showcase/anip-capability-runtime-governance.csv").read_text()
    inputs = (repo_root / "docs/examples/gtm-showcase/anip-capability-input-contracts.csv").read_text()
    source = "\n\n".join([
        "The capability inventory is canonical.",
        governance,
        inputs,
        inputs,
    ])

    inventory = assistant_service._canonical_capability_inventory_from_source(source)
    by_id = {entry["capability_id"]: entry for entry in inventory}

    assert len(inventory) == 23
    assert "capability_id" not in by_id
    assert by_id["gtm.pipeline_summary"]["service_id"] == "gtm-pipeline-service"
    assert by_id["gtm.at_risk_followup_preparation"]["kind"] == "composed"
    pipeline_inputs = by_id["gtm.pipeline_summary"]["inputs"]
    assert [item["input_name"] for item in pipeline_inputs] == ["quarter", "owner_scope", "detail_level"]


def test_assistant_rejects_capability_formalization_input_contract_drift():
    source = (
        "# Canonical capability inventory\n\n"
        "The canonical capability inventory is source owned.\n\n"
        "```json\n"
        '{"canonical_capability_inventory":[{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary",'
        '"inputs":[{"input_name":"quarter","input_type":"string","required":true,"semantic_type":"time_scope"},'
        '{"input_name":"owner_scope","input_type":"string","required":false,"semantic_type":"scope_reference"}]}]}\n'
        "```"
    )
    model_result = {
            "title": "Capability Formalization Proposal",
            "summary": "Drafted from source.",
            "mode": "dev",
            "capability": "propose_capability_formalization",
            "questions_for_user": [],
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "capability_formalization",
                "items": [
                    {
                        "client_id": "capabilities",
                        "title": "Drifting capability contract",
                        "body": "Pipeline owns summary.",
                        "confidence": "high",
                        "rationale": "Model renamed owner_scope.",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "service_id": "gtm-pipeline-service",
                                    "capability_id": "gtm.pipeline_summary",
                                    "summary": "Return a bounded pipeline summary.",
                                    "backend_operation": "gtm.pipeline_summary",
                                    "output_shape": "gtm_pipeline_summary_result",
                                    "business_effects": {
                                        "produces": ["content.summary"],
                                        "does_not_produce": ["raw_data_export"],
                                    },
                                    "inputs": [
                                        {
                                            "input_name": "quarter",
                                            "input_type": "string",
                                            "required": True,
                                            "semantic_type": "time_scope",
                                            "summary": "Quarter.",
                                        },
                                        {
                                            "input_name": "region_scope",
                                            "input_type": "string",
                                            "required": False,
                                            "semantic_type": "scope_reference",
                                            "summary": "Region.",
                                        },
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
        }

    with pytest.raises(ANIPError) as exc:
        assistant_service._validate_source_grounded_model_result(
            "propose_capability_formalization",
            source,
            model_result,
            deterministic={},
        )
    assert exc.value.error_type == "invalid_request"
    assert "inputs that drift from the source-owned canonical runtime interface" in exc.value.detail
    assert "owner_scope" in exc.value.detail
    assert "region_scope" in exc.value.detail


def test_overlay_source_owned_capability_inventory_preserves_reviewed_inputs():
    source_entry = {
        "service_id": "gtm-pipeline-service",
        "capability_id": "gtm.pipeline_summary",
        "summary": "Return a bounded pipeline summary.",
        "operation_type": "read",
        "side_effect_level": "read",
        "business_effects": {
            "produces": ["content.summary"],
            "does_not_produce": ["raw_data_export"],
        },
        "inputs": [
            {
                "input_name": "quarter",
                "input_type": "string",
                "required": True,
                "semantic_type": "time_scope",
                "summary": "Quarter label.",
            },
            {
                "input_name": "detail_level",
                "input_type": "string",
                "required": False,
                "default": "summary",
                "allowed_values": ["summary", "stage_breakdown"],
                "summary": "Summary depth.",
            },
        ],
    }
    model_result = {
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "items": [
                {
                    "structured_data": {
                        "capabilities": [
                            {
                                "service_id": "wrong-service",
                                "capability_id": "gtm.pipeline_summary",
                                "summary": "Model drafted contract.",
                                "backend_operation": "gtm.pipeline_summary",
                                "output_shape": "pipeline_result",
                                "business_effects": {
                                    "produces": ["content.rationale"],
                                    "does_not_produce": [],
                                },
                                "inputs": [
                                    {
                                        "input_name": "quarter",
                                        "input_type": "string",
                                        "required": True,
                                        "summary": "Quarter without semantic type.",
                                    },
                                    {
                                        "input_name": "scope",
                                        "input_type": "string",
                                        "required": False,
                                        "summary": "Wrong input.",
                                    },
                                ],
                            }
                        ]
                    }
                }
            ],
        }
    }

    repaired = assistant_service._overlay_source_owned_capability_inventory(model_result, [source_entry])
    capability = repaired["proposal"]["items"][0]["structured_data"]["capabilities"][0]

    assert capability["service_id"] == "gtm-pipeline-service"
    assert capability["business_effects"] == source_entry["business_effects"]
    assert [item["input_name"] for item in capability["inputs"]] == ["quarter", "detail_level"]
    assert capability["inputs"][0]["semantic_type"] == "time_scope"
    assert capability["inputs"][1]["default"] == "summary"
    assert capability["inputs"][1]["allowed_values"] == ["summary", "stage_breakdown"]


def test_service_design_prompt_drafts_reviewable_capability_ids_for_clear_boundaries():
    prompt = assistant_provider._user_prompt(
        "propose_service_design",
        {
            "project": {"id": "proj", "name": "Revenue Ops", "domain": "gtm"},
            "source_document_text": (
                "The enrichment service summarizes firmographic context and finds lookalike accounts. "
                "The outreach service drafts outreach and must not send messages."
            ),
            "source_shape_services": ["gtm-enrichment-service", "gtm-outreach-service"],
            "source_declared_capability_id_candidates": [],
            "source_declared_service_id_candidates": ["gtm-enrichment-service", "gtm-outreach-service"],
            "service_topology_preference": {"target_service_count": 2},
            "deterministic_draft": {},
        },
    )

    assert "draft a small candidate capability surface" in prompt
    assert "requiring PM/dev confirmation" in prompt
    assert "Prefer exact copied ids over paraphrased service ids" in prompt
    assert "Leave a service capabilities array empty only when both the boundary and its responsibilities are too vague" in prompt


def test_business_summary_prompt_requires_supported_question_families():
    prompt = assistant_provider._user_prompt(
        "propose_business_summary",
        {
            "project": {"id": "proj", "name": "Revenue Ops", "domain": "gtm"},
            "source_document_text": "Help managers answer pipeline risk, forecast, enrichment, routing, and outreach drafting questions.",
            "deterministic_draft": {},
        },
    )

    assert "/supported_question_families" in prompt
    assert "stable user question/task families" in prompt
    assert "return targeted questions instead of silently omitting that field" in prompt


def test_capability_formalization_prompt_separates_read_and_approval_preview_intent():
    prompt = assistant_provider._user_prompt(
        "propose_capability_formalization",
        {
            "project": {"id": "proj", "name": "Revenue Ops", "domain": "gtm"},
            "source_document_text": (
                "The service explains account fit, ranks priority cohorts, prepares routing recommendations, "
                "and stops before any routing mutation is executed."
            ),
            "source_shape_services": ["gtm-enrichment-service", "gtm-prioritization-service"],
            "source_declared_capability_id_candidates": [],
            "source_declared_service_id_candidates": ["gtm-enrichment-service", "gtm-prioritization-service"],
            "deterministic_draft": {},
        },
    )

    assert "prefer those exact service ids for service_id values" in prompt
    assert "Classify side effects from explicit source evidence" in prompt
    assert "do not infer execution authority from capability names alone" in prompt
    assert "Every capability must include business_effects.produces and business_effects.does_not_produce" in prompt
    assert "If kind is composed, include contract-level composition metadata" in prompt


def test_openai_provider_requests_json_object_mode(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    async def _fake_post_json_with_retry(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "{\"title\":\"ok\"}"}}]}

    monkeypatch.setattr(assistant_provider, "_post_json_with_retry", _fake_post_json_with_retry)

    result = asyncio.run(
        assistant_provider._invoke_openai_compatible(
            assistant_provider.AssistantProviderConfig(
                provider="openai",
                model="gpt-test",
                base_url=None,
                api_key="test-key",
                temperature=0.2,
                timeout_seconds=30,
                strict=True,
            ),
            "suggest_next_step",
            {"project": {"id": "proj"}},
        )
    )

    assert result == {"title": "ok"}
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_input_contract_prompt_requires_complete_canonical_inventory():
    prompt = assistant_provider._user_prompt(
        "propose_input_contracts",
        {
            "project": {"id": "proj", "name": "Revenue Ops", "domain": "gtm"},
            "source_document_text": "Service exposes gtm.pipeline_summary.",
            "canonical_capability_inventory": [{"capability_id": "gtm.pipeline_summary"}],
            "deterministic_draft": {},
        },
    )

    assert "canonical_capability_inventory" in prompt
    assert "exactly one entry for every inventory entry" in prompt
    assert "do not emit empty inputs" in prompt


def test_assistant_can_clarify_pm_design_section(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design", "documents_count": 1},
    )
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "id": "pm-summary",
            "data": {
                "artifact_type": "product_summary",
                "product_purpose": "Help ops teams answer governed business questions.",
                "business_problem": "",
                "business_goals": [],
                "supported_question_families": [],
                "governed_behavior_summary": "",
                "approval_posture_summary": "",
            },
        }
    ])

    token = _issue_token(client, "clarify_design_section")
    resp = client.post(
        "/studio-assistant/anip/invoke/clarify_design_section",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-pm-clarify",
                "mode": "pm",
                "section_key": "product_summary",
                "source_document_text": "Build a governed assistant for revenue operations.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "pm"
    assert result["capability"] == "clarify_design_section"
    assert result["proposal"]["proposal_kind"] == "clarification_questions"
    assert len(result["proposal"]["questions"]) >= 1


def test_permission_intent_fallback_rules_do_not_count_complete():
    assert assistant_service._permission_intent_complete(
        {
            "artifact_type": "permission_intent",
            "policy_summary": "Bounded access with approval stops.",
            "rules": [
                {
                    "actor_id": "sales_leader",
                    "business_area": "pipeline_health",
                    "access_posture": "bounded",
                    "governed_outcome_type": "bounded_result",
                    "governed_outcome": "Allow bounded pipeline review.",
                    "notes": "Studio-derived review candidate because the assistant produced a policy summary but no concrete actor-by-business-area rules. Confirm or edit before locking Product Design.",
                }
            ],
        }
    ) is False


def test_assistant_can_clarify_dev_design_section(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {"id": sid, "title": "Service Shape", "data": {"shape": {"services": [{"id": "svc-1", "name": "Pipeline"}]}}},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [{"id": "req-1"}])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [{"id": "scn-1"}])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [{"id": "shape-1"}])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {"id": "baseline", "data": {"artifact_type": "developer_baseline"}},
        {
            "id": "actors",
            "data": {
                "artifact_type": "actor_model",
                "actors": [{"actor_id": "ops_manager", "title": "Ops Manager", "summary": ""}],
            },
        },
        {
            "id": "areas",
            "data": {
                "artifact_type": "business_areas",
                "entries": [{"business_area_id": "pipeline", "label": "Pipeline"}],
            },
        },
        {
            "id": "permissions",
            "data": {
                "artifact_type": "permission_intent",
                "policy_summary": "",
                "rules": [],
            },
        },
    ])

    token = _issue_token(client, "clarify_design_section")
    resp = client.post(
        "/studio-assistant/anip/invoke/clarify_design_section",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-dev-clarify",
                "mode": "dev",
                "section_key": "authority_and_approval",
                "source_document_text": "Approval boundaries must stay explicit.",
                "source_shape_id": "shape-1",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "clarify_design_section"
    assert result["proposal"]["proposal_kind"] == "clarification_questions"
    assert len(result["proposal"]["questions"]) >= 1


def test_pm_section_proposal_uses_saved_clarification_answers(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _capture(_capability: str, payload: dict[str, object]):
        captured.update(payload)
        return None

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _capture)
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design", "documents_count": 1},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "id": "pm-clarify",
            "data": {
                "artifact_type": "assistant_section_clarifications",
                "mode": "pm",
                "section_key": "product_summary",
                "accepted_payload": [
                    {
                        "question_id": "product-summary-purpose",
                        "prompt": "What is the product trying to accomplish?",
                        "answer": "It should help operators answer governed revenue questions.",
                    },
                ],
            },
        },
    ])

    token = _issue_token(client, "propose_business_summary")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_business_summary",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-pm-answer-context", "source_document_text": "Build a governed assistant."}},
    )
    assert resp.status_code == 200, resp.text
    assert "It should help operators answer governed revenue questions." in str(captured.get("source_document_text", ""))
    assert captured.get("section_clarification_answers") == [
        "What is the product trying to accomplish? Answer: It should help operators answer governed revenue questions.",
    ]


def test_dev_section_proposal_uses_saved_clarification_answers(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    async def _capture(_capability: str, payload: dict[str, object]):
        captured.update(payload)
        return None

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _capture)
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {"id": sid, "title": "Service Shape", "data": {"shape": {"services": [{"id": "svc-1", "name": "Pipeline"}]}}},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [{"id": "req-1"}])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [{"id": "scn-1"}])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [{"id": "shape-1"}])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {"id": "baseline", "data": {"artifact_type": "developer_baseline"}},
        {
            "id": "dev-clarify",
            "data": {
                "artifact_type": "assistant_section_clarifications",
                "mode": "dev",
                "section_key": "authority_and_approval",
                "accepted_payload": [
                    {
                        "question_id": "authority-and-approval-1",
                        "prompt": "Where should the runtime allow, restrict, clarify, deny, or stop for approval?",
                        "answer": "Stop for approval before any high-impact write that changes operational state.",
                    },
                ],
            },
        },
    ])

    token = _issue_token(client, "propose_runtime_policy_bindings")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_runtime_policy_bindings",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-dev-answer-context", "source_document_text": "Approval boundaries must stay explicit.", "source_shape_id": "shape-1"}},
    )
    assert resp.status_code == 200, resp.text
    assert "Stop for approval before any high-impact write that changes operational state." in str(captured.get("source_document_text", ""))
    assert captured.get("section_clarification_answers") == [
        "Where should the runtime allow, restrict, clarify, deny, or stop for approval? Answer: Stop for approval before any high-impact write that changes operational state.",
    ]


def test_assistant_can_propose_capability_formalization(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {
                "shape": {
                    "services": [
                        {"id": "svc-pipeline", "name": "Pipeline"},
                        {"id": "svc-prioritization", "name": "Prioritization"},
                    ]
                }
            },
        },
    )

    token = _issue_token(client, "propose_capability_formalization")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_capability_formalization",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-cap-form",
                "source_document_text": "Define stable capability ids, explicit required inputs, and approval-sensitive capability boundaries.",
                "source_shape_id": "shape-cap-form",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_capability_formalization"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "capability_formalization"
    assert len(result["proposal"]["items"]) >= 3


def test_assistant_can_propose_runtime_policy_bindings(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {
                "shape": {
                    "services": [
                        {"id": "svc-pipeline", "name": "Pipeline"},
                        {"id": "svc-prioritization", "name": "Prioritization"},
                    ]
                }
            },
        },
    )

    token = _issue_token(client, "propose_runtime_policy_bindings")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_runtime_policy_bindings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-runtime-policy",
                "source_document_text": "Make approval stops explicit, keep actor visibility bounded, and clarify when the system should ask for more information before returning an answer.",
                "source_shape_id": "shape-runtime-policy",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_runtime_policy_bindings"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "runtime_policy_bindings"
    assert len(result["proposal"]["items"]) >= 3


def test_assistant_can_propose_input_contracts(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {
                "shape": {
                    "services": [
                        {"id": "svc-pipeline", "name": "Pipeline"},
                        {"id": "svc-prioritization", "name": "Prioritization"},
                    ]
                }
            },
        },
    )

    token = _issue_token(client, "propose_input_contracts")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_input_contracts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-input-contracts",
                "source_document_text": "Define stable required inputs, allowed values, and clarification thresholds so the runtime does not depend on hidden assumptions.",
                "source_shape_id": "shape-input-contracts",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_input_contracts"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "input_contracts"
    assert len(result["proposal"]["items"]) >= 3


def test_input_contracts_asks_for_clarification_when_canonical_inventory_has_no_inputs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {"shape": {"services": [{"id": "gtm-pipeline-service", "name": "Pipeline"}]}},
        },
    )

    token = _issue_token(client, "propose_input_contracts")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_input_contracts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-input-contracts-clarify",
                "source_document_text": "\n".join(
                    [
                        "The following capability inventory is canonical for this showcase.",
                        "### Pipeline Service",
                        "Service:",
                        "- `gtm-pipeline-service`",
                        "Capabilities:",
                        "- `gtm.pipeline_summary`",
                    ]
                ),
                "source_shape_id": "shape-input-contracts",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["capability"] == "propose_input_contracts"
    assert result["proposal"]["proposal_kind"] == "clarification_questions"
    assert "developer-owned runtime input-contract evidence" in result["summary"]
    assert result["proposal"]["questions"][0]["question_id"] == "developer-input-contract-evidence-needed"
    assert "items" not in result["proposal"]


def test_input_contracts_uses_inline_guided_clarification_answer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {"shape": {"services": [{"id": "gtm-pipeline-service", "name": "Pipeline"}]}},
        },
    )

    async def fake_model_response(capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured_payloads.append(payload)
        assert capability == "propose_input_contracts"
        return {
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "input_contracts",
                "items": [
                    {
                        "client_id": "input-contracts",
                        "title": "Input contracts",
                        "body": "Structured contracts.",
                        "rationale": "Developer provided the input evidence.",
                        "confidence": "high",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "capability_id": "gtm.pipeline_summary",
                                    "inputs": [
                                        {
                                            "input_name": "quarter",
                                            "input_type": "string",
                                            "summary": "Quarter label",
                                            "required": True,
                                            "semantic_type": "time_scope",
                                            "resolution": {"mode": "clarify"},
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
            "questions_for_user": [],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", fake_model_response)

    token = _issue_token(client, "propose_input_contracts")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_input_contracts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-input-contracts-guided-inline-answer",
                "source_document_text": "\n".join(
                    [
                        "The following capability inventory is canonical for this showcase.",
                        "Capabilities:",
                        "- `gtm.pipeline_summary`",
                        "---",
                        "Assistant clarification answers for Input Contracts:",
                        json.dumps(
                            [
                                {
                                    "question_id": "developer-input-contract-evidence-needed",
                                    "prompt": "Provide developer-owned runtime input-contract evidence.",
                                    "answer": "gtm.pipeline_summary: quarter string required semantic=time_scope resolution=clarify.",
                                }
                            ]
                        ),
                    ]
                ),
                "source_shape_id": "shape-input-contracts",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["capability"] == "propose_input_contracts"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "input_contracts"
    assert captured_payloads
    assert captured_payloads[0]["section_clarification_answers"]
    assert "quarter string required" in captured_payloads[0]["section_clarification_answers"][0]


def test_capability_formalization_uses_inline_guided_governance_answer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {"shape": {"services": [{"id": "gtm-pipeline-service", "name": "Pipeline"}]}},
        },
    )
    monkeypatch.setattr(
        assistant_service,
        "list_pm_artifacts",
        lambda _conn, _pid: [
            {
                "data": {
                    "artifact_type": "assistant_input_contract_candidates",
                    "source_proposal": {
                        "items": [
                            {
                                "structured_data": {
                                    "capabilities": [
                                        {
                                            "capability_id": "gtm.pipeline_summary",
                                            "inputs": [
                                                {
                                                    "input_name": "quarter",
                                                    "input_type": "string",
                                                    "summary": "Quarter label",
                                                    "required": True,
                                                }
                                            ],
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                }
            }
        ],
    )

    async def fake_model_response(capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured_payloads.append(payload)
        assert capability == "propose_capability_formalization"
        return {
            "title": "Capability Formalization Proposal",
            "summary": "Drafted from reviewed runtime governance.",
            "mode": "dev",
            "capability": "propose_capability_formalization",
            "watchouts": [],
            "next_steps": [],
            "proposal": {
                "proposal_kind": "candidate_blocks",
                "artifact_type": "capability_formalization",
                "items": [
                    {
                        "client_id": "capability-contracts",
                        "title": "Capability contracts",
                        "body": "Structured contracts.",
                        "rationale": "Developer provided runtime governance.",
                        "confidence": "high",
                        "structured_data": {
                            "capabilities": [
                                {
                                    "capability_id": "gtm.pipeline_summary",
                                    "service_id": "gtm-pipeline-service",
                                    "kind": "atomic",
                                    "intent_type": "business_action",
                                    "operation_type": "read",
                                    "side_effect_level": "read",
                                    "summary": "Return bounded pipeline evidence.",
                                    "backend_operation": "gtm.pipeline_summary",
                                    "output_shape": "gtm_pipeline_summary_result",
                                    "business_effects": {
                                        "produces": ["content.summary"],
                                        "does_not_produce": ["raw_data_export"],
                                    },
                                    "inputs": [
                                        {
                                            "input_name": "quarter",
                                            "input_type": "string",
                                            "summary": "Quarter label",
                                            "required": True,
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                ],
            },
            "questions_for_user": [],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", fake_model_response)

    source_text = "\n".join(
        [
            json.dumps(
                {
                    "canonical_capability_inventory": [
                        {
                            "service_id": "gtm-pipeline-service",
                            "capability_id": "gtm.pipeline_summary",
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "summary": "Quarter label",
                                    "required": True,
                                }
                            ],
                        }
                    ]
                }
            ),
            "---",
            "Assistant clarification answers for Capability Formalization:",
            json.dumps(
                [
                    {
                        "question_id": "capability-runtime-governance-and-composition",
                        "prompt": "Provide reviewed capability formalization.",
                        "answer": "gtm.pipeline_summary: kind=atomic operation_type=read side_effect_level=read produces=content.summary does_not_produce=raw_data_export.",
                    }
                ]
            ),
        ]
    )

    token = _issue_token(client, "propose_capability_formalization")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_capability_formalization",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-capability-guided-inline-answer",
                "source_document_text": source_text,
                "source_shape_id": "shape-capability-contracts",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "capability" in result, result
    assert result["capability"] == "propose_capability_formalization"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert captured_payloads
    assert "content.summary" in captured_payloads[0]["section_clarification_answers"][0]


def test_capability_formalization_compiles_inline_structured_governance_with_saved_inputs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [{}])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [{}])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [{}])
    monkeypatch.setattr(
        assistant_service,
        "list_pm_artifacts",
        lambda _conn, _pid: [
            {
                "data": {
                    "artifact_type": "assistant_input_contract_candidates",
                    "source_proposal": {
                        "items": [
                            {
                                "structured_data": {
                                    "capabilities": [
                                        {
                                            "capability_id": "gtm.pipeline_summary",
                                            "inputs": [
                                                {
                                                    "input_name": "quarter",
                                                    "input_type": "string",
                                                    "summary": "Quarter label like 2017-Q2.",
                                                    "required": True,
                                                }
                                            ],
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                }
            }
        ],
    )

    async def fail_model_response(_capability: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("complete structured guided evidence should not be sent through the model")

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", fail_model_response)

    source_text = "\n".join(
        [
            json.dumps(
                {
                    "shape": {
                        "services": [
                            {
                                "id": "gtm-pipeline-service",
                                "name": "Pipeline",
                                "capabilities": ["gtm.pipeline_summary"],
                            }
                        ]
                    }
                }
            ),
            "---",
            "Assistant clarification answers for Capability Formalization:",
            json.dumps(
                [
                    {
                        "question_id": "capability-runtime-governance-and-composition",
                        "prompt": "Provide reviewed capability formalization.",
                        "answer": "\n".join(
                            [
                                "## Capability runtime governance",
                                "| capability_id | kind | operation_type | side_effect_level | produces | does_not_produce | backend_operation | output_shape | output_intent | summary |",
                                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                                "| gtm.pipeline_summary | atomic | read | read | content.summary | raw_data_export | gtm.pipeline_summary | gtm_pipeline_summary_result | Return bounded pipeline health evidence. | Return bounded pipeline health evidence without exporting raw rows. |",
                            ]
                        ),
                    }
                ]
            ),
        ]
    )

    token = _issue_token(client, "propose_capability_formalization")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_capability_formalization",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-capability-guided-structured-answer",
                "source_document_text": source_text,
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    capabilities = body["result"]["proposal"]["items"][0]["structured_data"]["capabilities"]
    assert capabilities[0]["capability_id"] == "gtm.pipeline_summary"
    assert capabilities[0]["inputs"][0]["input_name"] == "quarter"
    assert capabilities[0]["business_effects"] == {
        "produces": ["content.summary"],
        "does_not_produce": ["raw_data_export"],
    }


def test_input_contracts_asks_for_clarification_when_canonical_inventory_is_partial(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {"shape": {"services": [{"id": "gtm-pipeline-service", "name": "Pipeline"}]}},
        },
    )

    token = _issue_token(client, "propose_input_contracts")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_input_contracts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-input-contracts-partial",
                "source_document_text": (
                    '{"canonical_capability_inventory":['
                    '{"service_id":"gtm-pipeline-service","capability_id":"gtm.pipeline_summary",'
                    '"inputs":[{"input_name":"quarter","input_type":"string","summary":"Quarter label"}]},'
                    '{"service_id":"gtm-pipeline-service","capability_id":"gtm.prepare_followup_tasks"}'
                    "]}"
                ),
                "source_shape_id": "shape-input-contracts",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["capability"] == "propose_input_contracts"
    assert result["proposal"]["proposal_kind"] == "clarification_questions"
    assert result["proposal"]["questions"][0]["question_id"] == "developer-input-contract-evidence-needed"
    assert "gtm.prepare_followup_tasks has no structured inputs" in result["proposal"]["questions"][0]["why_it_matters"]
    assert "items" not in result["proposal"]


def test_input_contracts_asks_for_clarification_when_canonical_ids_are_declared_without_inventory(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {"shape": {"services": [{"id": "gtm-pipeline-service", "name": "Pipeline"}]}},
        },
    )

    token = _issue_token(client, "propose_input_contracts")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_input_contracts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-input-contracts-explicit",
                "source_document_text": "\n".join(
                        [
                            "Preserve these exact capability ids before generation.",
                            "- `gtm.pipeline_summary`",
                            "- `gtm.prepare_followup_tasks`",
                        ]
                    ),
                "source_shape_id": "shape-input-contracts",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["capability"] == "propose_input_contracts"
    assert result["proposal"]["proposal_kind"] == "clarification_questions"
    assert "gtm.pipeline_summary has no structured inputs" in result["proposal"]["questions"][0]["why_it_matters"]
    assert "items" not in result["proposal"]


def test_capability_input_evidence_issues_accepts_saved_input_contract_payload():
    artifacts = [
        {
            "data": {
                "artifact_type": "assistant_input_contract_candidates",
                "accepted_payload": [
                    {
                        "structured_data": {
                            "capabilities": [
                                {
                                    "capability_id": "gtm.pipeline_summary",
                                    "inputs": [
                                        {
                                            "input_name": "quarter",
                                            "input_type": "string",
                                            "summary": "Quarter label",
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ],
            }
        }
    ]

    assert assistant_service._capability_input_evidence_issues(artifacts, ["gtm.pipeline_summary"]) == []
    assert assistant_service._capability_input_evidence_issues(
        artifacts,
        ["gtm.pipeline_summary", "gtm.prepare_followup_tasks"],
    ) == ["gtm.prepare_followup_tasks has no structured inputs"]
    inventory = assistant_service._capability_input_inventory_from_artifacts(artifacts, ["gtm.pipeline_summary"])
    assert inventory[0]["capability_id"] == "gtm.pipeline_summary"
    assert inventory[0]["inputs"][0]["input_name"] == "quarter"
    assert inventory[0]["inputs"][0]["input_type"] == "string"
    assert inventory[0]["inputs"][0]["summary"] == "Quarter label"


def test_capability_contract_inventory_reuses_saved_capability_formalization_payload():
    capability = {
        "capability_id": "gtm.pipeline_summary",
        "summary": "Return bounded summary.",
        "backend_operation": "gtm.pipeline_summary",
        "output_shape": "gtm_pipeline_summary_result",
        "operation_type": "read",
        "side_effect_level": "read",
        "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
        "inputs": [{"input_name": "quarter", "input_type": "string", "summary": "Quarter label"}],
    }
    artifacts = [
        {
            "data": {
                "artifact_type": "assistant_capability_formalization_candidates",
                "accepted_payload": [{"structured_data": {"capabilities": [capability]}}],
            }
        }
    ]

    inventory = assistant_service._capability_contract_inventory_from_artifacts(artifacts, ["gtm.pipeline_summary"])
    assert len(inventory) == 1
    assert inventory[0]["capability_id"] == "gtm.pipeline_summary"
    assert inventory[0]["business_effects"]["produces"] == ["content.summary"]


def test_assistant_can_propose_verification_expectations(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {
                "shape": {
                    "services": [
                        {"id": "svc-pipeline", "name": "Pipeline"},
                        {"id": "svc-prioritization", "name": "Prioritization"},
                    ]
                }
            },
        },
    )

    token = _issue_token(client, "propose_verification_expectations")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_verification_expectations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-verification-expectations",
                "source_document_text": "Make the evidence posture explicit for supported question families, success criteria, and non-goal guards.",
                "source_shape_id": "shape-verification-expectations",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_verification_expectations"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "verification_expectations"
    assert len(result["proposal"]["items"]) >= 3


def test_assistant_can_propose_backend_bindings(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(
        assistant_service,
        "get_shape",
        lambda _conn, _pid, sid: {
            "id": sid,
            "title": "Service Shape",
            "data": {
                "shape": {
                    "services": [
                        {"id": "svc-pipeline", "name": "Pipeline"},
                        {"id": "svc-prioritization", "name": "Prioritization"},
                    ]
                }
            },
        },
    )

    token = _issue_token(client, "propose_backend_bindings")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_backend_bindings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-backend-bindings",
                "source_document_text": "Make the data target, integration system, auth posture, and any per-service backend overrides explicit.",
                "source_shape_id": "shape-backend-bindings",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_backend_bindings"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "backend_bindings"
    assert len(result["proposal"]["items"]) >= 3


def test_assistant_can_propose_governed_fronting_capabilities(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Jira Fronting Service",
            "domain": "jira",
            "summary": "Govern Jira API and MCP operations behind ANIP.",
            "integration_profile": {
                "kind": "mcp",
                "systems": [
                    {
                        "system_id": "jira",
                        "display_name": "Jira",
                        "backend_kind": "mcp",
                        "connection_ref": "jira-mcp",
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        assistant_service,
        "list_integration_discovery_records",
        lambda _conn, _pid: [
            {
                "id": "jira-create-issue",
                "project_id": "proj-fronting",
                "connection_id": "jira-mcp",
                "operation_id": "jira.create_issue",
                "backend_kind": "mcp",
                "method": "tool",
                "path_template": "createIssue",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["project_key", "summary"], "optional": ["labels"]},
                "risk_notes": ["Creating issues should require governed semantics."],
            }
        ],
    )

    token = _issue_token(client, "propose_governed_fronting_capabilities")
    resp = client.post(
        "/studio-assistant/anip/invoke/propose_governed_fronting_capabilities",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-fronting",
                "source_document_text": "Expose Jira safely through governed capabilities instead of raw MCP tools.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "dev"
    assert result["capability"] == "propose_governed_fronting_capabilities"
    assert result["proposal"]["proposal_kind"] == "candidate_blocks"
    assert result["proposal"]["artifact_type"] == "governed_fronting_capabilities"
    item = result["proposal"]["items"][0]
    assert item["structured_data"]["backend_bindings"][0]["raw_operation_refs"] == ["jira.create_issue"]
    assert item["structured_data"]["execution_posture"] == "approval_gated"
    assert "project_key" in item["structured_data"]["required_inputs"]


def test_assistant_can_identify_missing_business_info(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )

    token = _issue_token(client, "identify_missing_business_info")
    resp = client.post(
        "/studio-assistant/anip/invoke/identify_missing_business_info",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-clarify",
                "source_document_text": "Build an internal assistant that helps answer revenue operations questions and guide the next action.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["mode"] == "pm"
    assert result["capability"] == "identify_missing_business_info"
    assert result["proposal"]["proposal_kind"] == "clarification_questions"
    assert len(result["proposal"]["questions"]) >= 1


def test_assistant_identify_missing_business_info_prefers_section_clarifications(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Revenue Ops Assistant",
            "domain": "gtm",
            "summary": "GTM design",
            "documents_count": 1,
        },
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "id": "pm-summary",
            "data": {
                "artifact_type": "product_summary",
                "product_purpose": "Help operators answer governed business questions.",
                "business_problem": "",
                "business_goals": [],
                "supported_question_families": [],
                "governed_behavior_summary": "",
                "approval_posture_summary": "",
            },
        }
    ])

    token = _issue_token(client, "identify_missing_business_info")
    resp = client.post(
        "/studio-assistant/anip/invoke/identify_missing_business_info",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-missing-info-prefers-section",
                "source_document_text": "Build a governed assistant for revenue operations.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    prompts = [question["prompt"] for question in result["proposal"]["questions"]]
    assert "What business problem is it solving?" in prompts
    assert "Which business goals must Studio preserve?" in prompts
    assert all(question["target_artifact"] == "product_summary" for question in result["proposal"]["questions"])


def test_assistant_clarify_design_section_uses_confirm_prompt_after_saved_pm_clarification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Revenue Ops Assistant",
            "domain": "gtm",
            "summary": "GTM design",
            "documents_count": 1,
        },
    )
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "id": "pm-summary-clarification",
            "data": {
                "artifact_type": "assistant_section_clarifications",
                "mode": "pm",
                "section_key": "product_summary",
                "accepted_payload": [
                    {
                        "question_id": "product-summary-purpose",
                        "prompt": "What is the product trying to accomplish?",
                        "answer": "It should help operators answer governed revenue questions.",
                    },
                ],
            },
        }
    ])
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [])

    token = _issue_token(client, "clarify_design_section")
    resp = client.post(
        "/studio-assistant/anip/invoke/clarify_design_section",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-pm-draftable-clarify",
                "mode": "pm",
                "section_key": "product_summary",
                "source_document_text": "Build a governed assistant for revenue operations.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    questions = result["proposal"]["questions"]
    assert len(questions) == 1
    assert questions[0]["question_id"] == "product_summary-confirm-readiness"
    assert "What is still ambiguous in Business Summary" in questions[0]["prompt"]


def test_assistant_can_suggest_next_step_for_pm_clarification_first(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Revenue Ops Assistant",
            "domain": "gtm",
            "summary": "GTM design",
            "documents_count": 1,
        },
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_evaluations", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "id": "pm-summary",
            "data": {
                "artifact_type": "product_summary",
                "product_purpose": "Help operators answer governed business questions.",
                "business_problem": "",
                "business_goals": [],
                "supported_question_families": [],
                "governed_behavior_summary": "",
                "approval_posture_summary": "",
            },
        }
    ])

    token = _issue_token(client, "suggest_next_step")
    resp = client.post(
        "/studio-assistant/anip/invoke/suggest_next_step",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-next-step-pm-clarify",
                "mode": "pm",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "Resolve the targeted ambiguity in Business Summary" in result["focused_answer"]
    assert result["action_label"] == "Open Business Summary"
    assert result["action_path"].endswith("/product-summary")
    assert any("What business problem is it solving?" in step for step in result["next_steps"])


def test_assistant_suggest_next_step_falls_back_when_provider_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {
            "id": pid,
            "name": "Travel Assistant",
            "domain": "travel",
            "summary": "Travel planning design",
            "documents_count": 1,
        },
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [{"id": "req-1"}])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [{"id": "scn-1"}])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [{"id": "shape-1"}])
    monkeypatch.setattr(assistant_service, "list_evaluations", lambda _conn, _pid: [])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [])

    async def _provider_failure(_capability, _payload):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _provider_failure)

    token = _issue_token(client, "suggest_next_step")
    resp = client.post(
        "/studio-assistant/anip/invoke/suggest_next_step",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-next-step-provider-failure",
                "mode": "pm",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert result["focused_answer"]
    assert any("LLM provider failed" in item for item in result["watchouts"])


def test_assistant_can_suggest_next_step_for_dev(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [{"id": "req-1"}])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [{"id": "scn-1"}])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [{"id": "shape-1"}])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {"data": {"artifact_type": "developer_baseline"}},
        {"data": {"artifact_type": "design_traceability"}},
    ])
    monkeypatch.setattr(assistant_service, "list_evaluations", lambda _conn, _pid: [])

    token = _issue_token(client, "suggest_next_step")
    resp = client.post(
        "/studio-assistant/anip/invoke/suggest_next_step",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-next-step",
                "mode": "dev",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "Capability Contracts" in result["focused_answer"]
    assert result["action_label"] == "Open Capability Contracts"
    assert result["action_path"].endswith("/developer/definition")
    assert len(result["next_steps"]) >= 1


def test_assistant_suggest_next_step_uses_saved_dev_clarifications(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(assistant_service, "list_requirements", lambda _conn, _pid: [{"id": "req-1"}])
    monkeypatch.setattr(assistant_service, "list_scenarios", lambda _conn, _pid: [{"id": "scn-1"}])
    monkeypatch.setattr(assistant_service, "list_shapes", lambda _conn, _pid: [{"id": "shape-1"}])
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {"data": {"artifact_type": "developer_baseline"}},
        {
            "data": {
                "artifact_type": "assistant_section_clarifications",
                "mode": "dev",
                "section_key": "authority_and_approval",
                "accepted_payload": [
                    {
                        "question_id": "authority-and-approval-1",
                        "prompt": "Where should the runtime stop for approval?",
                        "answer": "Stop for approval before any high-impact write that changes operational state.",
                    },
                ],
            },
        },
    ])
    monkeypatch.setattr(assistant_service, "list_evaluations", lambda _conn, _pid: [])

    token = _issue_token(client, "suggest_next_step")
    resp = client.post(
        "/studio-assistant/anip/invoke/suggest_next_step",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-next-step-dev-clarified", "mode": "dev"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "Capability Contracts" in result["focused_answer"]
    assert result["action_path"].endswith("/developer/definition")


def test_assistant_simulator_fix_plan_includes_blocked_readiness(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    readiness_report = {
        "artifact_type": "agent_consumption_readiness",
        "status": "blocked",
        "score": 55,
        "summary": {"blockers": 1, "warnings": 1, "info": 0, "probes": 12, "required_app_glue": 0},
        "findings": [
            {
                "id": "approval-preview-read-only",
                "severity": "blocker",
                "category": "approval_boundary",
                "owner": "developer_contract",
                "title": "Approval-preview intent is declared as read-only",
                "detail": "Approval-adjacent behavior needs explicit effects.",
                "recommendation": "Declare approval-preview effects or rewrite the contract as read-only.",
                "capability_id": "gtm.prepare_followup_tasks",
                "source": "capability",
            },
            {
                "id": "derived-target-owner",
                "severity": "warning",
                "category": "derived_target",
                "owner": "developer_contract",
                "title": "Derived target behavior needs an explicit owner",
                "detail": "Top or selected target requests need review.",
                "recommendation": "Classify this as contract-owned behavior, app glue, acceptable warning, or follow-up.",
                "capability_id": "gtm.stage_bottleneck_summary",
                "source": "capability",
            },
        ],
        "probes": [],
        "required_app_glue": [],
        "finding_reviews": {},
    }
    high_risk_report = {
        "artifact_type": "high_risk_confirmations",
        "summary": {"total": 3, "unresolved": 3, "confirmed": 0, "deferred": 0, "blockers": 1, "warnings": 2},
        "items": [],
        "reviews": {},
    }

    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "data": {
                "artifact_type": "agent_consumption_simulation_report",
                "status": "pass",
                "summary": {"passed": 12, "failed": 0},
                "cases": [],
                "simulator_runtime": {"provider": "openai", "model": "gpt-5.4-mini"},
            },
            "updated_at": "2026-04-29T20:00:00Z",
        },
        {
            "data": {
                "artifact_type": "design_traceability",
            },
        },
    ])

    async def _bad_model_response(capability, payload):
        assert capability == "analyze_agent_consumption_simulation"
        assert payload["agent_consumption_readiness"]["status"] == "blocked"
        return {
            "title": "Readiness is absent",
            "summary": "agent_consumption_readiness is null.",
            "focused_answer": "No fixes are needed because agent_consumption_readiness is null.",
            "action_label": "Open Developer Coverage",
            "action_path": "/design/projects/proj-sim-readiness-blocked/developer/coverage",
            "highlights": ["agent_consumption_readiness is null."],
            "watchouts": ["No readiness fixes are available."],
            "next_steps": ["No fixes needed."],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _bad_model_response)

    token = _issue_token(client, "analyze_agent_consumption_simulation")
    resp = client.post(
        "/studio-assistant/anip/invoke/analyze_agent_consumption_simulation",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-sim-readiness-blocked",
                "agent_consumption_readiness": readiness_report,
                "high_risk_confirmations": high_risk_report,
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    result = body["result"]
    assert "fix plan is not empty" in result["focused_answer"]
    assert any("Approval-preview intent is declared as read-only" in step for step in result["next_steps"])
    assert any("Derived target behavior needs an explicit owner" in step for step in result["next_steps"])
    assert not any("No fixes needed" in step for step in result["next_steps"])
    assert any("Unreviewed readiness findings: 2" in item for item in result["watchouts"] + result["highlights"])
    assert any("High-risk confirmations" in item for item in result["watchouts"] + result["highlights"])


def test_assistant_simulator_fix_plan_names_failed_probes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "data": {
                "artifact_type": "agent_consumption_simulation_report",
                "status": "fail",
                "summary": {"passed": 6, "failed": 2},
                "cases": [
                    {
                        "probe_id": "approval-preview-boundary",
                        "status": "fail",
                        "expected_outcome": "approval_required",
                        "actual_outcome": "success",
                        "expected_capability_id": "gtm.prepare_followup_tasks",
                        "selected_capability_id": "gtm.prepare_followup_tasks",
                        "failures": ["Expected outcome approval_required, got success."],
                    },
                    {
                        "probe_id": "derived-target-owner",
                        "status": "fail",
                        "expected_outcome": "clarification_required",
                        "actual_outcome": "success",
                        "expected_capability_id": "gtm.stage_bottleneck_summary",
                        "selected_capability_id": "gtm.pipeline_summary",
                        "failures": [
                            "Expected outcome clarification_required, got success.",
                            "Expected capability gtm.stage_bottleneck_summary, got gtm.pipeline_summary.",
                        ],
                    },
                ],
                "simulator_runtime": {"provider": "openai", "model": "gpt-5.4-mini"},
            },
            "updated_at": "2026-04-29T20:00:00Z",
        },
    ])

    async def _bad_model_response(_capability, _payload):
        return {
            "title": "No concrete probe fixes",
            "summary": "General review needed.",
            "focused_answer": "Review failed probes generally.",
            "action_label": "Open Developer Coverage",
            "action_path": "/design/projects/proj-sim-failed-probes/developer/coverage",
            "highlights": ["Failed probes exist."],
            "watchouts": ["Simulator evidence only."],
            "next_steps": ["For each failed probe, decide where the fix belongs."],
        }

    monkeypatch.setattr(assistant_service, "try_model_assistant_response", _bad_model_response)

    token = _issue_token(client, "analyze_agent_consumption_simulation")
    resp = client.post(
        "/studio-assistant/anip/invoke/analyze_agent_consumption_simulation",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_id": "proj-sim-failed-probes"}},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    joined_steps = "\n".join(result["next_steps"])
    assert "approval-preview-boundary" in joined_steps
    assert "approval-preview business effects/grant policy" in joined_steps
    assert "derived-target-owner" in joined_steps
    assert "required context/clarification behavior" in joined_steps
    assert "For each failed probe" not in result["next_steps"][0]


def test_assistant_high_risk_focus_returns_decision_help(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Revenue Ops Assistant", "domain": "gtm", "summary": "GTM design"},
    )
    monkeypatch.setattr(assistant_service, "list_pm_artifacts", lambda _conn, _pid: [
        {
            "data": {
                "artifact_type": "agent_consumption_simulation_report",
                "status": "pass",
                "summary": {"passed": 12, "failed": 0},
                "cases": [],
                "simulator_runtime": {"provider": "openai", "model": "gpt-5.4-mini"},
            },
            "updated_at": "2026-04-29T20:00:00Z",
        },
    ])

    token = _issue_token(client, "analyze_agent_consumption_simulation")
    resp = client.post(
        "/studio-assistant/anip/invoke/analyze_agent_consumption_simulation",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-high-risk-focus",
                "high_risk_confirmations": {
                    "artifact_type": "high_risk_confirmations",
                    "summary": {"total": 1, "unresolved": 1, "confirmed": 0, "deferred": 0, "blockers": 1, "warnings": 0},
                    "items": [
                        {
                            "id": "service-ownership:services-without-capabilities",
                            "category": "service_ownership",
                            "severity": "blocker",
                            "title": "Confirm services without canonical capabilities",
                            "detail": "3 service boundaries have responsibilities but no canonical capability IDs.",
                            "recommendation": "Add canonical capability IDs, merge the boundary away, or defer as app/service glue.",
                            "source": "developer_design",
                            "target_route": "/design/projects/proj-high-risk-focus/developer/services",
                        }
                    ],
                    "reviews": {},
                },
                "focus": {
                    "kind": "high_risk_confirmation",
                    "id": "service-ownership:services-without-capabilities",
                },
            }
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert "high-risk confirmation" in result["focused_answer"]
    assert any("Confirm services without canonical capabilities" in step for step in result["next_steps"])
    assert any("intentionally defer" in step.lower() for step in result["next_steps"])


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


def test_assistant_biases_intent_for_project_consumer_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        assistant_service,
        "get_project_detail",
        lambda _conn, pid: {"id": pid, "name": "Studio Project", "labels": ["consumer:agent_anip"]},
    )

    token = _issue_token(client, "interpret_project_intent")
    resp = client.post(
        "/studio-assistant/anip/invoke/interpret_project_intent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_id": "proj-agent",
                "intent": "We need a system that books travel and escalates exceptions.",
            }
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert "agents and tools through anip" in result["summary"].lower()
    assert any(
        "machine-usable" in item.lower() or "anip consumer" in item.lower()
        for item in result["requirements_focus"]
    )


def test_incomplete_capability_contracts_require_effects_grant_and_composition():
    proposal = {
        "items": [
            {
                "structured_data": {
                    "capabilities": [
                        {
                            "capability_id": "demo.prepare_assignment",
                            "summary": "Prepare an assignment preview.",
                            "backend_operation": "demo.prepare_assignment",
                            "output_shape": "assignment_preview",
                            "inputs": [{"input_name": "target_ref", "summary": "Selected target."}],
                            "kind": "composed",
                            "operation_type": "approval_gated",
                            "side_effect_level": "approval_required",
                            "business_effects": {
                                "produces": ["approval.request"],
                                "does_not_produce": ["approval.execute"],
                            },
                            "grant_policy": {
                                "allowed_grant_types": ["one_time"],
                                "default_grant_type": "one_time",
                            },
                            "composition": None,
                        }
                    ]
                }
            }
        ]
    }

    assert assistant_service._incomplete_capability_contracts(proposal) == ["demo.prepare_assignment"]


def test_complete_capability_contract_with_composition_is_accepted():
    proposal = {
        "items": [
            {
                "structured_data": {
                    "capabilities": [
                        {
                            "capability_id": "demo.prepare_assignment",
                            "summary": "Prepare an assignment preview.",
                            "backend_operation": "demo.prepare_assignment",
                            "output_shape": "assignment_preview",
                            "inputs": [{"input_name": "target_ref", "summary": "Selected target."}],
                            "kind": "composed",
                            "operation_type": "approval_gated",
                            "side_effect_level": "approval_required",
                            "business_effects": {
                                "produces": ["approval.request", "system.preview_mutation"],
                                "does_not_produce": ["approval.execute"],
                            },
                            "grant_policy": {
                                "allowed_grant_types": ["one_time"],
                                "default_grant_type": "one_time",
                            },
                            "composition": {
                                "authority_boundary": "same_service",
                                "steps": [{"id": "select_target", "capability": "demo.select_target"}],
                                "input_mapping": {"select_target": {"target_ref": "$.input.target_ref"}},
                                "output_mapping": {"result": "$.steps.select_target.output.result"},
                                "failure_policy": {"child_error": "fail_parent"},
                            },
                        }
                    ]
                }
            }
        ]
    }

    assert assistant_service._incomplete_capability_contracts(proposal) == []
