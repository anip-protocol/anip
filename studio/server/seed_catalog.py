"""Curated Studio seed projects for local demos and realistic artifact output."""

from __future__ import annotations

SEED_PROJECTS = [
    {
        "project": {
            "id": "enterprise-deal-desk",
            "name": "Enterprise Deal Desk",
            "domain": "revenue_operations",
            "summary": (
                "PM brief: Sales needs a shared deal-desk workflow for non-standard enterprise renewals. "
                "Account executives should be able to submit a request that explains the customer context, "
                "discount ask, payment-term exception, and legal redlines in plain business language. Finance "
                "must approve or reject commercial risk, legal must only be pulled in when custom paper is "
                "actually involved, and the account team needs a clean timeline they can use to update the "
                "customer without reconstructing status from Slack threads, forwarded email, and spreadsheets."
            ),
        },
        "requirements": {
            "id": "req-enterprise-deal-desk",
            "title": "Enterprise deal desk requirements",
            "data": {
                "system": {
                    "name": "enterprise-deal-desk",
                    "domain": "revenue_operations",
                    "deployment_intent": "multi_service_agent_execution",
                },
                "transports": {"http": True, "stdio": False, "grpc": False},
                "trust": {"mode": "signed", "checkpoints": True},
                "auth": {
                    "delegation_tokens": True,
                    "purpose_binding": True,
                    "scoped_authority": True,
                    "service_to_service_handoffs": True,
                },
                "permissions": {
                    "preflight_discovery": True,
                    "restricted_vs_denied": True,
                    "grantable_requirements": True,
                },
                "audit": {
                    "durable": True,
                    "searchable": True,
                    "cross_service_reconstruction_required": True,
                },
                "lineage": {
                    "invocation_id": True,
                    "client_reference_id": True,
                    "task_id": True,
                    "parent_invocation_id": True,
                    "cross_service_continuity_required": True,
                },
                "business_constraints": {
                    "finance_signoff_for_margin_exceptions": True,
                    "legal_review_only_when_custom_paper_is_present": True,
                    "customer_timeline_must_be_shareable_without_internal_jargon": True,
                    "approval_state_must_be_reconstructable_during_quarter_close": True,
                },
                "scale": {
                    "shape_preference": "multi_service_estate",
                    "high_availability": True,
                },
            },
        },
        "scenario": {
            "id": "scn-enterprise-deal-desk",
            "title": "Regional rep submits a risky renewal for approval",
            "data": {
                "scenario": {
                    "name": "renewal_discount_and_terms_exception",
                    "category": "approval",
                    "narrative": (
                        "A regional account executive needs approval for a late-quarter renewal that combines a "
                        "22 percent discount, net-60 payment terms, and customer redlines on the paper. Finance "
                        "should evaluate commercial risk, legal should only join if the redlines are real, and the "
                        "account team should see one coherent status trail instead of stitching together comments "
                        "from multiple tools."
                    ),
                    "context": {
                        "request_type": "renewal_exception",
                        "discount_percentage": 22,
                        "payment_terms": "net_60",
                        "custom_paper_requested": True,
                        "quarter_close_pressure": "high",
                    },
                    "expected_behavior": [
                        "deal_request_is_intakeable_in_plain_language",
                        "finance_and_legal_decisions_are_separated_but_linked",
                        "account_team_can_read_a_customer_safe_status_timeline",
                        "operators_can_reconstruct_approval_chain_without_chat_logs",
                    ],
                    "expected_anip_support": [
                        "task_id_support",
                        "cross_service_contract",
                        "recovery_target",
                        "audit_queryability",
                        "capability_targeted_delegation",
                    ],
                }
            },
        },
        "proposal": {
            "id": "prop-enterprise-deal-desk",
            "title": "Deal desk multi-service proposal",
            "data": {
                "proposal": {
                    "recommended_shape": "multi_service_estate",
                    "rationale": [
                        "request intake, approval policy, and outward status updates have different change rates",
                        "finance and legal decisions should be independently auditable",
                        "customer-safe communication should not be hidden in the approval service itself",
                    ],
                    "service_shapes": {
                        "request-intake-service": {"shape": "production_single_service"},
                        "approval-policy-service": {"shape": "production_single_service"},
                        "timeline-service": {"shape": "production_single_service"},
                    },
                    "required_components": [
                        "manifest_generator_per_service",
                        "permission_evaluator_per_service",
                        "durable_audit_store_per_service",
                        "lineage_recorder_per_service",
                        "cross_service_contract_surfaces",
                        "recovery_target_surfaces",
                    ],
                    "declared_surfaces": {
                        "budget_enforcement": False,
                        "binding_requirements": True,
                        "authority_posture": True,
                        "recovery_class": True,
                        "cross_service_handoff": True,
                        "cross_service_continuity": True,
                    },
                    "expected_glue_reduction": {
                        "orchestration": [
                            "approval_chain_guesswork",
                            "manual_status_translation_between_internal_and_customer_views",
                        ],
                        "observability": [
                            "quarter_close reconstruction from side channels",
                        ],
                    },
                }
            },
        },
        "shape": {
            "id": "shape-enterprise-deal-desk",
            "title": "Deal desk service design",
            "data": {
                "shape": {
                    "id": "enterprise-deal-desk-shape",
                    "name": "Enterprise Deal Desk",
                    "type": "multi_service",
                    "notes": [
                        "Keep commercial review, legal review routing, and timeline publication explicit.",
                        "Do not hide customer-safe messaging rules inside finance-only approval logic.",
                    ],
                    "services": [
                        {
                            "id": "request-intake-service",
                            "name": "Request Intake Service",
                            "role": "captures and normalizes deal desk requests from account teams",
                            "responsibilities": [
                                "Accept a plain-language deal request with customer context and proposed exceptions.",
                                "Normalize inputs into a reviewable request packet without losing the original narrative.",
                            ],
                            "capabilities": [
                                "submit_deal_request",
                                "update_request_context",
                                "summarize_request_for_review",
                            ],
                            "owns_concepts": ["deal-request", "customer-brief"],
                        },
                        {
                            "id": "approval-policy-service",
                            "name": "Approval Policy Service",
                            "role": "applies finance and legal approval policy",
                            "responsibilities": [
                                "Route a request to finance approval based on commercial risk.",
                                "Escalate to legal only when custom paper or material redlines are present.",
                            ],
                            "capabilities": [
                                "request_finance_approval",
                                "record_approval_decision",
                                "request_legal_review",
                            ],
                            "owns_concepts": ["approval-decision", "risk-policy"],
                        },
                        {
                            "id": "timeline-service",
                            "name": "Timeline Service",
                            "role": "publishes internal and customer-safe deal status",
                            "responsibilities": [
                                "Maintain a readable internal timeline of request state changes.",
                                "Generate account-team safe status updates that hide internal-only rationale.",
                            ],
                            "capabilities": [
                                "publish_internal_status",
                                "publish_customer_safe_update",
                            ],
                            "owns_concepts": ["status-timeline"],
                        },
                    ],
                    "coordination": [
                        {
                            "from": "request-intake-service",
                            "to": "approval-policy-service",
                            "relationship": "handoff",
                            "description": "A normalized request packet is handed off for commercial and legal review.",
                        },
                        {
                            "from": "approval-policy-service",
                            "to": "timeline-service",
                            "relationship": "followup",
                            "description": "Approval outcomes are translated into internal and customer-safe timeline updates.",
                        },
                    ],
                    "domain_concepts": [
                        {
                            "id": "deal-request",
                            "name": "Deal Request",
                            "meaning": "The account team's original request including customer context and requested exceptions.",
                            "owner": "request-intake-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "customer-brief",
                            "name": "Customer Brief",
                            "meaning": "The commercial context that explains why the exception is being requested.",
                            "owner": "request-intake-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "approval-decision",
                            "name": "Approval Decision",
                            "meaning": "The authoritative finance or legal decision and supporting rationale.",
                            "owner": "approval-policy-service",
                            "sensitivity": "high",
                        },
                        {
                            "id": "risk-policy",
                            "name": "Risk Policy",
                            "meaning": "The policy thresholds that determine whether finance or legal must be involved.",
                            "owner": "approval-policy-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "status-timeline",
                            "name": "Status Timeline",
                            "meaning": "A customer-safe and operator-readable timeline of how the request progressed.",
                            "owner": "timeline-service",
                            "sensitivity": "low",
                        },
                    ],
                }
            },
        },
        "evaluation": {
            "id": "eval-enterprise-deal-desk",
            "source": "imported",
            "data": {
                "evaluation": {
                    "scenario_name": "renewal_discount_and_terms_exception",
                    "result": "HANDLED",
                    "handled_by_anip": [
                        "capability-targeted token issuance",
                        "restricted versus denied permission handling",
                        "cross-service continuation semantics",
                        "customer-safe follow-up routing",
                        "searchable cross-service audit",
                    ],
                    "glue_you_will_still_write": [
                        "customer-facing copy quality and account-team coaching rules still live in product logic",
                    ],
                    "glue_category": ["presentation"],
                    "why": [
                        "The protocol carries enough permission, continuation, and audit meaning that the approval chain is no longer reconstructed ad hoc in the client.",
                        "The service design separates finance/legal reasoning from outward customer status while keeping the lineage connected.",
                    ],
                    "what_would_improve": [
                        "Add policy simulation examples so revenue operations can preview why a request will escalate before submission.",
                    ],
                    "confidence": "high",
                }
            },
        },
    },
    {
        "project": {
            "id": "returns-resolution-console",
            "name": "Returns Resolution Console",
            "domain": "commerce_operations",
            "summary": (
                "PM brief: Support and operations need a single workflow for messy return and refund cases. Agents should be able "
                "to open a return case, understand whether warehouse evidence or carrier evidence is missing, request the right "
                "follow-up without switching tools, and only authorize a refund when payout reversal, fraud risk, and customer "
                "communication are all in a coherent state. Finance and support leadership need a durable trail because today's "
                "cases are spread across order history, WMS notes, payout tooling, and macros."
            ),
        },
        "requirements": {
            "id": "req-returns-resolution-console",
            "title": "Returns resolution requirements",
            "data": {
                "system": {
                    "name": "returns-resolution-console",
                    "domain": "commerce_operations",
                    "deployment_intent": "multi_service_agent_execution",
                },
                "transports": {"http": True, "stdio": False, "grpc": False},
                "trust": {"mode": "signed", "checkpoints": True},
                "auth": {
                    "delegation_tokens": True,
                    "purpose_binding": True,
                    "scoped_authority": True,
                    "service_to_service_handoffs": True,
                },
                "permissions": {
                    "preflight_discovery": True,
                    "restricted_vs_denied": True,
                    "grantable_requirements": True,
                },
                "audit": {
                    "durable": True,
                    "searchable": True,
                    "cross_service_reconstruction_required": True,
                },
                "lineage": {
                    "invocation_id": True,
                    "client_reference_id": True,
                    "task_id": True,
                    "parent_invocation_id": True,
                    "cross_service_continuity_required": True,
                },
                "business_constraints": {
                    "high_value_refunds_require_evidence_before_release": True,
                    "payout_reversal_state_must_be_visible_before_agent_resolution": True,
                    "customer_updates_must_stay_consistent_with_actual_case_state": True,
                    "ops_review_should_not_depend_on_copy_pasted_warehouse_notes": True,
                },
                "scale": {
                    "shape_preference": "multi_service_estate",
                    "high_availability": True,
                },
            },
        },
        "scenario": {
            "id": "scn-returns-resolution-console",
            "title": "High-value damaged return with missing warehouse evidence",
            "data": {
                "scenario": {
                    "name": "damaged_return_with_evidence_gap",
                    "category": "operations",
                    "narrative": (
                        "A support agent is handling a high-value return for a damaged order. The customer has uploaded photos, "
                        "but the warehouse inspection has not landed yet and the payout team needs to know whether the refund can "
                        "still be netted against the merchant settlement. The system should make the missing evidence explicit, "
                        "route the right follow-up, and keep the customer status aligned with the actual operational state."
                    ),
                    "context": {
                        "refund_value_band": "high",
                        "evidence_gap": "warehouse_inspection_missing",
                        "merchant_settlement_window": "open",
                        "customer_already_contacted": True,
                    },
                    "expected_behavior": [
                        "agent_can_open_one_case_view_instead_of_hunting_for_notes",
                        "missing_evidence_is_explicit_and_actionable",
                        "refund_release_waits_for_the_right_combination_of_signals",
                        "customer_update_matches_actual_case_state",
                    ],
                    "expected_anip_support": [
                        "permission_preflight",
                        "recovery_target",
                        "audit_queryability",
                        "capability_graph",
                        "checkpoints_and_proofs",
                    ],
                }
            },
        },
        "proposal": {
            "id": "prop-returns-resolution-console",
            "title": "Returns operations multi-service proposal",
            "data": {
                "proposal": {
                    "recommended_shape": "multi_service_estate",
                    "rationale": [
                        "case orchestration, evidence verification, and payout release each change at different rates",
                        "support-facing coordination should not directly own payout safety rules",
                        "warehouse and payout follow-up must remain auditable after the case is closed",
                    ],
                    "service_shapes": {
                        "case-orchestration-service": {"shape": "production_single_service"},
                        "evidence-service": {"shape": "production_single_service"},
                        "refund-release-service": {"shape": "production_single_service"},
                    },
                    "required_components": [
                        "manifest_generator_per_service",
                        "permission_evaluator_per_service",
                        "durable_audit_store_per_service",
                        "lineage_recorder_per_service",
                        "recovery_target_surfaces",
                        "capability_graph_surfaces",
                    ],
                    "declared_surfaces": {
                        "budget_enforcement": False,
                        "binding_requirements": True,
                        "authority_posture": True,
                        "recovery_class": True,
                        "cross_service_handoff": True,
                        "cross_service_continuity": True,
                    },
                    "expected_glue_reduction": {
                        "orchestration": [
                            "warehouse_followup_guesswork",
                            "refund_release sequencing logic in the frontend",
                        ],
                        "observability": [
                            "post-hoc case reconstruction across support and payouts",
                        ],
                    },
                }
            },
        },
        "shape": {
            "id": "shape-returns-resolution-console",
            "title": "Returns resolution service design",
            "data": {
                "shape": {
                    "id": "returns-resolution-console-shape",
                    "name": "Returns Resolution Console",
                    "type": "multi_service",
                    "notes": [
                        "Keep evidence verification, refund authorization, and customer-facing case orchestration separate but linked.",
                    ],
                    "services": [
                        {
                            "id": "case-orchestration-service",
                            "name": "Case Orchestration Service",
                            "role": "coordinates the support-facing return case",
                            "responsibilities": [
                                "Provide one case view for support agents.",
                                "Track which downstream evidence or refund steps are still outstanding.",
                            ],
                            "capabilities": [
                                "open_return_case",
                                "request_missing_evidence",
                                "publish_case_status",
                            ],
                            "owns_concepts": ["return-case", "customer-update"],
                        },
                        {
                            "id": "evidence-service",
                            "name": "Evidence Service",
                            "role": "collects and validates warehouse and carrier evidence",
                            "responsibilities": [
                                "Ingest customer evidence and warehouse inspection results.",
                                "Decide whether the case has enough evidence to proceed to refund release.",
                            ],
                            "capabilities": [
                                "collect_customer_evidence",
                                "record_warehouse_inspection",
                                "evaluate_evidence_completeness",
                            ],
                            "owns_concepts": ["evidence-bundle"],
                        },
                        {
                            "id": "refund-release-service",
                            "name": "Refund Release Service",
                            "role": "authorizes and records refund release decisions",
                            "responsibilities": [
                                "Check payout reversal state before refund release.",
                                "Record the final refund authorization decision and merchant impact.",
                            ],
                            "capabilities": [
                                "check_payout_reversal_state",
                                "authorize_refund_release",
                            ],
                            "owns_concepts": ["refund-decision", "payout-state"],
                        },
                    ],
                    "coordination": [
                        {
                            "from": "case-orchestration-service",
                            "to": "evidence-service",
                            "relationship": "verification",
                            "description": "Case orchestration requests evidence completion checks before refund release.",
                        },
                        {
                            "from": "evidence-service",
                            "to": "refund-release-service",
                            "relationship": "handoff",
                            "description": "Only evidence-complete cases move to refund authorization.",
                        },
                    ],
                    "domain_concepts": [
                        {
                            "id": "return-case",
                            "name": "Return Case",
                            "meaning": "The support-visible case that coordinates the return resolution workflow.",
                            "owner": "case-orchestration-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "customer-update",
                            "name": "Customer Update",
                            "meaning": "The status message the customer should see about the return case.",
                            "owner": "case-orchestration-service",
                            "sensitivity": "low",
                        },
                        {
                            "id": "evidence-bundle",
                            "name": "Evidence Bundle",
                            "meaning": "The combined customer, carrier, and warehouse evidence needed to resolve the case.",
                            "owner": "evidence-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "refund-decision",
                            "name": "Refund Decision",
                            "meaning": "The final authorization to release or hold a refund.",
                            "owner": "refund-release-service",
                            "sensitivity": "high",
                        },
                        {
                            "id": "payout-state",
                            "name": "Payout State",
                            "meaning": "Whether merchant settlement can still be reversed before refund release.",
                            "owner": "refund-release-service",
                            "sensitivity": "high",
                        },
                    ],
                }
            },
        },
        "evaluation": {
            "id": "eval-returns-resolution-console",
            "source": "imported",
            "data": {
                "evaluation": {
                    "scenario_name": "damaged_return_with_evidence_gap",
                    "result": "HANDLED",
                    "handled_by_anip": [
                        "permission preflight",
                        "recovery target handling",
                        "capability graph guidance",
                        "durable audit and checkpoint-backed verification",
                        "purpose-bound delegation for refund-sensitive actions",
                    ],
                    "glue_you_will_still_write": [
                        "support tone and policy copy still belong in the product layer",
                    ],
                    "glue_category": ["presentation"],
                    "why": [
                        "The protocol surfaces are strong enough that the agent does not have to invent missing sequencing rules for evidence completion and refund release.",
                        "Checkpointed audit plus graph relationships make the case legible after the fact instead of forcing operators to infer the workflow from tooling sprawl.",
                    ],
                    "what_would_improve": [
                        "Add policy simulation for merchant-specific refund windows before an agent opens the case.",
                    ],
                    "confidence": "high",
                }
            },
        },
    },
]
