from __future__ import annotations

from studio.server.shared_artifacts import (
    build_business_brief,
    build_developer_spec,
    build_engineering_contract,
    build_pm_spec,
)


def _context() -> dict:
    return {
        "project": {"id": "proj-1", "name": "Deal Desk", "summary": "A governed approval flow."},
        "requirements": {
            "id": "req-1",
            "title": "Requirements",
            "data": {
                "requirements": {
                    "business_constraints": {
                        "approval_expected_for_high_risk": True,
                        "followup_execution_must_stop_for_approval": True,
                        "blocked_failure_posture": "human_review_for_unresolved_or_approval_gated_work",
                        "clarification_required_for_missing_quarter": True,
                        "phase_1_export_posture": "deny_raw_row_level_exports",
                    },
                    "behavior_translation": {
                        "representative_requests": [
                            "Which deals in our Q2 pipeline are at risk this quarter, and why?",
                            "Prepare follow-up tasks for the highest-risk accounts in my Q2 pipeline.",
                        ],
                        "behavior_families": [
                            {
                                "class": "ambiguity_requiring_clarification",
                                "studio_expectation": "clarification_required_without_guessing",
                            }
                        ],
                    },
                }
            },
        },
        "source_requirements": {
            "id": "req-source-1",
            "title": "Canonical GTM business spec",
            "data": {
                "source_document": {"path": "docs/examples/gtm-showcase/business-spec.md"},
                "business_spec": {
                    "summary": "Canonical PM-readable source document for the GTM showcase.",
                    "business_goal": [
                        "summarize bounded pipeline health",
                        "identify at-risk accounts with explicit evidence",
                    ],
                    "non_goals": [
                        "no unconstrained raw CRM access",
                        "no outreach drafting in phase 1",
                    ],
                },
            },
        },
        "scenario": {
            "id": "scn-1",
            "title": "Approval Scenario",
            "data": {
                "scenario": {
                    "narrative": "A risky approval flow.",
                    "context": {"capability": "deal.review"},
                    "expected_behavior": ["approval_required_before_mutation"],
                    "expected_anip_support": ["bounded_capability_contracts"],
                }
            },
        },
        "scenarios": [
            {
                "id": "scn-1",
                "title": "Approval Scenario",
                "data": {
                    "scenario": {
                        "narrative": "A risky approval flow.",
                        "context": {"capability": "deal.review"},
                        "expected_behavior": ["approval_required_before_mutation"],
                        "expected_anip_support": ["bounded_capability_contracts"],
                    }
                },
            },
            {
                "id": "scn-2",
                "title": "Clarification path",
                "data": {"scenario": {"narrative": "Clarify missing quarter.", "context": {}}},
            },
        ],
        "proposal": {
            "id": "prop-1",
            "title": "Technical proposal",
            "data": {
                "proposal": {
                    "cross_service_contract": {
                        "handoff": [
                            {
                                "target": {"service": "svc-b", "capability": "enrich.account"},
                                "required_for_task_completion": False,
                                "continuity": "same_task",
                                "completion_mode": "downstream_acceptance",
                                "carry_fields": ["account_id"],
                                "rationale": "Only bounded account identifiers may cross the handoff.",
                            }
                        ],
                        "followup": [],
                        "verification": [],
                    },
                    "developer_translation": {
                        "translation_goal": "Turn the PM behavior model into an explicit service contract.",
                        "translation_principles": ["keep the first release bounded"],
                        "service_contract_decisions": ["approval-gate write behavior"],
                        "service_behavior_coverage": ["missing scope yields clarification_required in the service contract"],
                        "orchestration_contract_coverage": ["only bounded identifiers may cross the service handoff"],
                        "runtime_glue_inventory": ["quarter formatting still normalizes in the runtime"],
                        "actor_policy_model": {
                            "identity_source": "delegation.root_principal claims",
                            "policy_axes": ["actor role", "authority scope", "visibility level"],
                            "visibility_rules": [
                                {
                                    "when": "an actor asks for data beyond their authorized scope",
                                    "outcome": "restricted",
                                    "rationale": "The service should expose the narrower safe scope explicitly.",
                                }
                            ],
                            "approval_rules": [
                                {
                                    "action": "prepare follow-up tasks",
                                    "requester_posture": "authorized operators receive approval_required with a durable request",
                                    "approver_requirement": "a separate approver role must approve the request",
                                    "notes": ["approval requests remain queryable after creation"],
                                }
                            ],
                            "approval_surface": {
                                "list_path": "/approvals",
                                "approve_path_template": "/approvals/{approvalRequestId}/approve",
                                "notes": ["Studio can review approval state through this linked surface."],
                            },
                            "audit_expectations": [
                                "actor identity must remain visible in audit review",
                                "approval transitions must remain queryable",
                            ],
                        },
                    }
                }
            },
        },
        "shape": {
            "id": "shape-1",
            "title": "Shape",
            "data": {
                "shape": {
                    "type": "single_service",
                    "services": [{"id": "svc-a", "name": "Deal Service", "capabilities": ["deal.review"]}],
                    "domain_concepts": [],
                    "implementation_contract": {
                        "implementation_language": "python",
                        "runtime_profile": "fastapi_anip_service",
                        "transport_profile": "http_rest_anip",
                        "implementation_root": "examples/showcase/demo",
                        "runtime_entrypoint": "examples/showcase/demo/app.py",
                        "generated_from": {
                            "studio_flow": "business -> developer -> generated scaffold",
                            "generated_artifacts": ["service.py"],
                            "showcase_runtime_files": ["app.py"],
                        },
                    },
                    "capability_contracts": [
                        {
                            "id": "deal.review",
                            "purpose": "Review the deal safely.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated write contract; the current runtime returns a preview until approval exists",
                            "minimum_scope": ["deal.review"],
                            "approval_required_when": ["mutation would occur"],
                        }
                    ],
                    "metadata_contract": {
                        "manifest_required": True,
                        "discovery_required": True,
                        "conformance_checks": ["capability is declared"],
                    },
                    "implementation_trace": {
                        "business_source_artifact_id": "req-source-1",
                        "requirements_artifact_id": "req-1",
                        "scenario_artifact_id": "scn-1",
                        "proposal_artifact_id": "prop-1",
                        "shape_artifact_id": "shape-1",
                        "generated_code_used_for_showcase": True,
                        "running_service_id": "svc-a",
                    },
                }
            },
        },
        "evaluation": {
            "id": "eval-1",
            "result": "HANDLED",
            "data": {
                "evaluation": {
                    "handled_by_anip": ["approval routing"],
                    "what_would_improve": ["None"],
                    "conformance_status": "partial",
                }
            },
            "input_snapshot": {
                "service_metadata": {
                    "source": "inspect_discovery_manifest",
                    "service_id": "svc-a",
                    "protocol": "anip/0.2",
                    "signature_present": True,
                    "jwks_uri_present": False,
                    "capabilities": [{"id": "deal.review"}],
                }
            },
        },
    }


