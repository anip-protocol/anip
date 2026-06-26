import json
from pathlib import Path

from anip_runtime_utils.agent_consumption import (
    build_agent_capability_catalog,
    build_clarification_continuation,
    build_clarification_continuation_prompt,
    build_compact_agent_capability_brief,
    canonical_from_candidates,
    clarification_continuation_from_history,
    capability_match_score,
    compact_capability_match_score,
    contains_deictic_reference,
    conversation_text_from_history,
    conversation_supports_canonical_value,
    effective_business_effects,
    has_conditional_approval_boundary,
    has_approval_intent,
    is_conditional_approval_boundary_active,
    is_ungrounded_declared_context,
    metadata_with_manifest_controls,
    missing_required_input_names,
    normalize_clarification_continuation_plan,
    normalize_declared_parameters,
    normalize_invocation_plan,
    normalize_reference_value,
    requested_primary_content_effect,
    requested_unsupported_effects,
    select_consumable_capability,
    should_clear_planner_unsupported_for_approval_boundary,
    user_authored_conversation_text,
)


def test_build_agent_capability_catalog_compacts_routing_brief() -> None:
    catalog = build_agent_capability_catalog(
        [
            {
                "name": "pipeline",
                "url": "http://pipeline.test",
                "discovery": {
                    "capabilities": {
                        "gtm.pipeline_summary": {
                            "description": "Summarize pipeline health.",
                            "minimum_scope": ["pipeline:read"],
                            "side_effect": "none",
                        }
                    }
                },
                "manifest": {
                    "capabilities": {
                        "gtm.pipeline_summary": {
                            "description": "Summarize pipeline health.",
                            "inputs": [
                                {"name": "quarter", "type": "string", "required": True},
                                {"name": "slice_by", "type": "string", "required": False, "default": "region"},
                            ],
                            "business_effects": {
                                "produces": ["data.read", "content.summary"],
                                "does_not_produce": ["data.export"],
                            },
                        }
                    }
                },
            }
        ],
        {
            "gtm.pipeline_summary": {
                "capability_framing": "Bounded pipeline summary.",
                "input_meanings": {"quarter": {"2017-Q2": "Reviewed Q2 scope."}},
                "reference_catalogs": {"owner_scope": ["Enterprise"]},
                "required_context": [{"input": "quarter", "missing_behavior": "clarify"}],
            }
        },
    )

    assert catalog["metadata"]["gtm.pipeline_summary"]["service_name"] == "pipeline"
    assert "required_context=" in catalog["routing_brief"]
    assert "input_meanings=" not in catalog["routing_brief"]
    assert "input_meanings=" in catalog["detail_brief"]
    assert catalog["stats"]["routing_brief_chars"] < catalog["stats"]["detail_brief_chars"]


def test_build_compact_agent_capability_brief_selects_top_candidates() -> None:
    metadata = {
        "crm.pipeline_summary": {
            "description": "Summarize quarterly pipeline health by region.",
            "service_name": "pipeline",
            "input_specs": [{"name": "quarter", "required": True}, {"name": "owner_scope", "required": False}],
            "side_effect": "read",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
        },
        "crm.send_email": {
            "description": "Send an outbound email immediately.",
            "service_name": "outreach",
            "input_specs": [{"name": "target_ref", "required": True}],
            "side_effect": "write",
            "business_effects": {"produces": ["external_dispatch"], "does_not_produce": []},
        },
        "crm.account_enrichment": {
            "description": "Summarize bounded account enrichment context.",
            "service_name": "enrichment",
            "input_specs": [{"name": "account_names", "required": True}],
            "side_effect": "read",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
        },
    }

    brief, stats = build_compact_agent_capability_brief(
        "Show pipeline health for 2017-Q2 in the East region.",
        metadata,
        top_n=2,
    )

    assert stats["compact_catalog"] is True
    assert stats["compact_top_n"] == 2
    assert stats["compact_candidate_ids"][0] == "crm.pipeline_summary"
    assert "crm.pipeline_summary" in brief
    assert "inputs=quarter(req), owner_scope(opt)" in brief
    assert "forbids=raw_data_export" in brief
    assert "crm.send_email" not in brief
    assert stats["compact_brief_chars"] == len(brief)


def test_compact_agent_capability_brief_prefers_read_bottleneck_for_read_intent() -> None:
    metadata = {
        "gtm.stage_bottleneck_summary": {
            "description": "Return bounded bottleneck evidence without exporting raw rows.",
            "service_name": "pipeline",
            "input_specs": [{"name": "quarter", "required": True}],
            "side_effect": "read",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
        },
        "gtm.at_risk_followup_preparation": {
            "description": "Compose at-risk account selection with follow-up preparation and stop at approval.",
            "service_name": "pipeline",
            "input_specs": [{"name": "quarter", "required": True}, {"name": "ranking_basis", "required": False}],
            "side_effect": "write",
            "grant_policy": {"allowed_grant_types": ["one_time"]},
            "business_effects": {
                "produces": ["approval.request", "content.summary", "system.preview_mutation"],
                "does_not_produce": ["system.mutation", "raw_data_export"],
            },
        },
    }

    conversation = "Show the biggest bottlenecks in 2017-Q1."
    read_score = compact_capability_match_score(conversation, "gtm.stage_bottleneck_summary", metadata["gtm.stage_bottleneck_summary"])
    approval_score = compact_capability_match_score(
        conversation,
        "gtm.at_risk_followup_preparation",
        metadata["gtm.at_risk_followup_preparation"],
    )
    brief, stats = build_compact_agent_capability_brief(conversation, metadata, top_n=1)

    assert read_score > approval_score
    assert stats["compact_candidate_ids"] == ["gtm.stage_bottleneck_summary"]
    assert "gtm.stage_bottleneck_summary" in brief
    assert "gtm.at_risk_followup_preparation" not in brief


def test_capability_match_score_prefers_less_specialized_tie() -> None:
    conversation = "Summarize Q2 pipeline for the company."
    pipeline_score = capability_match_score(
        conversation,
        "gtm.pipeline_summary",
        {"capability_framing": "Return bounded pipeline health evidence without exporting raw rows."},
    )
    forecast_score = capability_match_score(
        conversation,
        "gtm.pipeline_forecast_summary",
        {"capability_framing": "Return bounded forecast evidence without exporting raw rows."},
    )
    product_score = capability_match_score(
        conversation,
        "gtm.product_pipeline_summary",
        {"capability_framing": "Return bounded product pipeline evidence without exporting raw rows."},
    )

    assert pipeline_score > forecast_score
    assert pipeline_score > product_score


def test_requested_primary_content_effect_ignores_negated_draft_terms() -> None:
    conversation = "For 2017-Q2 East, summarize the pipeline bottleneck with bounded evidence and do not export rows or draft outreach."

    assert requested_primary_content_effect(conversation) == "content.summary"


