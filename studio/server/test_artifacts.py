"""Tests for artifact CRUD, referential integrity, and project coherence."""

import os
import pytest
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_project(client, pid="proj-art"):
    """Create a project with a requirements set and scenario for reuse."""
    client.post("/api/projects", json={"id": pid, "name": f"Project {pid}"})
    client.post(f"/api/projects/{pid}/requirements", json={
        "id": f"req-{pid}",
        "title": "Requirements",
        "data": {"system": {"name": "test"}},
    })
    client.post(f"/api/projects/{pid}/scenarios", json={
        "id": f"scn-{pid}",
        "title": "Scenario",
        "data": {"scenario": {"name": "test"}},
    })


# ---------------------------------------------------------------------------
# Requirements CRUD
# ---------------------------------------------------------------------------

def test_create_and_list_requirements(client):
    _seed_project(client, "proj-req-crud")
    resp = client.get("/api/projects/proj-req-crud/requirements")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == "req-proj-req-crud"


def test_get_requirements(client):
    _seed_project(client, "proj-req-get")
    resp = client.get("/api/projects/proj-req-get/requirements/req-proj-req-get")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Requirements"


def test_update_requirements(client):
    _seed_project(client, "proj-req-upd")
    resp = client.put("/api/projects/proj-req-upd/requirements/req-proj-req-upd", json={
        "title": "Updated Reqs",
        "status": "active",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated Reqs"
    assert data["status"] == "active"


def test_apply_assistant_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-apply", "name": "Assistant Apply"})
    resp = client.post("/api/projects/proj-assist-apply/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-req-candidates",
        "title": "Accepted Requirement Candidates",
        "capability": "propose_requirements",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "requirements",
            "items": [
                {
                    "client_id": "req-1",
                    "title": "Make approvals explicit",
                    "body": "Approval boundaries must be explicit.",
                    "confidence": "high",
                    "rationale": "Needed for governed behavior.",
                },
                {
                    "client_id": "req-2",
                    "title": "Preserve actor-specific visibility",
                    "body": "Different actor roles must see bounded results.",
                    "confidence": "medium",
                    "rationale": "Needed for actor-aware behavior.",
                },
            ],
        },
        "accepted_item_ids": ["req-1"],
        "rejected_item_ids": ["req-2"],
        "notes": "Keep only the approval-boundary candidate for the first PM pass.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-req-candidates"
    assert data["data"]["artifact_type"] == "assistant_requirement_candidates"
    assert data["data"]["source_capability"] == "propose_requirements"
    assert data["data"]["accepted_item_ids"] == ["req-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "req-1"


def test_append_assistant_audit_event_appends_server_side(client):
    client.post("/api/projects", json={"id": "proj-assist-audit", "name": "Assistant Audit"})

    first = client.post("/api/projects/proj-assist-audit/assistant/audit-events", json={
        "event_type": "draft_created",
        "lane": "pm",
        "bundle_artifact_id": "bundle-1",
        "section_count": 6,
        "assistant_runtime": {"provider": "openai", "model": "gpt-5.4", "base_url": None},
    })
    assert first.status_code == 201, first.text
    first_data = first.json()["data"]
    assert first_data["artifact_type"] == "assistant_audit_log"
    assert len(first_data["events"]) == 1
    assert first_data["events"][0]["project_id"] == "proj-assist-audit"
    assert first_data["events"][0]["event_type"] == "draft_created"

    second = client.post("/api/projects/proj-assist-audit/assistant/audit-events", json={
        "event_type": "section_saved",
        "lane": "pm",
        "bundle_artifact_id": "bundle-1",
        "section_id": "business_summary",
        "selected_ids": ["patch-1"],
    })
    assert second.status_code == 201, second.text
    second_data = second.json()["data"]
    assert second.json()["id"] == first.json()["id"]
    assert len(second_data["events"]) == 2
    assert second_data["events"][1]["event_type"] == "section_saved"
    assert second_data["events"][1]["section_id"] == "business_summary"


def test_update_pm_artifact_accepts_active_status(client):
    client.post("/api/projects", json={"id": "proj-pm-status", "name": "PM Status"})
    created = client.post("/api/projects/proj-pm-status/pm-artifacts", json={
        "id": "simulation-report",
        "title": "Agent Consumption Simulation Report",
        "data": {"artifact_type": "agent_consumption_simulation_report", "status": "pass"},
    })
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "frozen"

    updated = client.put("/api/projects/proj-pm-status/pm-artifacts/simulation-report", json={
        "status": "active",
        "data": {"artifact_type": "agent_consumption_simulation_report", "status": "pass", "rerun": True},
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "active"
    assert updated.json()["data"]["rerun"] is True


def test_update_pm_artifact_invalid_status_returns_422(client):
    client.post("/api/projects", json={"id": "proj-pm-invalid-status", "name": "PM Invalid Status"})
    created = client.post("/api/projects/proj-pm-invalid-status/pm-artifacts", json={
        "id": "simulation-report-invalid-status",
        "title": "Agent Consumption Simulation Report",
        "data": {"artifact_type": "agent_consumption_simulation_report"},
    })
    assert created.status_code == 201, created.text

    updated = client.put("/api/projects/proj-pm-invalid-status/pm-artifacts/simulation-report-invalid-status", json={
        "status": "accepted",
    })
    assert updated.status_code == 422, updated.text


def test_apply_assistant_scenario_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-scenarios", "name": "Assistant Scenarios"})
    resp = client.post("/api/projects/proj-assist-scenarios/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-scn-candidates",
        "title": "Accepted Scenario Candidates",
        "capability": "propose_scenarios",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "scenarios",
            "items": [
                {
                    "client_id": "scn-1",
                    "title": "Review a governed business risk question",
                    "body": "A manager reviews a bounded pipeline risk question and receives a governed result.",
                    "confidence": "high",
                    "rationale": "Anchors the primary PM scenario.",
                },
                {
                    "client_id": "scn-2",
                    "title": "Stop for approval before a high-impact change",
                    "body": "The system prepares a proposed action but stops at an approval boundary.",
                    "confidence": "high",
                    "rationale": "Makes the approval stop condition explicit.",
                },
            ],
        },
        "accepted_item_ids": ["scn-2"],
        "rejected_item_ids": ["scn-1"],
        "notes": "Keep the approval-stop scenario for the first PM pass.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-scn-candidates"
    assert data["data"]["artifact_type"] == "assistant_scenario_candidates"
    assert data["data"]["source_capability"] == "propose_scenarios"
    assert data["data"]["accepted_item_ids"] == ["scn-2"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "scn-2"


def test_apply_section_clarification_persists_answers(client):
    client.post("/api/projects", json={"id": "proj-assist-clarify", "name": "Assistant Clarify"})
    resp = client.post("/api/projects/proj-assist-clarify/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-clarifications",
        "title": "Saved Clarifications",
        "capability": "clarify_design_section",
        "proposal": {
            "proposal_kind": "clarification_questions",
            "mode": "pm",
            "section_key": "product_summary",
            "questions": [
                {
                    "question_id": "product-summary-purpose",
                    "prompt": "What is the product trying to accomplish?",
                    "why_it_matters": "This changes downstream drafting.",
                    "target_artifact": "product_summary",
                },
            ],
        },
        "accepted_item_ids": ["product-summary-purpose"],
        "accepted_answers": {
            "product-summary-purpose": "Help operators answer governed revenue questions with explicit approval stops.",
        },
        "rejected_item_ids": [],
        "notes": "Captured only the missing product-purpose clarification.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["data"]["artifact_type"] == "assistant_section_clarifications"
    assert data["data"]["mode"] == "pm"
    assert data["data"]["section_key"] == "product_summary"
    assert data["data"]["accepted_payload"][0]["answer"] == "Help operators answer governed revenue questions with explicit approval stops."


@pytest.mark.parametrize(
    ("capability", "artifact_type", "proposal_artifact_type"),
    [
        ("propose_business_summary", "assistant_business_summary_candidates", "product_summary"),
        ("propose_actor_model", "assistant_actor_model_candidates", "actor_model"),
        ("propose_business_areas", "assistant_business_area_candidates", "business_areas"),
        ("propose_permission_intent", "assistant_permission_intent_candidates", "permission_intent"),
        ("propose_non_goals", "assistant_non_goal_candidates", "non_goals"),
        ("propose_success_criteria", "assistant_success_criteria_candidates", "success_criteria"),
    ],
)
def test_apply_remaining_pm_patch_proposals_persist_pm_artifacts(client, capability, artifact_type, proposal_artifact_type):
    project_id = f"proj-{capability}"
    client.post("/api/projects", json={"id": project_id, "name": f"Project {capability}"})
    resp = client.post(f"/api/projects/{project_id}/assistant/proposals/apply", json={
        "artifact_id": f"pm-{capability}",
        "title": f"Accepted {capability}",
        "capability": capability,
        "proposal": {
            "proposal_kind": "patch_candidates",
            "artifact_type": proposal_artifact_type,
            "patches": [
                {
                    "path": "/example",
                    "op": "replace",
                    "value": "example",
                    "rationale": "Example deterministic PM patch.",
                },
            ],
        },
        "accepted_item_ids": ["0"],
        "rejected_item_ids": [],
        "notes": "Keep the first PM patch candidate.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["data"]["artifact_type"] == artifact_type
    assert data["data"]["source_capability"] == capability
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["path"] == "/example"


def test_apply_assistant_service_design_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-service-design", "name": "Assistant Service Design"})
    resp = client.post("/api/projects/proj-assist-service-design/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-service-design-candidates",
        "title": "Accepted Service Design Candidates",
        "capability": "propose_service_design",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "service_design",
            "items": [
                {
                    "client_id": "svc-1",
                    "title": "Make service ownership boundaries explicit",
                    "body": "State which service owns each bounded responsibility.",
                    "confidence": "high",
                    "rationale": "Needed for stable capability ownership.",
                },
            ],
        },
        "accepted_item_ids": ["svc-1"],
        "rejected_item_ids": [],
        "notes": "Keep the service-boundary ownership candidate.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-service-design-candidates"
    assert data["data"]["artifact_type"] == "assistant_service_design_candidates"
    assert data["data"]["source_capability"] == "propose_service_design"
    assert data["data"]["accepted_item_ids"] == ["svc-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "svc-1"


def test_apply_assistant_capability_formalization_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-cap-form", "name": "Assistant Capability Formalization"})
    resp = client.post("/api/projects/proj-assist-cap-form/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-capability-formalization-candidates",
        "title": "Accepted Capability Formalization Candidates",
        "capability": "propose_capability_formalization",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "capability_formalization",
            "items": [
                {
                    "client_id": "cap-1",
                    "title": "Define stable capability identifiers",
                    "body": "List bounded actions and assign stable capability ids.",
                    "confidence": "high",
                    "rationale": "Needed for generation and verification.",
                },
            ],
        },
        "accepted_item_ids": ["cap-1"],
        "rejected_item_ids": [],
        "notes": "Keep the stable capability-id formalization guidance.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-capability-formalization-candidates"
    assert data["data"]["artifact_type"] == "assistant_capability_formalization_candidates"
    assert data["data"]["source_capability"] == "propose_capability_formalization"
    assert data["data"]["accepted_item_ids"] == ["cap-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "cap-1"


def test_apply_capability_formalization_materializes_fronting_mappings(client):
    client.post(
        "/api/projects",
        json={
            "id": "proj-fronting-cap-form",
            "name": "Fronting Capability Formalization",
            "domain": "jira",
            "project_type": "governed_service_project",
            "integration_profile": {
                "kind": "native_api",
                "systems": [
                    {
                        "system_id": "jira",
                        "display_name": "Jira",
                        "backend_kind": "native_api",
                        "connection_ref": "conn-jira-prod",
                    }
                ],
            },
        },
    )
    client.post("/api/projects/proj-fronting-cap-form/requirements", json={
        "id": "req-proj-fronting-cap-form",
        "title": "Requirements",
        "data": {"system": {"name": "fronting"}},
    })
    shape = client.post("/api/projects/proj-fronting-cap-form/shapes", json={
        "id": "shape-fronting",
        "title": "Fronting Shape",
        "requirements_id": "req-proj-fronting-cap-form",
        "data": {
            "shape": {
                "id": "shape-fronting",
                "name": "Jira Governed Fronting",
                "type": "single_service",
                "services": [
                    {
                        "id": "jira-governance-service",
                        "name": "Jira Governance Service",
                        "role": "governed Jira capability fronting",
                        "capabilities": ["jira.issue.get_context", "jira.incident_bug.prepare"],
                    }
                ],
                "domain_concepts": [
                    {
                        "id": "jira-issue",
                        "name": "Jira Issue",
                        "meaning": "Actor-visible Jira work item context.",
                        "owner": "jira-governance-service",
                        "sensitivity": "medium",
                    }
                ],
            }
        },
    })
    assert shape.status_code == 201, shape.text

    resp = client.post("/api/projects/proj-fronting-cap-form/assistant/proposals/apply", json={
        "artifact_id": "proj-fronting-cap-form-assistant-capability-formalization-candidates",
        "title": "Accepted Capability Formalization Candidates",
        "capability": "propose_capability_formalization",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "capability_formalization",
            "items": [
                {
                    "client_id": "cap-fronting",
                    "title": "Reviewed Jira capabilities",
                    "structured_data": {
                        "capabilities": [
                            {
                                "capability_id": "jira.issue.get_context",
                                "service_id": "jira-governance-service",
                                "title": "Get Issue Context",
                                "summary": "Inspect one Jira issue with bounded actor-visible fields.",
                                "operation_type": "read",
                                "side_effect_level": "read",
                                "backend_operation": "jira.rest.get_issue; jira.rest.get_comments",
                                "subject_kind": "jira_issue",
                                "context_type": "issue_context",
                                "output_intent": "bounded_issue_detail",
                                "inputs": [
                                    {"input_name": "issue_key", "input_type": "string", "required": True},
                                    {"input_name": "include_comments", "input_type": "boolean", "required": False},
                                ],
                            },
                            {
                                "capability_id": "jira.adapter.raw_get_issue",
                                "service_id": "jira-adapter-service",
                                "title": "Adapter Raw Get Issue",
                                "summary": "Internal adapter operation that must not become a public mapping.",
                                "operation_type": "read",
                                "side_effect_level": "read",
                                "backend_operation": "jira.rest.get_issue",
                                "inputs": [{"input_name": "issue_key", "input_type": "string", "required": True}],
                            },
                            {
                                "capability_id": "jira.incident_bug.prepare",
                                "service_id": "jira-governance-service",
                                "title": "Prepare Incident Bug",
                                "summary": "Prepare a Jira bug preview from bounded incident context without creating it.",
                                "operation_type": "write",
                                "side_effect_level": "write_adjacent",
                                "execution_posture": "prepare_only",
                                "backend_operation": "jira.rest.create_issue",
                                "subject_kind": "jira_issue",
                                "context_type": "incident_context",
                                "output_intent": "issue_create_preview",
                                "inputs": [
                                    {"input_name": "project_key", "input_type": "string", "required": True},
                                    {"input_name": "incident_summary", "input_type": "string", "required": True},
                                    {"input_name": "labels", "input_type": "string_array", "required": False},
                                ],
                            },
                        ]
                    },
                },
            ],
        },
        "accepted_item_ids": ["cap-fronting"],
        "rejected_item_ids": [],
    })
    assert resp.status_code == 201, resp.text
    artifacts = client.get("/api/projects/proj-fronting-cap-form/pm-artifacts")
    assert artifacts.status_code == 200
    mappings = [
        item
        for item in artifacts.json()
        if item["data"].get("artifact_type") == "integration_fronting_capability_mapping"
    ]
    mappings_by_capability = {item["data"]["capability_id"]: item["data"] for item in mappings}
    assert sorted(mappings_by_capability) == ["jira.incident_bug.prepare", "jira.issue.get_context"]
    mapping = mappings_by_capability["jira.issue.get_context"]
    assert mapping["service_id"] == "jira-governance-service"
    assert mapping["connection_ref"] == "conn-jira-prod"
    assert mapping["required_inputs"] == ["issue_key"]
    assert mapping["optional_inputs"] == ["include_comments"]
    assert mapping["backend_bindings"][0]["raw_operation_refs"] == [
        "jira.rest.get_issue",
        "jira.rest.get_comments",
    ]
    prepare_mapping = mappings_by_capability["jira.incident_bug.prepare"]
    assert prepare_mapping["operation_type"] == "write"
    assert prepare_mapping["side_effect_level"] == "write_adjacent"
    assert prepare_mapping["execution_posture"] == "prepare_only"
    assert prepare_mapping["required_inputs"] == ["project_key", "incident_summary"]
    assert prepare_mapping["optional_inputs"] == ["labels"]


def test_saved_capability_formalization_artifact_materializes_fronting_mappings(client):
    client.post(
        "/api/projects",
        json={
            "id": "proj-fronting-cap-form-save",
            "name": "Fronting Capability Save",
            "domain": "jira",
            "project_type": "governed_service_project",
            "integration_profile": {
                "kind": "native_api",
                "systems": [
                    {
                        "system_id": "jira",
                        "display_name": "Jira",
                        "backend_kind": "native_api",
                        "connection_ref": "conn-jira-prod",
                    }
                ],
            },
        },
    )
    client.post("/api/projects/proj-fronting-cap-form-save/requirements", json={
        "id": "req-proj-fronting-cap-form-save",
        "title": "Requirements",
        "data": {"system": {"name": "fronting"}},
    })
    shape = client.post("/api/projects/proj-fronting-cap-form-save/shapes", json={
        "id": "shape-fronting-save",
        "title": "Fronting Shape",
        "requirements_id": "req-proj-fronting-cap-form-save",
        "data": {
            "shape": {
                "id": "shape-fronting-save",
                "name": "Jira Governed Fronting",
                "type": "single_service",
                "services": [
                    {
                        "id": "jira-governance-service",
                        "name": "Jira Governance Service",
                        "role": "governed Jira capability fronting",
                        "capabilities": ["jira.issue.get_context"],
                    }
                ],
            }
        },
    })
    assert shape.status_code == 201, shape.text

    payload = {
        "artifact_type": "assistant_capability_formalization_candidates",
        "source_capability": "propose_capability_formalization",
        "accepted_payload": [
            {
                "structured_data": {
                    "capabilities": [
                        {
                            "capability_id": "jira.issue.get_context",
                            "service_id": "jira-governance-service",
                            "title": "Get Issue Context",
                            "summary": "Inspect one Jira issue with bounded actor-visible fields.",
                            "operation_type": "read",
                            "side_effect_level": "read",
                            "backend_operation": "jira.rest.get_issue",
                            "inputs": [
                                {"input_name": "issue_key", "input_type": "string", "required": True},
                            ],
                        }
                    ]
                }
            }
        ],
    }
    resp = client.post("/api/projects/proj-fronting-cap-form-save/pm-artifacts", json={
        "id": "proj-fronting-cap-form-save-assistant-capability-formalization-candidates",
        "title": "Accepted Capability Formalization Candidates",
        "data": payload,
    })
    assert resp.status_code == 201, resp.text
    artifacts = client.get("/api/projects/proj-fronting-cap-form-save/pm-artifacts")
    assert artifacts.status_code == 200
    mappings = [
        item
        for item in artifacts.json()
        if item["data"].get("artifact_type") == "integration_fronting_capability_mapping"
    ]
    assert [item["data"]["capability_id"] for item in mappings] == ["jira.issue.get_context"]


def test_updated_capability_formalization_artifact_materializes_fronting_mappings(client):
    client.post(
        "/api/projects",
        json={
            "id": "proj-fronting-cap-form-update",
            "name": "Fronting Capability Update",
            "domain": "jira",
            "project_type": "governed_service_project",
            "integration_profile": {"kind": "native_api"},
        },
    )
    client.post("/api/projects/proj-fronting-cap-form-update/requirements", json={
        "id": "req-proj-fronting-cap-form-update",
        "title": "Requirements",
        "data": {"system": {"name": "fronting"}},
    })
    shape = client.post("/api/projects/proj-fronting-cap-form-update/shapes", json={
        "id": "shape-fronting-update",
        "title": "Fronting Shape",
        "requirements_id": "req-proj-fronting-cap-form-update",
        "data": {
            "shape": {
                "type": "single_service",
                "services": [
                    {
                        "id": "jira-governance-service",
                        "name": "Jira Governance Service",
                        "capabilities": ["jira.issue.get_context"],
                    }
                ],
            }
        },
    })
    assert shape.status_code == 201, shape.text
    artifact = client.post("/api/projects/proj-fronting-cap-form-update/pm-artifacts", json={
        "id": "proj-fronting-cap-form-update-assistant-capability-formalization-candidates",
        "title": "Accepted Capability Formalization Candidates",
        "data": {"artifact_type": "assistant_capability_formalization_candidates", "accepted_payload": []},
    })
    assert artifact.status_code == 201, artifact.text

    resp = client.put(
        "/api/projects/proj-fronting-cap-form-update/pm-artifacts/proj-fronting-cap-form-update-assistant-capability-formalization-candidates",
        json={
            "title": "Accepted Capability Formalization Candidates",
            "data": {
                "artifact_type": "assistant_capability_formalization_candidates",
                "source_capability": "propose_capability_formalization",
                "accepted_payload": [
                    {
                        "structured_data": {
                            "capabilities": [
                                {
                                    "capability_id": "jira.issue.get_context",
                                    "service_id": "jira-governance-service",
                                    "title": "Get Issue Context",
                                    "operation_type": "read",
                                    "side_effect_level": "read",
                                    "backend_operation": "jira.rest.get_issue",
                                    "inputs": [
                                        {"input_name": "issue_key", "input_type": "string", "required": True},
                                    ],
                                }
                            ]
                        }
                    }
                ],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    artifacts = client.get("/api/projects/proj-fronting-cap-form-update/pm-artifacts")
    assert artifacts.status_code == 200
    mappings = [
        item
        for item in artifacts.json()
        if item["data"].get("artifact_type") == "integration_fronting_capability_mapping"
    ]
    assert [item["data"]["capability_id"] for item in mappings] == ["jira.issue.get_context"]


def test_apply_assistant_runtime_policy_binding_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-runtime-policy", "name": "Assistant Runtime Policy"})
    resp = client.post("/api/projects/proj-assist-runtime-policy/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-runtime-policy-binding-candidates",
        "title": "Accepted Runtime Policy Binding Candidates",
        "capability": "propose_runtime_policy_bindings",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "runtime_policy_bindings",
            "items": [
                {
                    "client_id": "rp-1",
                    "title": "Make approval boundaries explicit",
                    "body": "High-impact writes should stop at approval-required boundaries with a named approver role.",
                    "confidence": "high",
                    "rationale": "Needed for deterministic review and runtime policy evaluation.",
                },
            ],
        },
        "accepted_item_ids": ["rp-1"],
        "rejected_item_ids": [],
        "notes": "Keep the explicit approval-boundary candidate.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-runtime-policy-binding-candidates"
    assert data["data"]["artifact_type"] == "assistant_runtime_policy_binding_candidates"
    assert data["data"]["source_capability"] == "propose_runtime_policy_bindings"
    assert data["data"]["accepted_item_ids"] == ["rp-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "rp-1"


def test_apply_assistant_input_contract_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-input-contract", "name": "Assistant Input Contracts"})
    resp = client.post("/api/projects/proj-assist-input-contract/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-input-contract-candidates",
        "title": "Accepted Input Contract Candidates",
        "capability": "propose_input_contracts",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "input_contracts",
            "items": [
                {
                    "client_id": "ic-1",
                    "title": "Make required inputs explicit",
                    "body": "Define required fields, allowed values, and clarification thresholds for each bounded capability.",
                    "confidence": "high",
                    "rationale": "Needed for deterministic runtime input handling.",
                },
            ],
        },
        "accepted_item_ids": ["ic-1"],
        "rejected_item_ids": [],
        "notes": "Keep the explicit input-contract candidate.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-input-contract-candidates"
    assert data["data"]["artifact_type"] == "assistant_input_contract_candidates"
    assert data["data"]["source_capability"] == "propose_input_contracts"
    assert data["data"]["accepted_item_ids"] == ["ic-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "ic-1"


def test_apply_assistant_verification_expectation_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-verification", "name": "Assistant Verification"})
    resp = client.post("/api/projects/proj-assist-verification/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-verification-expectation-candidates",
        "title": "Accepted Verification Expectation Candidates",
        "capability": "propose_verification_expectations",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "verification_expectations",
            "items": [
                {
                    "client_id": "ve-1",
                    "title": "Bind supported question families to explicit evidence",
                    "body": "Define what runtime evidence proves the system answers the intended question families correctly.",
                    "confidence": "high",
                    "rationale": "Needed for deterministic verification and PM review.",
                },
            ],
        },
        "accepted_item_ids": ["ve-1"],
        "rejected_item_ids": [],
        "notes": "Keep the explicit evidence-binding candidate.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-verification-expectation-candidates"
    assert data["data"]["artifact_type"] == "assistant_verification_expectation_candidates"
    assert data["data"]["source_capability"] == "propose_verification_expectations"
    assert data["data"]["accepted_item_ids"] == ["ve-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "ve-1"


def test_apply_assistant_backend_binding_proposal_persists_pm_artifact(client):
    client.post("/api/projects", json={"id": "proj-assist-backend", "name": "Assistant Backend"})
    resp = client.post("/api/projects/proj-assist-backend/assistant/proposals/apply", json={
        "artifact_id": "pm-assistant-backend-binding-candidates",
        "title": "Accepted Backend Binding Candidates",
        "capability": "propose_backend_bindings",
        "proposal": {
            "proposal_kind": "candidate_blocks",
            "artifact_type": "backend_bindings",
            "items": [
                {
                    "client_id": "bb-1",
                    "title": "Name the data target explicitly",
                    "body": "Define the governed data target label and the integration system name before generation.",
                    "confidence": "high",
                    "rationale": "Needed for deterministic backend wiring.",
                },
            ],
        },
        "accepted_item_ids": ["bb-1"],
        "rejected_item_ids": [],
        "notes": "Keep the explicit backend-target candidate.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == "pm-assistant-backend-binding-candidates"
    assert data["data"]["artifact_type"] == "assistant_backend_binding_candidates"
    assert data["data"]["source_capability"] == "propose_backend_bindings"
    assert data["data"]["accepted_item_ids"] == ["bb-1"]
    assert len(data["data"]["accepted_payload"]) == 1
    assert data["data"]["accepted_payload"][0]["client_id"] == "bb-1"


# ---------------------------------------------------------------------------
# Scenarios CRUD
# ---------------------------------------------------------------------------

def test_create_and_list_scenarios(client):
    _seed_project(client, "proj-scn-crud")
    resp = client.get("/api/projects/proj-scn-crud/scenarios")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == "scn-proj-scn-crud"


def test_update_scenario(client):
    _seed_project(client, "proj-scn-upd")
    resp = client.put("/api/projects/proj-scn-upd/scenarios/scn-proj-scn-upd", json={
        "title": "Updated Scenario",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Scenario"


# ---------------------------------------------------------------------------
# Service Metadata CRUD
# ---------------------------------------------------------------------------

def test_create_and_list_service_metadata(client):
    client.post("/api/projects", json={"id": "proj-svc-meta", "name": "Project proj-svc-meta"})
    create_resp = client.post("/api/projects/proj-svc-meta/service-metadata", json={
        "id": "service-metadata-svc-gtm",
        "title": "Observed Service Metadata: svc-gtm",
        "data": {
            "source": "inspect_discovery",
            "observed_at": "2026-04-11T12:00:00Z",
            "service_id": "svc-gtm",
            "protocol": "anip/0.2",
            "capabilities": [{"id": "gtm.account_risk_summary"}],
        },
    })
    assert create_resp.status_code == 201

    list_resp = client.get("/api/projects/proj-svc-meta/service-metadata")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == "service-metadata-svc-gtm"
    assert items[0]["data"]["service_id"] == "svc-gtm"


# ---------------------------------------------------------------------------
# Proposals with project coherence
# ---------------------------------------------------------------------------

def test_create_proposal_with_valid_requirements_id(client):
    _seed_project(client, "proj-prop-ok")
    resp = client.post("/api/projects/proj-prop-ok/proposals", json={
        "id": "prop-ok",
        "title": "Valid Proposal",
        "requirements_id": "req-proj-prop-ok",
        "data": {"proposal": {"name": "test"}},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["requirements_id"] == "req-proj-prop-ok"


def test_create_proposal_cross_project_ref_returns_422(client):
    """A proposal's requirements_id must belong to the same project."""
    _seed_project(client, "proj-a")
    _seed_project(client, "proj-b")
    # Try to create a proposal in proj-b referencing requirements from proj-a
    resp = client.post("/api/projects/proj-b/proposals", json={
        "id": "prop-cross",
        "title": "Cross-project proposal",
        "requirements_id": "req-proj-a",  # belongs to proj-a, not proj-b
        "data": {},
    })
    assert resp.status_code == 422


def test_delete_requirements_blocked_by_proposal_returns_409(client):
    """Cannot delete requirements when a proposal references them."""
    _seed_project(client, "proj-del-block")
    client.post("/api/projects/proj-del-block/proposals", json={
        "id": "prop-block",
        "title": "Blocking Proposal",
        "requirements_id": "req-proj-del-block",
        "data": {},
    })
    resp = client.delete("/api/projects/proj-del-block/requirements/req-proj-del-block")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "prop-block" in detail["refs"]


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def test_create_evaluation_with_all_refs(client):
    """Create an evaluation referencing proposal, scenario, and requirements."""
    _seed_project(client, "proj-eval")
    client.post("/api/projects/proj-eval/proposals", json={
        "id": "prop-eval",
        "title": "Proposal for eval",
        "requirements_id": "req-proj-eval",
        "data": {},
    })
    resp = client.post("/api/projects/proj-eval/evaluations", json={
        "id": "eval-1",
        "proposal_id": "prop-eval",
        "scenario_id": "scn-proj-eval",
        "requirements_id": "req-proj-eval",
        "source": "live_validation",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {"requirements": {}, "proposal": {}, "scenario": {}},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["proposal_id"] == "prop-eval"
    assert data["scenario_id"] == "scn-proj-eval"
    assert data["requirements_id"] == "req-proj-eval"


def test_create_evaluation_cross_project_ref_returns_422(client):
    """Evaluation refs must all belong to the same project."""
    _seed_project(client, "proj-eval-a")
    _seed_project(client, "proj-eval-b")
    client.post("/api/projects/proj-eval-a/proposals", json={
        "id": "prop-eval-a",
        "title": "Proposal A",
        "requirements_id": "req-proj-eval-a",
        "data": {},
    })
    # Try creating an evaluation in proj-eval-b referencing proposal from proj-eval-a
    resp = client.post("/api/projects/proj-eval-b/evaluations", json={
        "id": "eval-cross",
        "proposal_id": "prop-eval-a",
        "scenario_id": "scn-proj-eval-b",
        "requirements_id": "req-proj-eval-b",
        "source": "manual",
        "data": {"evaluation": {"result": "PARTIAL"}},
        "input_snapshot": {},
    })
    assert resp.status_code == 422


def test_delete_evaluation_succeeds_leaf_node(client):
    """Evaluations are leaf nodes and can always be deleted."""
    _seed_project(client, "proj-eval-del")
    client.post("/api/projects/proj-eval-del/proposals", json={
        "id": "prop-eval-del",
        "title": "Proposal",
        "requirements_id": "req-proj-eval-del",
        "data": {},
    })
    client.post("/api/projects/proj-eval-del/evaluations", json={
        "id": "eval-leaf",
        "proposal_id": "prop-eval-del",
        "scenario_id": "scn-proj-eval-del",
        "requirements_id": "req-proj-eval-del",
        "source": "manual",
        "data": {"evaluation": {"result": "REQUIRES_GLUE"}},
        "input_snapshot": {},
    })
    resp = client.delete("/api/projects/proj-eval-del/evaluations/eval-leaf")
    assert resp.status_code == 204

    # Verify gone
    resp = client.get("/api/projects/proj-eval-del/evaluations/eval-leaf")
    assert resp.status_code == 404


def test_delete_scenario_blocked_by_evaluation_returns_409(client):
    """Cannot delete a scenario when an evaluation references it."""
    _seed_project(client, "proj-scn-block")
    client.post("/api/projects/proj-scn-block/proposals", json={
        "id": "prop-scn-block",
        "title": "Proposal",
        "requirements_id": "req-proj-scn-block",
        "data": {},
    })
    client.post("/api/projects/proj-scn-block/evaluations", json={
        "id": "eval-scn-block",
        "proposal_id": "prop-scn-block",
        "scenario_id": "scn-proj-scn-block",
        "requirements_id": "req-proj-scn-block",
        "source": "manual",
        "data": {"evaluation": {"result": "HANDLED"}},
        "input_snapshot": {},
    })
    resp = client.delete("/api/projects/proj-scn-block/scenarios/scn-proj-scn-block")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "eval-scn-block" in detail["refs"]


def test_evaluation_has_input_snapshot_and_source(client):
    """Verify evaluation response includes input_snapshot and source fields."""
    _seed_project(client, "proj-eval-fields")
    client.post("/api/projects/proj-eval-fields/proposals", json={
        "id": "prop-eval-fields",
        "title": "Proposal",
        "requirements_id": "req-proj-eval-fields",
        "data": {},
    })
    snapshot = {"requirements": {"x": 1}, "proposal": {"y": 2}, "scenario": {"z": 3}}
    client.post("/api/projects/proj-eval-fields/evaluations", json={
        "id": "eval-fields",
        "proposal_id": "prop-eval-fields",
        "scenario_id": "scn-proj-eval-fields",
        "requirements_id": "req-proj-eval-fields",
        "source": "live_validation",
        "data": {"evaluation": {"result": "PARTIAL"}},
        "input_snapshot": snapshot,
    })
    resp = client.get("/api/projects/proj-eval-fields/evaluations/eval-fields")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "live_validation"
    assert data["input_snapshot"] == snapshot