def test_build_business_brief_includes_anip_conformance_snapshot():
    document = build_business_brief(_context())

    assert "## Validation Decision Summary" in document
    assert "### ANIP Conformance Snapshot" in document
    assert "Observed metadata source: inspect_discovery_manifest" in document
    assert "Manifest signature: present" in document
    assert "JWKS URI: missing" in document
    assert "Missing intended capabilities: none" in document


def test_build_engineering_contract_includes_anip_conformance_snapshot():
    document = build_engineering_contract(_context())

    assert "## Validation Readout" in document
    assert "## ANIP Conformance Snapshot" in document
    assert "Observed service: svc-a" in document
    assert "Protocol declared: anip/0.2" in document
    assert "Broader than intended: none" in document


def test_build_pm_spec_preserves_business_spec_structure_with_traceability():
    document = build_pm_spec(_context())

    assert "# PM Spec: Deal Desk" in document
    assert "## Purpose" in document
    assert "not an exhaustive inventory of every possible user utterance" in document
    assert "## Business Source" in document
    assert "## Business Goal" in document
    assert "## What The Agent Must Be Able To Do" in document
    assert "## What It Must Not Do" in document
    assert "## Behavior Classes" in document
    assert "## Representative Scenario Requests" in document
    assert "These requests are representative, not exhaustive." in document
    assert "## Business Safety Posture" in document
    assert "## Validation Intent" in document
    assert "## Studio Translation" in document
    assert "Source document: docs/examples/gtm-showcase/business-spec.md" in document
    assert "Scenario pack size: 2" in document
    assert "Ambiguity Requiring Clarification (Studio key: clarification_required_without_guessing)" in document
    assert "No downstream mutations without approval" in document
    assert "#### Business Behavior Expectations" in document
    assert "#### ANIP / Implementation Expectations" in document
    assert "Status: HANDLED" in document


def test_build_developer_spec_preserves_translation_and_runtime_traceability():
    document = build_developer_spec(_context())

    assert "# Developer Spec: Deal Desk" in document
    assert "## Technical Purpose" in document
    assert "## Translation Chain" in document
    assert "## Developer Enrichment" in document
    assert "Turn the PM behavior model into an explicit service contract." in document
    assert "## Behavior Placement" in document
    assert "### Service-Covered Behavior" in document
    assert "missing scope yields clarification_required in the service contract" in document
    assert "### Orchestration-Covered Behavior" in document
    assert "only bounded identifiers may cross the service handoff" in document
    assert "### Cross-Service Contract" in document
    assert "#### Handoff" in document
    assert "Target service: svc-b" in document
    assert "Carry fields:" in document
    assert "account_id" in document
    assert "### Remaining Runtime Glue" in document
    assert "quarter formatting still normalizes in the runtime" in document
    assert "## Actor, Authority, And Audit Policy" in document
    assert "### Actor Model" in document
    assert "Identity source: delegation.root_principal claims" in document
    assert "### Visibility And Restriction Rules" in document
    assert "Governed outcome: restricted" in document
    assert "### Approval Authority Rules" in document
    assert "Action: prepare follow-up tasks" in document
    assert "### Audit Review Expectations" in document
    assert "approval transitions must remain queryable" in document
    assert "### Linked Approval Review Surface" in document
    assert "List path: /approvals" in document
    assert "Approve path template: /approvals/{approvalRequestId}/approve" in document
    assert "## Service Implementation Contract" in document
    assert "Implementation language: python" in document
    assert "## Capability Contracts" in document
    assert "### deal.review" in document
    assert "Side effect contract: approval-gated write contract; the current runtime returns a preview until approval exists" in document
    assert "## Metadata And Conformance Requirements" in document
    assert "Requirement: Manifest Required" in document
    assert "## Generated Implementation Trace" in document
    assert "Generated code used for showcase: yes" in document
    assert "## Current Runtime Validation" in document
    assert "Status: HANDLED; runtime metadata captured with open conformance gaps." in document
    assert "Business constraint: Escalate to human review only for unresolved or approval-gated work" in document