def test_normalize_invocation_plan_rewrites_negated_draft_to_summary_capability() -> None:
    metadata = {
        "gtm.stage_bottleneck_summary": {
            "description": "Return bounded bottleneck evidence without exporting raw rows.",
            "service_name": "pipeline",
            "input_specs": [{"name": "quarter", "required": True}, {"name": "owner_scope", "required": False}],
            "side_effect": "read",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
        },
        "gtm.bottleneck_account_outreach_draft": {
            "description": "Select a bounded bottleneck target, draft outreach, and stop at approval.",
            "service_name": "outreach",
            "input_specs": [{"name": "quarter", "required": True}, {"name": "target_ref", "required": False}],
            "side_effect": "write",
            "grant_policy": {"allowed_grant_types": ["one_time"]},
            "business_effects": {
                "produces": ["approval.request", "system.preview_mutation", "content.draft"],
                "does_not_produce": ["external_dispatch", "system.mutation", "raw_data_export"],
            },
        },
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.bottleneck_account_outreach_draft",
            "parameters": {"quarter": "2017-Q2"},
            "unsupported": False,
            "unsupported_reason": None,
        },
        "For 2017-Q2 East, summarize the pipeline bottleneck with bounded evidence and do not export rows or draft outreach.",
        metadata,
    )

    assert plan["selected_capability"] == "gtm.stage_bottleneck_summary"


def test_build_agent_capability_catalog_rejects_duplicate_service_urls() -> None:
    service = {
        "url": "http://same.test",
        "discovery": {"capabilities": {}},
        "manifest": {"capabilities": {"cap.one": {"inputs": []}}},
    }

    try:
        build_agent_capability_catalog([{"name": "one", **service}, {"name": "two", **service}])
    except ValueError as exc:
        assert "Duplicate ANIP service URL" in str(exc)
    else:
        raise AssertionError("expected duplicate service URL rejection")


def test_build_clarification_continuation_extracts_structured_state() -> None:
    continuation = build_clarification_continuation(
        capability="crm.account_summary",
        parameters={"quarter": "2026-Q2"},
        anip_result={
            "success": False,
            "failure": {
                "type": "clarification_required",
                "detail": "Missing account names.",
                "resolution": {"action": "provide_missing_input", "requires": "account_names"},
            },
        },
        capability_metadata={
            "service_name": "crm",
            "input_specs": [
                {"name": "quarter", "required": True},
                {"name": "account_names", "required": True},
            ],
        },
    )

    assert continuation == {
        "type": "clarification",
        "capability": "crm.account_summary",
        "service": "crm",
        "parameters": {"quarter": "2026-Q2"},
        "missing_inputs": ["account_names"],
        "requires": "account_names",
        "action": "provide_missing_input",
        "failure_type": "clarification_required",
    }


def test_clarification_continuation_from_history_uses_last_assistant_state() -> None:
    history = [
        {"role": "assistant", "content": "older", "continuation": {"type": "clarification", "capability": "old"}},
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "Need account.", "continuation": {"type": "clarification", "capability": "new"}},
    ]

    assert clarification_continuation_from_history(history)["capability"] == "new"


def test_user_authored_conversation_text_excludes_assistant_framing() -> None:
    conversation = "\n".join(
        [
            "user: Summarize firmographic context for important accounts.",
            "assistant: I can summarize top at-risk accounts after clarification.",
            "user: Acme Corporation and Codehow.",
        ]
    )

    assert user_authored_conversation_text(conversation) == "\n".join(
        [
            "user: Summarize firmographic context for important accounts.",
            "user: Acme Corporation and Codehow.",
        ]
    )


def test_normalize_invocation_plan_ignores_assistant_text_for_selection_hints() -> None:
    metadata = {
        "crm.account_enrichment_summary": {
            "description": "Return firmographic account enrichment context for named accounts.",
            "input_specs": [{"name": "account_names", "type": "string", "required": True}],
            "business_effects": {"produces": ["content.summary"]},
        },
        "crm.account_risk_summary": {
            "description": "Rank top at-risk accounts for a quarter.",
            "input_specs": [{"name": "quarter", "type": "string", "required": True}],
            "business_effects": {"produces": ["content.summary"]},
        },
    }
    conversation = "\n".join(
        [
            "user: Summarize firmographic context for important accounts.",
            "assistant: I can summarize top at-risk accounts after clarification.",
            "user: Acme Corporation and Codehow.",
        ]
    )

    plan = normalize_invocation_plan(
        {
            "selected_capability": "crm.account_enrichment_summary",
            "parameters": {"account_names": "Acme Corporation and Codehow"},
        },
        conversation,
        metadata,
        selection_hints=[
            {
                "capability": "crm.account_risk_summary",
                "all_terms": ["at-risk", "accounts"],
                "any_terms": ["top", "risk"],
                "lock_capability": True,
            }
        ],
    )

    assert plan["selected_capability"] == "crm.account_enrichment_summary"
    assert plan["parameters"] == {"account_names": "Acme Corporation and Codehow"}


def test_select_consumable_capability_prefers_grounded_approval_peer() -> None:
    metadata = {
        "crm.route_records": {
            "description": "Prepare routing recommendations and stop at approval.",
            "input_specs": [
                {
                    "name": "cohort_ref",
                    "required": True,
                    "allowed_values": ["inbound_last_week"],
                    "resolution": {"mode": "closed_values", "on_missing": "clarify"},
                },
                {
                    "name": "target_queue",
                    "required": False,
                    "allowed_values": ["sales"],
                    "default": "sales",
                    "resolution": {"mode": "closed_values", "on_missing": "use_default"},
                },
            ],
            "app_profile": {
                "input_meanings": {
                    "cohort_ref": {"inbound_last_week": "inbound last week"},
                    "target_queue": {"sales": "sales queue"},
                }
            },
            "business_effects": {"produces": ["approval.request", "system.preview_mutation"]},
        },
        "crm.priority_routing_preparation": {
            "description": "Compose account prioritization with routing preparation and stop at approval.",
            "input_specs": [
                {
                    "name": "cohort_ref",
                    "required": True,
                    "allowed_values": ["expansion_candidates_q2", "at_risk_q2"],
                    "resolution": {"mode": "closed_values", "on_missing": "clarify"},
                }
            ],
            "app_profile": {
                "input_meanings": {
                    "cohort_ref": {
                        "expansion_candidates_q2": "expansion candidates q2",
                        "at_risk_q2": "at risk q2",
                    }
                }
            },
            "business_effects": {"produces": ["approval.request", "system.preview_mutation"]},
        },
    }

    selected = select_consumable_capability(
        "Prepare routing recommendations for hot inbound leads.",
        "crm.priority_routing_preparation",
        metadata,
    )

    assert selected == "crm.route_records"


