"""Tests for seed, export, and import operations."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def test_seed_creates_projects(client):
    """Seeding from example packs creates one project per pack."""
    resp = client.post("/api/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["created_projects"] > 0


def test_seed_is_idempotent(client):
    """Running seed again does not create duplicates."""
    resp1 = client.post("/api/seed")
    first = resp1.json()

    resp2 = client.post("/api/seed")
    second = resp2.json()
    assert second["created_projects"] == 0
    assert second["skipped"] == first["created_projects"] + first["skipped"]


def test_gtm_seed_includes_source_business_spec_artifact(client):
    client.post("/api/seed")

    requirements = client.get("/api/projects/gtm-pipeline-q2-review/requirements").json()
    assert any(item["id"] == "req-gtm-revenue-operations-business-spec" for item in requirements)

    translated = next(item for item in requirements if item["id"] == "req-gtm-pipeline-q2-review")
    source_refs = translated["data"].get("source_documents", [])
    assert any(ref.get("artifact_id") == "req-gtm-revenue-operations-business-spec" for ref in source_refs)

    translation = translated["data"].get("behavior_translation", {})
    assert translation.get("source_artifact_id") == "req-gtm-revenue-operations-business-spec"
    assert any(
        item.get("class") == "ambiguity_requiring_clarification"
        for item in translation.get("behavior_families", [])
    )
    umbrella_goals = next(
        item["data"]["business_spec"]["business_goal"]
        for item in requirements
        if item["id"] == "req-gtm-revenue-operations-business-spec"
    )
    assert "enrich account context and identify lookalikes" in umbrella_goals


def test_gtm_seed_loads_source_business_spec_documents(client):
    client.post("/api/seed")

    documents = client.get("/api/projects/gtm-pipeline-q2-review/documents").json()
    document_ids = {item["id"] for item in documents}

    assert "req-gtm-revenue-operations-business-spec" in document_ids
    assert "req-gtm-pipeline-forecast-business-spec" in document_ids
    assert "req-gtm-stage-bottleneck-business-spec" in document_ids
    assert "req-gtm-prepare-reassignment-business-spec" in document_ids
    assert "req-gtm-sales-team-performance-business-spec" in document_ids
    assert "req-gtm-product-pipeline-business-spec" in document_ids
    assert "req-gtm-pipeline-business-spec" in document_ids
    assert "req-gtm-pipeline-q2-review-enrichment-business-spec" in document_ids
    assert "req-gtm-pipeline-q2-review-prioritization-business-spec" in document_ids
    assert "req-gtm-pipeline-q2-review-outreach-business-spec" in document_ids
    assert len(document_ids) == 10
    canonical = next(item for item in documents if item["id"] == "req-gtm-revenue-operations-business-spec")
    assert canonical["source_path"] == "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md"
    assert canonical["media_type"] == "text/markdown"


def test_retired_typescript_generator_endpoint_returns_gone(client):
    client.post("/api/projects", json={
        "id": "proj-generator",
        "name": "Generator Target",
    })

    resp = client.post(
        "/api/projects/proj-generator/generator/typescript",
        json={
            "definition": {"system": {"name": "retired-generator-target"}},
            "package_name": "proj-generator",
            "dependency_source": "local",
        },
    )
    assert resp.status_code == 410, resp.text
    assert "retired" in resp.json()["detail"]
    assert "generator" in resp.json()["detail"]


def test_retired_local_runtime_proof_endpoint_returns_gone(client):
    client.post("/api/seed")
    project_id = "project-issue-tracker-fronting-showcase"
    generation_run_artifact_id = "proof-generation-run"
    create_resp = client.post(
        f"/api/projects/{project_id}/pm-artifacts",
        json={
            "id": generation_run_artifact_id,
            "title": "Developer Generation Run",
            "data": {
                "artifact_type": "developer_generation_run",
                "source_inputs": {
                    "requirements_id": "req-issue-tracker-fronting",
                    "scenario_ids": ["scenario-issue-tracker-transition-request"],
                },
                "compiled_contract_identity": {
                    "signature": "proof-signature",
                    "signature_algorithm": "sha256",
                    "artifact_name": "proof-definition.json",
                },
                "generator_inputs": {
                    "dependency_source": "local",
                },
            },
        },
    )
    assert create_resp.status_code == 201, create_resp.text

    resp = client.post(
        f"/api/projects/{project_id}/proofs/local-runtime",
        json={"generation_run_artifact_id": generation_run_artifact_id},
    )
    assert resp.status_code == 410, resp.text
    assert "retired" in resp.json()["detail"]
    assert "verifier" in resp.json()["detail"]


def test_gtm_seed_includes_behavior_class_scenario_pack(client):
    client.post("/api/seed")

    scenarios = client.get("/api/projects/gtm-pipeline-q2-review/scenarios").json()
    scenario_ids = {item["id"] for item in scenarios}
    assert {
        "scn-gtm-pipeline-q2-review",
        "scn-gtm-pipeline-clarification",
        "scn-gtm-pipeline-stalled-opportunities",
        "scn-gtm-pipeline-raw-export-denial",
        "scn-gtm-pipeline-out-of-scope",
    }.issubset(scenario_ids)

    clarification = next(item for item in scenarios if item["id"] == "scn-gtm-pipeline-clarification")
    assert "clarification_required_for_missing_quarter" in clarification["data"]["scenario"]["expected_behavior"]

    denial = next(item for item in scenarios if item["id"] == "scn-gtm-pipeline-raw-export-denial")
    assert "denied_for_raw_row_level_export" in denial["data"]["scenario"]["expected_behavior"]


def test_gtm_seed_includes_developer_translation_and_contract_trace(client):
    client.post("/api/seed")

    proposals = client.get("/api/projects/gtm-pipeline-q2-review/proposals").json()
    proposal = next(item for item in proposals if item["id"] == "prop-gtm-pipeline-q2-review")
    developer_translation = proposal["data"]["proposal"].get("developer_translation", {})
    assert developer_translation.get("source_artifact_id") == "req-gtm-pipeline-q2-review"
    assert "GTM Pipeline Service owns bounded pipeline analytics, risk, and preparation capabilities" in developer_translation.get(
        "service_contract_decisions", []
    )
    assert "GTM Enrichment Service owns bounded account enrichment and lookalike capabilities" in developer_translation.get(
        "service_contract_decisions", []
    )
    assert "GTM Prioritization Service owns explainable scoring, prioritization, and routing recommendation capabilities" in developer_translation.get(
        "service_contract_decisions", []
    )
    assert "GTM Outreach Service owns bounded draft-only outreach support capabilities" in developer_translation.get(
        "service_contract_decisions", []
    )
    assert "raw CRM, enrichment, scoring-feature, and outreach-source exports are denied rather than narrowed silently" in developer_translation.get(
        "service_contract_decisions", []
    )

    shapes = client.get("/api/projects/gtm-pipeline-q2-review/shapes").json()
    shape = next(item for item in shapes if item["id"] == "shape-gtm-pipeline-q2-review")
    shape_data = shape["data"]["shape"]
    assert shape_data["type"] == "multi_service_estate"
    assert shape_data["implementation_contract"]["implementation_language"] == "python"
    assert shape_data["implementation_contract"]["runtime_profile"] == "mixed_anip_service_estate"
    assert shape_data["implementation_trace"]["generated_code_used_for_showcase"] is True
    assert (
        shape_data["implementation_contract"]["runtime_entrypoint"]
        == "examples/showcase/gtm/docker-compose.yml"
    )
    assert [item["id"] for item in shape_data["services"]] == [
        "gtm-pipeline-service",
        "gtm-enrichment-service",
        "gtm-prioritization-service",
        "gtm-outreach-service",
    ]
    capability_ids = [item["id"] for item in shape_data.get("capability_contracts", [])]
    assert capability_ids == [
        "gtm.pipeline_summary",
        "gtm.pipeline_forecast_summary",
        "gtm.stage_bottleneck_summary",
        "gtm.sales_team_performance_summary",
        "gtm.product_pipeline_summary",
        "gtm.stalled_opportunity_review",
        "gtm.account_risk_summary",
        "gtm.prepare_followup_tasks",
        "gtm.prepare_reassignment_plan",
        "gtm.at_risk_followup_preparation",
        "gtm.at_risk_reassignment_preparation",
        "gtm.account_enrichment_summary",
        "gtm.lookalike_accounts",
        "gtm.at_risk_account_enrichment_summary",
        "gtm.score_leads",
        "gtm.prioritize_accounts",
        "gtm.route_leads",
        "gtm.prioritized_routing_preparation",
        "gtm.draft_outreach_message",
        "gtm.suggest_followup_content",
        "gtm.objection_response_variants",
        "gtm.prioritized_outreach_draft",
        "gtm.bottleneck_account_outreach_draft",
    ]
    followup_contract = next(item for item in shape_data["capability_contracts"] if item["id"] == "gtm.prepare_followup_tasks")
    assert "approval-gated write contract" in followup_contract["side_effect_detail"]


def test_gtm_enrichment_seed_includes_actor_policy_and_cross_service_trace(client):
    client.post("/api/seed")

    proposals = client.get("/api/projects/gtm-account-enrichment/proposals").json()
    proposal = next(item for item in proposals if item["id"] == "prop-gtm-account-enrichment")
    developer_translation = proposal["data"]["proposal"].get("developer_translation", {})
    actor_policy_model = developer_translation.get("actor_policy_model", {})

    assert developer_translation.get("source_artifact_id") == "req-gtm-account-enrichment"
    assert "only bounded account identifiers may cross the pipeline-to-enrichment handoff" in developer_translation.get(
        "orchestration_contract_coverage", []
    )
    assert "mechanical account-name normalization still happens in the runtime before enrichment invocation" in developer_translation.get(
        "runtime_glue_inventory", []
    )
    assert actor_policy_model.get("identity_source") == "delegation.root_principal claims carried through ANIP token issuance"
    assert any(
        item.get("outcome") == "success with bounded enrichment fields only"
        for item in actor_policy_model.get("visibility_rules", [])
    )
    assert actor_policy_model.get("approval_rules") == []
    assert "cross-service handoff into enrichment should preserve actor and task continuity" in actor_policy_model.get(
        "audit_expectations", []
    )

    shapes = client.get("/api/projects/gtm-account-enrichment/shapes").json()
    shape = next(item for item in shapes if item["id"] == "shape-gtm-account-enrichment")
    shape_data = shape["data"]["shape"]

    assert shape_data["implementation_contract"]["implementation_language"] == "python"
    assert shape_data["implementation_trace"]["generated_code_used_for_showcase"] is True
    capability_ids = [item["id"] for item in shape_data.get("capability_contracts", [])]
    assert capability_ids == [
        "gtm.account_enrichment_summary",
        "gtm.lookalike_accounts",
    ]


def test_export_returns_full_project_graph(client):
    """Export returns the project plus all artifact collections."""
    # Seed first to have data
    client.post("/api/seed")

    # List projects and pick a legacy seed with the complete proposal/evaluation graph.
    # Governed fronting seeds intentionally do not need legacy proposal artifacts.
    projects = client.get("/api/projects").json()
    assert len(projects) > 0
    pid = None
    data = None
    for project in projects:
        candidate = client.get(f"/api/projects/{project['id']}/export")
        assert candidate.status_code == 200
        candidate_data = candidate.json()
        if candidate_data["proposals"] and candidate_data["evaluations"]:
            pid = project["id"]
            data = candidate_data
            break
    assert pid is not None
    assert data is not None

    # Should have the project and all artifact arrays
    assert "project" in data
    assert data["project"]["id"] == pid
    assert "requirements" in data
    assert "scenarios" in data
    assert "proposals" in data
    assert "evaluations" in data
    # Seeded projects should have at least one of each
    assert len(data["requirements"]) >= 1
    assert len(data["scenarios"]) >= 1
    assert len(data["proposals"]) >= 1
    assert len(data["evaluations"]) >= 1


def test_export_includes_content_hash_on_artifacts(client):
    """Export includes content_hash on every artifact record."""
    client.post("/api/seed")
    projects = client.get("/api/projects").json()
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    for req in data["requirements"]:
        assert "content_hash" in req, "requirements should have content_hash"
        assert len(req["content_hash"]) == 64, "content_hash should be SHA-256 hex"

    for scn in data["scenarios"]:
        assert "content_hash" in scn, "scenarios should have content_hash"
        assert len(scn["content_hash"]) == 64

    for prop in data["proposals"]:
        assert "content_hash" in prop, "proposals should have content_hash"
        assert len(prop["content_hash"]) == 64


def test_export_includes_per_artifact_hashes_on_evaluations(client):
    """Export includes per-artifact hashes on evaluations (no is_stale)."""
    client.post("/api/seed")
    projects = client.get("/api/projects").json()
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    for ev in data["evaluations"]:
        assert "requirements_hash" in ev, "evaluation should have requirements_hash"
        assert "proposal_hash" in ev, "evaluation should have proposal_hash"
        assert "scenario_hash" in ev, "evaluation should have scenario_hash"
        # is_stale must NOT be present — it's environment-relative
        assert "is_stale" not in ev, "export must NOT include is_stale"
        assert "stale_artifacts" not in ev, "export must NOT include stale_artifacts"


def test_export_includes_metadata(client):
    """Export includes a metadata section with export timestamp."""
    client.post("/api/seed")
    projects = client.get("/api/projects").json()
    pid = projects[0]["id"]

    resp = client.get(f"/api/projects/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    assert "metadata" in data
    assert "exported_at" in data["metadata"]
    # Should be a valid ISO timestamp string
    from datetime import datetime
    ts = data["metadata"]["exported_at"]
    datetime.fromisoformat(ts)  # raises ValueError if invalid


def test_import_artifacts_into_project(client):
    """Import requirements and scenarios into an existing project."""
    client.post("/api/projects", json={
        "id": "proj-import",
        "name": "Import Target",
    })
    resp = client.post("/api/projects/proj-import/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "imp-req-1",
                    "title": "Imported Reqs",
                    "data": {
                        "system": {
                            "name": "imported",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                        "transports": {"http": True},
                        "trust": {"mode": "unsigned", "checkpoints": False},
                        "auth": {},
                        "permissions": {},
                        "audit": {},
                        "lineage": {},
                        "scale": {
                            "shape_preference": "production_single_service",
                            "high_availability": False
                        },
                    },
                },
            },
            {
                "type": "scenario",
                "data": {
                    "id": "imp-scn-1",
                    "title": "Imported Scenario",
                    "data": {
                        "scenario": {
                            "name": "test_scenario",
                            "category": "safety",
                            "narrative": "A test scenario",
                            "context": {"key": "value"},
                            "expected_behavior": ["behave correctly"],
                            "expected_anip_support": ["trust"],
                        }
                    },
                },
            },
            {
                "type": "proposal",
                "data": {
                    "id": "imp-prop-1",
                    "title": "Imported Proposal",
                    "requirements_id": "imp-req-1",
                    "data": {
                        "proposal": {
                            "recommended_shape": "production_single_service",
                            "rationale": ["test rationale"],
                            "required_components": ["component-a"],
                        }
                    },
                },
            },
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 3
    assert data["errors"] == []

    # Verify the imported artifacts exist
    reqs = client.get("/api/projects/proj-import/requirements").json()
    assert any(r["id"] == "imp-req-1" for r in reqs)
    scenarios = client.get("/api/projects/proj-import/scenarios").json()
    assert any(s["id"] == "imp-scn-1" for s in scenarios)
    proposals = client.get("/api/projects/proj-import/proposals").json()
    assert any(p["id"] == "imp-prop-1" for p in proposals)


def test_import_duplicate_id_rejected(client):
    """Importing an artifact with a duplicate ID is rejected with a clear error."""
    client.post("/api/projects", json={
        "id": "proj-dup-test",
        "name": "Duplicate Test Project",
    })

    # First import — creates the requirements set
    resp1 = client.post("/api/projects/proj-dup-test/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "dup-req-1",
                    "title": "Original Reqs",
                    "data": {
                        "system": {
                            "name": "original",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                        "transports": {},
                        "trust": {"mode": "unsigned", "checkpoints": False},
                        "auth": {},
                        "permissions": {},
                        "audit": {},
                        "lineage": {},
                        "scale": {
                            "shape_preference": "production_single_service",
                            "high_availability": False
                        },
                    },
                },
            },
        ],
    })
    assert resp1.status_code == 200
    assert resp1.json()["imported"] == 1

    # Second import — tries to use the same ID
    resp2 = client.post("/api/projects/proj-dup-test/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "dup-req-1",
                    "title": "Duplicate Reqs",
                    "data": {
                        "system": {
                            "name": "duplicate",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                        "transports": {},
                        "trust": {"mode": "unsigned", "checkpoints": False},
                        "auth": {},
                        "permissions": {},
                        "audit": {},
                        "lineage": {},
                        "scale": {
                            "shape_preference": "production_single_service",
                            "high_availability": False
                        },
                    },
                },
            },
        ],
    })
    assert resp2.status_code == 200
    result = resp2.json()
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "duplicate" in result["errors"][0].lower() or "dup-req-1" in result["errors"][0]


def test_import_proposal_with_missing_requirements_id_rejected(client):
    """Importing a proposal whose requirements_id does not exist is rejected."""
    client.post("/api/projects", json={
        "id": "proj-missing-req",
        "name": "Missing Req Test",
    })

    resp = client.post("/api/projects/proj-missing-req/import", json={
        "artifacts": [
            {
                "type": "proposal",
                "data": {
                    "id": "prop-orphan",
                    "title": "Orphan Proposal",
                    "requirements_id": "nonexistent-req-id",
                    "data": {
                        "proposal": {
                            "recommended_shape": "production_single_service",
                            "rationale": ["orphan"],
                            "required_components": ["x"],
                        }
                    },
                },
            },
        ],
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "nonexistent-req-id" in result["errors"][0] or "requirements_id" in result["errors"][0]


def test_import_schema_validation_rejects_invalid_artifact(client):
    """Schema validation rejects artifacts that do not conform to their schema."""
    client.post("/api/projects", json={
        "id": "proj-schema-val",
        "name": "Schema Validation Test",
    })

    # Missing required top-level fields in requirements data
    resp = client.post("/api/projects/proj-schema-val/import", json={
        "artifacts": [
            {
                "type": "requirements",
                "data": {
                    "id": "bad-req-1",
                    "title": "Bad Requirements",
                    "data": {
                        # Missing required fields: transports, trust, auth, etc.
                        "system": {
                            "name": "minimal",
                            "domain": "test",
                            "deployment_intent": "test"
                        },
                    },
                },
            },
        ],
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "schema validation failed" in result["errors"][0]