def test_normalize_clarification_continuation_plan_locks_capability_and_parameters() -> None:
    metadata = {
        "input_specs": [
            {"name": "quarter", "type": "string", "required": True},
            {
                "name": "account_names",
                "type": "string",
                "required": True,
                "resolution": {"mode": "backend_resolved", "resolver_ref": "crm.account_catalog"},
            },
        ]
    }
    continuation = {
        "type": "clarification",
        "capability": "crm.account_summary",
        "parameters": {"quarter": "2026-Q2"},
        "requires": "account_names",
    }
    conversation = conversation_text_from_history(
        "Use Acme Corporation and Codehow.",
        [
            {"role": "user", "content": "Summarize Q2 account context."},
            {"role": "assistant", "content": "Which account_names?", "continuation": continuation},
        ],
    )

    plan = normalize_clarification_continuation_plan(
        {
            "selected_capability": "crm.other_capability",
            "parameters": {"account_names": "Acme Corporation and Codehow", "debug": "ignored"},
            "rationale": "The user answered the clarification.",
        },
        conversation=conversation,
        continuation=continuation,
        capability_metadata=metadata,
    )

    assert plan["selected_capability"] == "crm.account_summary"
    assert plan["parameters"] == {"quarter": "2026-Q2", "account_names": "Acme Corporation and Codehow"}
    assert plan["unsupported"] is False


def test_normalize_clarification_continuation_plan_allows_intent_change_fallback() -> None:
    assert (
        normalize_clarification_continuation_plan(
            {"intent_changed": True, "parameters": {"account_names": "Acme"}},
            conversation="user: show pipeline instead",
            continuation={"type": "clarification", "capability": "crm.account_summary"},
            capability_metadata={"input_specs": [{"name": "account_names", "required": True}]},
        )
        is None
    )


def test_normalize_clarification_continuation_plan_falls_back_when_missing_input_not_answered() -> None:
    assert (
        normalize_clarification_continuation_plan(
            {"parameters": {"account_names": "Acme Corporation"}},
            conversation="user: Use Acme Corporation.",
            continuation={
                "type": "clarification",
                "capability": "crm.at_risk_account_summary",
                "parameters": {},
                "missing_inputs": ["quarter"],
            },
            capability_metadata={
                "input_specs": [
                    {"name": "quarter", "type": "string", "required": True},
                    {"name": "ranking_basis", "type": "string", "required": False, "default": "risk_score"},
                ]
            },
        )
        is None
    )


def test_build_clarification_continuation_prompt_is_capability_agnostic() -> None:
    prompt = build_clarification_continuation_prompt(
        question="Use Acme.",
        continuation={"type": "clarification", "capability": "crm.account_summary", "requires": "account_names"},
        capability_metadata={"input_specs": [{"name": "account_names", "type": "string", "required": True}]},
    )

    assert "crm.account_summary" in prompt
    assert "account_names" in prompt
    assert "Use Acme." in prompt


def test_canonical_from_candidates_uses_meanings_without_phrase_aliases() -> None:
    candidates = {
        "expansion_candidates_q2": "Expansion candidates or accounts to prioritize.",
        "at_risk_q2": "Q2 at-risk account cohort.",
    }

    assert (
        canonical_from_candidates("expansion candidates", "Prioritize Q2 expansion candidates", candidates)
        == "expansion_candidates_q2"
    )


def test_canonical_from_candidates_does_not_map_temporal_only_business_reference() -> None:
    candidates = {
        "expansion_candidates_q2": "Expansion candidates for Q2 account prioritization.",
        "at_risk_q2": "Q2 at-risk account cohort.",
    }

    assert canonical_from_candidates("Q2 candidates", "Prioritize Q2 candidates", candidates) is None


def test_canonical_from_candidates_requires_temporal_evidence_for_temporal_candidate() -> None:
    candidates = {
        "at_risk_q2": "Q2 at-risk account cohort.",
        "expansion_candidates_q2": "Expansion candidates for Q2 account prioritization.",
    }

    assert canonical_from_candidates("at risk", "Which deals are at risk this quarter?", candidates) is None
    assert canonical_from_candidates("at risk", "Which deals are at risk in Q2?", candidates) == "at_risk_q2"


def test_required_temporal_enum_does_not_infer_from_vague_temporal_context() -> None:
    metadata = {
        "input_specs": [
            {
                "name": "cohort_ref",
                "required": True,
                "allowed_values": ["at_risk_q2", "expansion_candidates_q2"],
                "resolution": {"mode": "closed_values", "on_missing": "clarify"},
            }
        ],
        "app_profile": {
            "input_meanings": {
                "cohort_ref": {
                    "at_risk_q2": "Q2 at-risk account cohort.",
                    "expansion_candidates_q2": "Expansion candidates for Q2 account prioritization.",
                }
            }
        },
    }

    assert normalize_declared_parameters({}, "Which deals are at risk this quarter?", metadata) == {}
    assert normalize_declared_parameters({}, "Which deals are at risk in Q2?", metadata)["cohort_ref"] == "at_risk_q2"


def test_reference_value_normalizes_from_reference_catalog() -> None:
    metadata = {
        "app_profile": {
            "reference_catalogs": {"target_ref": ["Acme Corporation", "Codehow"]},
        }
    }

    assert (
        normalize_reference_value({"name": "target_ref"}, "acme corporation", "Draft for Acme Corporation", metadata)
        == "Acme Corporation"
    )


def test_entity_reference_does_not_bind_other_declared_input_value() -> None:
    metadata = {
        "input_specs": [
            {
                "name": "target_ref",
                "required": True,
                "entity_reference": True,
                "resolution": {"mode": "backend_resolved", "on_missing": "clarify"},
            },
            {
                "name": "channel",
                "required": False,
                "allowed_values": ["email", "linkedin"],
                "default": "email",
                "resolution": {"mode": "closed_values", "on_missing": "use_default"},
            },
        ]
    }

    params = normalize_declared_parameters(
        {"target_ref": "LinkedIn", "channel": "linkedin"},
        "Draft a LinkedIn outreach note.",
        metadata,
    )

    assert "target_ref" not in params
    assert params["channel"] == "linkedin"


def test_open_backend_reference_is_not_inferred_from_arbitrary_request_text() -> None:
    metadata = {
        "input_specs": [
            {
                "name": "target_ref",
                "required": True,
                "entity_reference": True,
                "resolution": {"mode": "backend_resolved", "on_missing": "clarify"},
            }
        ]
    }

    assert normalize_declared_parameters({}, "Where are we bottlenecked?", metadata) == {}
    assert normalize_declared_parameters({}, "Rank the highest priority targets.", metadata) == {}


def test_missing_required_input_names_honors_defaults_and_planned_parameters() -> None:
    missing = missing_required_input_names(
        "Draft a LinkedIn outreach note.",
        {
            "input_specs": [
                {
                    "name": "target_ref",
                    "required": True,
                    "entity_reference": True,
                    "resolution": {"mode": "backend_resolved", "on_missing": "clarify"},
                },
                {
                    "name": "objective",
                    "required": True,
                    "default": "first_touch",
                    "resolution": {"on_missing": "use_default"},
                },
            ],
        },
        {"target_ref": "Acme Corporation"},
    )

    assert missing == set()


def test_declared_allowed_value_normalizes_business_adjective_to_backend_field() -> None:
    metadata = {
        "runtime_customization": {
            "normalization": {
                "token_variant_rules": [{"suffix": "al", "replacement": "", "min_length": 6}],
            }
        }
    }
    params = normalize_declared_parameters(
        {"slice_by": "region"},
        "Show the biggest bottlenecks for the West region.",
        {
            "input_specs": [
                {
                    "name": "slice_by",
                    "type": "string",
                    "required": False,
                    "allowed_values": ["regional_office", "manager_name", "product_name"],
                }
            ]
        }
        | metadata,
    )

    assert params["slice_by"] == "regional_office"


def test_declared_value_normalizes_from_compact_description_when_allowed_values_missing() -> None:
    params = normalize_declared_parameters(
        {"slice_by": "region"},
        "Show the biggest bottlenecks in 2017-Q2 for the East region.",
        {
            "input_specs": [
                {
                    "default": "regional_office",
                    "description": "regional_office, manager_name, or product_name",
                    "name": "slice_by",
                    "required": False,
                    "type": "string",
                }
            ],
            "runtime_customization": {
                "normalization": {
                    "token_variant_rules": [{"suffix": "al", "replacement": "", "min_length": 6}],
                }
            },
        },
    )

    assert params["slice_by"] == "regional_office"


def test_declared_allowed_value_drops_invalid_model_value() -> None:
    params = normalize_declared_parameters(
        {"slice_by": "team"},
        "Show East team performance for Q2 2017.",
        {
            "input_specs": [
                {
                    "name": "slice_by",
                    "required": False,
                    "type": "string",
                    "default": "manager_name",
                    "allowed_values": ["manager_name", "regional_office"],
                }
            ],
        },
    )

    assert "slice_by" not in params


def test_required_enum_infers_from_semantic_allowed_values() -> None:
    params = normalize_declared_parameters(
        {"quarter": "Q2 2017"},
        "Preview reassignment for risky Q2 2017 accounts without applying it.",
        {
            "input_specs": [
                {"name": "quarter", "required": True, "type": "string"},
                {"name": "basis", "required": True, "type": "enum"},
            ],
            "input_semantics": [
                {
                    "input_name": "basis",
                    "required": True,
                    "semantic_type": "analysis_mode",
                    "allowed_values": [
                        {"value": "manager_load", "meaning": "manager workload or capacity"},
                        {"value": "regional_capacity", "meaning": "regional capacity"},
                        {"value": "account_risk", "meaning": "risky accounts or account risk"},
                    ],
                }
            ],
        },
    )

    assert params["quarter"] == "2017-Q2"
    assert params["basis"] == "account_risk"


def test_required_enum_can_use_unique_reviewed_value_token() -> None:
    params = normalize_declared_parameters(
        {"quarter": "Q2 2017"},
        "Plan account reassignment for Q2 2017 and stop before execution.",
        {
            "input_specs": [
                {"name": "quarter", "required": True, "type": "string"},
                {"name": "basis", "required": True, "type": "enum"},
            ],
            "input_semantics": [
                {
                    "input_name": "basis",
                    "required": True,
                    "semantic_type": "analysis_mode",
                    "allowed_values": [
                        {"value": "manager_load", "meaning": "manager workload or capacity"},
                        {"value": "regional_capacity", "meaning": "regional capacity"},
                        {"value": "account_risk", "meaning": "risky accounts or account risk"},
                    ],
                }
            ],
        },
    )

    assert params["basis"] == "account_risk"


def test_quarter_shorthand_requires_reviewed_candidate_metadata() -> None:
    metadata = {
        "input_specs": [{"name": "quarter", "required": True, "type": "string"}],
        "app_profile": {
            "input_meanings": {
                "quarter": {
                    "2017-Q2": "Q2 at-risk account review context.",
                }
            }
        },
    }

    assert normalize_declared_parameters({}, "Find Q2 at-risk accounts.", metadata)["quarter"] == "2017-Q2"
    assert normalize_declared_parameters({}, "Show Q2 pipeline health.", {"input_specs": metadata["input_specs"]}) == {}


def test_quarter_input_drops_vague_planner_value_without_explicit_quarter() -> None:
    params = normalize_declared_parameters(
        {"quarter": "What", "ranking_basis": "risk_score"},
        "What should I focus on first?",
        {
            "input_specs": [
                {
                    "name": "quarter",
                    "description": "Quarter label like 2017-Q2",
                    "required": True,
                    "type": "string",
                },
                {
                    "name": "ranking_basis",
                    "allowed_values": ["risk_score"],
                    "required": False,
                    "type": "string",
                },
            ],
            "app_profile": {
                "required_context": [{"input": "quarter", "missing_behavior": "clarify_or_app_select"}],
            },
        },
    )

    assert "quarter" not in params
    assert params["ranking_basis"] == "risk_score"


def test_quarter_input_drops_planner_invented_quarter_without_explicit_quarter() -> None:
    params = normalize_declared_parameters(
        {"quarter": "2024-Q2"},
        "Show me stalled opportunities.",
        {
            "input_specs": [
                {
                    "name": "quarter",
                    "description": "Quarter label like 2017-Q2",
                    "required": True,
                    "type": "string",
                }
            ],
            "app_profile": {
                "required_context": [{"input": "quarter", "missing_behavior": "clarify_or_app_select"}],
            },
        },
    )

    assert "quarter" not in params


def test_missing_scope_context_does_not_infer_command_word_as_value() -> None:
    params = normalize_declared_parameters(
        {"owner_scope": "Summarize"},
        "Summarize pipeline health for 2017-Q2.",
        {
            "input_specs": [
                {
                    "name": "owner_scope",
                    "description": "Regional office or company",
                    "required": False,
                    "type": "string",
                }
            ],
            "app_profile": {
                "required_context": [{"input": "owner_scope", "missing_behavior": "clarify"}],
            },
        },
    )

    assert "owner_scope" not in params


def test_v024_actor_policy_scope_blocks_command_word_leakage() -> None:
    params = normalize_declared_parameters(
        {"owner_scope": "Score"},
        "Score the inbound last week cohort.",
        {
            "input_specs": [
                {
                    "name": "owner_scope",
                    "description": "Actor-visible owner scope.",
                    "required": False,
                    "type": "string",
                    "resolution": {"mode": "actor_policy_or_explicit", "on_missing": "use_actor_scope"},
                }
            ],
            "input_semantics": [
                {
                    "input_name": "owner_scope",
                    "semantic_type": "scope_reference",
                    "resolution": {"mode": "actor_policy_or_explicit", "on_missing": "use_actor_scope"},
                }
            ],
        },
    )

    assert "owner_scope" not in params


def test_v024_backend_resolved_reference_still_allows_open_entity_name() -> None:
    params = normalize_declared_parameters(
        {"target_ref": "Acme Corporation"},
        "Summarize Acme Corporation risk.",
        {
            "input_specs": [
                {
                    "name": "target_ref",
                    "description": "Account target reference.",
                    "required": True,
                    "type": "string",
                    "resolution": {"mode": "backend_resolved", "resolver_ref": "gtm.account_catalog"},
                }
            ],
        },
    )

    assert params["target_ref"] == "Acme Corporation"


def test_effect_selection_preserves_stronger_semantic_match() -> None:
    metadata = {
        "gtm.stalled_opportunity_review": {
            "description": "Return stalled open opportunities with bounded evidence and explainable stall reasoning.",
            "input_specs": [{"name": "quarter", "required": True, "type": "string"}],
            "business_effects": {"produces": ["data.read"]},
        },
        "gtm.prioritized_outreach_draft": {
            "description": "Prioritize a bounded account cohort and draft one outreach message.",
            "input_specs": [{"name": "cohort_ref", "required": True, "type": "string"}],
            "business_effects": {"produces": ["content.draft"]},
        },
    }

    selected = select_consumable_capability(
        "Show a bounded summary of stalled 2017-Q4 opportunities older than 45 days.",
        "gtm.stalled_opportunity_review",
        metadata,
    )

    assert selected == "gtm.stalled_opportunity_review"


def test_grounded_selection_does_not_swap_same_count_different_missing_inputs() -> None:
    metadata = {
        "crm.direct_draft": {
            "description": "Draft outreach content without sending messages.",
            "input_specs": [
                {"name": "target_ref", "required": True, "semantic_type": "entity_reference"},
                {"name": "objective", "required": True, "default": "first_touch", "resolution": {"on_missing": "use_default"}},
            ],
            "business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]},
        },
        "crm.quarterly_draft": {
            "description": "Draft quarterly outreach for a selected bottleneck account.",
            "input_specs": [
                {"name": "quarter", "required": True, "semantic_type": "time_scope"},
                {"name": "target_ref", "required": False, "semantic_type": "entity_reference"},
            ],
            "business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]},
        },
    }

    selected = select_consumable_capability(
        "Draft outreach for the account.",
        "crm.direct_draft",
        metadata,
        parameter_values={"objective": "first_touch"},
    )

    assert selected == "crm.direct_draft"


def test_stronger_contract_match_can_clarify_instead_of_executing_nearby_capability() -> None:
    metadata = {
        "crm.bottleneck_outreach_draft": {
            "capability_id": "crm.bottleneck_outreach_draft",
            "description": "Draft outreach for a selected bottleneck account.",
            "business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]},
            "input_specs": [
                {"name": "segment_ref", "required": True, "input_type": "string", "allowed_values": ["enterprise"]},
                {"name": "channel", "required": False, "input_type": "string", "allowed_values": ["email", "linkedin"]},
            ],
        },
        "crm.prioritized_cohort_outreach_draft": {
            "capability_id": "crm.prioritized_cohort_outreach_draft",
            "description": "Prioritize a bounded account cohort, include enrichment context, and draft outreach.",
            "business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]},
            "input_specs": [
                {
                    "name": "cohort_ref",
                    "required": True,
                    "allowed_values": ["expansion_candidates_q2", "at_risk_q2"],
                    "input_type": "string",
                    "resolution": {"on_missing": "clarify", "on_ambiguous": "clarify"},
                },
                {"name": "channel", "required": False, "input_type": "string", "allowed_values": ["email", "linkedin"]},
            ],
            "app_profile": {
                "capability_framing": (
                    "Prioritize a bounded account cohort and produce draft outreach content only."
                ),
                "input_meanings": {
                    "cohort_ref": {
                        "expansion_candidates_q2": "Expansion candidates for Q2 account prioritization.",
                        "at_risk_q2": "At-risk accounts for Q2 prioritization.",
                    }
                },
            },
        },
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "crm.bottleneck_outreach_draft",
            "parameters": {"segment_ref": "enterprise", "channel": "linkedin"},
            "unsupported": False,
        },
        "Prioritize enterprise candidates, add enrichment for the top three, and draft LinkedIn outreach for the top account.",
        metadata,
    )

    assert plan["selected_capability"] == "crm.prioritized_cohort_outreach_draft"
    assert "cohort_ref" not in plan["parameters"]


def test_declared_reference_requires_grounding_when_catalog_exists() -> None:
    metadata = {
        "app_profile": {
            "input_meanings": {
                "target_queue": {
                    "ae": "Route leads to sales or account executive handoff.",
                    "sdr": "SDR qualification queue.",
                }
            }
        }
    }

    assert is_ungrounded_declared_context({"name": "target_queue"}, "sdr", "Route hot inbound leads", metadata)
    assert not is_ungrounded_declared_context({"name": "target_queue"}, "ae", "Route hot inbound leads to sales", metadata)


def test_declared_reference_does_not_infer_catalog_from_deictic_wording() -> None:
    params = normalize_declared_parameters(
        {"cohort_ref": "inbound_last_week", "target_queue": "sales"},
        "Route the hot ones to sales.",
        {
            "input_specs": [
                {"name": "cohort_ref", "required": True, "type": "string"},
                {"name": "target_queue", "required": False, "type": "string"},
            ],
            "app_profile": {
                "input_meanings": {
                    "cohort_ref": {
                        "inbound_last_week": "Hot inbound leads, recent inbound leads, or inbound leads received during the last week.",
                        "webinar_q2": "Leads sourced from the Q2 webinar motion.",
                    },
                    "target_queue": {"sales": "Route leads to sales handoff."},
                },
            },
            "runtime_customization": {"normalization": {"deictic_terms": ["ones"]}},
        },
    )

    assert "cohort_ref" not in params
    assert params["target_queue"] == "sales"


def test_canonical_value_support_does_not_accept_unrelated_catalog_meaning() -> None:
    candidates = {
        "ae": "Route leads to sales or account executive handoff.",
        "sdr": "SDR qualification queue.",
    }

    assert conversation_supports_canonical_value("route to sales", "ae", candidates)
    assert not conversation_supports_canonical_value("route hot inbound leads", "sdr", candidates)
    assert not conversation_supports_canonical_value("suggest follow-up for that account", "Condax", {"Condax": "Known account"})


def test_token_variant_rules_are_runtime_customization_not_hidden_defaults() -> None:
    candidates = {"regional_office": "Regional office"}

    assert canonical_from_candidates("region", "Show west region bottlenecks.", candidates) is None
    assert (
        canonical_from_candidates(
            "region",
            "Show west region bottlenecks.",
            candidates,
            {"normalization": {"token_variant_rules": [{"suffix": "al", "replacement": "", "min_length": 6}]}},
        )
        == "regional_office"
    )


def test_deictic_terms_are_runtime_customization_not_hidden_defaults() -> None:
    assert not contains_deictic_reference("the hot ones")
    assert contains_deictic_reference("the hot ones", {"normalization": {"deictic_terms": ["ones"]}})


def test_deictic_reference_is_ungrounded_even_if_text_present() -> None:
    metadata = {}
    spec = {"name": "reference_account", "description": "Reference account"}

    assert is_ungrounded_declared_context(spec, "that one", "Find companies like that one.", metadata)


def test_command_and_scope_phrase_is_not_concrete_reference() -> None:
    metadata = {}
    spec = {"name": "target_ref", "description": "Specific account target"}

    assert is_ungrounded_declared_context(spec, "Show East Q2", "Show East Q2 bottlenecks.", metadata)


def test_unknown_named_cohort_does_not_match_by_generic_tokens_only() -> None:
    candidates = {
        "inbound_last_week": "Inbound leads received during the last week.",
        "webinar_q2": "Leads sourced from the Q2 webinar motion.",
    }

    assert canonical_from_candidates("SuperBowl leads cohort", "Score the SuperBowl leads cohort.", candidates) is None


def test_requested_unsupported_effect_detects_send_for_draft_only_capability() -> None:
    metadata = {"business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]}}

    assert requested_unsupported_effects("Prioritize candidates and send the outreach.", metadata) == {"external_dispatch"}
    assert requested_unsupported_effects("Draft a first-touch email.", metadata) == set()
    assert requested_unsupported_effects("Draft content without sending it.", metadata) == set()


def test_requested_unsupported_effect_detects_declared_system_mutation_boundary() -> None:
    metadata = {
        "business_effects": {
            "produces": ["content.draft"],
            "does_not_produce": ["external_dispatch", "system.mutation"],
        }
    }

    assert requested_unsupported_effects("Update CRM after drafting outreach for Codehow.", metadata) == {
        "system.mutation"
    }
    assert requested_unsupported_effects("Draft outreach for Codehow.", metadata) == set()


def test_requested_unsupported_effect_blocks_raw_export_by_default() -> None:
    metadata = {"business_effects": {"produces": ["approval.request"]}}

    assert requested_unsupported_effects("Route the leads and include the raw underlying model payload.", metadata) == {
        "raw_data_export"
    }
    assert requested_unsupported_effects("Summarize the leads with no raw export.", metadata) == set()


def test_requested_unsupported_effect_denies_explicit_approval_bypass() -> None:
    metadata = {
        "business_effects": {
            "produces": ["approval.request", "system.preview_mutation"],
            "does_not_produce": ["approval.execute"],
        }
    }

    assert requested_unsupported_effects("Route the leads directly without approval.", metadata) == {
        "approval.execute"
    }
    assert requested_unsupported_effects("Prepare the routing preview for approval.", metadata) == set()


def test_requested_primary_content_effect_prefers_variants_over_draft_wording() -> None:
    assert requested_primary_content_effect("Draft objection response variants for pricing.") == "content.recommendation"
    assert requested_primary_content_effect("Draft a first-touch email.") == "content.draft"
    assert requested_primary_content_effect("Find lookalike accounts and explain the match basis.") is None


def test_requested_unsupported_effect_uses_declared_boundary_terms() -> None:
    metadata = {
        "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
        "app_profile": {
            "app_boundaries": {
                "unsupported_terms": {
                    "raw_data_export": [
                        "masked financial detail",
                        "even if my role normally gets masked values",
                    ],
                },
            },
        },
    }

    assert requested_unsupported_effects("Summarize using masked financial detail only.", metadata) == {
        "raw_data_export"
    }
    assert requested_unsupported_effects(
        "Show exact revenue numbers even if my role normally gets masked values.",
        metadata,
    ) == {"raw_data_export"}
    assert requested_unsupported_effects("Show exact numbers for the bounded summary.", metadata) == set()


def test_approval_intent_and_match_score_support_generic_precedence() -> None:
    metadata = {
        "description": "Prepare follow-up task previews for high-risk accounts.",
        "input_specs": [{"name": "quarter"}],
    }

    assert has_approval_intent("Show forecast and prepare follow-up previews.")
    assert has_approval_intent("Draft a reviewed outreach message.")
    assert not has_approval_intent("Score inbound leads without routing them.")
    assert capability_match_score("Show forecast and prepare follow-up previews.", "gtm.prepare_followup_tasks", metadata) > 0


def test_approval_boundary_can_clear_planner_unsupported_without_blocked_effects() -> None:
    metadata = {"business_effects": {"produces": ["approval.request", "system.preview_mutation"]}}

    assert should_clear_planner_unsupported_for_approval_boundary(
        "Prepare routing recommendations and draft outreach for the routed account.",
        metadata,
        requested_effects=set(),
    )


def test_approval_boundary_does_not_clear_explicit_blocked_effects() -> None:
    metadata = {
        "business_effects": {
            "produces": ["approval.request", "system.preview_mutation"],
            "does_not_produce": ["external_dispatch"],
        }
    }

    assert not should_clear_planner_unsupported_for_approval_boundary(
        "Prepare routing recommendations and send the outreach now.",
        metadata,
        requested_effects={"external_dispatch"},
    )


def test_conditional_approval_boundary_is_not_primary_business_effect() -> None:
    metadata = {
        "business_effects": {"produces": ["content.draft"]},
        "app_profile": {
            "app_boundaries": {
                "conditional_approval_boundary": {
                    "when_missing": ["target_ref"],
                    "produces": ["approval.request", "system.preview_mutation"],
                }
            }
        },
    }

    assert has_conditional_approval_boundary(metadata)
    assert is_conditional_approval_boundary_active(metadata, {})
    assert is_conditional_approval_boundary_active(metadata, {"target_ref": ""})
    assert not is_conditional_approval_boundary_active(metadata, {"target_ref": "Acme Corporation"})
    assert should_clear_planner_unsupported_for_approval_boundary(
        "Enrich the at-risk account and draft for the top one.",
        metadata,
        parameter_values={},
        requested_effects=set(),
    )


def test_effective_business_effects_derive_approval_boundary_from_grant_policy() -> None:
    effects = effective_business_effects(
        {"business_effects": {"produces": ["data.read"], "does_not_produce": ["raw_data_export"]}},
        {"grant_policy": {"allowed_grant_types": ["one_time"]}},
    )

    assert "data.read" not in effects["produces"]
    assert set(effects["produces"]) == {"approval.request", "system.preview_mutation"}
    assert set(effects["does_not_produce"]) == {"approval.execute", "raw_data_export"}


def test_metadata_with_manifest_controls_adds_approval_profile() -> None:
    metadata = metadata_with_manifest_controls({}, {"grant_policy": {"allowed_grant_types": ["one_time"]}})

    assert metadata["approval"]["required"] is True
    assert metadata["approval"]["grant_types"] == ["one_time"]
    assert "approval-governed" in metadata["app_boundaries"]["guidance"]


def test_select_consumable_capability_prefers_approval_boundary_for_compound_request() -> None:
    metadata = {
        "gtm.pipeline_summary": {
            "description": "Summarize pipeline forecast.",
            "business_effects": {"produces": ["content.summary"]},
        },
        "gtm.prepare_followup_tasks": {
            "description": "Prepare follow-up task previews for high-risk accounts.",
            "business_effects": {"produces": ["approval.request", "system.preview_mutation"]},
        },
    }

    assert (
        select_consumable_capability(
            "Summarize the forecast and prepare follow-up previews.",
            "gtm.pipeline_summary",
            metadata,
        )
        == "gtm.prepare_followup_tasks"
    )


def test_select_consumable_capability_preserves_approval_boundary_for_bypass_denial() -> None:
    metadata = {
        "crm.account_summary": {
            "description": "Summarize account risk.",
            "business_effects": {"produces": ["content.summary"]},
            "input_specs": [{"name": "quarter", "required": True}],
        },
        "crm.route_records": {
            "description": "Prepare governed routing preview.",
            "business_effects": {
                "produces": ["approval.request", "system.preview_mutation"],
                "does_not_produce": ["approval.execute"],
            },
            "input_specs": [
                {"name": "cohort", "required": True, "allowed_values": ["inbound"]},
                {"name": "target_queue", "required": True, "allowed_values": ["sales"]},
            ],
            "app_profile": {
                "input_meanings": {
                    "cohort": {"inbound": "inbound records"},
                    "target_queue": {"sales": "sales queue"},
                }
            },
        },
    }

    selected = select_consumable_capability(
        "Score the inbound records and send them directly to sales without approval.",
        "crm.route_records",
        metadata,
    )

    assert selected == "crm.route_records"
    assert requested_unsupported_effects(
        "Score the inbound records and send them directly to sales without approval.",
        metadata[selected],
    ) == {"approval.execute"}


def test_normalize_declared_parameters_filters_and_infers_from_metadata() -> None:
    metadata = {
        "input_specs": [
            {"name": "quarter", "description": "Quarter label like 2017-Q2", "required": True},
            {"name": "target_ref", "required": False},
            {"name": "queue", "allowed_values": ["ae", "sdr"], "required": False},
        ],
        "app_profile": {
            "reference_catalogs": {"target_ref": ["Acme Corporation"]},
            "input_meanings": {"queue": {"ae": "sales account executive handoff", "sdr": "qualification queue"}},
        },
    }

    normalized = normalize_declared_parameters(
        {"quarter": "Q2 2017", "target_ref": "that one", "queue": "sales", "ignored": "x"},
        "Route Q2 2017 leads to sales for Acme Corporation.",
        metadata,
    )

    assert normalized == {"quarter": "2017-Q2", "target_ref": "Acme Corporation", "queue": "ae"}


def test_normalize_invocation_plan_applies_selection_parameters_and_unsupported_effects() -> None:
    metadata = {
        "gtm.draft_outreach_message": {
            "description": "Draft outreach content.",
            "business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]},
            "input_specs": [{"name": "target_ref"}],
            "app_profile": {"reference_catalogs": {"target_ref": ["Acme Corporation"]}},
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.draft_outreach_message",
            "parameters": {"target_ref": "acme corporation", "extra": "ignored"},
            "unsupported": False,
        },
        "Draft outreach for Acme Corporation and send it now.",
        metadata,
    )

    assert plan["selected_capability"] == "gtm.draft_outreach_message"
    assert plan["parameters"] == {"target_ref": "Acme Corporation"}
    assert plan["unsupported"] is True
    assert "external_dispatch" in plan["unsupported_reason"]


def test_normalize_invocation_plan_clears_planner_unsupported_for_missing_required_context() -> None:
    metadata = {
        "gtm.lookalike_accounts": {
            "description": "Find lookalike accounts.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "reference_account", "required": True}],
            "app_profile": {
                "required_context": [{"input": "reference_account", "missing_behavior": "clarify"}],
            },
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.lookalike_accounts",
            "parameters": {},
            "unsupported": True,
            "unsupported_reason": "Reference account is missing.",
        },
        "Find lookalike accounts for our best customer.",
        metadata,
    )

    assert plan["unsupported"] is False
    assert plan["unsupported_reason"] is None


def test_normalize_invocation_plan_clears_model_only_unsupported_when_declared_effect_matches() -> None:
    metadata = {
        "gtm.prioritized_outreach_draft": {
            "description": "Prioritize a bounded account cohort, include bounded enrichment context, and draft outreach.",
            "business_effects": {
                "produces": ["content.draft", "content.recommendation"],
                "does_not_produce": ["external_dispatch", "system.mutation"],
            },
            "input_specs": [
                {"name": "cohort_ref", "required": True, "allowed_values": ["expansion_candidates_q2"]},
                {"name": "channel", "allowed_values": ["email", "linkedin"]},
            ],
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.prioritized_outreach_draft",
            "parameters": {"cohort_ref": "expansion_candidates_q2", "channel": "linkedin"},
            "unsupported": True,
            "unsupported_reason": "The model guessed enrichment is outside this capability.",
        },
        "Prioritize expansion candidates, enrich the top three, and draft LinkedIn outreach.",
        metadata,
    )

    assert plan["unsupported"] is False
    assert plan["unsupported_reason"] is None


def test_normalize_invocation_plan_clears_model_only_unsupported_for_bounded_read() -> None:
    metadata = {
        "gtm.pipeline_summary": {
            "description": "Summarize bounded pipeline health.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [
                {"name": "quarter", "required": True},
                {"name": "owner_scope"},
            ],
            "app_profile": {
                "app_boundaries": {
                    "unsupported_terms": {
                        "raw_data_export": ["masked financial detail"],
                    },
                },
            },
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.pipeline_summary",
            "parameters": {"quarter": "2017-Q2", "owner_scope": "West"},
            "unsupported": True,
            "unsupported_reason": "The model guessed exact numbers are out of contract.",
        },
        "Show the same West summary and include exact numbers.",
        metadata,
    )

    assert plan["unsupported"] is False
    assert plan["unsupported_reason"] is None


def test_normalize_invocation_plan_prefers_grounded_peer_when_scores_are_zero() -> None:
    metadata = {
        "demo.selected_draft": {
            "description": "",
            "business_effects": {"produces": ["content.draft"], "does_not_produce": []},
            "input_specs": [{"name": "cohort_ref", "required": True, "allowed_values": ["known_cohort"]}],
        },
        "demo.provider_selected_draft": {
            "description": "",
            "business_effects": {"produces": ["content.draft", "approval.request"], "does_not_produce": []},
            "input_specs": [{"name": "quarter", "required": False}],
        },
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "demo.selected_draft",
            "parameters": {},
            "unsupported": False,
        },
        "Draft for the top candidate.",
        metadata,
    )

    assert plan["selected_capability"] == "demo.provider_selected_draft"


def test_business_language_rule_can_mark_reviewed_phrase_supported() -> None:
    metadata = {
        "gtm.pipeline_summary": {
            "description": "Summarize bounded pipeline health and risk evidence.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "quarter", "required": True}],
            "app_profile": {
                "business_language_rules": [
                    {
                        "id": "bounded-risk-concentration",
                        "meaning": "Risk concentration means bounded risk evidence, not raw export.",
                        "owner": "agent_app_glue",
                        "applies_when": {
                            "all_terms": ["risk"],
                            "any_terms": ["concentration", "concentrated"],
                            "exclude_terms": ["raw", "export"],
                        },
                        "interpretation": "Treat this as supported summary intent.",
                        "agent_action": "treat_as_supported",
                    }
                ]
            },
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.pipeline_summary",
            "parameters": {"quarter": "2017-Q3"},
            "unsupported": True,
            "unsupported_reason": "Risk concentration is not supported.",
        },
        "Summarize 2017-Q3 pipeline health and highlight material risk concentration.",
        metadata,
    )

    assert plan["unsupported"] is False
    assert plan["unsupported_reason"] is None


def test_runtime_customization_business_language_rule_can_mark_reviewed_phrase_supported() -> None:
    metadata = {
        "gtm.pipeline_summary": {
            "capability_id": "gtm.pipeline_summary",
            "description": "Summarize bounded pipeline health and risk evidence.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "quarter", "required": True}],
            "runtime_customization": {
                "capability_selection": {
                    "business_language_rules": [
                        {
                            "capability": "gtm.pipeline_summary",
                            "id": "bounded-risk-concentration",
                            "meaning": "Risk concentration means bounded risk evidence, not raw export.",
                            "owner": "agent_app_glue",
                            "applies_when": {
                                "all_terms": ["risk"],
                                "any_terms": ["concentration", "concentrated"],
                                "exclude_terms": ["raw", "export"],
                            },
                            "interpretation": "Treat this as supported summary intent.",
                            "agent_action": "treat_as_supported",
                        }
                    ]
                }
            },
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.pipeline_summary",
            "parameters": {"quarter": "2017-Q3"},
            "unsupported": True,
            "unsupported_reason": "Risk concentration is not supported.",
        },
        "Summarize 2017-Q3 pipeline health and highlight material risk concentration.",
        metadata,
    )

    assert plan["unsupported"] is False
    assert plan["unsupported_reason"] is None


def test_runtime_customization_selection_hint_can_route_capability() -> None:
    runtime_customization = {
        "capability_selection": {
            "selection_hints": [
                {
                    "capability": "gtm.pipeline_forecast_summary",
                    "all_terms": ["forecast"],
                    "any_terms": ["projection"],
                }
            ]
        }
    }
    metadata = {
        "gtm.pipeline_summary": {
            "capability_id": "gtm.pipeline_summary",
            "description": "Summarize bounded pipeline health.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "quarter", "required": True}],
            "runtime_customization": runtime_customization,
        },
        "gtm.pipeline_forecast_summary": {
            "capability_id": "gtm.pipeline_forecast_summary",
            "description": "Summarize bounded forecast projection.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "quarter", "required": True}],
            "runtime_customization": runtime_customization,
        },
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.pipeline_summary",
            "parameters": {"quarter": "2017-Q3"},
            "unsupported": False,
        },
        "Summarize the 2017-Q3 forecast projection.",
        metadata,
    )

    assert plan["selected_capability"] == "gtm.pipeline_forecast_summary"


def test_unrequested_draft_capability_rewrites_to_read_capability() -> None:
    metadata = {
        "gtm.bottleneck_account_outreach_draft": {
            "capability_id": "gtm.bottleneck_account_outreach_draft",
            "description": "Draft outreach content for bottleneck accounts.",
            "business_effects": {"produces": ["content.draft"], "does_not_produce": ["external_dispatch"]},
            "input_specs": [{"name": "target", "required": True}],
            "runtime_customization": {
                "capability_selection": {
                    "effect_floor_min_score": 0.01,
                    "effect_floor_margin": 0.0,
                }
            },
        },
        "gtm.at_risk_account_enrichment_summary": {
            "capability_id": "gtm.at_risk_account_enrichment_summary",
            "description": "Enrich top at-risk accounts contributing to bottlenecks with bounded summary evidence.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "quarter", "required": True}],
            "runtime_customization": {
                "capability_selection": {
                    "effect_floor_min_score": 0.01,
                    "effect_floor_margin": 0.0,
                }
            },
        },
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.bottleneck_account_outreach_draft",
            "parameters": {"quarter": "2017-Q2"},
            "unsupported": False,
        },
        "For 2017-Q2 in the East region, show the biggest bottlenecks and enrich the top 3 at-risk accounts contributing to them.",
        metadata,
    )

    assert plan["selected_capability"] == "gtm.at_risk_account_enrichment_summary"


def test_business_language_rule_does_not_override_excluded_terms() -> None:
    metadata = {
        "gtm.pipeline_summary": {
            "description": "Summarize bounded pipeline health and risk evidence.",
            "business_effects": {"produces": ["content.summary"], "does_not_produce": ["raw_data_export"]},
            "input_specs": [{"name": "quarter", "required": True}],
            "app_profile": {
                "business_language_rules": [
                    {
                        "id": "bounded-risk-concentration",
                        "meaning": "Risk concentration means bounded risk evidence, not raw export.",
                        "owner": "agent_app_glue",
                        "applies_when": {
                            "all_terms": ["risk"],
                            "any_terms": ["concentration", "concentrated"],
                            "exclude_terms": ["raw", "export"],
                        },
                        "interpretation": "Treat this as supported summary intent.",
                        "agent_action": "treat_as_supported",
                    }
                ]
            },
        }
    }

    plan = normalize_invocation_plan(
        {
            "selected_capability": "gtm.pipeline_summary",
            "parameters": {"quarter": "2017-Q3"},
            "unsupported": False,
        },
        "Export raw 2017-Q3 risk concentration rows.",
        metadata,
    )

    assert plan["unsupported"] is True
    assert "raw_data_export" in plan["unsupported_reason"]


def test_shared_agent_consumption_fixtures() -> None:
    fixture_path = Path(__file__).resolve().parents[3] / "agent-consumption-fixtures" / "capability-selection.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    for case in fixture["cases"]:
        metadata = case["metadata"]
        selected = case["selected_capability"]
        conversation = case["conversation"]
        chosen = select_consumable_capability(conversation, selected, metadata)

        assert chosen == case["expected_capability"], case["id"]
        assert sorted(missing_required_input_names(conversation, metadata[chosen])) == sorted(
            case["expected_missing_inputs"]
        ), case["id"]
        assert sorted(requested_unsupported_effects(conversation, metadata[selected])) == sorted(
            case["expected_unsupported_effects"]
        ), case["id"]
