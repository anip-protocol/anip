"""ANIP-backed Studio assistant service.

Studio exposes assistant behaviors through a real ANIP service so the UI can
inspect governed capabilities instead of relying on hidden prompt-only flows.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
from typing import Any

from anip_core import (
    CapabilityDeclaration,
    CapabilityComposition,
    CapabilityInput,
    CapabilityOutput,
    CrossServiceContract,
    CrossServiceContractEntry,
    ResponseMode,
    ServiceCapabilityRef,
    SessionInfo,
    SessionType,
    SideEffect,
    SideEffectType,
)
from anip_service import ANIPError, ANIPService, Capability

from .assistant_provider import try_model_assistant_response
from .consumer_mode import consumer_mode_from_labels, consumer_mode_label, normalize_consumer_mode
from .db import get_pool
from .derivation import derive_contract_expectations
from .repository import (
    NotFoundError,
    get_evaluation,
    get_project_detail,
    get_requirements,
    get_scenario,
    get_shape,
    list_evaluations,
    list_integration_discovery_records,
    list_pm_artifacts,
    list_requirements,
    list_scenarios,
    list_shapes,
)

BOOTSTRAP_BEARER = "studio-assistant-bootstrap"
ASSISTANT_SCOPES = [
    "studio.assistant.explain_shape",
    "studio.assistant.explain_evaluation",
    "studio.assistant.interpret_project_intent",
    "studio.assistant.propose_requirements",
    "studio.assistant.propose_scenarios",
    "studio.assistant.propose_business_summary",
    "studio.assistant.propose_actor_model",
    "studio.assistant.propose_business_areas",
    "studio.assistant.propose_permission_intent",
    "studio.assistant.propose_non_goals",
    "studio.assistant.propose_success_criteria",
    "studio.assistant.propose_service_design",
    "studio.assistant.propose_capability_formalization",
    "studio.assistant.propose_runtime_policy_bindings",
    "studio.assistant.propose_input_contracts",
    "studio.assistant.propose_verification_expectations",
    "studio.assistant.propose_backend_bindings",
    "studio.assistant.propose_governed_fronting_capabilities",
    "studio.assistant.identify_missing_business_info",
    "studio.assistant.clarify_design_section",
    "studio.assistant.suggest_next_step",
    "studio.assistant.analyze_agent_consumption_simulation",
    "studio.assistant.start_design_review_session",
    "studio.assistant.stream_design_review",
]

CAPABILITY_INVENTORY_BASE_FIELDS = (
    "service_name",
    "service_role",
    "title",
    "summary",
    "description",
    "kind",
    "composition",
    "grant_policy",
    "business_effects",
    "minimum_scope",
    "backend_operation",
    "path_template",
    "output_shape",
    "output_intent",
    "intent_type",
    "operation_type",
    "side_effect_level",
    "side_effect_type",
    "entity_targeted",
    "subject_kind",
    "context_type",
    "implementation_fit",
    "source_kind",
)

FRONTING_CAPABILITY_EVIDENCE_FIELDS = (
    "execution_posture",
    "backend_kind",
    "connection_ref",
    "raw_operation_refs",
    "backend_input_mode",
    "derived_required_backend_inputs",
    "derived_optional_backend_inputs",
    "explicit_required_backend_inputs",
    "explicit_optional_backend_inputs",
    "approval_rule_refs",
    "denial_rule_refs",
    "clarification_rule_refs",
    "audit_required",
    "outbound_controls",
)

CAPABILITY_INVENTORY_EVIDENCE_FIELDS = (
    *CAPABILITY_INVENTORY_BASE_FIELDS,
    *FRONTING_CAPABILITY_EVIDENCE_FIELDS,
)

CAPABILITY_CSV_HEADER_CELLS = {
    "allowed_values",
    "audit_policy_json",
    "backend_operation",
    "catalog_ref",
    "child_capability_id",
    "composition_required",
    "context_type",
    "default_value",
    "does_not_produce",
    "entity_reference",
    "failure_policy_json",
    "grant_policy",
    "input_mapping_json",
    "input_name",
    "input_type",
    "intent_type",
    "kind",
    "minimum_scope",
    "needs_developer_input",
    "on_ambiguous",
    "on_missing",
    "on_unresolved",
    "operation_type",
    "output_intent",
    "output_mapping_json",
    "output_shape",
    "product_design_hash",
    "product_revision_artifact_id",
    "product_revision_number",
    "project_id",
    "produces",
    "required",
    "resolution_mode",
    "resolver_ref",
    "semantic_type",
    "service_id",
    "service_name",
    "side_effect_level",
    "step_id",
    "step_order",
    "summary",
    "subject_kind",
    *FRONTING_CAPABILITY_EVIDENCE_FIELDS,
}


def create_studio_assistant_service() -> ANIPService:
    capabilities: list[Capability] = [
            Capability(
                declaration=CapabilityDeclaration(
                    name="interpret_project_intent",
                    description="Turn a plain-language project brief into first-pass requirements, scenarios, concepts, and service-shape suggestions.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the brief belongs to.",
                        ),
                        CapabilityInput(
                            name="intent",
                            type="string",
                            required=False,
                            description="Optional plain-language description of what the user wants to build when no source artifact is provided.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as the canonical business-spec source.",
                        ),
                        CapabilityInput(
                            name="consumer_mode",
                            type="string",
                            required=False,
                            description="Optional audience bias: human_app, agent_anip, or hybrid.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "recommended_shape_type",
                            "recommended_shape_reason",
                            "requirements_focus",
                            "scenario_starters",
                            "domain_concepts",
                            "service_suggestions",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.interpret_project_intent"],
                    cross_service_contract=CrossServiceContract(
                        handoff=[
                            CrossServiceContractEntry(
                                target=ServiceCapabilityRef(
                                    service="studio-workbench",
                                    capability="accept_first_design",
                                ),
                                required_for_task_completion=False,
                                continuity="same_task",
                                completion_mode="downstream_acceptance",
                            )
                        ]
                    ),
                ),
                handler=_interpret_project_intent,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_requirements",
                    description="Draft candidate requirements from a business brief or source requirements artifact without persisting them.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Plain-language business brief or source document excerpt.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional existing requirements artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_requirements"],
                ),
                handler=_propose_requirements,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_scenarios",
                    description="Draft candidate PM scenarios from a business brief or source requirements artifact without persisting them.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Plain-language business brief or source document excerpt.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional existing requirements artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_scenarios"],
                ),
                handler=_propose_scenarios,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_business_summary",
                    description="Draft candidate PM business summary edits from a business brief without persisting them.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project the proposal belongs to."),
                        CapabilityInput(name="source_document_text", type="string", required=False, description="Plain-language business brief or source document excerpt."),
                        CapabilityInput(name="source_requirements_id", type="string", required=False, description="Optional existing requirements artifact to use as reference context."),
                    ],
                    output=CapabilityOutput(type="object", fields=["title", "summary", "mode", "capability", "questions_for_user", "watchouts", "next_steps", "proposal"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.propose_business_summary"],
                ),
                handler=_propose_business_summary,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_actor_model",
                    description="Draft candidate PM actor model edits from a business brief without persisting them.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project the proposal belongs to."),
                        CapabilityInput(name="source_document_text", type="string", required=False, description="Plain-language business brief or source document excerpt."),
                        CapabilityInput(name="source_requirements_id", type="string", required=False, description="Optional existing requirements artifact to use as reference context."),
                    ],
                    output=CapabilityOutput(type="object", fields=["title", "summary", "mode", "capability", "questions_for_user", "watchouts", "next_steps", "proposal"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.propose_actor_model"],
                ),
                handler=_propose_actor_model,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_business_areas",
                    description="Draft candidate PM business area edits from a business brief without persisting them.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project the proposal belongs to."),
                        CapabilityInput(name="source_document_text", type="string", required=False, description="Plain-language business brief or source document excerpt."),
                        CapabilityInput(name="source_requirements_id", type="string", required=False, description="Optional existing requirements artifact to use as reference context."),
                    ],
                    output=CapabilityOutput(type="object", fields=["title", "summary", "mode", "capability", "questions_for_user", "watchouts", "next_steps", "proposal"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.propose_business_areas"],
                ),
                handler=_propose_business_areas,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_permission_intent",
                    description="Draft candidate PM permission intent edits from a business brief without persisting them.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project the proposal belongs to."),
                        CapabilityInput(name="source_document_text", type="string", required=False, description="Plain-language business brief or source document excerpt."),
                        CapabilityInput(name="source_requirements_id", type="string", required=False, description="Optional existing requirements artifact to use as reference context."),
                    ],
                    output=CapabilityOutput(type="object", fields=["title", "summary", "mode", "capability", "questions_for_user", "watchouts", "next_steps", "proposal"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.propose_permission_intent"],
                ),
                handler=_propose_permission_intent,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_non_goals",
                    description="Draft candidate PM non-goal edits from a business brief without persisting them.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project the proposal belongs to."),
                        CapabilityInput(name="source_document_text", type="string", required=False, description="Plain-language business brief or source document excerpt."),
                        CapabilityInput(name="source_requirements_id", type="string", required=False, description="Optional existing requirements artifact to use as reference context."),
                    ],
                    output=CapabilityOutput(type="object", fields=["title", "summary", "mode", "capability", "questions_for_user", "watchouts", "next_steps", "proposal"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.propose_non_goals"],
                ),
                handler=_propose_non_goals,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_success_criteria",
                    description="Draft candidate PM success criteria edits from a business brief without persisting them.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project the proposal belongs to."),
                        CapabilityInput(name="source_document_text", type="string", required=False, description="Plain-language business brief or source document excerpt."),
                        CapabilityInput(name="source_requirements_id", type="string", required=False, description="Optional existing requirements artifact to use as reference context."),
                    ],
                    output=CapabilityOutput(type="object", fields=["title", "summary", "mode", "capability", "questions_for_user", "watchouts", "next_steps", "proposal"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.propose_success_criteria"],
                ),
                handler=_propose_success_criteria,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_service_design",
                    description="Draft candidate developer-facing service design guidance from the locked PM baseline without persisting it.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note or additional source context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_service_design"],
                ),
                handler=_propose_service_design,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_capability_formalization",
                    description="Draft candidate developer-facing capability formalization guidance from the locked PM baseline without persisting it.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note or additional source context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_capability_formalization"],
                ),
                handler=_propose_capability_formalization,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_runtime_policy_bindings",
                    description="Draft candidate developer-facing runtime policy binding guidance from the locked PM baseline without persisting it.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note or additional source context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_runtime_policy_bindings"],
                ),
                handler=_propose_runtime_policy_bindings,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_input_contracts",
                    description="Draft candidate developer-facing input contract guidance from the locked PM baseline without persisting it.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note or additional source context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_input_contracts"],
                ),
                handler=_propose_input_contracts,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_verification_expectations",
                    description="Draft candidate developer-facing verification expectation guidance from the locked PM baseline without persisting it.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note or additional source context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_verification_expectations"],
                ),
                handler=_propose_verification_expectations,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_backend_bindings",
                    description="Draft candidate developer-facing backend binding guidance from the locked PM baseline without persisting it.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note or additional source context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_backend_bindings"],
                ),
                handler=_propose_backend_bindings,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="propose_governed_fronting_capabilities",
                    description="Draft candidate governed ANIP capabilities in front of selected native API, MCP, database, or hybrid backend operations without persisting them.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Govern API / MCP project the proposal belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional developer note, source-doc excerpt, or pasted raw operation context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional service design artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.propose_governed_fronting_capabilities"],
                ),
                handler=_propose_governed_fronting_capabilities,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="identify_missing_business_info",
                    description="Identify missing business decisions that should be clarified before PM design is treated as stable.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the clarification set belongs to.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Plain-language business brief or source document excerpt.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional existing requirements artifact to use as reference context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.identify_missing_business_info"],
                ),
                handler=_identify_missing_business_info,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="clarify_design_section",
                    description="Return only the small set of clarification questions for one PM or Dev design section without drafting the rest of the model.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the clarification set belongs to.",
                        ),
                        CapabilityInput(
                            name="mode",
                            type="string",
                            required=True,
                            description="Whether the clarification is for PM or Dev flow.",
                        ),
                        CapabilityInput(
                            name="section_key",
                            type="string",
                            required=True,
                            description="Deterministic section identifier from the PM or Dev sufficiency model.",
                        ),
                        CapabilityInput(
                            name="source_document_text",
                            type="string",
                            required=False,
                            description="Optional source brief or local design note for additional context.",
                        ),
                        CapabilityInput(
                            name="source_requirements_id",
                            type="string",
                            required=False,
                            description="Optional requirements artifact to use as reference context.",
                        ),
                        CapabilityInput(
                            name="source_shape_id",
                            type="string",
                            required=False,
                            description="Optional shape artifact for dev clarification context.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "mode",
                            "capability",
                            "questions_for_user",
                            "watchouts",
                            "next_steps",
                            "proposal",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.clarify_design_section"],
                ),
                handler=_clarify_design_section,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="suggest_next_step",
                    description="Recommend the single highest-leverage next Studio action from the current deterministic project state.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project to inspect.",
                        ),
                        CapabilityInput(
                            name="mode",
                            type="string",
                            required=False,
                            description="Optional workflow focus: pm or dev.",
                        ),
                        CapabilityInput(
                            name="question",
                            type="string",
                            required=False,
                            description="Optional focus question from the user.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "focused_answer",
                            "action_label",
                            "action_path",
                            "highlights",
                            "watchouts",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.suggest_next_step"],
                ),
                handler=_suggest_next_step,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="analyze_agent_consumption_simulation",
                    description="Analyze the latest saved agent-consumption simulator report and propose reviewable contract or app-glue fixes.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project whose saved simulation report should be analyzed.",
                        ),
                        CapabilityInput(
                            name="question",
                            type="string",
                            required=False,
                            description="Optional focus question for the analysis.",
                        ),
                        CapabilityInput(
                            name="agent_consumption_readiness",
                            type="object",
                            required=False,
                            description="Optional current page readiness report. Used when Studio has computed readiness that is not yet persisted.",
                        ),
                        CapabilityInput(
                            name="high_risk_confirmations",
                            type="object",
                            required=False,
                            description="Optional current page high-risk confirmation report.",
                        ),
                        CapabilityInput(
                            name="focus",
                            type="object",
                            required=False,
                            description="Optional focused item: simulator_case or readiness_finding with an id.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "focused_answer",
                            "action_label",
                            "action_path",
                            "highlights",
                            "watchouts",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.analyze_agent_consumption_simulation"],
                ),
                handler=_analyze_agent_consumption_simulation,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="explain_shape",
                    description="Explain the current Studio service shape in PM-friendly terms.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project containing the shape.",
                        ),
                        CapabilityInput(
                            name="shape_id",
                            type="string",
                            required=True,
                            description="Shape to explain.",
                        ),
                        CapabilityInput(
                            name="question",
                            type="string",
                            required=False,
                            description="Optional focus question from the user.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "focused_answer",
                            "highlights",
                            "watchouts",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.explain_shape"],
                ),
                handler=_explain_shape,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="explain_evaluation",
                    description="Explain a Studio evaluation result and what it means next.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project containing the evaluation.",
                        ),
                        CapabilityInput(
                            name="evaluation_id",
                            type="string",
                            required=True,
                            description="Evaluation to explain.",
                        ),
                        CapabilityInput(
                            name="question",
                            type="string",
                            required=False,
                            description="Optional focus question from the user.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "focused_answer",
                            "highlights",
                            "watchouts",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.explain_evaluation"],
                    cross_service_contract=CrossServiceContract(
                        followup=[
                            CrossServiceContractEntry(
                                target=ServiceCapabilityRef(
                                    service="studio-workbench",
                                    capability="draft_fix_from_change",
                                ),
                                required_for_task_completion=False,
                                continuity="same_task",
                                completion_mode="downstream_acceptance",
                            )
                        ]
                    ),
                ),
                handler=_explain_evaluation,
            ),
        ]

    capabilities.extend(
        [
            Capability(
                declaration=CapabilityDeclaration(
                    name="start_design_review_session",
                    description="Start a bounded review session for the current Studio design.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project to review."),
                        CapabilityInput(name="shape_id", type="string", required=False, description="Optional active shape."),
                        CapabilityInput(name="scenario_id", type="string", required=False, description="Optional active scenario."),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=["session_id", "title", "summary", "review_focus", "next_step"],
                    ),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.start_design_review_session"],
                    composes_with=[CapabilityComposition(capability="stream_design_review", optional=False)],
                    session=SessionInfo(type=SessionType.CONTINUATION),
                ),
                handler=_start_design_review_session,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="stream_design_review",
                    description="Stream a bounded review walkthrough for the current Studio design session.",
                    inputs=[
                        CapabilityInput(name="project_id", type="string", required=True, description="Project being reviewed."),
                        CapabilityInput(name="session_id", type="string", required=True, description="Review session to continue."),
                        CapabilityInput(name="question", type="string", required=False, description="Optional focus question."),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=["session_id", "summary", "highlights", "next_steps"],
                    ),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["studio.assistant.stream_design_review"],
                    response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
                    session=SessionInfo(type=SessionType.CONTINUATION),
                ),
                handler=_stream_design_review,
            ),
        ]
    )

    return ANIPService(
        service_id="studio-assistant",
        capabilities=capabilities,
        storage=":memory:",
        authenticate=_authenticate_bootstrap_bearer,
        trust="signed",
        disclosure_level="full",
    )


def _authenticate_bootstrap_bearer(bearer: str) -> str | None:
    if bearer == BOOTSTRAP_BEARER:
        return "studio-user"
    return None


def _invalid_request(detail: str) -> ANIPError:
    return ANIPError(
        "invalid_request",
        detail,
        resolution={
            "action": "fix_request_parameters",
            "recovery_class": "retry_now",
            "requires": detail,
            "grantable_by": None,
            "estimated_availability": None,
        },
        retry=True,
    )


def _not_found(detail: str) -> ANIPError:
    return ANIPError(
        "not_found",
        detail,
        resolution={
            "action": "revalidate_state",
            "recovery_class": "revalidate_then_retry",
            "requires": detail,
            "grantable_by": None,
            "estimated_availability": None,
            "recovery_target": {
                "kind": "revalidation",
                "target": {
                    "service": "studio-workbench",
                    "capability": "read_project_state",
                },
                "continuity": "same_task",
                "retry_after_target": True,
            },
        },
        retry=False,
    )


def _assistant_provider_failure(detail: str) -> ANIPError:
    return ANIPError(
        "assistant_provider_failed",
        detail,
        resolution={
            "action": "check_assistant_provider_or_use_deterministic_draft",
            "recovery_class": "retry_after_external_fix",
            "requires": "Working LLM provider configuration, or explicit deterministic draft mode.",
            "grantable_by": None,
            "estimated_availability": None,
        },
        retry=True,
    )


def _required_param(params: dict[str, Any], name: str) -> str:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _invalid_request(f"{name} is required")
    return value.strip()


def _optional_param(params: dict[str, Any], name: str) -> str:
    value = params.get(name)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _use_deterministic_assistant(params: dict[str, Any]) -> bool:
    return bool(params.get("use_deterministic"))


def _string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _normalized_words(text: str) -> list[str]:
    cleaned = []
    current = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
        else:
            if current:
                cleaned.append("".join(current))
                current = []
    if current:
        cleaned.append("".join(current))
    return cleaned


def _contains_any(words: set[str], *items: str) -> bool:
    return any(item in words for item in items)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _explicit_capability_ids(source_text: str) -> list[str]:
    """Extract source-declared capability id candidates for human review."""
    candidates = re.findall(r"`([a-z][a-z0-9]*(?:[._][a-z0-9]+)+)`", source_text, flags=re.IGNORECASE)
    result: list[str] = []
    for candidate in candidates:
        value = candidate.strip()
        lower = value.lower()
        if lower.endswith((".md", ".json", ".yaml", ".yml")):
            continue
        if "://" in lower or "/" in lower:
            continue
        if "." not in value:
            continue
        result.append(value)
    return _unique(result)


def _source_declares_canonical_capability_inventory(source_text: str) -> bool:
    normalized = " ".join(source_text.lower().split())
    return any(
        phrase in normalized
        for phrase in (
            '"capability_formalizations"',
            "'capability_formalizations'",
            '"canonical_capability_inventory"',
            "capability inventory is canonical",
            "canonical capability inventory",
            "complete capability inventory",
            "preserve these exact capability ids",
            "reviewed developer evidence",
        )
    )


def _explicit_service_ids(source_text: str) -> list[str]:
    """Extract source-declared service id candidates for human review."""
    candidates = re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", source_text, flags=re.IGNORECASE)
    result: list[str] = []
    for candidate in candidates:
        value = candidate.strip()
        lower = value.lower()
        if lower.endswith((".md", ".json", ".yaml", ".yml")):
            continue
        if "://" in lower or "/" in lower:
            continue
        if "service" not in lower.replace("-", " "):
            continue
        result.append(value)
    return _unique(result)


def _source_declared_service_capability_inventory(source_text: str) -> list[dict[str, Any]]:
    """Extract simple Markdown service -> capability ownership declarations.

    This intentionally handles product-readable source docs, not only machine
    JSON/CSV evidence. A common PM-friendly shape is:

    Service:
    - `billing-service`

    Capabilities:
    - `billing.invoice_summary`
    """
    service_ids = set(_explicit_service_ids(source_text))
    if not service_ids:
        return []

    def canonical_capability_ids(value: str) -> list[str]:
        return [
            candidate.strip()
            for candidate in re.findall(r"`([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)`", value, flags=re.IGNORECASE)
            if "." in candidate
        ]

    def service_ids_in(value: str) -> list[str]:
        return [
            candidate.strip()
            for candidate in re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", value, flags=re.IGNORECASE)
            if candidate.strip() in service_ids
        ]

    result: list[dict[str, Any]] = []
    current_service_id = ""
    current_service_name = ""
    expecting_service = False
    reading_capabilities = False
    lines = source_text.splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        heading = re.match(r"^#{2,6}\s+(?:\d+[.)]\s*)?(.*)$", line)
        if heading:
            current_service_name = heading.group(1).strip()
            current_service_id = ""
            expecting_service = False
            reading_capabilities = False
            continue

        label = line.rstrip(":").strip().lower()
        if label == "service":
            expecting_service = True
            reading_capabilities = False
            continue
        if label == "capabilities":
            expecting_service = False
            reading_capabilities = True
            continue

        if expecting_service:
            declared_services = service_ids_in(line)
            if declared_services:
                current_service_id = declared_services[0]
                expecting_service = False
            elif not line.startswith(("-", "*")):
                expecting_service = False
            continue

        if reading_capabilities:
            capability_ids = canonical_capability_ids(line)
            if capability_ids and current_service_id:
                for capability_id in capability_ids:
                    result.append(
                        {
                            "service_id": current_service_id,
                            "service_name": current_service_name,
                            "capability_id": capability_id,
                        }
                    )
                continue
            if not line.startswith(("-", "*", "`")):
                reading_capabilities = False

    # Also support prose such as: `capability.id` is owned by `service-id`.
    prose_pattern = re.compile(
        r"`([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)`[^.\n]{0,180}?\bowned\s+by\s+`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`",
        flags=re.IGNORECASE,
    )
    for capability_id, service_id in prose_pattern.findall(source_text):
        if service_id in service_ids:
            result.append({"service_id": service_id, "capability_id": capability_id})

    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for entry in result:
        service_id = str(entry.get("service_id") or "").strip()
        capability_id = str(entry.get("capability_id") or "").strip()
        key = (service_id, capability_id)
        if not service_id or not capability_id or key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


_SOURCE_ANCHOR_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "should",
    "must",
    "will",
    "system",
    "user",
    "users",
    "business",
    "product",
    "assistant",
    "agent",
    "service",
    "scenario",
    "requirement",
    "requirements",
    "design",
    "workflow",
    "data",
    "draft",
    "review",
    "governed",
    "bounded",
    "capability",
    "capabilities",
}

_FALLBACK_MARKER_SCHEMA_TERMS = {
    "actor_model",
    "artifact_type",
    "approval sensitive",
    "approval-sensitive",
    "business_areas",
    "business_summary",
    "candidate_blocks",
    "clarification_questions",
    "client_id",
    "non_goals",
    "patch_candidates",
    "pm-facing",
    "permission_intent",
    "product_summary",
    "proposal_kind",
    "requirements",
    "scenarios",
    "service_design",
    "source declared",
    "source-declared",
    "success_criteria",
}

_CANONICAL_BUSINESS_EFFECT_IDS = {
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

_PROPOSAL_GROUNDING_METADATA_FIELDS = {
    "artifact_type",
    "capability",
    "client_id",
    "mode",
    "op",
    "path",
    "proposal_kind",
}


def _proposal_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_proposal_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_proposal_text(item) for item in value.values())
    return str(value)


def _proposal_grounding_text(value: Any) -> str:
    """Return only user-facing proposal content, excluding JSON patch/schema metadata."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_proposal_grounding_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(
            _proposal_grounding_text(item)
            for key, item in value.items()
            if str(key) not in _PROPOSAL_GROUNDING_METADATA_FIELDS
        )
    return str(value)


def _source_anchor_terms(source_text: str) -> list[str]:
    anchors: list[str] = []
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9&/+-]*(?:\s+[A-Z][A-Za-z0-9&/+-]*){1,5}\b", source_text):
        phrase = " ".join(match.group(0).split()).strip(":-,.;()[]")
        words = _normalized_words(phrase)
        if len(words) < 2:
            continue
        if all(word in _SOURCE_ANCHOR_STOPWORDS for word in words):
            continue
        anchors.append(phrase.lower())

    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"^[-*]\s*", "", stripped)
        stripped = re.sub(r"^\d+[.)]\s*", "", stripped)
        if ":" in stripped:
            stripped = stripped.split(":", 1)[0]
        words = [
            word
            for word in _normalized_words(stripped)
            if word not in _SOURCE_ANCHOR_STOPWORDS and len(word) >= 4
        ]
        if 1 <= len(words) <= 5:
            anchors.append(" ".join(words).lower())

    return _unique([anchor for anchor in anchors if 3 <= len(anchor) <= 80])[:80]


def _source_is_rich_enough_for_grounding(source_text: str) -> bool:
    words = _normalized_words(source_text)
    heading_count = len(re.findall(r"^#{1,6}\s+", source_text, flags=re.MULTILINE))
    bullet_count = len(re.findall(r"^\s*[-*]\s+", source_text, flags=re.MULTILINE))
    return len(words) >= 400 and (heading_count >= 2 or bullet_count >= 6 or len(_source_anchor_terms(source_text)) >= 4)


def _fallback_marker_terms(deterministic: dict[str, Any], source_text: str) -> list[str]:
    fallback_payload = deterministic.get("proposal") or deterministic
    fallback_text = _proposal_grounding_text(fallback_payload).lower()
    source_normalized = source_text.lower()
    source_term_normalized = _source_term_comparison_text(source_text)
    terms: list[str] = []

    for match in re.finditer(r"\b[a-z][a-z0-9]+(?:[-_][a-z0-9]+)+\b", fallback_text):
        term = match.group(0)
        if term in _FALLBACK_MARKER_SCHEMA_TERMS:
            continue
        if term not in source_normalized and _source_term_comparison_text(term) not in source_term_normalized:
            terms.append(term)

    def collect_phrase_terms(value: Any) -> None:
        if isinstance(value, str):
            if value.strip().lower() in _FALLBACK_MARKER_SCHEMA_TERMS:
                return
            for fragment in re.split(r"[.;:()\[\]\n]+", value):
                words = [
                    word
                    for word in _normalized_words(fragment)
                    if word not in _SOURCE_ANCHOR_STOPWORDS and len(word) >= 4
                ]
                if 2 <= len(words) <= 6:
                    term = " ".join(words)
                    if term not in source_normalized and _source_term_comparison_text(term) not in source_term_normalized:
                        terms.append(term)
            return
        if isinstance(value, list):
            for item in value:
                collect_phrase_terms(item)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key) in _PROPOSAL_GROUNDING_METADATA_FIELDS:
                    continue
                collect_phrase_terms(item)

    collect_phrase_terms(fallback_payload)

    for phrase in _source_anchor_terms(fallback_text):
        if phrase not in source_normalized:
            terms.append(phrase)

    return _unique(terms)[:80]


def _source_term_comparison_text(value: str) -> str:
    """Normalize ids and prose variants so `sales_leader` matches `Sales Leader`."""
    return " ".join(_normalized_words(value))


def _fallback_marker_hits(deterministic: dict[str, Any], source_text: str, proposal_text: str) -> list[str]:
    normalized = proposal_text.lower()
    return sorted(term for term in _fallback_marker_terms(deterministic, source_text) if term in normalized)


def _source_anchor_hits(source_text: str, proposal_text: str) -> list[str]:
    normalized = proposal_text.lower()
    normalized_terms = _source_term_comparison_text(proposal_text)
    hits: list[str] = []
    for anchor in _source_anchor_terms(source_text):
        if anchor in normalized or _source_term_comparison_text(anchor) in normalized_terms:
            hits.append(anchor)
    return hits


def _validate_source_grounded_model_result(
    capability: str,
    source_text: str,
    result: dict[str, Any],
    deterministic: dict[str, Any],
    service_topology_preference: dict[str, Any] | None = None,
) -> None:
    if capability == "propose_service_design":
        target_count = _service_topology_target_count(service_topology_preference)
        if target_count is not None:
            actual_count = _first_structured_service_count(result.get("proposal"))
            if actual_count is None or actual_count != target_count:
                raise _invalid_request(
                    "Assistant provider returned a service design that ignored the requested topology. "
                    f"Expected {target_count} service(s), got {actual_count if actual_count is not None else 'no structured service shape'}. "
                    "Adjust the service topology preference or regenerate with a model result that honors it."
                )
        ownership_issues = _structured_shape_capability_ownership_issues(result.get("proposal"))
        if ownership_issues:
            raise _invalid_request(
                "Assistant provider returned a service design with unsafe capability ownership. "
                + " ".join(ownership_issues)
                + ". Each canonical capability id must have one owning service. Draft inferred ids only when service responsibilities make ownership clear; otherwise leave capabilities empty and surface a review question."
            )
        explicit_capability_ids = _explicit_capability_ids(source_text)
        if explicit_capability_ids:
            proposed_capability_id_list = _structured_shape_capability_ids(result.get("proposal"))
            proposed_capability_ids = set(proposed_capability_id_list)
            missing = [capability_id for capability_id in explicit_capability_ids if capability_id not in proposed_capability_ids]
            if missing:
                raise _invalid_request(
                    "Assistant provider returned a service design that dropped source-declared capability IDs. "
                    + "Missing: "
                    + ", ".join(missing[:12])
                    + ". Preserve explicit source capability IDs or ask the user to resolve them before locking Developer Design."
                )
            if _source_declares_canonical_capability_inventory(source_text):
                inventory_ids = [
                    str(entry.get("capability_id") or "").strip()
                    for entry in _canonical_capability_inventory_from_source(source_text)
                    if str(entry.get("capability_id") or "").strip()
                ]
                explicit_set = set(inventory_ids or explicit_capability_ids)
                extra = [capability_id for capability_id in proposed_capability_id_list if capability_id not in explicit_set]
                if extra:
                    raise _invalid_request(
                        "Assistant provider returned a service design that added capability IDs outside the canonical source inventory. "
                        + "Extra: "
                        + ", ".join(extra[:12])
                        + ". Use the source-declared capability inventory or ask the user to revise the source before generation."
                    )

    if capability == "propose_capability_formalization" and _source_declares_canonical_capability_inventory(source_text):
        explicit_capability_ids = _explicit_capability_ids(source_text)
        proposed_capability_id_list = _proposal_capability_ids(result.get("proposal"))
        proposed_capability_ids = set(proposed_capability_id_list)
        placeholder_capability_ids = _placeholder_capability_contracts(result.get("proposal"))
        if placeholder_capability_ids:
            raise _invalid_request(
                "Assistant provider returned placeholder capability formalization instead of source-derived contract detail. "
                + "Placeholder capability IDs: "
                + ", ".join(placeholder_capability_ids[:12])
                + ". Preserve the canonical IDs, but replace placeholders with concrete inputs, behavior, side-effect posture, and output intent from the source before generation."
            )
        inventory_ids = [
            str(entry.get("capability_id") or "").strip()
            for entry in _canonical_capability_inventory_from_source(source_text)
            if str(entry.get("capability_id") or "").strip()
        ]
        expected_capability_ids = inventory_ids or explicit_capability_ids
        missing = [capability_id for capability_id in expected_capability_ids if capability_id not in proposed_capability_ids]
        if missing:
            raise _invalid_request(
                "Assistant provider returned a capability formalization that dropped source-declared canonical capability IDs. "
                + "Missing: "
                + ", ".join(missing[:12])
                + ". Preserve the complete canonical capability inventory or ask the user to revise the source before generation."
            )
        explicit_set = set(expected_capability_ids)
        extra = [capability_id for capability_id in proposed_capability_id_list if capability_id not in explicit_set]
        if extra:
            raise _invalid_request(
                "Assistant provider returned a capability formalization that added capability IDs outside the canonical source inventory. "
                + "Extra: "
                + ", ".join(extra[:12])
                + ". Use the source-declared capability inventory or ask the user to revise the source before generation."
            )
        incomplete_capability_ids = _incomplete_capability_contracts(result.get("proposal"))
        if incomplete_capability_ids:
            raise _invalid_request(
                "Assistant provider returned incomplete capability formalization for source-declared canonical capabilities. "
                + "Incomplete capability IDs: "
                + ", ".join(incomplete_capability_ids[:12])
                + ". Each canonical capability must include concrete summary, backend operation, output shape, and input contract details before Developer Design can be locked."
            )
        input_contract_inventory = _canonical_capability_inventory_from_source(source_text)
        input_contract_issues = _capability_input_contract_drift(result.get("proposal"), input_contract_inventory)
        if input_contract_issues:
            raise _invalid_request(
                "Assistant provider returned capability inputs that drift from the source-owned canonical runtime interface. "
                + " ".join(input_contract_issues[:8])
                + ". Preserve the canonical input names, types, required flags, defaults, allowed values, and semantic types before generation."
            )

    if capability == "propose_input_contracts" and _source_declares_canonical_capability_inventory(source_text):
        explicit_capability_ids = _explicit_capability_ids(source_text)
        inventory_ids = [
            str(entry.get("capability_id") or "").strip()
            for entry in _canonical_capability_inventory_from_source(source_text)
            if str(entry.get("capability_id") or "").strip()
        ]
        expected_capability_ids = inventory_ids or explicit_capability_ids
        input_contract_issues = _input_contract_proposal_issues(result.get("proposal"), expected_capability_ids)
        if input_contract_issues:
            raise _invalid_request(
                "Assistant provider returned input-contract guidance without concrete structured capability inputs. "
                + " ".join(input_contract_issues[:12])
                + ". Each source-declared capability must either include reviewed structured inputs or the assistant must ask a precise clarification before Developer Design can proceed."
            )

    if not _source_is_rich_enough_for_grounding(source_text):
        return
    proposal = result.get("proposal")
    if not isinstance(proposal, dict):
        raise _invalid_request("Assistant provider returned a proposal without a structured proposal object.")

    text = _proposal_grounding_text(proposal)
    generic_hits = _fallback_marker_hits(deterministic, source_text, text)
    anchor_hits = _source_anchor_hits(source_text, text)
    if generic_hits and len(anchor_hits) < 2:
        raise _invalid_request(
            "Assistant provider returned a generic draft instead of a source-grounded proposal. "
            f"Generic markers: {', '.join(generic_hits[:5])}. "
            "The business spec has enough concrete source terms for a richer draft; revise the prompt/model output or use deterministic draft explicitly."
        )

    if capability in {"propose_actor_model", "propose_business_areas", "propose_service_design"} and len(anchor_hits) < 1:
        raise _invalid_request(
            "Assistant provider returned a draft with no clear source-specific anchors. "
            "Studio rejected it so generic placeholders are not mistaken for source-derived design truth."
        )


def _overlay_source_owned_capability_inventory(
    result: dict[str, Any],
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preserve reviewed developer-owned capability fields in model candidates."""

    if not isinstance(result, dict) or not inventory:
        return result
    by_capability = {
        str(entry.get("capability_id") or "").strip(): entry
        for entry in inventory
        if isinstance(entry, dict) and str(entry.get("capability_id") or "").strip()
    }
    if not by_capability:
        return result

    def overlay(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            source_entry = by_capability.get(capability_id)
            if source_entry:
                if source_entry.get("service_id"):
                    value["service_id"] = source_entry["service_id"]
                for field in CAPABILITY_INVENTORY_EVIDENCE_FIELDS:
                    source_value = source_entry.get(field)
                    if source_value not in (None, ""):
                        value[field] = source_value
                if isinstance(source_entry.get("grant_policy"), dict):
                    value["grant_policy"] = _normalized_inventory_grant_policy(source_entry["grant_policy"])
                source_inputs = source_entry.get("inputs")
                if isinstance(source_inputs, list) and source_inputs:
                    value["inputs"] = [
                        _capability_input_from_inventory(input_contract)
                        for input_contract in source_inputs
                        if isinstance(input_contract, dict)
                    ]
            for item in value.values():
                overlay(item)
            return
        if isinstance(value, list):
            for item in value:
                overlay(item)

    overlay(result.get("proposal"))
    return result


async def _model_or_deterministic(
    capability: str,
    params: dict[str, Any],
    deterministic: dict[str, Any],
    payload: dict[str, Any],
    source_text: str,
    service_topology_preference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if _use_deterministic_assistant(params):
        return deterministic
    try:
        model_result = await try_model_assistant_response(capability, payload)
    except ANIPError:
        raise
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        raise _assistant_provider_failure(f"Assistant provider failed while drafting {capability}: {detail}") from exc
    if model_result:
        if capability == "propose_capability_formalization":
            inventory = _canonical_capability_inventory_from_source(source_text)
            if inventory:
                model_result = _overlay_source_owned_capability_inventory(model_result, inventory)
        _validate_source_grounded_model_result(
            capability,
            source_text,
            model_result,
            deterministic,
            service_topology_preference=service_topology_preference,
        )
        return model_result
    return deterministic


def _service_topology_target_count(preference: dict[str, Any] | None) -> int | None:
    if not isinstance(preference, dict):
        return None
    value = preference.get("target_service_count")
    if value in (None, ""):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise _invalid_request("service_topology_preference.target_service_count must be a positive integer when provided")
    if count < 1 or count > 20:
        raise _invalid_request("service_topology_preference.target_service_count must be between 1 and 20")
    return count


def _service_topology_preference(params: dict[str, Any], source_service_names: list[str]) -> dict[str, Any] | None:
    raw = params.get("service_topology_preference")
    preference = raw if isinstance(raw, dict) else {}
    target_count = _service_topology_target_count(preference)
    granularity = str(preference.get("granularity") or "source_defined").strip().lower()
    if granularity not in {"coarse", "balanced", "fine", "source_defined"}:
        granularity = "source_defined"

    preserve_source = preference.get("preserve_source_services")
    if preserve_source is None:
        preserve_source = bool(source_service_names) and target_count is None

    if not preference and not source_service_names:
        return None

    return {
        "granularity": granularity,
        "target_service_count": target_count,
        "preserve_source_services": bool(preserve_source),
        "source_service_count": len(source_service_names),
        "source_service_names": source_service_names,
        "rationale": str(preference.get("rationale") or "").strip(),
    }


def _first_structured_service_count(proposal: Any) -> int | None:
    if not isinstance(proposal, dict) or proposal.get("proposal_kind") != "candidate_blocks":
        return None
    for item in proposal.get("items") or []:
        if not isinstance(item, dict):
            continue
        structured = item.get("structured_data")
        if not isinstance(structured, dict):
            continue
        shape = structured.get("shape") if isinstance(structured.get("shape"), dict) else structured
        if not isinstance(shape, dict):
            continue
        services = shape.get("services")
        if isinstance(services, list):
            return len([service for service in services if isinstance(service, dict)])
    return None


def _first_structured_shape(proposal: Any) -> dict[str, Any] | None:
    if not isinstance(proposal, dict) or proposal.get("proposal_kind") != "candidate_blocks":
        return None
    for item in proposal.get("items") or []:
        if not isinstance(item, dict):
            continue
        structured = item.get("structured_data")
        if not isinstance(structured, dict):
            continue
        shape = structured.get("shape") if isinstance(structured.get("shape"), dict) else structured
        if isinstance(shape, dict):
            return shape
    return None


def _structured_shape_capability_ownership_issues(proposal: Any) -> list[str]:
    shape = _first_structured_shape(proposal)
    if not shape:
        return []
    owners_by_capability: dict[str, list[str]] = {}
    invalid: list[str] = []
    services = shape.get("services") if isinstance(shape.get("services"), list) else []
    for service in services:
        if not isinstance(service, dict):
            continue
        service_id = str(service.get("id") or service.get("name") or "service").strip()
        capabilities = service.get("capabilities") if isinstance(service.get("capabilities"), list) else []
        for raw_capability in capabilities:
            capability_id = str(raw_capability or "").strip()
            if not capability_id:
                continue
            if not re.match(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$", capability_id, flags=re.IGNORECASE):
                invalid.append(f"{service_id}:{capability_id}")
                continue
            owners_by_capability.setdefault(capability_id, []).append(service_id)
    duplicate = [
        f"{capability_id} -> {', '.join(sorted(set(owners)))}"
        for capability_id, owners in owners_by_capability.items()
        if len(set(owners)) > 1
    ]
    issues: list[str] = []
    if duplicate:
        issues.append("duplicate capability ownership: " + "; ".join(duplicate[:8]))
    if invalid:
        issues.append("non-canonical capability labels: " + "; ".join(invalid[:8]))
    return issues


def _structured_shape_capability_ids(proposal: Any) -> list[str]:
    shape = _first_structured_shape(proposal)
    if not shape:
        return []
    result: list[str] = []
    services = shape.get("services") if isinstance(shape.get("services"), list) else []
    for service in services:
        if not isinstance(service, dict):
            continue
        capabilities = service.get("capabilities") if isinstance(service.get("capabilities"), list) else []
        for raw_capability in capabilities:
            capability_id = str(raw_capability or "").strip()
            if capability_id:
                result.append(capability_id)
    return _unique(result)


def _service_shape_capability_ids(shape: Any) -> list[str]:
    if not isinstance(shape, dict):
        return []
    result: list[str] = []
    services = shape.get("services") if isinstance(shape.get("services"), list) else []
    for service in services:
        if not isinstance(service, dict):
            continue
        capabilities = service.get("capabilities") if isinstance(service.get("capabilities"), list) else []
        for raw_capability in capabilities:
            capability_id = str(raw_capability or "").strip()
            if capability_id:
                result.append(capability_id)
    return _unique(result)


def _canonical_capability_inventory_from_source(source_text: str) -> list[dict[str, Any]]:
    """Extract reviewed capability inventory from JSON or Markdown developer artifacts."""

    def normalize_input(raw_input: Any) -> dict[str, Any] | None:
        if not isinstance(raw_input, dict):
            return None
        input_name = str(raw_input.get("input_name") or raw_input.get("name") or "").strip()
        if not input_name:
            return None
        result: dict[str, Any] = {"input_name": input_name}
        for source_key, target_key in (
            ("input_type", "input_type"),
            ("type", "input_type"),
            ("required", "required"),
            ("semantic_type", "semantic_type"),
            ("allowed_values", "allowed_values"),
            ("default", "default"),
            ("default_value", "default"),
            ("entity_reference", "entity_reference"),
            ("resolution", "resolution"),
            ("catalog_ref", "catalog_ref"),
            ("resolver_ref", "resolver_ref"),
            ("input_format", "input_format"),
            ("validation_pattern", "validation_pattern"),
            ("clarification_hint", "clarification_hint"),
            ("summary", "summary"),
            ("description", "summary"),
        ):
            if source_key in raw_input and raw_input.get(source_key) not in (None, ""):
                result[target_key] = raw_input.get(source_key)
        return result

    def normalize_entry(raw_entry: Any, inherited_service_id: str | None = None) -> dict[str, Any] | None:
        if isinstance(raw_entry, str):
            capability_id = raw_entry.strip()
            if not capability_id:
                return None
            return {"service_id": inherited_service_id or "", "capability_id": capability_id}
        if not isinstance(raw_entry, dict):
            return None
        capability_id = str(raw_entry.get("capability_id") or raw_entry.get("id") or raw_entry.get("name") or "").strip()
        if not capability_id or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", capability_id, flags=re.IGNORECASE):
            return None
        inputs = [
            normalized
            for normalized in (normalize_input(item) for item in (raw_entry.get("inputs") or []))
            if normalized is not None
        ]
        result: dict[str, Any] = {
            "service_id": str(raw_entry.get("service_id") or inherited_service_id or "").strip(),
            "capability_id": capability_id,
        }
        for field in CAPABILITY_INVENTORY_EVIDENCE_FIELDS:
            if field in raw_entry and raw_entry.get(field) not in (None, ""):
                result[field] = raw_entry.get(field)
        if inputs:
            result["inputs"] = inputs
        return result

    def normalize_inventory(raw_inventory: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_inventory, list):
            return []
        result: list[dict[str, Any]] = []
        for raw_entry in raw_inventory:
            normalized = normalize_entry(raw_entry)
            if normalized is not None:
                result.append(normalized)
        return result

    def service_shape_inventory(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        service_design = payload.get("service_design")
        if isinstance(service_design, dict):
            data = service_design.get("data")
            shape = data.get("shape") if isinstance(data, dict) and isinstance(data.get("shape"), dict) else service_design
        else:
            shape = payload.get("shape") if isinstance(payload.get("shape"), dict) else payload
        services = shape.get("services") if isinstance(shape, dict) and isinstance(shape.get("services"), list) else []
        result: list[dict[str, Any]] = []
        for service in services:
            if not isinstance(service, dict):
                continue
            service_id = str(service.get("id") or service.get("service_id") or service.get("name") or "").strip()
            if not service_id:
                continue
            for raw_capability in service.get("capabilities") or []:
                normalized = normalize_entry(raw_capability, service_id)
                if normalized is None:
                    continue
                normalized.setdefault("service_name", service.get("name"))
                normalized.setdefault("service_role", service.get("role"))
                result.append(normalized)
        return result

    def find_inventory(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            for key in (
                "canonical_capability_inventory",
                "capability_formalizations",
                "capability_contracts",
                "capabilities",
            ):
                raw_inventory = payload.get(key)
                if isinstance(raw_inventory, list):
                    direct = [normalize_entry(item) for item in raw_inventory]
                    direct = [item for item in direct if item is not None]
                    if direct:
                        return direct
                inventory = normalize_inventory(raw_inventory)
                if inventory:
                    return inventory
            inventory = service_shape_inventory(payload)
            if inventory:
                return inventory
            for item in payload.values():
                inventory = find_inventory(item)
                if inventory:
                    return inventory
        if isinstance(payload, list):
            for item in payload:
                inventory = find_inventory(item)
                if inventory:
                    return inventory
        return []

    def json_payloads_from_source() -> list[Any]:
        payloads: list[Any] = []
        try:
            payloads.append(json.loads(source_text))
        except Exception:
            pass
        stripped_source = source_text.lstrip()
        if stripped_source.startswith(("{", "[")):
            try:
                payload, _ = json.JSONDecoder().raw_decode(stripped_source)
                payloads.append(payload)
            except Exception:
                pass
        for match in re.finditer(r"```(?:json)?\s*\n?(.*?)```", source_text, flags=re.IGNORECASE | re.DOTALL):
            try:
                payloads.append(json.loads(match.group(1).strip()))
            except Exception:
                continue
        return payloads

    def parse_csv_list(value: str) -> list[str]:
        normalized = value.strip()
        if not normalized:
            return []
        return [item.strip() for item in re.split(r"[,;]", normalized) if item.strip()]

    def parse_bool(value: str) -> bool:
        return value.strip().lower() in {"true", "yes", "required", "1"}

    def is_canonical_capability_id(value: str) -> bool:
        return bool(re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", value.strip(), flags=re.IGNORECASE))

    def is_canonical_input_name(value: str) -> bool:
        return bool(re.fullmatch(r"[a-z][a-z0-9_]*", value.strip(), flags=re.IGNORECASE))

    def looks_like_csv_header(cells: list[str]) -> bool:
        normalized = {cell.strip().lower() for cell in cells if cell.strip()}
        if "capability_id" not in normalized:
            return False
        return len(normalized.intersection(CAPABILITY_CSV_HEADER_CELLS)) >= 2

    def reject_placeholder_row(row: dict[str, str], source_kind: str, capability_id: str) -> None:
        if parse_bool(row.get("needs_developer_input", "")):
            target = capability_id or row.get("capability_id", "").strip() or "unknown capability"
            raise _invalid_request(
                f"Developer {source_kind} source still contains a placeholder row for {target}. "
                "Complete the row, set needs_developer_input=false, or remove the row before running Autopilot."
            )

    def parse_json_object(value: str, source_kind: str, capability_id: str, field_name: str) -> dict[str, Any]:
        normalized = value.strip()
        if not normalized:
            return {}
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise _invalid_request(
                f"Developer {source_kind} source has invalid JSON in {field_name} for {capability_id}: {exc.msg}."
            ) from exc
        if not isinstance(parsed, dict):
            raise _invalid_request(
                f"Developer {source_kind} source expects {field_name} for {capability_id} to be a JSON object."
            )
        return parsed

    def parse_grant_policy(value: str) -> dict[str, Any] | None:
        normalized = value.strip().lower().replace("-", "_")
        if not normalized or normalized in {"none", "n/a", "na"}:
            return None
        if normalized in {"default_one_time", "one_time", "approval_required", "approval_gated"}:
            return {
                "allowed_grant_types": ["one_time", "session_bound"],
                "default_grant_type": "one_time",
                "expires_in_seconds": 900,
                "max_uses": 1,
            }
        allowed = [item for item in parse_csv_list(normalized) if item in {"one_time", "session_bound"}]
        if allowed:
            return {
                "allowed_grant_types": allowed,
                "default_grant_type": allowed[0],
                "expires_in_seconds": 900,
                "max_uses": 1,
            }
        return None

    def csv_sections_from_source(required_headers: set[str]) -> list[list[dict[str, str]]]:
        lines = source_text.splitlines()
        sections: list[list[dict[str, str]]] = []
        index = 0
        while index < len(lines):
            raw_header = lines[index].strip()
            if not raw_header or "," not in raw_header:
                index += 1
                continue
            try:
                header = next(csv.reader([raw_header]))
            except csv.Error:
                index += 1
                continue
            normalized_header = [cell.strip().lower() for cell in header]
            if not required_headers.issubset(set(normalized_header)):
                index += 1
                continue

            block = [raw_header]
            index += 1
            while index < len(lines):
                line = lines[index].strip()
                if not line:
                    break
                if line.startswith("#") or line.startswith("|"):
                    break
                if "," not in line:
                    break
                try:
                    possible_header = next(csv.reader([line]))
                except csv.Error:
                    possible_header = []
                possible_normalized_header = [cell.strip().lower() for cell in possible_header]
                if required_headers.issubset(set(possible_normalized_header)):
                    break
                if looks_like_csv_header(possible_normalized_header):
                    break
                block.append(line)
                index += 1

            reader = csv.DictReader(io.StringIO("\n".join(block)))
            rows = [
                {str(key or "").strip().lower(): str(value or "").strip() for key, value in row.items()}
                for row in reader
                if any(str(value or "").strip() for value in row.values())
            ]
            if rows:
                sections.append(rows)
            index += 1
        return sections

    def csv_capability_governance_from_source() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        sections = csv_sections_from_source({"capability_id", "operation_type", "side_effect_level", "produces", "does_not_produce"})
        for rows in sections:
            for row in rows:
                capability_id = row.get("capability_id", "").strip()
                if not capability_id:
                    continue
                reject_placeholder_row(row, "runtime governance", capability_id)
                if not is_canonical_capability_id(capability_id):
                    raise _invalid_request(
                        "Developer runtime governance source declares an invalid capability_id "
                        f"{capability_id!r}. Capability IDs must be stable dotted identifiers such as vendor.action_name."
                    )
                produces = parse_csv_list(row.get("produces", ""))
                does_not_produce = parse_csv_list(row.get("does_not_produce", ""))
                unknown_effects = [
                    effect
                    for effect in [*produces, *does_not_produce]
                    if effect not in _CANONICAL_BUSINESS_EFFECT_IDS
                ]
                if unknown_effects:
                    raise _invalid_request(
                        "Developer runtime governance source declares unknown business effect IDs for "
                        f"{capability_id}: {', '.join(unknown_effects)}. "
                        "Use canonical effect IDs only: "
                        + ", ".join(sorted(_CANONICAL_BUSINESS_EFFECT_IDS))
                        + "."
                    )
                entry: dict[str, Any] = {"capability_id": capability_id}
                for key in (
                    "service_id",
                    *CAPABILITY_INVENTORY_EVIDENCE_FIELDS,
                ):
                    if row.get(key):
                        entry[key] = row[key]
                if produces or does_not_produce:
                    entry["business_effects"] = {
                        "produces": produces,
                        "does_not_produce": does_not_produce,
                    }
                minimum_scope = parse_csv_list(row.get("minimum_scope", ""))
                if minimum_scope:
                    entry["minimum_scope"] = minimum_scope
                grant_policy = parse_grant_policy(row.get("grant_policy", ""))
                if grant_policy:
                    entry["grant_policy"] = grant_policy
                result.append(entry)
        return result

    def csv_input_contracts_from_source() -> list[dict[str, Any]]:
        by_capability: dict[str, dict[str, Any]] = {}
        input_keys_by_capability: dict[str, dict[str, dict[str, Any]]] = {}
        order: list[str] = []
        sections = csv_sections_from_source({"capability_id", "input_name", "input_type", "required"})
        for rows in sections:
            for row in rows:
                capability_id = row.get("capability_id", "").strip()
                input_name = row.get("input_name", "").strip()
                if capability_id:
                    reject_placeholder_row(row, "input-contract", capability_id)
                if not capability_id or not input_name:
                    continue
                if not is_canonical_capability_id(capability_id):
                    raise _invalid_request(
                        "Developer input-contract source declares an invalid capability_id "
                        f"{capability_id!r}. Capability IDs must be stable dotted identifiers such as vendor.action_name."
                    )
                if not is_canonical_input_name(input_name):
                    raise _invalid_request(
                        "Developer input-contract source declares an invalid input_name "
                        f"{input_name!r} for {capability_id}. Input names must be stable snake_case identifiers."
                    )
                entry = by_capability.setdefault(capability_id, {"capability_id": capability_id, "inputs": []})
                if capability_id not in order:
                    order.append(capability_id)
                input_contract: dict[str, Any] = {
                    "input_name": input_name,
                    "input_type": row.get("input_type") or "string",
                    "required": parse_bool(row.get("required", "")),
                    "entity_reference": parse_bool(row.get("entity_reference", "")),
                }
                for row_key, target_key in (
                    ("semantic_type", "semantic_type"),
                    ("default_value", "default"),
                    ("catalog_ref", "catalog_ref"),
                    ("summary", "summary"),
                    ("clarification_hint", "clarification_hint"),
                    ("input_format", "input_format"),
                    ("validation_pattern", "validation_pattern"),
                ):
                    if row.get(row_key):
                        input_contract[target_key] = row[row_key]
                allowed_values = parse_csv_list(row.get("allowed_values", ""))
                if allowed_values:
                    input_contract["allowed_values"] = allowed_values
                resolution_mode = row.get("resolution_mode", "").strip()
                if resolution_mode:
                    input_contract["resolution"] = {
                        "mode": resolution_mode,
                        "on_missing": row.get("on_missing", "").strip() or "clarify",
                        "on_ambiguous": row.get("on_ambiguous", "").strip() or "clarify",
                        "on_unresolved": row.get("on_unresolved", "").strip() or "clarify",
                    }
                    resolver_ref = row.get("resolver_ref", "").strip() or row.get("catalog_ref", "").strip()
                    if resolver_ref and resolution_mode == "backend_resolved":
                        input_contract["resolution"]["resolver_ref"] = resolver_ref
                prior_by_name = input_keys_by_capability.setdefault(capability_id, {})
                prior = prior_by_name.get(input_name)
                if prior is not None:
                    if json.dumps(prior, sort_keys=True) != json.dumps(input_contract, sort_keys=True):
                        raise _invalid_request(
                            "Developer input-contract source declares conflicting duplicate input metadata for "
                            f"{capability_id}.{input_name}."
                        )
                    continue
                prior_by_name[input_name] = input_contract
                entry["inputs"].append(input_contract)
        return [by_capability[capability_id] for capability_id in order if capability_id in by_capability]

    def csv_composition_from_source() -> list[dict[str, Any]]:
        by_capability: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        sections = csv_sections_from_source({"capability_id", "composition_required"})
        for rows in sections:
            for row in rows:
                capability_id = row.get("capability_id", "").strip()
                if not capability_id:
                    continue
                reject_placeholder_row(row, "composition", capability_id)
                if not is_canonical_capability_id(capability_id):
                    raise _invalid_request(
                        "Developer composition source declares an invalid capability_id "
                        f"{capability_id!r}. Capability IDs must be stable dotted identifiers such as vendor.action_name."
                    )
                composition_required_raw = row.get("composition_required", "").strip().lower()
                has_step_detail = any(
                    row.get(field, "").strip()
                    for field in (
                        "authority_boundary",
                        "step_id",
                        "child_capability_id",
                        "input_mapping_json",
                        "output_mapping_json",
                        "failure_policy_json",
                    )
                )
                if not composition_required_raw and not has_step_detail:
                    continue
                existing = by_capability.setdefault(
                    capability_id,
                    {
                        "capability_id": capability_id,
                        "kind": "composed" if parse_bool(composition_required_raw) or has_step_detail else "atomic",
                    },
                )
                if capability_id not in order:
                    order.append(capability_id)
                if composition_required_raw and not parse_bool(composition_required_raw):
                    existing["kind"] = "atomic"
                    continue

                existing["kind"] = "composed"
                composition = existing.setdefault(
                    "composition",
                    {
                        "authority_boundary": "",
                        "steps": [],
                        "input_mapping": {},
                        "output_mapping": {},
                        "failure_policy": {},
                        "audit_policy": {},
                    },
                )
                authority_boundary = row.get("authority_boundary", "").strip()
                if authority_boundary:
                    composition["authority_boundary"] = authority_boundary
                step_id = row.get("step_id", "").strip()
                child_capability_id = row.get("child_capability_id", "").strip()
                if step_id or child_capability_id:
                    if not step_id or not child_capability_id:
                        raise _invalid_request(
                            f"Developer composition source must provide both step_id and child_capability_id for {capability_id}."
                        )
                    step: dict[str, Any] = {
                        "id": step_id,
                        "capability": child_capability_id,
                    }
                    step_order = row.get("step_order", "").strip()
                    if step_order:
                        try:
                            step["step_order"] = int(step_order)
                        except ValueError as exc:
                            raise _invalid_request(
                                f"Developer composition source has invalid step_order {step_order!r} for {capability_id}."
                            ) from exc
                    composition["steps"].append(step)

                input_mapping = parse_json_object(row.get("input_mapping_json", ""), "composition", capability_id, "input_mapping_json")
                if input_mapping:
                    composition["input_mapping"][step_id or child_capability_id or f"step_{len(composition['input_mapping']) + 1}"] = input_mapping
                output_mapping = parse_json_object(row.get("output_mapping_json", ""), "composition", capability_id, "output_mapping_json")
                if output_mapping:
                    composition["output_mapping"].update(output_mapping)
                failure_policy = parse_json_object(row.get("failure_policy_json", ""), "composition", capability_id, "failure_policy_json")
                if failure_policy:
                    composition["failure_policy"].update(failure_policy)
                audit_policy = parse_json_object(row.get("audit_policy_json", ""), "composition", capability_id, "audit_policy_json")
                if audit_policy:
                    composition["audit_policy"].update(audit_policy)

        for capability_id, entry in by_capability.items():
            composition = entry.get("composition")
            if not isinstance(composition, dict):
                continue
            if not str(composition.get("authority_boundary") or "").strip():
                raise _invalid_request(f"Developer composition source is missing authority_boundary for {capability_id}.")
            if not composition.get("steps"):
                raise _invalid_request(f"Developer composition source is missing composition steps for {capability_id}.")
            if not composition.get("input_mapping"):
                raise _invalid_request(f"Developer composition source is missing input_mapping_json for {capability_id}.")
            if not composition.get("output_mapping"):
                raise _invalid_request(f"Developer composition source is missing output_mapping_json for {capability_id}.")
            if not composition.get("failure_policy"):
                raise _invalid_request(f"Developer composition source is missing failure_policy_json for {capability_id}.")

        return [by_capability[capability_id] for capability_id in order if capability_id in by_capability]

    def markdown_inventory_from_source() -> list[dict[str, Any]]:
        normalized = source_text.lower()
        if not _source_declares_canonical_capability_inventory(source_text):
            return []
        if "capabilities:" not in normalized:
            return []
        result: list[dict[str, Any]] = []
        current_service_id = ""
        awaiting_service_id = False
        in_capabilities = False
        seen_inventory_marker = False
        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            lower = line.lower()
            if not seen_inventory_marker:
                if "capability inventory is canonical" in lower or "canonical capability inventory" in lower:
                    seen_inventory_marker = True
                continue
            if result and line.startswith("## "):
                break
            if line.startswith("### "):
                in_capabilities = False
                awaiting_service_id = False
                continue
            if lower == "service:":
                awaiting_service_id = True
                in_capabilities = False
                continue
            if lower == "capabilities:":
                in_capabilities = True
                awaiting_service_id = False
                continue
            code_match = re.search(r"`([^`]+)`", line)
            if awaiting_service_id and code_match:
                current_service_id = code_match.group(1).strip()
                awaiting_service_id = False
                continue
            if in_capabilities and code_match:
                capability_id = code_match.group(1).strip()
                if "." in capability_id:
                    result.append({"service_id": current_service_id, "capability_id": capability_id})
                continue
        return result

    def markdown_input_contract_inventory_from_source() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        current_capability_id = ""
        headers: list[str] = []
        current_inputs: list[dict[str, Any]] = []

        def flush_current() -> None:
            nonlocal current_capability_id, headers, current_inputs
            if current_capability_id and current_inputs:
                result.append({"capability_id": current_capability_id, "inputs": current_inputs})
            headers = []
            current_inputs = []

        def parse_bool(value: str) -> bool:
            return value.strip().lower() in {"true", "yes", "required", "1"}

        def parse_allowed_values(value: str) -> list[str]:
            normalized = value.strip()
            if not normalized:
                return []
            return [item.strip() for item in normalized.split(",") if item.strip()]

        def split_row(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip().strip("|").split("|")]

        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            capability_match = re.match(r"^##\s+Capability:\s*`?([^`\s]+)`?\s*$", line, flags=re.IGNORECASE)
            if capability_match:
                flush_current()
                current_capability_id = capability_match.group(1).strip()
                continue
            if not current_capability_id or not line.startswith("|"):
                continue
            cells = split_row(line)
            if not cells:
                continue
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            normalized_cells = [cell.strip().lower() for cell in cells]
            if "input_name" in normalized_cells and "input_type" in normalized_cells:
                headers = normalized_cells
                continue
            if not headers or len(cells) < len(headers):
                continue
            row = {headers[index]: cells[index].strip() for index in range(min(len(headers), len(cells)))}
            input_name = row.get("input_name", "").strip()
            if not input_name:
                continue
            input_contract: dict[str, Any] = {
                "input_name": input_name,
                "input_type": row.get("input_type") or "string",
                "required": parse_bool(row.get("required", "")),
                "entity_reference": parse_bool(row.get("entity_reference", "")),
            }
            for row_key, target_key in (
                ("semantic_type", "semantic_type"),
                ("default_value", "default"),
                ("catalog_ref", "catalog_ref"),
                ("summary", "summary"),
                ("clarification_hint", "clarification_hint"),
            ):
                if row.get(row_key):
                    input_contract[target_key] = row[row_key]
            allowed_values = parse_allowed_values(row.get("allowed_values", ""))
            if allowed_values:
                input_contract["allowed_values"] = allowed_values
            resolution_mode = row.get("resolution_mode", "").strip()
            if resolution_mode:
                input_contract["resolution"] = {
                    "mode": resolution_mode,
                    "on_missing": row.get("on_missing", "").strip() or "clarify",
                    "on_ambiguous": row.get("on_ambiguous", "").strip() or "clarify",
                    "on_unresolved": row.get("on_unresolved", "").strip() or "clarify",
                }
                if input_contract.get("catalog_ref") and resolution_mode == "backend_resolved":
                    input_contract["resolution"]["resolver_ref"] = input_contract["catalog_ref"]
            current_inputs.append(input_contract)

        flush_current()
        return result

    def markdown_capability_governance_from_source() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        headers: list[str] = []
        in_governance_table = False

        def split_row(line: str) -> list[str]:
            return [cell.strip() for cell in line.strip().strip("|").split("|")]

        def parse_list(value: str) -> list[str]:
            return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]

        def parse_grant_policy(value: str) -> dict[str, Any] | None:
            normalized = value.strip().lower().replace("-", "_")
            if not normalized or normalized in {"none", "n/a", "na"}:
                return None
            if normalized in {"default_one_time", "one_time", "approval_required", "approval_gated"}:
                return {
                    "allowed_grant_types": ["one_time", "session_bound"],
                    "default_grant_type": "one_time",
                    "expires_in_seconds": 900,
                    "max_uses": 1,
                }
            allowed = [item for item in parse_list(normalized) if item in {"one_time", "session_bound"}]
            if allowed:
                return {
                    "allowed_grant_types": allowed,
                    "default_grant_type": allowed[0],
                    "expires_in_seconds": 900,
                    "max_uses": 1,
                }
            return None

        for raw_line in source_text.splitlines():
            line = raw_line.strip()
            heading_match = re.match(r"^##\s+(.+?)\s*$", line)
            if heading_match:
                heading = heading_match.group(1).strip().lower()
                in_governance_table = heading in {
                    "capability runtime governance",
                    "runtime capability governance",
                    "capability governance",
                }
                headers = []
                continue
            if not in_governance_table:
                continue
            if not line.startswith("|"):
                continue
            cells = split_row(line)
            if not cells:
                continue
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            normalized_cells = [cell.strip().lower() for cell in cells]
            if "capability_id" in normalized_cells:
                headers = normalized_cells
                continue
            if not headers or len(cells) < len(headers):
                continue
            row = {headers[index]: cells[index].strip() for index in range(min(len(headers), len(cells)))}
            capability_id = row.get("capability_id", "").strip()
            if not capability_id:
                continue
            entry: dict[str, Any] = {"capability_id": capability_id}
            for key in ("kind", "side_effect_level", "operation_type", "summary", "backend_operation", "path_template", "output_shape", "output_intent", "intent_type", "subject_kind", "context_type"):
                if row.get(key):
                    entry[key] = row[key]
            produces = parse_list(row.get("produces", ""))
            does_not_produce = parse_list(row.get("does_not_produce", ""))
            unknown_effects = [
                effect
                for effect in [*produces, *does_not_produce]
                if effect not in _CANONICAL_BUSINESS_EFFECT_IDS
            ]
            if unknown_effects:
                raise _invalid_request(
                    "Developer runtime governance source declares unknown business effect IDs for "
                    f"{capability_id}: {', '.join(unknown_effects)}. "
                    "Use canonical effect IDs only: "
                    + ", ".join(sorted(_CANONICAL_BUSINESS_EFFECT_IDS))
                    + "."
                )
            if produces or does_not_produce:
                entry["business_effects"] = {
                    "produces": produces,
                    "does_not_produce": does_not_produce,
                }
            minimum_scope = parse_list(row.get("minimum_scope", ""))
            if minimum_scope:
                entry["minimum_scope"] = minimum_scope
            grant_policy = parse_grant_policy(row.get("grant_policy", ""))
            if grant_policy:
                entry["grant_policy"] = grant_policy
            result.append(entry)

        return result

    def merge_inventory_inputs(
        base_inventory: list[dict[str, Any]],
        input_inventory: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not input_inventory:
            return base_inventory
        by_capability = {
            str(entry.get("capability_id") or "").strip(): dict(entry)
            for entry in base_inventory
            if str(entry.get("capability_id") or "").strip()
        }
        order = [str(entry.get("capability_id") or "").strip() for entry in base_inventory if str(entry.get("capability_id") or "").strip()]
        for input_entry in input_inventory:
            capability_id = str(input_entry.get("capability_id") or "").strip()
            if not capability_id:
                continue
            existing = by_capability.setdefault(capability_id, {"capability_id": capability_id})
            existing["inputs"] = input_entry.get("inputs") or []
            if capability_id not in order:
                order.append(capability_id)
        return [by_capability[capability_id] for capability_id in order if capability_id in by_capability]

    def merge_inventory_metadata(
        base_inventory: list[dict[str, Any]],
        metadata_inventory: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not metadata_inventory:
            return base_inventory
        by_capability = {
            str(entry.get("capability_id") or "").strip(): dict(entry)
            for entry in base_inventory
            if str(entry.get("capability_id") or "").strip()
        }
        order = [str(entry.get("capability_id") or "").strip() for entry in base_inventory if str(entry.get("capability_id") or "").strip()]
        for metadata_entry in metadata_inventory:
            capability_id = str(metadata_entry.get("capability_id") or "").strip()
            if not capability_id:
                continue
            existing = by_capability.setdefault(capability_id, {"capability_id": capability_id})
            for key, value in metadata_entry.items():
                if key == "capability_id" or value in (None, "", [], {}):
                    continue
                existing[key] = value
            if capability_id not in order:
                order.append(capability_id)
        return [by_capability[capability_id] for capability_id in order if capability_id in by_capability]

    inventory: list[dict[str, Any]] = []
    for payload in json_payloads_from_source():
        payload_inventory = find_inventory(payload)
        if payload_inventory:
            inventory = merge_inventory_metadata(inventory, payload_inventory) if inventory else payload_inventory
    inventory = merge_inventory_metadata(inventory, csv_capability_governance_from_source())
    inventory = merge_inventory_inputs(inventory, csv_input_contracts_from_source())
    inventory = merge_inventory_metadata(inventory, csv_composition_from_source())
    inventory = merge_inventory_metadata(inventory, markdown_inventory_from_source())
    inventory = merge_inventory_inputs(inventory, markdown_input_contract_inventory_from_source())
    inventory = merge_inventory_metadata(inventory, markdown_capability_governance_from_source())
    if inventory:
        return inventory
    return []


def _capability_input_contract_drift(proposal: Any, inventory: list[dict[str, Any]]) -> list[str]:
    """Find reviewed input contracts that the model renamed, omitted, or weakened."""
    expected_by_capability = {
        str(entry.get("capability_id") or "").strip(): entry
        for entry in inventory
        if str(entry.get("capability_id") or "").strip() and isinstance(entry.get("inputs"), list) and entry.get("inputs")
    }
    if not expected_by_capability:
        return []

    contracts: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            if capability_id and isinstance(value.get("inputs"), list):
                contracts[capability_id] = value
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    def input_name(raw_input: Any) -> str:
        if not isinstance(raw_input, dict):
            return ""
        return str(raw_input.get("input_name") or raw_input.get("name") or "").strip()

    def normalized_type(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        aliases = {
            "int": "integer",
            "long": "integer",
            "float": "number",
            "double": "number",
            "str": "string",
            "bool": "boolean",
        }
        return aliases.get(normalized, normalized)

    def normalized_allowed(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return sorted(str(item) for item in value)

    def comparable_input(raw_input: Any) -> dict[str, Any]:
        if not isinstance(raw_input, dict):
            return {}
        result: dict[str, Any] = {
            "input_name": input_name(raw_input),
            "input_type": normalized_type(raw_input.get("input_type") or raw_input.get("type")),
        }
        if "required" in raw_input:
            result["required"] = bool(raw_input.get("required"))
        if raw_input.get("semantic_type") not in (None, ""):
            result["semantic_type"] = str(raw_input.get("semantic_type"))
        if raw_input.get("allowed_values") not in (None, []):
            result["allowed_values"] = normalized_allowed(raw_input.get("allowed_values"))
        if raw_input.get("default") not in (None, ""):
            result["default"] = raw_input.get("default")
        if "entity_reference" in raw_input:
            result["entity_reference"] = bool(raw_input.get("entity_reference"))
        return result

    visit(proposal)
    issues: list[str] = []
    for capability_id, expected_entry in expected_by_capability.items():
        expected_inputs = [item for item in expected_entry.get("inputs") or [] if isinstance(item, dict)]
        actual_contract = contracts.get(capability_id)
        actual_inputs = actual_contract.get("inputs") if isinstance(actual_contract, dict) else []
        if not isinstance(actual_inputs, list):
            actual_inputs = []
        expected_names = [input_name(item) for item in expected_inputs if input_name(item)]
        actual_names = [input_name(item) for item in actual_inputs if input_name(item)]
        if sorted(expected_names) != sorted(actual_names):
            issues.append(f"{capability_id} expected inputs {', '.join(expected_names)}; got {', '.join(actual_names) or 'none'}")
            continue
        actual_by_name = {input_name(item): comparable_input(item) for item in actual_inputs if input_name(item)}
        for expected_input in expected_inputs:
            name = input_name(expected_input)
            expected_comparable = comparable_input(expected_input)
            actual_comparable = actual_by_name.get(name) or {}
            mismatched = [
                key
                for key, expected_value in expected_comparable.items()
                if key != "summary" and actual_comparable.get(key) != expected_value
            ]
            if mismatched:
                issues.append(
                    f"{capability_id}.{name} changed "
                    + ", ".join(f"{key} expected {expected_comparable.get(key)!r} got {actual_comparable.get(key)!r}" for key in mismatched[:4])
                )
                break
    return issues


def _humanized_capability_title(capability_id: str) -> str:
    leaf = capability_id.split(".")[-1] if capability_id else "capability"
    words = [word for word in re.split(r"[_\-\s]+", leaf) if word]
    return " ".join(word.capitalize() for word in words) or capability_id


def _capability_side_effect_from_inventory_entry(entry: dict[str, Any]) -> tuple[str, str]:
    side_effect = str(entry.get("side_effect_level") or entry.get("side_effect_type") or "").strip()
    operation_type = str(entry.get("operation_type") or "").strip()
    if side_effect and operation_type:
        return side_effect, operation_type

    capability_id = str(entry.get("capability_id") or "").lower()
    mutating_terms = (
        "approve",
        "assign",
        "create",
        "delete",
        "execute",
        "mutate",
        "post",
        "publish",
        "reassign",
        "route",
        "save",
        "send",
        "submit",
        "update",
    )
    preparation_terms = ("prepare", "preparation", "plan")
    if any(term in capability_id for term in mutating_terms) or any(term in capability_id for term in preparation_terms):
        return side_effect or "approval_required", operation_type or "approval_gated"
    return side_effect or "read", operation_type or "read"


def _normalized_inventory_grant_policy(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    allowed = value.get("allowed_grant_types")
    if isinstance(allowed, list) and allowed:
        return {
            "allowed_grant_types": [str(item) for item in allowed if str(item).strip()],
            "default_grant_type": str(value.get("default_grant_type") or allowed[0]),
            "expires_in_seconds": int(value.get("expires_in_seconds") or 900),
            "max_uses": int(value.get("max_uses") or 1),
        }
    mode = str(value.get("mode") or value.get("grant_policy") or "").strip().lower().replace("-", "_")
    if mode in {"default_one_time", "one_time", "approval_required", "approval_gated"}:
        return {
            "allowed_grant_types": ["one_time", "session_bound"],
            "default_grant_type": "one_time",
            "expires_in_seconds": 900,
            "max_uses": 1,
        }
    return dict(value)


def _capability_input_from_inventory(input_contract: dict[str, Any]) -> dict[str, Any]:
    input_name = str(input_contract.get("input_name") or input_contract.get("name") or "").strip()
    input_type = str(input_contract.get("input_type") or input_contract.get("type") or "string").strip() or "string"
    default_value = input_contract.get("default")
    if default_value is None:
        default_value = input_contract.get("default_value")
    result: dict[str, Any] = {
        "input_name": input_name,
        "input_type": input_type,
        "required": bool(input_contract.get("required")),
        "summary": str(input_contract.get("summary") or input_contract.get("description") or f"Reviewed input contract for {input_name}.").strip(),
        "allowed_values": [str(value) for value in input_contract.get("allowed_values") or []],
        "entity_reference": bool(input_contract.get("entity_reference")),
    }
    optional_fields = (
        "semantic_type",
        "input_format",
        "validation_pattern",
        "clarification_hint",
        "normalization_hint",
        "normalization_context",
        "catalog_ref",
    )
    for field in optional_fields:
        value = input_contract.get(field)
        if value not in (None, ""):
            result[field] = value
    if default_value not in (None, ""):
        result["default"] = default_value
        result["default_value"] = default_value
    if isinstance(input_contract.get("resolution"), dict):
        result["resolution"] = dict(input_contract["resolution"])
        if (
            not result["resolution"].get("resolver_ref")
            and result["resolution"].get("mode") == "backend_resolved"
            and result.get("catalog_ref")
        ):
            result["resolution"]["resolver_ref"] = result["catalog_ref"]
    for field in ("reference_catalog", "semantic_aliases", "allowed_value_semantics"):
        value = input_contract.get(field)
        if isinstance(value, list) and value:
            result[field] = value
    return result


def _capability_contract_from_inventory_entry(entry: dict[str, Any]) -> dict[str, Any]:
    capability_id = str(entry.get("capability_id") or "").strip()
    service_id = str(entry.get("service_id") or "").strip()
    title = str(entry.get("title") or _humanized_capability_title(capability_id)).strip()
    side_effect_level, operation_type = _capability_side_effect_from_inventory_entry(entry)
    inputs = [
        _capability_input_from_inventory(input_contract)
        for input_contract in entry.get("inputs") or []
        if isinstance(input_contract, dict)
    ]
    summary = str(entry.get("summary") or entry.get("description") or f"Reviewed contract for {title}.").strip()
    return {
        "service_id": service_id,
        "capability_id": capability_id,
        "kind": str(entry.get("kind") or "atomic"),
        "title": title,
        "summary": summary,
        "intent_type": str(entry.get("intent_type") or "business_action"),
        "operation_type": operation_type,
        "side_effect_level": side_effect_level,
        "backend_operation": str(entry.get("backend_operation") or capability_id),
        "path_template": str(entry.get("path_template") or ""),
        "output_shape": str(entry.get("output_shape") or "governed_result"),
        "entity_targeted": bool(entry.get("entity_targeted")),
        "subject_kind": str(entry.get("subject_kind") or ""),
        "context_type": str(entry.get("context_type") or ""),
        "output_intent": str(entry.get("output_intent") or "governed_result"),
        "composition": entry.get("composition") if isinstance(entry.get("composition"), dict) else None,
        "grant_policy": _normalized_inventory_grant_policy(entry.get("grant_policy")),
        "business_effects": entry.get("business_effects") if isinstance(entry.get("business_effects"), dict) else None,
        "implementation_fit": entry.get("implementation_fit") if isinstance(entry.get("implementation_fit"), dict) else None,
        "minimum_scope": entry.get("minimum_scope") if isinstance(entry.get("minimum_scope"), list) else [],
        "inputs": inputs,
    }


def _inventory_entry_has_capability_contract_detail(entry: dict[str, Any]) -> bool:
    """Return true only when inventory contains full capability metadata, not just inputs."""
    if not isinstance(entry, dict):
        return False
    capability_id = str(entry.get("capability_id") or "").strip()
    if not capability_id:
        return False
    contract_fields = (
        "summary",
        "description",
        "backend_operation",
        "path_template",
        "output_shape",
        "output_intent",
        "intent_type",
        "operation_type",
        "side_effect_level",
        "side_effect_type",
        "subject_kind",
        "context_type",
        "grant_policy",
        "business_effects",
        "minimum_scope",
        "implementation_fit",
        "composition",
        "kind",
    )
    return any(entry.get(field) not in (None, "") for field in contract_fields)


def _inventory_has_capability_contract_detail(inventory: list[dict[str, Any]]) -> bool:
    detailed = [
        entry
        for entry in inventory
        if _inventory_entry_has_capability_contract_detail(entry)
    ]
    return bool(detailed) and len(detailed) == len([entry for entry in inventory if str(entry.get("capability_id") or "").strip()])


def _capability_formalization_from_inventory(
    project_name: str,
    inventory: list[dict[str, Any]],
    section_questions: list[Any],
) -> dict[str, Any]:
    capabilities = [
        _capability_contract_from_inventory_entry(entry)
        for entry in inventory
        if str(entry.get("capability_id") or "").strip()
    ]
    services = sorted({capability["service_id"] for capability in capabilities if capability.get("service_id")})
    return _proposal_envelope(
        title=f"Capability Formalization Proposal: {project_name}",
        summary=(
            "Compiled reviewed canonical capability inventory into concrete Developer Design capability contracts. "
            "Because the source includes machine-readable interface evidence, Studio preserves it deterministically instead of asking the model to retype it."
        ),
        capability="propose_capability_formalization",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Review side-effect posture, backend operation labels, and output shape names before locking Developer Design if the source inventory did not specify them.",
            "Input names, types, required flags, defaults, allowed values, semantic types, and resolution posture were copied from the reviewed inventory.",
        ],
        next_steps=[
            "Accept the compiled capability contracts that belong in Developer Design.",
            "Edit any side-effect or output-shape fields that need stricter implementation-specific wording before package generation.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "capability_formalization",
            "items": [
                {
                    "client_id": "canonical-capability-inventory",
                    "title": "Canonical capability contracts",
                    "body": f"Compiled {len(capabilities)} reviewed capability contracts across {len(services)} service boundary/boundaries.",
                    "confidence": "high",
                    "rationale": "The source provided machine-readable canonical capability inventory with reviewed runtime input contracts.",
                    "structured_data": {
                        "capabilities": capabilities,
                    },
                }
            ],
        },
        mode="dev",
    )


def _input_contracts_from_inventory(
    project_name: str,
    inventory: list[dict[str, Any]],
    questions_for_user: list[str],
) -> dict[str, Any]:
    inputs_by_name: dict[str, dict[str, Any]] = {}
    capability_count = 0
    for entry in inventory:
        capability_id = str(entry.get("capability_id") or "").strip()
        inputs = entry.get("inputs") if isinstance(entry.get("inputs"), list) else []
        if capability_id:
            capability_count += 1
        for input_contract in inputs:
            if not isinstance(input_contract, dict):
                continue
            name = str(input_contract.get("input_name") or input_contract.get("name") or "").strip()
            if not name:
                continue
            normalized = _capability_input_from_inventory(input_contract)
            record = inputs_by_name.setdefault(
                name,
                {
                    "input_name": name,
                    "input_type": normalized.get("input_type", "string"),
                    "required_somewhere": False,
                    "semantic_types": set(),
                    "allowed_values": set(),
                    "defaults": set(),
                    "capability_ids": [],
                    "summaries": [],
                },
            )
            record["required_somewhere"] = bool(record["required_somewhere"] or normalized.get("required"))
            if normalized.get("semantic_type"):
                record["semantic_types"].add(str(normalized["semantic_type"]))
            for value in normalized.get("allowed_values") or []:
                record["allowed_values"].add(str(value))
            default_value = normalized.get("default")
            if default_value not in (None, ""):
                record["defaults"].add(str(default_value))
            if capability_id:
                record["capability_ids"].append(capability_id)
            summary = str(normalized.get("summary") or "").strip()
            if summary:
                record["summaries"].append(summary)

    def format_input(record: dict[str, Any]) -> str:
        semantic_types = sorted(record["semantic_types"])
        allowed_values = sorted(record["allowed_values"])
        defaults = sorted(record["defaults"])
        capability_ids = _unique(record["capability_ids"])
        parts = [
            f"`{record['input_name']}` ({record['input_type']})",
            "required by at least one capability" if record["required_somewhere"] else "optional/defaulted where used",
        ]
        if semantic_types:
            parts.append("semantic type(s): " + ", ".join(semantic_types))
        if allowed_values:
            parts.append("allowed values: " + ", ".join(allowed_values))
        if defaults:
            parts.append("default(s): " + ", ".join(defaults))
        if capability_ids:
            parts.append("used by: " + ", ".join(capability_ids[:6]) + (" ..." if len(capability_ids) > 6 else ""))
        return "; ".join(parts) + "."

    input_summaries = [format_input(record) for record in sorted(inputs_by_name.values(), key=lambda item: item["input_name"])]
    summary_body = "\n".join(f"- {line}" for line in input_summaries) or "No reviewed inputs were present in the canonical inventory."
    return _proposal_envelope(
        title=f"Input Contract Proposal: {project_name}",
        summary=(
            "Compiled reviewed input contracts from canonical capability inventory. "
            "Studio preserves this metadata deterministically instead of asking the model to infer it from field names."
        ),
        capability="propose_input_contracts",
        questions_for_user=questions_for_user,
        watchouts=[
            "Review normalization hints and aliases if user phrasing needs to map onto closed values.",
            "Do not move these runtime field names into business-owned product specs; keep them in Developer Design or developer-owned interface evidence.",
        ],
        next_steps=[
            "Accept the input-contract guidance for Developer Design review.",
            "Edit aliases, normalization hints, or catalog references if implementation code has stronger resolver behavior.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "input_contracts",
            "items": [
                _proposal_item(
                    "input-required-fields",
                    "Reviewed runtime inputs from canonical inventory",
                    summary_body,
                    f"Compiled {len(inputs_by_name)} unique input field(s) across {capability_count} reviewed capability contract(s).",
                    "high",
                    structured_data={
                        "capabilities": [
                            {
                                "capability_id": str(entry.get("capability_id") or "").strip(),
                                "inputs": [
                                    _capability_input_from_inventory(input_contract)
                                    for input_contract in (entry.get("inputs") or [])
                                    if isinstance(input_contract, dict)
                                ],
                            }
                            for entry in inventory
                            if str(entry.get("capability_id") or "").strip()
                        ],
                    },
                ),
                _proposal_item(
                    "input-semantic-classification",
                    "Reviewed input semantic classification",
                    summary_body,
                    "Semantic types, defaults, allowed values, and required posture came from developer-owned interface evidence.",
                    "high",
                ),
            ],
        },
        mode="dev",
    )


def _proposal_capability_ids(proposal: Any) -> list[str]:
    """Extract capability IDs from assistant proposal structures."""
    result: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = value.get("capability_id")
            if isinstance(capability_id, str) and capability_id.strip():
                result.append(capability_id.strip())
            capabilities = value.get("capabilities")
            if isinstance(capabilities, list):
                for item in capabilities:
                    if isinstance(item, str) and item.strip():
                        result.append(item.strip())
                    else:
                        visit(item)
            for key, item in value.items():
                if key in {"capability_id", "capabilities"}:
                    continue
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(proposal)
    return _unique(result)


_PLACEHOLDER_CAPABILITY_TEXT_MARKERS = (
    "placeholder:",
    "review_needed",
    "needs explicit",
    "needs source",
    "needs review",
    "tbd",
    "todo",
)


def _placeholder_capability_contracts(proposal: Any) -> list[str]:
    """Find assistant capability entries that are review placeholders, not contracts."""
    result: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            if capability_id:
                text = " ".join(
                    str(value.get(field) or "").lower()
                    for field in ("title", "summary", "description", "backend_operation", "output_shape")
                )
                if any(marker in text for marker in _PLACEHOLDER_CAPABILITY_TEXT_MARKERS):
                    result.append(capability_id)
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(proposal)
    return _unique(result)


def _incomplete_capability_contracts(proposal: Any) -> list[str]:
    """Find canonical capability entries that are still shells instead of contracts."""
    result: list[str] = []

    def has_text(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    def has_structured_inputs(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        for item in value:
            if not isinstance(item, dict):
                continue
            if has_text(item.get("input_name") or item.get("name")) and has_text(item.get("summary") or item.get("description")):
                return True
        return False

    def has_business_effects(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        produces = value.get("produces")
        does_not_produce = value.get("does_not_produce")
        return (
            isinstance(produces, list)
            and any(has_text(item) for item in produces)
            and isinstance(does_not_produce, list)
            and any(has_text(item) for item in does_not_produce)
        )

    def has_grant_policy(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        return (
            isinstance(value.get("allowed_grant_types"), list)
            and any(has_text(item) for item in value.get("allowed_grant_types") or [])
            and has_text(value.get("default_grant_type"))
        )

    def is_approval_or_write_capable(value: dict[str, Any]) -> bool:
        text = " ".join(
            str(value.get(field) or "").strip().lower()
            for field in ("intent_type", "operation_type", "side_effect_level")
        )
        effects = value.get("business_effects") if isinstance(value.get("business_effects"), dict) else {}
        produced = " ".join(str(item).strip().lower() for item in effects.get("produces", []) if isinstance(item, str))
        return "approval" in text or "write" in text or "mutation" in text or "approval.request" in produced or "system.mutation" in produced

    def has_complete_composition(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        return (
            has_text(value.get("authority_boundary"))
            and isinstance(value.get("steps"), list)
            and bool(value.get("steps"))
            and isinstance(value.get("input_mapping"), dict)
            and bool(value.get("input_mapping"))
            and isinstance(value.get("output_mapping"), dict)
            and bool(value.get("output_mapping"))
            and isinstance(value.get("failure_policy"), dict)
            and bool(value.get("failure_policy"))
        )

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            if capability_id:
                missing_summary = not has_text(value.get("summary") or value.get("description") or value.get("purpose"))
                missing_backend = not has_text(value.get("backend_operation"))
                missing_output = not has_text(value.get("output_shape"))
                missing_inputs = not has_structured_inputs(value.get("inputs"))
                missing_effects = not has_business_effects(value.get("business_effects"))
                missing_grant = is_approval_or_write_capable(value) and not has_grant_policy(value.get("grant_policy"))
                missing_composition = str(value.get("kind") or "").strip().lower() == "composed" and not has_complete_composition(value.get("composition"))
                if missing_summary or missing_backend or missing_output or missing_inputs or missing_effects or missing_grant or missing_composition:
                    result.append(capability_id)
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(proposal)
    return _unique(result)


def _input_contract_proposal_issues(proposal: Any, expected_capability_ids: list[str]) -> list[str]:
    """Find source-declared capabilities missing concrete structured input contracts."""
    expected = [capability_id for capability_id in _unique(expected_capability_ids) if capability_id]
    if not expected:
        return []

    contracts: dict[str, list[Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            if capability_id and isinstance(value.get("inputs"), list):
                contracts[capability_id] = value.get("inputs") or []
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    def input_is_concrete(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        name = str(value.get("input_name") or value.get("name") or "").strip()
        input_type = str(value.get("input_type") or value.get("type") or "").strip()
        summary = str(value.get("summary") or value.get("description") or "").strip()
        return bool(name and input_type and summary)

    visit(proposal)
    issues: list[str] = []
    for capability_id in expected:
        inputs = contracts.get(capability_id)
        if not inputs:
            issues.append(f"{capability_id} has no structured inputs")
            continue
        if not any(input_is_concrete(item) for item in inputs):
            issues.append(f"{capability_id} has inputs without input_name, input_type, and summary")
    return issues


def _capability_input_contracts_from_proposal(proposal: Any, expected_capability_ids: list[str]) -> dict[str, dict[str, Any]]:
    expected = set(expected_capability_ids)
    contracts: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            inputs = value.get("inputs")
            if capability_id in expected and isinstance(inputs, list):
                normalized_inputs = []
                for item in inputs:
                    if isinstance(item, dict):
                        normalized = _capability_input_from_inventory(item)
                        if normalized.get("input_name"):
                            normalized_inputs.append(normalized)
                if normalized_inputs:
                    contract = {key: item for key, item in value.items() if key != "inputs"}
                    contract["capability_id"] = capability_id
                    contract["inputs"] = normalized_inputs
                    contracts[capability_id] = contract
            for item in value.values():
                visit(item)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(proposal)
    return contracts


async def _chunked_model_input_contracts(
    *,
    project_name: str,
    project: dict[str, Any],
    params: dict[str, Any],
    deterministic: dict[str, Any],
    source_text: str,
    service_names: list[str],
    canonical_capability_inventory: list[dict[str, Any]],
    expected_capability_ids: list[str],
    clarification_answers: list[str],
    questions_for_user: list[str],
) -> dict[str, Any]:
    """Ask the model for focused input-contract chunks so large inventories are not silently dropped."""
    project_id = _required_param(params, "project_id")
    inventory_by_id = {
        str(entry.get("capability_id") or "").strip(): entry
        for entry in canonical_capability_inventory
        if str(entry.get("capability_id") or "").strip()
    }
    merged_contracts: dict[str, dict[str, Any]] = {}
    model_questions: list[str] = []
    failures: list[str] = []
    chunk_size = 6

    for index in range(0, len(expected_capability_ids), chunk_size):
        chunk_ids = expected_capability_ids[index : index + chunk_size]
        chunk_inventory = [
            inventory_by_id.get(capability_id, {"capability_id": capability_id})
            for capability_id in chunk_ids
        ]
        payload = {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "canonical_capability_inventory": chunk_inventory,
            "input_contract_focus": {
                "capability_ids": chunk_ids,
                "instruction": "Return concrete structured input contracts for every focused capability id. Do not summarize or omit any focused capability.",
            },
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        }
        try:
            model_result = await try_model_assistant_response("propose_input_contracts", payload)
        except ANIPError:
            raise
        except Exception as exc:
            detail = str(exc).strip() or exc.__class__.__name__
            raise _assistant_provider_failure(f"Assistant provider failed while drafting propose_input_contracts: {detail}") from exc
        if not model_result:
            failures.append("No model result for " + ", ".join(chunk_ids))
            continue
        issues = _input_contract_proposal_issues(model_result.get("proposal"), chunk_ids)
        if issues:
            failures.extend(issues)
            continue
        for question in model_result.get("questions_for_user") or []:
            if isinstance(question, str) and question.strip():
                model_questions.append(question.strip())
        merged_contracts.update(_capability_input_contracts_from_proposal(model_result.get("proposal"), chunk_ids))

    missing = [capability_id for capability_id in expected_capability_ids if capability_id not in merged_contracts]
    if failures or missing:
        details = failures + [f"{capability_id} has no structured inputs" for capability_id in missing]
        raise _invalid_request(
            "Assistant provider returned input-contract guidance without concrete structured capability inputs. "
            + " ".join(_unique(details)[:12])
            + ". Each focused source-declared capability must include reviewed structured inputs or the assistant must ask a precise clarification before Developer Design can proceed."
        )

    capabilities = []
    for capability_id in expected_capability_ids:
        contract = dict(merged_contracts[capability_id])
        inventory_entry = inventory_by_id.get(capability_id, {})
        if inventory_entry.get("service_id") and not contract.get("service_id"):
            contract["service_id"] = inventory_entry.get("service_id")
        capabilities.append(contract)

    summary_lines = []
    for capability in capabilities:
        input_names = [
            str(item.get("input_name") or "").strip()
            for item in capability.get("inputs") or []
            if isinstance(item, dict) and str(item.get("input_name") or "").strip()
        ]
        summary_lines.append(f"- `{capability['capability_id']}`: " + ", ".join(f"`{name}`" for name in input_names))

    return _proposal_envelope(
        title=f"Input Contract Proposal: {project_name}",
        summary="Drafted focused input contracts for the complete canonical capability inventory.",
        capability="propose_input_contracts",
        questions_for_user=_unique(model_questions)[:3] or questions_for_user,
        watchouts=[
            "These input contracts were drafted in focused chunks because the canonical inventory is larger than a single safe review unit.",
            "Review field names, required flags, semantic types, defaults, and allowed values before locking Developer Design.",
        ],
        next_steps=[
            "Accept the structured input contracts that match the intended developer surface.",
            "Edit any fields that should use implementation-owned resolver names, catalog refs, or stricter clarification behavior.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "input_contracts",
            "items": [
                _proposal_item(
                    "input-contracts-focused-canonical-inventory",
                    "Focused canonical input contracts",
                    "\n".join(summary_lines),
                    f"Drafted concrete input contracts for {len(capabilities)} canonical capability/capabilities in focused chunks.",
                    "high",
                    structured_data={"capabilities": capabilities},
                )
            ],
        },
        mode="dev",
    )


def _deterministic_service_shape(
    project_name: str,
    service_names: list[str],
    preference: dict[str, Any] | None,
    explicit_service_ids: list[str] | None = None,
    explicit_capability_ids: list[str] | None = None,
    source_capability_inventory: list[dict[str, Any]] | None = None,
    source_text: str = "",
) -> dict[str, Any]:
    source_capability_inventory = source_capability_inventory or []
    inventory_service_ids = _unique(
        [
            str(entry.get("service_id") or "").strip()
            for entry in source_capability_inventory
            if str(entry.get("service_id") or "").strip()
        ]
    )
    source_service_ids = explicit_service_ids or inventory_service_ids
    source_capability_ids = explicit_capability_ids or _unique(
        [
            str(entry.get("capability_id") or "").strip()
            for entry in source_capability_inventory
            if str(entry.get("capability_id") or "").strip()
        ]
    )
    target_count = _service_topology_target_count(preference)
    if target_count is None and preference and preference.get("preserve_source_services"):
        if source_service_ids:
            target_count = len(source_service_ids)
        elif service_names:
            target_count = len(service_names)
    if target_count is None:
        target_count = len(source_service_ids) if source_service_ids else 1

    def _display_name(identifier: str) -> str:
        return " ".join(part.capitalize() for part in re.split(r"[-_.]+", identifier) if part and part.lower() != "service") or identifier

    def _service_tokens(identifier: str) -> set[str]:
        return {
            token
            for token in re.split(r"[-_.]+", identifier.lower())
            if len(token) > 2 and token not in {"svc", "service", "services", "api"}
        }

    def _capability_tokens(identifier: str) -> set[str]:
        return {
            token
            for token in re.split(r"[-_.]+", identifier.lower())
            if len(token) > 2 and token not in {"capability", "service"}
        }

    def _assign_capabilities(service_id: str) -> list[str]:
        owned = [
            str(entry.get("capability_id") or "").strip()
            for entry in source_capability_inventory
            if str(entry.get("service_id") or "").strip() == service_id and str(entry.get("capability_id") or "").strip()
        ]
        if owned:
            return _unique(owned)
        service_tokens = _service_tokens(service_id)
        matched = [
            capability_id
            for capability_id in source_capability_ids
            if service_tokens & _capability_tokens(capability_id)
        ]
        return _unique(matched)

    def _coordination_edges_from_source(services: list[dict[str, Any]]) -> list[dict[str, str]]:
        token_stopwords = {
            "account",
            "accounts",
            "action",
            "actions",
            "capability",
            "draft",
            "message",
            "plan",
            "preparation",
            "preview",
            "review",
            "service",
            "summary",
        }
        strong_cross_service_tokens = {
            "bottleneck",
            "enrichment",
            "forecast",
            "outreach",
            "prioritization",
            "prioritize",
            "risk",
            "route",
            "routing",
            "score",
        }

        def tokens_for_text(value: str) -> set[str]:
            return {
                token
                for token in re.split(r"[^a-z0-9]+", value.lower())
                if len(token) > 2 and token not in token_stopwords
            }

        service_tokens: dict[str, set[str]] = {}
        for service in services:
            service_id = str(service.get("id") or "").strip()
            tokens = tokens_for_text(service_id + " " + str(service.get("name") or ""))
            for capability_id in service.get("capabilities") or []:
                tokens.update(tokens_for_text(str(capability_id)))
            service_tokens[service_id] = tokens

        def best_service_for_phrase(phrase: str) -> str:
            phrase_tokens = tokens_for_text(phrase)
            if not phrase_tokens:
                return ""
            ranked = sorted(
                (
                    (len(phrase_tokens & tokens), service_id)
                    for service_id, tokens in service_tokens.items()
                    if phrase_tokens & tokens
                ),
                reverse=True,
            )
            return ranked[0][1] if ranked and ranked[0][0] > 0 else ""

        def source_context_for_capability(capability_id: str) -> str:
            escaped = re.escape(capability_id)
            match = re.search(escaped, source_text)
            if not match:
                return ""
            start = max(0, match.start() - 350)
            end = min(len(source_text), match.end() + 650)
            return source_text[start:end]

        def source_marks_capability_as_cross_service(capability_id: str) -> bool:
            context = source_context_for_capability(capability_id).lower()
            if not context:
                return False
            return any(
                marker in context
                for marker in (
                    "cross-service",
                    "compose",
                    "composes",
                    "composition",
                    "selected from",
                    "provider-selected",
                    "from a bounded",
                    "from an at-risk",
                    "from a bottleneck",
                    "into a",
                    "into follow-up",
                    "into routing",
                )
            )

        edges: list[dict[str, str]] = []
        seen_edges: set[tuple[str, str]] = set()

        def add_edge(source: str, target: str, description: str) -> None:
            if not source or not target or source == target:
                return
            key = (source, target)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append(
                {
                    "from": source,
                    "to": target,
                    "relationship": "handoff",
                    "description": description,
                }
            )

        for raw_line in source_text.splitlines():
            if "->" not in raw_line:
                continue
            parts = [part.strip(" `.-") for part in raw_line.split("->") if part.strip(" `.-")]
            chain = [best_service_for_phrase(part) for part in parts]
            chain = [service_id for service_id in chain if service_id]
            for index, source in enumerate(chain):
                for target in chain[index + 1 :]:
                    add_edge(source, target, "Derived from source-declared composition or handoff language.")

        for service in services:
            owner_id = str(service.get("id") or "").strip()
            owner_domain_tokens = _service_tokens(owner_id)
            for capability_id in service.get("capabilities") or []:
                if not source_marks_capability_as_cross_service(str(capability_id)):
                    continue
                capability_tokens = tokens_for_text(str(capability_id))
                for other_id, other_tokens in service_tokens.items():
                    if other_id == owner_id:
                        continue
                    overlap = capability_tokens & (other_tokens - owner_domain_tokens)
                    if len(overlap) >= 2 or bool(overlap & strong_cross_service_tokens):
                        add_edge(other_id, owner_id, "Derived from cross-service capability naming and source-declared ownership.")

        return edges

    services: list[dict[str, Any]] = []
    for index in range(target_count):
        declared_service_id = source_service_ids[index] if index < len(source_service_ids) else ""
        name = _display_name(declared_service_id) if declared_service_id else service_names[index] if index < len(service_names) else (
            project_name if target_count == 1 else f"{project_name} Service {index + 1}"
        )
        service_id = declared_service_id or _slugify_label(name) or f"service-{index + 1}"
        capabilities = _assign_capabilities(service_id)
        services.append(
            {
                "id": service_id,
                "name": name,
                "role": "implementation service",
                "responsibilities": [
                    "Own a reviewed portion of the bounded workflow, policy checks, clarification stops, and governed response contract.",
                ],
                "capabilities": capabilities if capabilities else [
                    "answer_governed_business_question",
                    "prepare_governed_next_action",
                    "explain_governed_outcome",
                ],
                "owns_concepts": [],
            }
        )

    coordination = _coordination_edges_from_source(services) or [
        {
            "from": services[index]["id"],
            "to": services[index + 1]["id"],
            "relationship": "handoff",
            "description": "Review this generated handoff and replace it with the real implementation relationship before locking.",
        }
        for index in range(len(services) - 1)
    ]

    return {
        "name": project_name,
        "type": "multi_service" if len(services) > 1 else "single_service",
        "notes": [
            "Assistant-derived first pass. Review service boundaries before locking Developer Design.",
            "Service topology was constrained by explicit topology preference or preserved source service boundaries.",
        ],
        "services": services,
        "coordination": coordination,
        "domain_concepts": [],
    }


def _slugify_label(value: str) -> str:
    parts = _normalized_words(value)
    return "-".join(parts)[:80]


def _proposal_item(
    client_id: str,
    title: str,
    body: str,
    rationale: str,
    confidence: str = "medium",
    structured_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "client_id": client_id,
        "title": title,
        "body": body,
        "confidence": confidence,
        "rationale": rationale,
    }
    if structured_data:
        item["structured_data"] = structured_data
    return item


def _scenario_structured_data(
    *,
    name: str,
    category: str,
    narrative: str,
    actor_context: str,
    business_scope: str,
    capability: str,
    service_id: str,
    outcome_type: str,
    stop_condition: str,
) -> dict[str, Any]:
    return {
        "scenario": {
            "name": _slugify_label(name) or name,
            "category": category,
            "narrative": narrative,
            "actor_context": actor_context,
            "business_scope": business_scope,
            "time_scope": "",
            "primary_capability": capability,
            "participating_services": [service_id] if service_id else [],
            "orchestration_steps": [
                {
                    "id": f"step-{_slugify_label(capability) or 'capability'}",
                    "service_id": service_id,
                    "step_kind": "capability_execution",
                    "capability_id": capability,
                    "outcome_type": outcome_type,
                    "outcome_notes": narrative,
                    "stop_condition": stop_condition,
                }
            ],
            "expected_behavior": [narrative],
            "expected_anip_support": [
                "Return explicit governed outcomes instead of relying on hidden prompt behavior.",
                "Preserve actor, scope, clarification, approval, and audit boundaries in the runtime contract.",
            ],
        }
    }


def _patch_candidate(
    path: str,
    op: str,
    value: Any,
    rationale: str,
) -> dict[str, Any]:
    return {
        "path": path,
        "op": op,
        "value": value,
        "rationale": rationale,
    }


def _proposal_envelope(
    *,
    title: str,
    summary: str,
    capability: str,
    questions_for_user: list[str],
    watchouts: list[str],
    next_steps: list[str],
    proposal: dict[str, Any],
    mode: str = "pm",
) -> dict[str, Any]:
    return {
        "title": title,
        "summary": summary,
        "mode": mode,
        "capability": capability,
        "questions_for_user": questions_for_user,
        "watchouts": watchouts,
        "next_steps": next_steps,
        "proposal": proposal,
    }


def _pm_source_context(
    project_id: str,
    source_document_text: str,
    source_requirements_id: str | None,
    section_key: str | None = None,
) -> tuple[dict[str, Any], str, set[str], list[dict[str, Any]], int, int, list[str]]:
    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            source_requirements = (
                get_requirements(conn, project_id, source_requirements_id)
                if source_requirements_id
                else None
            )
            requirements = _safe_call(list_requirements, conn, project_id) or []
            scenarios = _safe_call(list_scenarios, conn, project_id) or []
            pm_artifacts = _safe_call(list_pm_artifacts, conn, project_id) or []
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    source_text = _requirements_source_text(source_requirements, source_document_text)
    source_text, clarification_answers = _augment_source_text_with_section_answers(
        source_text,
        pm_artifacts,
        mode="pm",
        section_key=section_key,
    )
    if not source_text:
        raise _invalid_request("Provide source_document_text or source_requirements_id")
    return project, source_text, set(_normalized_words(source_text)), pm_artifacts, len(requirements), len(scenarios), clarification_answers


def _dev_source_context(
    project_id: str,
    source_document_text: str,
    source_requirements_id: str | None,
    source_shape_id: str | None,
    section_key: str | None = None,
) -> tuple[dict[str, Any], str, set[str], list[dict[str, Any]], int, int, int, list[str], list[str]]:
    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            source_requirements = (
                get_requirements(conn, project_id, source_requirements_id)
                if source_requirements_id
                else None
            )
            source_shape = (
                get_shape(conn, project_id, source_shape_id)
                if source_shape_id
                else None
            )
            requirements = _safe_call(list_requirements, conn, project_id) or []
            scenarios = _safe_call(list_scenarios, conn, project_id) or []
            shapes = _safe_call(list_shapes, conn, project_id) or []
            pm_artifacts = _safe_call(list_pm_artifacts, conn, project_id) or []
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    requirements_text = _requirements_source_text(source_requirements, "") if source_requirements else ""
    shape_data = ((source_shape or {}).get("data") or {}).get("shape") if isinstance(source_shape, dict) else None
    if not isinstance(shape_data, dict):
        shape_data = (source_shape or {}).get("data") if isinstance(source_shape, dict) else None
    shape_services = shape_data.get("services") if isinstance(shape_data, dict) else None
    service_names = [
        str(service.get("name") or service.get("id") or "").strip()
        for service in (shape_services or [])
        if isinstance(service, dict)
    ]
    service_names = [name for name in service_names if name]
    shape_capability_ids = _service_shape_capability_ids(shape_data)

    source_text = " ".join(part for part in [requirements_text, source_document_text] if part.strip()).strip()
    if shape_capability_ids:
        locked_inventory = (
            "The locked service capability inventory is canonical for Developer Design and must be preserved exactly: "
            + ", ".join(f"`{capability_id}`" for capability_id in shape_capability_ids)
            + "."
        )
        source_text = " ".join(part for part in [source_text, locked_inventory] if part.strip()).strip()
    source_text, clarification_answers = _augment_source_text_with_section_answers(
        source_text,
        pm_artifacts,
        mode="dev",
        section_key=section_key,
    )
    if not source_text and not service_names:
        raise _invalid_request("Provide source_document_text, source_requirements_id, or source_shape_id")

    return (
        project,
        source_text,
        set(_normalized_words(source_text)),
        pm_artifacts,
        len(requirements),
        len(scenarios),
        len(shapes),
        service_names,
        clarification_answers,
    )


def _requirements_source_text(
    source_requirements: dict[str, Any] | None,
    source_document_text: str,
) -> str:
    if source_document_text.strip():
        return source_document_text.strip()
    if not source_requirements:
        return ""
    source_data = source_requirements.get("data") or {}
    business_spec = source_data.get("business_spec") or {}
    summary = _string_value(business_spec.get("summary"), "")
    goals = "; ".join(_string_list(business_spec.get("business_goal", [])))
    non_goals = "; ".join(_string_list(business_spec.get("non_goals", [])))
    parts = [summary]
    if goals:
        parts.append(f"Business goals: {goals}")
    if non_goals:
        parts.append(f"Non-goals: {non_goals}")
    return " ".join(part for part in parts if part).strip()


def _missing_business_questions_from_words(words: set[str]) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    if not _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        questions.append(
            {
                "question_id": "missing-approval-posture",
                "prompt": "When should the system stop for approval instead of continuing automatically?",
                "why_it_matters": "Generation and verification need explicit approval boundaries for side-effecting or high-impact flows.",
                "target_artifact": "permission_intent",
            }
        )
    if not _contains_any(words, "region", "scope", "tenant", "segment", "team", "owner"):
        questions.append(
            {
                "question_id": "missing-scope-boundary",
                "prompt": "What business scope boundaries must the system preserve, such as region, tenant, team, or ownership?",
                "why_it_matters": "Without explicit scope constraints, Developer Design cannot produce correct runtime policy bindings or bounded access behavior.",
                "target_artifact": "business_areas",
            }
        )
    if not _contains_any(words, "quarter", "month", "period", "window", "date", "time"):
        questions.append(
            {
                "question_id": "missing-time-scope",
                "prompt": "Are there explicit time windows or reporting periods the product must preserve?",
                "why_it_matters": "Time boundaries often become required capability inputs and verification constraints.",
                "target_artifact": "success_criteria",
            }
        )
    if not _contains_any(words, "actor", "manager", "analyst", "user", "operator", "team"):
        questions.append(
            {
                "question_id": "missing-actor-model",
                "prompt": "Who are the distinct actors or user roles that need different visibility, authority, or workflow behavior?",
                "why_it_matters": "Actor differences drive PM review, developer formalization, runtime policy bindings, and verification.",
                "target_artifact": "actor_model",
            }
        )
    return questions


def _pm_question_family_candidates(words: set[str]) -> list[str]:
    families: list[str] = []
    if _contains_any(words, "risk", "health", "exposure", "warning", "issue"):
        families.append("Risk and health review")
    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        families.append("Approval and escalation guidance")
    if _contains_any(words, "coverage", "territory", "scope", "region", "owner"):
        families.append("Coverage and ownership questions")
    if _contains_any(words, "forecast", "trend", "plan", "quarter", "month", "period"):
        families.append("Forecast and planning questions")
    if not families:
        families.extend([
            "Operational review questions",
            "Actor-specific guidance questions",
        ])
    return families[:3]


def _pm_business_area_entries(words: set[str]) -> list[dict[str, str]]:
    entries = [
        {
            "business_area_id": "core_workflow",
            "label": "Core Workflow",
            "description": "The main bounded user or business workflow the product exists to support.",
        }
    ]
    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation", "review"):
        entries.append(
            {
                "business_area_id": "governance_review",
                "label": "Governance Review",
                "description": "Approval, review, and stop-condition handling that should remain governed and explicit.",
            }
        )
    else:
        entries.append(
            {
                "business_area_id": "decision_support",
                "label": "Decision Support",
                "description": "Guided recommendations or bounded answers that help users decide what to do next.",
            }
        )
    return entries[:3]


def _fronting_domain_from_capability_ids(capability_ids: list[str]) -> str:
    prefixes: list[str] = []
    for capability_id in capability_ids:
        prefix = capability_id.split(".", 1)[0].strip().lower().replace("-", "_")
        if prefix:
            prefixes.append(prefix)
    if not prefixes:
        return ""
    return max(_unique(prefixes), key=prefixes.count)


def _fronting_domain_from_source(source_text: str) -> str:
    return _fronting_domain_from_capability_ids(_explicit_capability_ids(source_text))


def _source_describes_governed_fronting(source_text: str, words: set[str]) -> bool:
    capability_ids = _explicit_capability_ids(source_text)
    if not capability_ids:
        return False
    normalized = " ".join(source_text.lower().split())
    return (
        "fronting" in words
        or "backend" in words
        or "mcp" in words
        or "rest" in words
        or "raw api" in normalized
        or "raw backend" in normalized
        or "native api" in normalized
    )


def _fronting_actor_entries(source_text: str, words: set[str]) -> list[dict[str, str]]:
    if not _source_describes_governed_fronting(source_text, words):
        return []
    domain = _fronting_domain_from_source(source_text)
    if not domain:
        return []
    title = _title_from_actor_id(domain)
    return [
        {
            "actor_id": f"{domain}_requester",
            "title": f"{title} Requester",
            "summary": f"Business user requesting bounded {title} context, prepared previews, or governed change requests.",
            "visibility_expectations": "Can inspect bounded context inside actor-visible project, workspace, or resource scope; must not receive raw exports or unrestricted backend data.",
            "action_expectations": "Can request read-oriented context and prepared change previews, but cannot bypass clarification, approval, or denial boundaries.",
            "approval_expectations": "Can initiate approval-gated requests; approval-sensitive backend changes must stop for an authorized approver.",
            "notes": "Derived from governed fronting source evidence. Tighten actor names during PM review if the product uses more specific business roles.",
        },
        {
            "actor_id": f"{domain}_approver",
            "title": f"{title} Approver",
            "summary": f"Authorized reviewer for governed {title} change requests and policy evidence.",
            "visibility_expectations": "Can inspect the bounded request preview, policy reason, and audit evidence needed to approve or reject governed changes.",
            "action_expectations": "Can review approval-stopped requests and decide whether the backend change may proceed under policy.",
            "approval_expectations": "Owns the explicit approval boundary for governed write-adjacent or state-changing requests.",
            "notes": "Derived from governed fronting source evidence. Replace with the exact approving role if the organization has a narrower authority model.",
        },
    ]


def _source_business_area_entry(area_id: str) -> dict[str, str]:
    return {
        "business_area_id": area_id,
        "label": _title_from_actor_id(area_id),
        "description": "Source-declared business area. Preserve this identifier unless PM review intentionally renames the responsibility boundary.",
    }


def _fronting_business_area_entries(source_text: str, words: set[str]) -> list[dict[str, str]]:
    if not _source_describes_governed_fronting(source_text, words):
        return []
    domain = _fronting_domain_from_source(source_text)
    if not domain:
        return []
    capability_ids = _explicit_capability_ids(source_text)
    cap_words = set(_normalized_words(" ".join(capability_ids)))
    subject = "issue" if "issue" in cap_words or "ticket" in cap_words else "work"
    entries = [
        {
            "business_area_id": f"{domain}_context_access",
            "label": f"{_title_from_actor_id(domain)} Context Access",
            "description": "Bounded read-only backend context inside allowed actor-visible scope, without raw export or unrestricted discovery.",
        }
    ]
    if any(term in cap_words for term in ("prepare", "draft", "notes", "comment", "story", "subtask", "bug")):
        entries.append(
            {
                "business_area_id": f"{domain}_{subject}_preparation",
                "label": f"{_title_from_actor_id(domain)} {_title_from_actor_id(subject)} Preparation",
                "description": "Prepared previews and draft artifacts that do not directly mutate the backend system.",
            }
        )
    if any(term in cap_words for term in ("request", "transition", "move", "assignee", "link", "assign", "change")):
        entries.append(
            {
                "business_area_id": f"{domain}_governed_change_requests",
                "label": f"{_title_from_actor_id(domain)} Governed Change Requests",
                "description": "Write-adjacent or state-changing requests that must preserve preview, approval, denial, and audit boundaries.",
            }
        )
    if _contains_any(words, "audit", "policy", "approval", "approve", "evidence", "denied", "deny"):
        entries.append(
            {
                "business_area_id": f"{domain}_policy_and_audit",
                "label": f"{_title_from_actor_id(domain)} Policy And Audit",
                "description": "Policy reason, approval evidence, denial reason, and audit trail expectations for governed backend access.",
            }
        )
    return entries[:6]


def _fronting_permission_rule_values(actor_ids: list[str], business_area_ids: list[str]) -> list[dict[str, str]]:
    requester_id = next((actor_id for actor_id in actor_ids if actor_id.endswith("_requester")), "")
    approver_id = next((actor_id for actor_id in actor_ids if actor_id.endswith("_approver")), "")
    context_area = next((area_id for area_id in business_area_ids if area_id.endswith("_context_access")), "")
    preparation_area = next((area_id for area_id in business_area_ids if area_id.endswith("_preparation")), "")
    change_area = next((area_id for area_id in business_area_ids if area_id.endswith("_governed_change_requests")), "")
    audit_area = next((area_id for area_id in business_area_ids if area_id.endswith("_policy_and_audit")), "")
    if not requester_id or not approver_id or not context_area:
        return []

    rules: list[dict[str, str]] = [
        {
            "actor_id": requester_id,
            "business_area": context_area,
            "access_posture": "bounded",
            "governed_outcome_type": "bounded_result",
            "governed_outcome": "Return bounded actor-visible backend context without exposing raw export, private scope, or unrestricted backend query behavior.",
            "notes": "Read-oriented fronting access remains scoped to allowed resources and reviewed visibility policy.",
        },
    ]
    if preparation_area:
        rules.append(
            {
                "actor_id": requester_id,
                "business_area": preparation_area,
                "access_posture": "bounded",
                "governed_outcome_type": "bounded_result",
                "governed_outcome": "Return a prepared preview or draft artifact without mutating the backend system.",
                "notes": "Preparation capabilities may produce reviewable content, but direct backend writes remain outside this bounded outcome.",
            }
        )
    if change_area:
        rules.extend(
            [
                {
                    "actor_id": requester_id,
                    "business_area": change_area,
                    "access_posture": "approval_required",
                    "governed_outcome_type": "approval_stop",
                    "governed_outcome": "Prepare the governed change request and stop for explicit approval before backend mutation or external dispatch.",
                    "notes": "Write-adjacent or state-changing fronting requests must not execute automatically.",
                },
                {
                    "actor_id": requester_id,
                    "business_area": change_area,
                    "access_posture": "restricted",
                    "governed_outcome_type": "clarification_required",
                    "governed_outcome": "Ask for missing scope, target, relationship, or requested state instead of guessing backend arguments.",
                    "notes": "Clarification is required when semantic inputs or actor-visible scope are incomplete.",
                },
                {
                    "actor_id": requester_id,
                    "business_area": change_area,
                    "access_posture": "denied",
                    "governed_outcome_type": "deny_request",
                    "governed_outcome": "Deny unapproved mutation, workflow bypass, private-scope exfiltration, or direct raw backend execution.",
                    "notes": "Denial remains a first-class business outcome rather than an implementation error.",
                },
                {
                    "actor_id": approver_id,
                    "business_area": change_area,
                    "access_posture": "bounded",
                    "governed_outcome_type": "bounded_result",
                    "governed_outcome": "Review the prepared change request, policy reason, and bounded evidence before approving or rejecting.",
                    "notes": "Approver authority is limited to reviewed governed requests.",
                },
            ]
        )
    rules.append(
        {
            "actor_id": requester_id,
            "business_area": context_area,
            "access_posture": "denied",
            "governed_outcome_type": "deny_request",
            "governed_outcome": "Deny raw export, unrestricted dumps, private resource exfiltration, and overbroad context access.",
            "notes": "Read-oriented fronting access must still deny requests outside the bounded product contract.",
        }
    )
    if audit_area:
        rules.append(
            {
                "actor_id": approver_id,
                "business_area": audit_area,
                "access_posture": "bounded",
                "governed_outcome_type": "bounded_result",
                "governed_outcome": "Inspect approval, denial, clarification, actor, policy, and audit evidence for governed backend interactions.",
                "notes": "Audit visibility is review-oriented and should not grant broader backend access by itself.",
            }
        )
    return rules


def _title_from_actor_id(actor_id: str) -> str:
    return " ".join(part for part in actor_id.replace("-", "_").split("_") if part).title()


_RESERVED_ACTOR_IDS = {
    "allowed",
    "bounded",
    "restricted",
    "denied",
    "approval_required",
    "approval_stop",
    "clarification_required",
    "direct_result",
    "bounded_result",
    "masked_or_restricted_result",
    "deny_request",
    "success",
    "available",
    "completed",
    "failed",
    "unsupported",
}


def _is_valid_actor_id(value: Any) -> bool:
    actor_id = str(value or "").strip().lower().replace("-", "_")
    return bool(actor_id) and actor_id not in _RESERVED_ACTOR_IDS


def _source_declared_actor_ids(source_text: str) -> list[str]:
    actor_section_terms = ("actor", "actors", "user", "users", "role", "roles", "persona", "personas")
    ids: list[str] = []
    in_actor_section = False
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            heading_words = set(_normalized_words(heading.group(1)))
            in_actor_section = bool(heading_words.intersection(actor_section_terms))
            continue
        if not in_actor_section:
            label = line.rstrip(":").lower()
            if any(term in label for term in ("actor", "user", "role", "persona")):
                in_actor_section = True
            else:
                continue
        for match in re.finditer(r"`([a-z][a-z0-9]*(?:[_-][a-z0-9]+)+)`", line):
            value = match.group(1).strip().lower().replace("-", "_")
            if value and _is_valid_actor_id(value) and "." not in value and not value.endswith("_service"):
                ids.append(value)
        bullet = re.match(r"^[-*]\s+([a-z][a-z0-9]*(?:[_-][a-z0-9]+)+)(?:\s|$)", line)
        if bullet:
            value = bullet.group(1).strip().lower().replace("-", "_")
            if value and _is_valid_actor_id(value) and "." not in value and not value.endswith("_service"):
                ids.append(value)
    return _unique(ids)[:8]


def _source_declared_business_area_ids(source_text: str) -> list[str]:
    area_section_terms = ("area", "areas", "business area", "business areas", "scope", "scopes")
    ids: list[str] = []
    in_area_section = False
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            normalized_heading = " ".join(_normalized_words(heading.group(1)))
            in_area_section = any(term in normalized_heading for term in area_section_terms)
            continue
        if not in_area_section:
            normalized_label = " ".join(_normalized_words(line.rstrip(":")))
            if any(term in normalized_label for term in area_section_terms):
                in_area_section = True
            else:
                continue
        for match in re.finditer(r"`([a-z][a-z0-9]*(?:[_-][a-z0-9]+)+)`", line):
            value = match.group(1).strip().lower().replace("-", "_")
            if value and "." not in value and not value.endswith("_service"):
                ids.append(value)
        bullet = re.match(r"^[-*]\s+([a-z][a-z0-9]*(?:[_-][a-z0-9]+)+)(?:\s|$)", line)
        if bullet:
            value = bullet.group(1).strip().lower().replace("-", "_")
            if value and "." not in value and not value.endswith("_service"):
                ids.append(value)
    return _unique(ids)[:12]


def _source_actor_entry(actor_id: str) -> dict[str, str]:
    title = _title_from_actor_id(actor_id)
    return {
        "actor_id": actor_id,
        "title": title,
        "summary": f"Source-declared actor family: {title}.",
        "visibility_expectations": "Use the source document and Permission Intent to define what this actor can see; do not broaden visibility beyond reviewed scope.",
        "action_expectations": "Use the source document and scenarios to define what this actor can request; unclear actions should remain review questions.",
        "approval_expectations": "Use Permission Intent to decide whether this actor can approve, must request approval, or must be denied for outcomes that require approval.",
        "notes": "Preserved from an explicit source-declared actor list. Tighten visibility, action, and approval differences during PM review.",
    }


def _pm_actor_entries(source_text: str, words: set[str]) -> list[dict[str, str]]:
    source_actor_ids = _source_declared_actor_ids(source_text)
    if source_actor_ids:
        return [_source_actor_entry(actor_id) for actor_id in source_actor_ids]
    fronting_actors = _fronting_actor_entries(source_text, words)
    if fronting_actors:
        return fronting_actors
    actors = [
        {
            "actor_id": "primary_operator",
            "title": "Primary Operator",
            "summary": "The main user who asks the recurring business questions this product is meant to support.",
            "visibility_expectations": "Can inspect the bounded answers and evidence needed to do daily work.",
            "action_expectations": "Can request guidance, summaries, or prepared recommendations within the governed product boundary.",
            "approval_expectations": "Can proceed directly with read-oriented or low-risk tasks but should stop when the product reaches a governed approval boundary.",
            "notes": "Treat this as the default PM-facing actor unless the business brief names a clearer role.",
        }
    ]
    if _contains_any(words, "approval", "approve", "approved", "manager", "review", "escalation"):
        actors.append(
            {
                "actor_id": "reviewing_manager",
                "title": "Reviewing Manager",
                "summary": "A review-oriented actor who approves governed outcomes before the system continues.",
                "visibility_expectations": "Can inspect broader context, rationale, and approval evidence than the default operator.",
                "action_expectations": "Can review prepared outcomes, approve them, or send them back for clarification.",
                "approval_expectations": "Acts as the explicit approval boundary when the product should not continue automatically.",
                "notes": "Use this actor when the business brief implies review or escalation behavior.",
            }
        )
    return actors


def _string_value(value: Any, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return default


def _merged_string_list(value: Any, fallback: list[str], *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return fallback[:limit]
    merged = [str(item).strip() for item in value if str(item).strip()]
    return merged[:limit] or fallback[:limit]


def _merge_intent_interpretation(
    fallback: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    shape_type = str(candidate.get("recommended_shape_type", "")).strip().lower()
    if shape_type not in {"single_service", "multi_service"}:
        shape_type = fallback["recommended_shape_type"]

    return {
        "title": _string_value(candidate.get("title"), fallback["title"]),
        "summary": _string_value(candidate.get("summary"), fallback["summary"]),
        "recommended_shape_type": shape_type,
        "recommended_shape_reason": _string_value(
            candidate.get("recommended_shape_reason"),
            fallback["recommended_shape_reason"],
        ),
        "requirements_focus": _merged_string_list(
            candidate.get("requirements_focus"),
            fallback["requirements_focus"],
            limit=5,
        ),
        "scenario_starters": _merged_string_list(
            candidate.get("scenario_starters"),
            fallback["scenario_starters"],
            limit=5,
        ),
        "domain_concepts": _merged_string_list(
            candidate.get("domain_concepts"),
            fallback["domain_concepts"],
            limit=6,
        ),
        "service_suggestions": _merged_string_list(
            candidate.get("service_suggestions"),
            fallback["service_suggestions"],
            limit=5,
        ),
        "next_steps": _merged_string_list(
            candidate.get("next_steps"),
            fallback["next_steps"],
            limit=5,
        ),
    }


def _merge_explanation(
    fallback: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": _string_value(candidate.get("title"), fallback["title"]),
        "summary": _string_value(candidate.get("summary"), fallback["summary"]),
        "focused_answer": _string_value(
            candidate.get("focused_answer"),
            fallback.get("focused_answer") or fallback["summary"],
        ),
        "action_label": _string_value(candidate.get("action_label"), fallback.get("action_label", "")) or None,
        "action_path": _string_value(candidate.get("action_path"), fallback.get("action_path", "")) or None,
        "highlights": _merged_string_list(candidate.get("highlights"), fallback["highlights"], limit=4),
        "watchouts": _merged_string_list(candidate.get("watchouts"), fallback["watchouts"], limit=4),
        "next_steps": _merged_string_list(candidate.get("next_steps"), fallback["next_steps"], limit=4),
    }


def _pm_artifact_type_present(pm_artifacts: list[dict[str, Any]], artifact_type: str) -> bool:
    return any(str((artifact.get("data") or {}).get("artifact_type") or "") == artifact_type for artifact in pm_artifacts)


def _assistant_action(label: str, path: str) -> dict[str, str]:
    return {
        "action_label": label,
        "action_path": path,
    }


def _pm_artifact_data(pm_artifacts: list[dict[str, Any]], artifact_type: str) -> dict[str, Any] | None:
    for artifact in pm_artifacts:
        data = artifact.get("data") or {}
        if str(data.get("artifact_type") or "") == artifact_type:
            return data if isinstance(data, dict) else None
    return None


def _latest_pm_artifact_data(pm_artifacts: list[dict[str, Any]], artifact_type: str) -> dict[str, Any] | None:
    candidates = [
        artifact
        for artifact in pm_artifacts
        if str(((artifact.get("data") or {}) if isinstance(artifact.get("data"), dict) else {}).get("artifact_type") or "") == artifact_type
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda artifact: str(artifact.get("updated_at") or artifact.get("created_at") or ""), reverse=True)
    data = candidates[0].get("data") or {}
    return data if isinstance(data, dict) else None


def _agent_consumption_simulation_evidence(pm_artifacts: list[dict[str, Any]]) -> dict[str, Any] | None:
    report = _latest_pm_artifact_data(pm_artifacts, "agent_consumption_simulation_report")
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    cases = report.get("cases") if isinstance(report.get("cases"), list) else []
    failed_cases = [
        {
            "probe_id": case.get("probe_id"),
            "expected_outcome": case.get("expected_outcome"),
            "actual_outcome": case.get("actual_outcome"),
            "selected_capability_id": case.get("selected_capability_id"),
            "expected_capability_id": case.get("expected_capability_id"),
            "failures": case.get("failures") if isinstance(case.get("failures"), list) else [],
            "parameter_plan": case.get("parameter_plan") if isinstance(case.get("parameter_plan"), dict) else {},
            "used_consumability_hints": case.get("used_consumability_hints") if isinstance(case.get("used_consumability_hints"), list) else [],
            "rationale": case.get("rationale"),
        }
        for case in cases
        if isinstance(case, dict) and case.get("status") == "fail"
    ]
    return {
        "status": report.get("status"),
        "generated_at": report.get("generated_at"),
        "summary": summary,
        "failed_cases": failed_cases[:8],
        "simulator_runtime": report.get("simulator_runtime") if isinstance(report.get("simulator_runtime"), dict) else {},
    }


def _simulator_failure_fix_step(case: dict[str, Any]) -> str:
    probe_id = str(case.get("probe_id") or "failed probe")
    expected_outcome = str(case.get("expected_outcome") or "unknown")
    actual_outcome = str(case.get("actual_outcome") or "unknown")
    expected_capability = str(case.get("expected_capability_id") or "").strip()
    selected_capability = str(case.get("selected_capability_id") or "").strip()
    failures = case.get("failures") if isinstance(case.get("failures"), list) else []
    failure_text = "; ".join(str(item) for item in failures[:2] if str(item).strip())
    owner_fix = _simulator_failure_owner_fix(
        expected_outcome=expected_outcome,
        actual_outcome=actual_outcome,
        expected_capability=expected_capability,
        selected_capability=selected_capability,
        failure_text=failure_text,
    )
    capability_text = ""
    if expected_capability and selected_capability and selected_capability != expected_capability:
        capability_text = f" Expected capability `{expected_capability}`, simulator selected `{selected_capability}`."
    elif expected_capability:
        capability_text = f" Target capability `{expected_capability}`."
    detail = f" {failure_text}" if failure_text else ""
    return (
        f"Fix failed probe `{probe_id}`: expected `{expected_outcome}`, simulated `{actual_outcome}`."
        f"{capability_text}{detail} {owner_fix}"
    )


def _simulator_failure_owner_fix(
    *,
    expected_outcome: str,
    actual_outcome: str,
    expected_capability: str,
    selected_capability: str,
    failure_text: str,
) -> str:
    normalized = f"{expected_outcome} {actual_outcome} {failure_text}".lower()
    capability_mismatch = bool(expected_capability and selected_capability and expected_capability != selected_capability)
    if expected_outcome == "approval_required" or "approval" in normalized:
        return (
            "Review Developer Definition approval boundary: add explicit approval-preview business effects/grant policy, "
            "or rewrite the capability so it is clearly read-only."
        )
    if expected_outcome == "clarification_required" or "clarification" in normalized:
        return (
            "Review required context/clarification behavior: declare the missing input, entity-reference semantics, "
            "or mark the target selection as explicit app glue."
        )
    if expected_outcome == "unsupported" or "unsupported" in normalized:
        return (
            "Review business effects/unsupported boundary metadata: declare what the package does not produce "
            "so the consuming app rejects the request before invocation."
        )
    if capability_mismatch:
        return (
            "Review intent ownership and consumability metadata: either tighten capability descriptions/effects "
            "or add reviewed app-glue guidance so the app selects the intended capability."
        )
    return (
        "Classify this as contract metadata, explicit app glue, service behavior, or acceptable limitation; "
        "then update the owning artifact before rerunning the simulator."
    )


def _has_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_non_empty_list(values: Any) -> bool:
    return isinstance(values, list) and any(_has_non_empty_string(item) for item in values)


def _safe_call(func: Any, *args: Any) -> Any:
    try:
        return func(*args)
    except Exception:
        return None


def _product_summary_complete(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    return (
        _has_non_empty_string(data.get("product_purpose"))
        and _has_non_empty_string(data.get("business_problem"))
        and _has_non_empty_list(data.get("business_goals"))
        and _has_non_empty_list(data.get("supported_question_families"))
        and _has_non_empty_string(data.get("governed_behavior_summary"))
        and _has_non_empty_string(data.get("approval_posture_summary"))
    )


def _actor_model_complete(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    actors = data.get("actors")
    if not isinstance(actors, list):
        return False
    return any(
        isinstance(actor, dict)
        and _has_non_empty_string(actor.get("actor_id"))
        and _is_valid_actor_id(actor.get("actor_id"))
        and _has_non_empty_string(actor.get("title"))
        and _has_non_empty_string(actor.get("summary"))
        for actor in actors
    )


def _business_areas_complete(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    entries = data.get("entries")
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(entry, dict)
        and _has_non_empty_string(entry.get("business_area_id"))
        and _has_non_empty_string(entry.get("label"))
        for entry in entries
    )


_PERMISSION_INTENT_FALLBACK_REVIEW_SOURCE = "studio_fallback_needs_review"
_PERMISSION_INTENT_FALLBACK_REVIEW_NOTE = "Studio-derived review candidate because the assistant produced a policy summary but no concrete actor-by-business-area rules."


def _is_permission_intent_fallback_rule(rule: dict[str, Any]) -> bool:
    return (
        str(rule.get("review_source") or "").strip() == _PERMISSION_INTENT_FALLBACK_REVIEW_SOURCE
        or _PERMISSION_INTENT_FALLBACK_REVIEW_NOTE in str(rule.get("notes") or "")
    )


def _permission_intent_complete(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    rules = data.get("rules")
    if not _has_non_empty_string(data.get("policy_summary")) or not isinstance(rules, list):
        return False
    return any(
        isinstance(rule, dict)
        and not _is_permission_intent_fallback_rule(rule)
        and _has_non_empty_string(rule.get("actor_id"))
        and _has_non_empty_string(rule.get("business_area"))
        and _has_non_empty_string(rule.get("access_posture"))
        and _has_non_empty_string(rule.get("governed_outcome_type"))
        and _has_non_empty_string(rule.get("governed_outcome"))
        for rule in rules
    )


def _non_goals_complete(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    entries = data.get("entries")
    if not isinstance(entries, list):
        return False
    return any(isinstance(entry, dict) and _has_non_empty_string(entry.get("statement")) for entry in entries)


def _success_criteria_complete(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    entries = data.get("entries")
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(entry, dict)
        and _has_non_empty_string(entry.get("statement"))
        and _has_non_empty_string(entry.get("evidence"))
        for entry in entries
    )


def _product_design_sufficiency(project_id: str, project: dict[str, Any], pm_artifacts: list[dict[str, Any]], requirements_count: int, scenarios_count: int) -> list[dict[str, Any]]:
    summary = _pm_artifact_data(pm_artifacts, "product_summary")
    actors = _pm_artifact_data(pm_artifacts, "actor_model")
    business_areas = _pm_artifact_data(pm_artifacts, "business_areas")
    permissions = _pm_artifact_data(pm_artifacts, "permission_intent")
    non_goals = _pm_artifact_data(pm_artifacts, "non_goals")
    success_criteria = _pm_artifact_data(pm_artifacts, "success_criteria")
    documents_count = int(project.get("documents_count") or 0)
    source_signal = documents_count > 0 or requirements_count > 0 or scenarios_count > 0

    actor_ready = _actor_model_complete(actors)
    areas_ready = _business_areas_complete(business_areas)

    cards = [
        {
            "key": "product_summary",
            "title": "Business Summary",
            "path": f"/design/projects/{project_id}/product-summary",
            "ready": _product_summary_complete(summary),
            "has_draft": isinstance(summary, dict),
            "draftable": source_signal,
            "questions": [
                "What is the product trying to accomplish?" if not _has_non_empty_string((summary or {}).get("product_purpose")) else None,
                "What business problem is it solving?" if not _has_non_empty_string((summary or {}).get("business_problem")) else None,
                "Which business goals must Studio preserve?" if not _has_non_empty_list((summary or {}).get("business_goals")) else None,
            ],
        },
        {
            "key": "actor_model",
            "title": "Actor Model",
            "path": f"/design/projects/{project_id}/actor-model",
            "ready": actor_ready,
            "has_draft": isinstance(actors, dict),
            "draftable": source_signal or _product_summary_complete(summary),
            "questions": [
                "Which distinct actors need separate treatment?" if not actor_ready else None,
                "What does each actor actually want to see or do?" if not actor_ready else None,
            ],
        },
        {
            "key": "business_areas",
            "title": "Business Areas",
            "path": f"/design/projects/{project_id}/business-areas",
            "ready": areas_ready,
            "has_draft": isinstance(business_areas, dict),
            "draftable": source_signal or requirements_count > 0 or scenarios_count > 0,
            "questions": [
                "Which stable business-area ids should downstream policy reuse?" if not areas_ready else None,
            ],
        },
        {
            "key": "permission_intent",
            "title": "Permission Intent",
            "path": f"/design/projects/{project_id}/permission-intent",
            "ready": _permission_intent_complete(permissions),
            "has_draft": isinstance(permissions, dict),
            "draftable": actor_ready and areas_ready,
            "questions": [
                "Finish the Actor Model first so access posture can bind to real actors." if not actor_ready else None,
                "Finish Business Areas first so permission rules bind to stable scopes." if not areas_ready else None,
                "Where should the system allow, restrict, clarify, deny, or stop for approval?" if actor_ready and areas_ready and not _permission_intent_complete(permissions) else None,
            ],
        },
        {
            "key": "non_goals",
            "title": "Non-Goals",
            "path": f"/design/projects/{project_id}/non-goals",
            "ready": _non_goals_complete(non_goals),
            "has_draft": isinstance(non_goals, dict),
            "draftable": source_signal or requirements_count > 0,
            "questions": [
                "What should the product explicitly not do?" if not _non_goals_complete(non_goals) else None,
            ],
        },
        {
            "key": "success_criteria",
            "title": "Success Criteria",
            "path": f"/design/projects/{project_id}/success-criteria",
            "ready": _success_criteria_complete(success_criteria),
            "has_draft": isinstance(success_criteria, dict),
            "draftable": source_signal or _product_summary_complete(summary),
            "questions": [
                "What business outcomes will prove this product is working?" if not _success_criteria_complete(success_criteria) else None,
                "What evidence should PM review to confirm success?" if not _success_criteria_complete(success_criteria) else None,
            ],
        },
    ]

    for card in cards:
        card["questions"] = [question for question in card["questions"] if question]
        clarification_resolved = _has_saved_section_clarification(pm_artifacts, "pm", str(card["key"]))
        if card["ready"]:
            card["status"] = "ready"
        elif clarification_resolved:
            card["status"] = "draftable"
            card["detail"] = f"{card['title']} has saved clarification answers. Rerun the draft step to fold them into the canonical artifact."
            card["questions"] = []
        elif card["has_draft"] and card["questions"]:
            card["status"] = "needs_clarification"
        elif card["draftable"]:
            card["status"] = "draftable"
        else:
            card["status"] = "blocked"
    return cards


def _developer_definition_sufficiency(
    project_id: str,
    pm_artifacts: list[dict[str, Any]],
    requirements_count: int,
    scenarios_count: int,
    shapes_count: int,
) -> list[dict[str, Any]]:
    has_baseline = _pm_artifact_type_present(pm_artifacts, "developer_baseline")
    has_definition = _pm_artifact_type_present(pm_artifacts, "developer_definition")
    summary_data = _pm_artifact_data(pm_artifacts, "product_summary")
    actor_data = _pm_artifact_data(pm_artifacts, "actor_model")
    business_area_data = _pm_artifact_data(pm_artifacts, "business_areas")
    permission_data = _pm_artifact_data(pm_artifacts, "permission_intent")
    non_goal_data = _pm_artifact_data(pm_artifacts, "non_goals")
    success_data = _pm_artifact_data(pm_artifacts, "success_criteria")
    capability_input_evidence_ready = _has_concrete_capability_input_evidence(pm_artifacts)
    summary_ready = _product_summary_complete(summary_data)
    actor_ready = _actor_model_complete(actor_data)
    areas_ready = _business_areas_complete(business_area_data)
    permissions_ready = _permission_intent_complete(permission_data)
    non_goals_ready = _non_goals_complete(non_goal_data)
    success_ready = _success_criteria_complete(success_data)
    summary_present = isinstance(summary_data, dict)
    actor_present = isinstance(actor_data, dict)
    areas_present = isinstance(business_area_data, dict)
    permissions_present = isinstance(permission_data, dict)
    non_goals_present = isinstance(non_goal_data, dict)
    success_present = isinstance(success_data, dict)

    requirements_ready = requirements_count > 0
    scenarios_ready = scenarios_count > 0
    shape_ready = shapes_count > 0

    cards = [
        {
            "key": "service_identity_topology",
            "title": "Service Identity & Topology",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and shape_ready,
            "questions": [
                "Which service design should Developer Design formalize?" if not shape_ready else None,
            ],
        },
        {
            "key": "capability_contracts",
            "title": "Capability Contracts",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and requirements_ready and scenarios_ready and shape_ready,
            "has_partial": shape_ready and not capability_input_evidence_ready,
            "questions": [
                "Which requirements set should the developer contract preserve?" if not requirements_ready else None,
                "Which concrete scenarios should capability behavior reflect?" if not scenarios_ready else None,
                "Which service design owns those capabilities?" if not shape_ready else None,
                "What are the reviewed implementation input names, types, required flags, defaults, and allowed values for each source-owned capability?" if shape_ready and not capability_input_evidence_ready else None,
            ],
        },
        {
            "key": "authority_and_approval",
            "title": "Authority & Approval",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and requirements_ready and scenarios_ready and shape_ready,
            "has_partial": (actor_present and not actor_ready) or (areas_present and not areas_ready) or (permissions_present and not permissions_ready),
            "questions": [
                "Which actors need distinct authority or visibility handling?" if actor_present and not actor_ready else None,
                "Which business areas should runtime policy bind to?" if areas_present and not areas_ready else None,
                "Where should the runtime allow, restrict, clarify, deny, or stop for approval?" if permissions_present and not permissions_ready else None,
            ],
        },
        {
            "key": "data_contracts",
            "title": "Data Contracts",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and requirements_ready and scenarios_ready,
            "questions": [
                "What governed data posture do the requirements establish?" if not requirements_ready else None,
                "Which scenario contexts drive the result-shaping and data-bounding rules?" if not scenarios_ready else None,
            ],
        },
        {
            "key": "scenario_context",
            "title": "Scenario Contract Basics",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and scenarios_ready,
            "questions": [
                "Which concrete scenario pack should execution context be derived from?" if not scenarios_ready else None,
            ],
        },
        {
            "key": "execution_semantics",
            "title": "Execution Semantics",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and scenarios_ready and shape_ready,
            "questions": [
                "Which scenarios define the required execution behavior?" if not scenarios_ready else None,
                "Which service design should those execution steps map onto?" if not shape_ready else None,
            ],
        },
        {
            "key": "backend_bindings",
            "title": "Backend Bindings",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and shape_ready,
            "questions": [
                "Which services need backend targets or adapters?" if not shape_ready else None,
            ],
        },
        {
            "key": "audit_and_lineage",
            "title": "Audit & Lineage",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and requirements_ready and scenarios_ready,
            "has_partial": (summary_present and not summary_ready) or (non_goals_present and not non_goals_ready) or (success_present and not success_ready),
            "questions": [
                "What business outcomes and risk posture should verification preserve?" if summary_present and not summary_ready else None,
                "Which non-goals need explicit guardrails in verification?" if non_goals_present and not non_goals_ready else None,
                "Which success criteria need evidence signals in the generated contract?" if success_present and not success_ready else None,
            ],
        },
        {
            "key": "generation_and_extensions",
            "title": "Generation & Extension Points",
            "path": f"/design/projects/{project_id}/developer/definition",
            "prerequisites_ready": has_baseline and shape_ready,
            "questions": [
                "Which locked service shape should generation target?" if not shape_ready else None,
            ],
        },
    ]

    for card in cards:
        card["questions"] = [question for question in card["questions"] if question]
        clarification_resolved = _has_saved_section_clarification(pm_artifacts, "dev", str(card["key"]))
        if has_definition:
            card["status"] = "ready"
        elif not has_baseline:
            card["status"] = "blocked"
            card["path"] = f"/design/projects/{project_id}/developer"
        elif clarification_resolved:
            card["status"] = "draftable"
            card["detail"] = f"{card['title']} has saved clarification answers. Rerun the draft step so Developer Definition can absorb them deterministically."
            card["questions"] = []
        elif card.get("has_partial") and card["questions"]:
            card["status"] = "needs_clarification"
        elif card["prerequisites_ready"]:
            card["status"] = "draftable"
        else:
            card["status"] = "blocked"
    return cards


def _first_matching_card(cards: list[dict[str, Any]], preferred_keys: list[str]) -> dict[str, Any] | None:
    for key in preferred_keys:
        for card in cards:
            if card.get("key") == key:
                return card
    return None


def _card_clarification_questions(card: dict[str, Any] | None) -> list[dict[str, str]]:
    if not card:
        return []
    target = str(card.get("key") or "")
    title = str(card.get("title") or target)
    return [
        {
            "question_id": f"{target}-clarification-{index}",
            "prompt": question,
            "why_it_matters": f"{title} cannot be drafted confidently without this decision.",
            "target_artifact": target,
        }
        for index, question in enumerate((card.get("questions") or [])[:3], start=1)
        if isinstance(question, str) and question.strip()
    ]


def _has_saved_section_clarification(pm_artifacts: list[dict[str, Any]], mode: str, section_key: str) -> bool:
    for artifact in pm_artifacts:
        data = artifact.get("data") or {}
        if str(data.get("artifact_type") or "") != "assistant_section_clarifications":
            continue
        if str(data.get("mode") or "").strip().lower() != mode:
            continue
        if str(data.get("section_key") or "").strip() != section_key:
            continue
        payload = data.get("accepted_payload") or []
        if any(isinstance(item, dict) and str(item.get("answer") or "").strip() for item in payload):
            return True
    return False


def _has_concrete_capability_input_evidence(pm_artifacts: list[dict[str, Any]]) -> bool:
    for artifact in pm_artifacts:
        data = artifact.get("data") if isinstance(artifact, dict) else None
        if not isinstance(data, dict):
            continue
        artifact_type = str(data.get("artifact_type") or "")
        if artifact_type == "developer_definition":
            capabilities = data.get("capability_formalizations")
            if isinstance(capabilities, list) and any(
                isinstance(capability, dict)
                and isinstance(capability.get("inputs"), list)
                and any(isinstance(input_item, dict) and str(input_item.get("input_name") or "").strip() for input_item in capability.get("inputs") or [])
                for capability in capabilities
            ):
                return True
        if artifact_type not in {"assistant_capability_formalization_candidates", "assistant_input_contract_candidates"}:
            continue
        source_proposal = data.get("source_proposal")
        items = source_proposal.get("items") if isinstance(source_proposal, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            structured_data = item.get("structured_data") if isinstance(item, dict) else None
            if not isinstance(structured_data, dict):
                continue
            capabilities = structured_data.get("capabilities")
            if isinstance(capabilities, list) and any(
                isinstance(capability, dict)
                and isinstance(capability.get("inputs"), list)
                and any(isinstance(input_item, dict) and str(input_item.get("input_name") or input_item.get("name") or "").strip() for input_item in capability.get("inputs") or [])
                for capability in capabilities
            ):
                return True
            inputs = structured_data.get("inputs")
            if isinstance(inputs, list) and any(isinstance(input_item, dict) and str(input_item.get("input_name") or input_item.get("name") or "").strip() for input_item in inputs):
                return True
    return False


def _capability_input_evidence_issues(pm_artifacts: list[dict[str, Any]], expected_capability_ids: list[str]) -> list[str]:
    """Return missing-input evidence issues across saved dev definition/candidate artifacts."""
    expected = [capability_id for capability_id in _unique(expected_capability_ids) if capability_id]
    if not expected:
        return []
    aggregate: list[Any] = []
    for artifact in pm_artifacts:
        data = artifact.get("data") if isinstance(artifact, dict) else None
        if not isinstance(data, dict):
            continue
        artifact_type = str(data.get("artifact_type") or "")
        if artifact_type == "developer_definition":
            capabilities = data.get("capability_formalizations")
            if isinstance(capabilities, list):
                aggregate.append({"capabilities": capabilities})
            continue
        if artifact_type not in {"assistant_capability_formalization_candidates", "assistant_input_contract_candidates"}:
            continue
        accepted_payload = data.get("accepted_payload")
        if isinstance(accepted_payload, list):
            aggregate.append({"items": accepted_payload})
        source_proposal = data.get("source_proposal")
        if isinstance(source_proposal, dict):
            aggregate.append(source_proposal)
    return _input_contract_proposal_issues({"evidence": aggregate}, expected)


def _capability_input_inventory_from_artifacts(pm_artifacts: list[dict[str, Any]], expected_capability_ids: list[str]) -> list[dict[str, Any]]:
    expected = [capability_id for capability_id in _unique(expected_capability_ids) if capability_id]
    if not expected:
        return []
    aggregate: list[Any] = []
    for artifact in pm_artifacts:
        data = artifact.get("data") if isinstance(artifact, dict) else None
        if not isinstance(data, dict):
            continue
        artifact_type = str(data.get("artifact_type") or "")
        if artifact_type == "developer_definition":
            capabilities = data.get("capability_formalizations")
            if isinstance(capabilities, list):
                aggregate.append({"capabilities": capabilities})
            continue
        if artifact_type not in {"assistant_capability_formalization_candidates", "assistant_input_contract_candidates"}:
            continue
        accepted_payload = data.get("accepted_payload")
        if isinstance(accepted_payload, list):
            aggregate.append({"items": accepted_payload})
        source_proposal = data.get("source_proposal")
        if isinstance(source_proposal, dict):
            aggregate.append(source_proposal)
    contracts = _capability_input_contracts_from_proposal({"evidence": aggregate}, expected)
    return [
        {
            "capability_id": capability_id,
            "inputs": contracts[capability_id].get("inputs") or [],
        }
        for capability_id in expected
        if capability_id in contracts
    ]


def _capability_contract_inventory_from_artifacts(pm_artifacts: list[dict[str, Any]], expected_capability_ids: list[str]) -> list[dict[str, Any]]:
    expected = [capability_id for capability_id in _unique(expected_capability_ids) if capability_id]
    if not expected:
        return []
    latest_by_id: dict[str, dict[str, Any]] = {}

    def ingest(value: Any) -> None:
        if isinstance(value, dict):
            capability_id = str(value.get("capability_id") or "").strip()
            if capability_id in expected and not _incomplete_capability_contracts({"capabilities": [value]}):
                latest_by_id[capability_id] = value
            for item in value.values():
                ingest(item)
            return
        if isinstance(value, list):
            for item in value:
                ingest(item)

    for artifact in pm_artifacts:
        data = artifact.get("data") if isinstance(artifact, dict) else None
        if not isinstance(data, dict):
            continue
        artifact_type = str(data.get("artifact_type") or "")
        if artifact_type == "developer_definition":
            ingest(data.get("capability_formalizations"))
            continue
        if artifact_type != "assistant_capability_formalization_candidates":
            continue
        ingest(data.get("accepted_payload"))
        ingest(data.get("source_proposal"))
    return [latest_by_id[capability_id] for capability_id in expected if capability_id in latest_by_id]


def _merge_capability_inventory_entries(
    base_inventory: list[dict[str, Any]],
    overlay_inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not overlay_inventory:
        return base_inventory
    by_capability = {
        str(entry.get("capability_id") or "").strip(): dict(entry)
        for entry in base_inventory
        if str(entry.get("capability_id") or "").strip()
    }
    order = [
        str(entry.get("capability_id") or "").strip()
        for entry in base_inventory
        if str(entry.get("capability_id") or "").strip()
    ]
    for overlay_entry in overlay_inventory:
        capability_id = str(overlay_entry.get("capability_id") or "").strip()
        if not capability_id:
            continue
        existing = by_capability.setdefault(capability_id, {"capability_id": capability_id})
        for key, value in overlay_entry.items():
            if key == "capability_id" or value in (None, "", [], {}):
                continue
            existing[key] = value
        if capability_id not in order:
            order.append(capability_id)
    return [by_capability[capability_id] for capability_id in order if capability_id in by_capability]


def _section_clarification_answers(pm_artifacts: list[dict[str, Any]], mode: str, section_key: str) -> list[str]:
    answers: list[str] = []
    for artifact in pm_artifacts:
        data = artifact.get("data") or {}
        if str(data.get("artifact_type") or "") != "assistant_section_clarifications":
            continue
        if str(data.get("mode") or "").strip().lower() != mode:
            continue
        if str(data.get("section_key") or "").strip() != section_key:
            continue
        payload = data.get("accepted_payload") or []
        for item in payload:
            if not isinstance(item, dict):
                continue
            prompt = str(item.get("prompt") or "").strip()
            answer = str(item.get("answer") or "").strip()
            if answer:
                answers.append(f"{prompt} Answer: {answer}" if prompt else answer)
    return answers


def _inline_clarification_answers_from_source(source_text: str) -> list[str]:
    """Extract browser-provided clarification answers appended to source text.

    The UI appends selected answers as JSON after a marker when a user clicks
    "Regenerate Section". Persisted clarification artifacts are still the
    durable path, but regeneration must also honor the in-flight browser answer.
    """
    answers: list[str] = []
    marker = "Assistant clarification answers for "
    decoder = json.JSONDecoder()
    search_start = 0
    while True:
        marker_index = source_text.find(marker, search_start)
        if marker_index < 0:
            break
        json_start = source_text.find("[", marker_index)
        if json_start < 0:
            break
        try:
            payload, consumed = decoder.raw_decode(source_text[json_start:])
        except json.JSONDecodeError:
            search_start = marker_index + len(marker)
            continue
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                prompt = str(item.get("prompt") or "").strip()
                answer = str(item.get("answer") or "").strip()
                if answer:
                    # Keep inline browser answers document-shaped. Structured
                    # answers often start with Markdown/CSV headings that the
                    # deterministic parsers consume; prefixing the prompt would
                    # turn those headings into prose.
                    answers.append(answer)
        search_start = json_start + max(consumed, 1)
    return answers


def _augment_source_text_with_section_answers(
    source_text: str,
    pm_artifacts: list[dict[str, Any]],
    *,
    mode: str,
    section_key: str | None,
) -> tuple[str, list[str]]:
    if not section_key:
        return source_text, _inline_clarification_answers_from_source(source_text)
    answers = _section_clarification_answers(pm_artifacts, mode, section_key)
    inline_answers = _inline_clarification_answers_from_source(source_text)
    answers = _unique([*answers, *inline_answers])
    if not answers:
        return source_text, []
    clarification_context = "\n\n".join(answers).strip()
    merged = "\n\n".join(part for part in [source_text, clarification_context] if part.strip()).strip()
    return merged, answers


async def _suggest_next_step(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    mode = str(params.get("mode", "") or "").strip().lower() or "pm"
    if mode not in {"pm", "dev"}:
        raise _invalid_request("mode must be pm or dev")
    question = str(params.get("question", "") or "").strip()

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            requirements = list_requirements(conn, project_id)
            scenarios = list_scenarios(conn, project_id)
            shapes = list_shapes(conn, project_id)
            pm_artifacts = list_pm_artifacts(conn, project_id)
            evaluations = list_evaluations(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    requirements_count = len(requirements)
    scenarios_count = len(scenarios)
    shapes_count = len(shapes)
    evaluations_count = len(evaluations)
    has_baseline = _pm_artifact_type_present(pm_artifacts, "developer_baseline")
    has_traceability = _pm_artifact_type_present(pm_artifacts, "design_traceability")
    has_definition = _pm_artifact_type_present(pm_artifacts, "developer_definition")
    has_generation = _pm_artifact_type_present(pm_artifacts, "developer_generation_run")
    simulation_evidence = _agent_consumption_simulation_evidence(pm_artifacts)
    simulation_failed = bool(simulation_evidence and simulation_evidence.get("status") == "fail")
    project_name = project.get("name", project_id)
    pm_cards = _product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count)
    dev_cards = _developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count)

    highlights = [
        f"{project_name} currently has {requirements_count} requirement set{'s' if requirements_count != 1 else ''}, {scenarios_count} scenario{'s' if scenarios_count != 1 else ''}, and {shapes_count} shape{'s' if shapes_count != 1 else ''}.",
    ]
    watchouts: list[str] = []
    action = _assistant_action("Open Product Design", f"/design/projects/{project_id}/pm")

    if mode == "pm":
        highlights.append(
            f"Developer baseline is {'present' if has_baseline else 'missing'}, and coverage mapping is {'present' if has_traceability else 'missing'}."
        )
        clarification_card = next((card for card in pm_cards if card["status"] == "needs_clarification"), None)
        blocked_card = next((card for card in pm_cards if card["status"] == "blocked"), None)
        draftable_card = next((card for card in pm_cards if card["status"] == "draftable"), None)
        if clarification_card:
            focused_answer = f"Resolve the targeted ambiguity in {clarification_card['title']} before asking for more PM surface area."
            summary = "Studio already has enough signal to draft most PM artifacts. The highest-value next step is the smallest clarification that changes the product behavior materially."
            next_steps = [
                f"Open {clarification_card['title']} and answer the targeted clarification instead of filling unrelated fields.",
                *[question for question in clarification_card["questions"][:2]],
            ]
            action = _assistant_action(f"Open {clarification_card['title']}", clarification_card["path"])
            watchouts.append("Do not turn PM flow into a field-by-field interview; resolve only the ambiguity that changes downstream behavior.")
        elif blocked_card:
            focused_answer = f"Unblock {blocked_card['title']} from source context before expecting the assistant to keep drafting reliably."
            summary = "Studio lacks the upstream source signal needed to draft this PM section confidently."
            next_steps = [
                f"Open {blocked_card['title']} and provide the missing source context or prerequisite artifact.",
                "Once the source signal exists, rerun the relevant PM assist action instead of typing every field manually.",
            ]
            action = _assistant_action(f"Open {blocked_card['title']}", blocked_card["path"])
        elif draftable_card:
            focused_answer = f"Draft {draftable_card['title']} directly from the current business spec and review the result."
            summary = "The current source brief is sufficient for Studio to propose the next PM section without another questionnaire."
            next_steps = [
                f"Open {draftable_card['title']} and use PM Assist to draft from source.",
                "Review the proposal and promote only the accepted parts into the canonical PM artifact.",
            ]
            action = _assistant_action(f"Open {draftable_card['title']}", draftable_card["path"])
        elif not has_baseline:
            focused_answer = "Lock the current Product Design baseline so Developer Design can start from stable delivery truth."
            summary = "PM artifacts are materially sufficient; the next value is handing off a stable baseline."
            next_steps = [
                "Open Developer Design Home and lock the current Product Design baseline.",
                "Only lock once the selected shape and PM artifacts are the ones you want developers to formalize.",
            ]
            action = _assistant_action("Open Developer Design", f"/design/projects/{project_id}/developer")
        else:
            focused_answer = "Review handoff quality and close any remaining PM ambiguity before pushing deeper into developer formalization."
            summary = "Core PM artifacts are in place, so the next value is handoff quality rather than more PM surface area."
            next_steps = [
                "Review PM Artifacts for accepted clarification items or proposed drafts that still need an explicit decision.",
                "Inspect Developer Design Home and confirm the locked baseline is ready for the next developer action.",
            ]
            action = _assistant_action("Open PM Artifacts", f"/design/projects/{project_id}/pm-artifacts")
            if not has_traceability:
                watchouts.append("Coverage Mapping is still missing, so downstream completeness claims are not yet grounded.")
    else:
        highlights.append(
            f"Developer baseline is {'present' if has_baseline else 'missing'}, coverage mapping is {'present' if has_traceability else 'missing'}, developer definition is {'present' if has_definition else 'missing'}, and generation evidence is {'present' if has_generation else 'missing'}."
        )
        clarification_card = next((card for card in dev_cards if card["status"] == "needs_clarification"), None)
        draftable_card = next((card for card in dev_cards if card["status"] == "draftable"), None)
        blocked_card = next((card for card in dev_cards if card["status"] == "blocked"), None)
        if simulation_failed:
            focused_answer = "Review the failed agent-consumption simulation before generating or publishing more runtime artifacts."
            summary = "The simulator found that a baseline consuming agent is likely to misread one or more contract probes. Treat this as contract or explicit app-glue feedback, not as a runtime deployment issue."
            failed_count = ((simulation_evidence or {}).get("summary") or {}).get("failed")
            next_steps = [
                "Open Developer Coverage and inspect the AI Simulation Result.",
                "Use the simulator failures to update reviewed consumability hints, clarification behavior, unsupported effects, or explicit app-glue notes.",
                "Rerun the simulator after the review changes and only then continue generation/publication.",
            ]
            action = _assistant_action("Open Developer Coverage", f"/design/projects/{project_id}/developer/coverage")
            if failed_count:
                highlights.append(f"Latest agent-consumption simulation has {failed_count} failed probe{'s' if failed_count != 1 else ''}.")
            watchouts.append("Do not patch the generic runtime for these failures unless the same behavior is truly package-agnostic.")
        elif requirements_count == 0 or scenarios_count == 0 or shapes_count == 0:
            focused_answer = "Finish the missing PM prerequisites before trying to formalize Developer Design."
            summary = "Developer work should not continue while the PM baseline inputs are incomplete."
            next_steps = [
                "Return to Product Design and make sure requirements, scenarios, and a selected shape all exist.",
                "Start Developer Design only from a complete Product Design handoff.",
            ]
            action = _assistant_action("Open Product Design", f"/design/projects/{project_id}/pm")
            watchouts.append("Developer formalization from partial PM inputs creates churn and weak traceability.")
        elif blocked_card:
            focused_answer = f"Unblock {blocked_card['title']} from the locked PM handoff before expanding developer detail."
            summary = "The next useful developer action is driven by a missing prerequisite, not by asking for every field in the contract."
            next_steps = [
                f"Open {blocked_card['title']} or the baseline handoff area and resolve the missing prerequisite.",
                "Once the prerequisite exists, let Studio draft the section from baseline instead of authoring it from scratch.",
            ]
            action = _assistant_action(f"Open {blocked_card['title']}", blocked_card["path"])
        elif clarification_card:
            focused_answer = f"Resolve the targeted ambiguity in {clarification_card['title']} instead of widening the developer definition blindly."
            summary = "The locked PM baseline is sufficient for most of the draft. The next value is a small clarification that changes runtime or verification behavior materially."
            next_steps = [
                f"Open {clarification_card['title']} and resolve the few missing developer decisions that still matter.",
                *[question for question in clarification_card["questions"][:2]],
            ]
            action = _assistant_action(f"Open {clarification_card['title']}", clarification_card["path"])
            watchouts.append("Do not keep filling the contract section by section if the only missing value is one approval, scope, or evidence decision.")
        elif draftable_card and not has_definition:
            focused_answer = f"Draft {draftable_card['title']} from the locked PM baseline and save the first Developer Definition."
            summary = "The baseline already carries enough signal for Studio to draft the next developer section without another interview."
            next_steps = [
                f"Open {draftable_card['title']} and use Dev Assist to draft from the locked baseline.",
                "Save the resulting Developer Definition once the seeded sections look defensible.",
            ]
            action = _assistant_action("Open Developer Definition", f"/design/projects/{project_id}/developer/definition")
        elif not has_traceability:
            focused_answer = "Create or refresh Coverage Mapping next so the locked baseline is formally addressed before more detail is added."
            summary = "Developer Design has a baseline, but no coverage record ties Product Design intent to concrete developer targets yet."
            next_steps = [
                "Open Developer Coverage and map the locked Product Design items to exact developer targets.",
                "Use the missing and partial rows to decide which contract sections need explicit formalization first.",
            ]
            action = _assistant_action("Open Developer Coverage", f"/design/projects/{project_id}/developer/coverage")
            watchouts.append("Without coverage mapping, later completeness claims are hard to defend.")
        elif not has_definition:
            focused_answer = "Save the first Developer Definition draft so generation and verification can run against a real contract artifact."
            summary = "Coverage exists, but the delivery-truth developer contract has not been saved yet."
            next_steps = [
                "Open Developer Definition and save the current draft.",
                "Review any assistant-seeded sections before saving if they still look too generic.",
            ]
            action = _assistant_action("Open Developer Definition", f"/design/projects/{project_id}/developer/definition")
        elif not has_generation:
            focused_answer = "Launch generation from the saved Developer Definition so the current contract produces concrete runtime evidence."
            summary = "The developer contract exists, but there is no generation evidence tied to it yet."
            next_steps = [
                "Open Developer Definition and launch generation from the saved contract.",
                "Inspect generated structure and runtime target outputs before moving on.",
            ]
            action = _assistant_action("Open Generation", f"/design/projects/{project_id}/developer/definition#generation-launch")
        elif evaluations_count == 0:
            focused_answer = "Run evaluation next so the saved contract and generated design are pressure-tested against real scenarios."
            summary = "Generation evidence exists, but there is no evaluation evidence yet."
            next_steps = [
                "Run evaluation against a representative scenario from the locked baseline.",
                "Use the result to decide whether the contract needs refinement before more generation work.",
            ]
            action = _assistant_action("Open Verification", f"/design/projects/{project_id}/verification")
        else:
            focused_answer = "Review the latest evidence and tighten the weakest contract section instead of widening the surface area."
            summary = "Core developer artifacts already exist, so the best next step is evidence-driven refinement."
            next_steps = [
                "Open the latest evaluation and identify the highest-signal gap or partial outcome.",
                "Update the corresponding Developer Definition section instead of adding unrelated new detail.",
            ]
            action = _assistant_action("Review Latest Evidence", f"/design/projects/{project_id}/verification")

    deterministic = {
        "title": f"Next Step Suggestion: {project_name}",
        "summary": summary,
        "focused_answer": focused_answer,
        "action_label": action["action_label"],
        "action_path": action["action_path"],
        "highlights": highlights,
        "watchouts": watchouts[:4],
        "next_steps": next_steps[:4],
    }

    try:
        model_result = await try_model_assistant_response(
            "suggest_next_step",
            {
                "project": {
                    "id": project_id,
                    "name": project_name,
                    "domain": project.get("domain"),
                    "summary": project.get("summary"),
                },
                "mode": mode,
                "question": question,
                "state": {
                    "requirements_count": requirements_count,
                    "scenarios_count": scenarios_count,
                    "shapes_count": shapes_count,
                    "evaluations_count": evaluations_count,
                    "has_baseline": has_baseline,
                    "has_traceability": has_traceability,
                    "has_definition": has_definition,
                    "has_generation": has_generation,
                },
                "agent_consumption_simulation": simulation_evidence,
                "deterministic_draft": deterministic,
            },
        )
    except Exception:
        deterministic["watchouts"] = [
            "LLM provider failed while refining this read-only recommendation. Studio is showing deterministic guidance instead; check Assistant Runtime Configuration if you expected model-generated guidance.",
            *deterministic.get("watchouts", []),
        ][:4]
        model_result = None
    if model_result:
        return _merge_explanation(deterministic, model_result)
    return deterministic


async def _analyze_agent_consumption_simulation(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    question = str(params.get("question", "") or "").strip()

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            pm_artifacts = list_pm_artifacts(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    project_name = project.get("name", project_id)
    simulation_evidence = _agent_consumption_simulation_evidence(pm_artifacts)
    traceability = _pm_artifact_data(pm_artifacts, "design_traceability") or {}
    readiness_param = params.get("agent_consumption_readiness")
    readiness = (
        readiness_param
        if isinstance(readiness_param, dict)
        else traceability.get("agent_consumption_readiness")
        if isinstance(traceability.get("agent_consumption_readiness"), dict)
        else None
    )
    readiness_findings = readiness.get("findings") if isinstance(readiness, dict) and isinstance(readiness.get("findings"), list) else []
    readiness_reviews = readiness.get("finding_reviews") if isinstance(readiness, dict) and isinstance(readiness.get("finding_reviews"), dict) else {}
    unresolved_readiness_findings = [
        finding
        for finding in readiness_findings
        if isinstance(finding, dict)
        and isinstance(finding.get("id"), str)
        and finding.get("id") not in readiness_reviews
    ]
    unresolved_readiness_blockers = [
        finding for finding in unresolved_readiness_findings if finding.get("severity") == "blocker"
    ]
    unresolved_readiness_warnings = [
        finding for finding in unresolved_readiness_findings if finding.get("severity") == "warning"
    ]
    high_risk_param = params.get("high_risk_confirmations")
    high_risk = (
        high_risk_param
        if isinstance(high_risk_param, dict)
        else traceability.get("high_risk_confirmations")
        if isinstance(traceability.get("high_risk_confirmations"), dict)
        else None
    )
    high_risk_summary = high_risk.get("summary") if isinstance(high_risk, dict) and isinstance(high_risk.get("summary"), dict) else {}
    try:
        high_risk_unresolved = int(high_risk_summary.get("unresolved") or 0)
    except (TypeError, ValueError):
        high_risk_unresolved = 0
    focus = params.get("focus") if isinstance(params.get("focus"), dict) else {}
    focus_kind = str(focus.get("kind") or "").strip()
    focus_id = str(focus.get("id") or "").strip()
    high_risk_items = high_risk.get("items") if isinstance(high_risk, dict) and isinstance(high_risk.get("items"), list) else []
    focused_high_risk_items = [
        item for item in high_risk_items
        if isinstance(item, dict) and str(item.get("id") or "") == focus_id
    ] if focus_kind == "high_risk_confirmation" and focus_id else []

    if not simulation_evidence:
        deterministic = {
            "title": f"Simulator Feedback: {project_name}",
            "summary": "No saved agent-consumption simulator report exists yet.",
            "focused_answer": "Run the simulator from Developer Coverage before asking the assistant to analyze simulator learnings.",
            "action_label": "Open Developer Coverage",
            "action_path": f"/design/projects/{project_id}/developer/coverage",
            "highlights": [
                "The assistant can analyze simulator evidence only after Studio has a saved simulation report artifact.",
            ],
            "watchouts": [
                "Do not substitute assistant opinion for simulator evidence; run the baseline simulator first.",
            ],
            "next_steps": [
                "Open Developer Coverage.",
                "Run AI Simulator after simulator provider/model/key are configured.",
                "Return here or use Ask Assistant for Fix Plan after the report is saved.",
            ],
        }
        return deterministic

    failed_cases = simulation_evidence.get("failed_cases") if isinstance(simulation_evidence.get("failed_cases"), list) else []
    failed_count = len(failed_cases)
    status = str(simulation_evidence.get("status") or "unknown")
    summary = simulation_evidence.get("summary") if isinstance(simulation_evidence.get("summary"), dict) else {}
    primary_failure = failed_cases[0] if failed_cases and isinstance(failed_cases[0], dict) else None
    if focus_kind == "simulator_case" and focus_id:
        focused_cases = [
            case for case in failed_cases
            if isinstance(case, dict) and str(case.get("probe_id") or "") == focus_id
        ]
        if focused_cases:
            failed_cases = focused_cases
            failed_count = len(failed_cases)
            primary_failure = failed_cases[0]
    if focus_kind == "readiness_finding" and focus_id:
        focused_findings = [
            finding for finding in unresolved_readiness_findings
            if isinstance(finding, dict) and str(finding.get("id") or "") == focus_id
        ]
        if focused_findings:
            unresolved_readiness_findings = focused_findings
            unresolved_readiness_blockers = [
                finding for finding in unresolved_readiness_findings if finding.get("severity") == "blocker"
            ]
            unresolved_readiness_warnings = [
                finding for finding in unresolved_readiness_findings if finding.get("severity") == "warning"
            ]
            failed_cases = []
            failed_count = 0
            primary_failure = None
    if focused_high_risk_items:
        failed_cases = []
        failed_count = 0
        primary_failure = None
        unresolved_readiness_findings = []
        unresolved_readiness_blockers = []
        unresolved_readiness_warnings = []
        high_risk_unresolved = 1

    if failed_count:
        focused_answer = (
            "Resolve this failed simulator probe with a reviewed contract, metadata, app-glue, or service behavior change."
            if focus_kind == "simulator_case"
            else "Treat failed simulator probes as reviewable contract or app-glue feedback, then rerun the simulator before generation or publication."
        )
        next_steps = [_simulator_failure_fix_step(case) for case in failed_cases[:3] if isinstance(case, dict)]
        if failed_count > len(next_steps):
            next_steps.append(f"Review the remaining {failed_count - len(next_steps)} failed simulator probe{'s' if failed_count - len(next_steps) != 1 else ''} in the saved report and classify each with the same owner/fix decision.")
        next_steps.append("Save Coverage Mapping and rerun the simulator after the reviewed contract, metadata, app-glue, or service behavior changes.")
        watchouts = [
            "Assistant proposals are not authoritative until PM/dev review and save the underlying contract or app-glue metadata.",
            "A simulator failure is not automatically a service bug; it may mean the package does not expose enough consumption guidance.",
        ]
        if primary_failure:
            watchouts.append(
                f"First failed probe: {primary_failure.get('probe_id')} expected {primary_failure.get('expected_outcome')} but simulated {primary_failure.get('actual_outcome')}."
            )
    elif focused_high_risk_items:
        item = focused_high_risk_items[0]
        title = str(item.get("title") or focus_id)
        recommendation = str(item.get("recommendation") or "Confirm or intentionally defer this decision before generation/publication.")
        target_route = str(item.get("target_route") or "")
        focused_answer = "Resolve this high-risk confirmation with an explicit PM/dev decision before generation or publication."
        next_steps = [
            f"Review high-risk confirmation: {title}. {recommendation}",
            "If the statement is true and safe to become contract/generation truth, mark it confirmed with a short evidence note.",
            "If the statement is ambiguous or still needs contract edits, intentionally defer it and open the source page before generation/publication.",
        ]
        if target_route:
            next_steps.append(f"Open source page `{target_route}` and inspect the underlying Developer Design fields before applying the decision.")
        watchouts = [
            "Assistant confirmation suggestions are not authoritative; the user must apply the reviewed decision.",
            "Do not confirm service ownership or capability identity if the underlying Developer Definition is still ambiguous.",
        ]
    elif unresolved_readiness_findings or high_risk_unresolved:
        focused_answer = (
            "Resolve this readiness finding with an explicit PM/dev decision before generation or publication."
            if focus_kind == "readiness_finding"
            else "The simulator passed, but the fix plan is not empty: resolve the unreviewed readiness findings "
            "and high-risk confirmations before generation, publication, or verifier/generator gates."
        )
        next_steps = []
        for finding in unresolved_readiness_findings[:2]:
            title = str(finding.get("title") or finding.get("id") or "Unreviewed readiness finding")
            recommendation = str(finding.get("recommendation") or "Record an explicit review decision.")
            next_steps.append(f"Fix or classify readiness finding: {title}. {recommendation}")
        next_steps.extend([
            "Resolve High-Risk Confirmations that would otherwise become contract truth or generated behavior.",
            "Save Coverage Mapping, then rerun the simulator only if the reviewed contract, metadata, app-glue, or service behavior changed.",
        ])
        watchouts = [
            "A passing simulator report is regression evidence, not permission to skip blocked readiness or high-risk review gates.",
            f"Unreviewed readiness findings: {len(unresolved_readiness_findings)} ({len(unresolved_readiness_blockers)} blocker, {len(unresolved_readiness_warnings)} warning).",
        ]
        if high_risk_unresolved:
            watchouts.append(f"High-risk confirmations still unresolved: {high_risk_unresolved}.")
    else:
        focused_answer = "The latest simulator report passed all saved probes; keep it as regression evidence and move to the next verification gate."
        next_steps = [
            "Keep the simulator report attached to the readiness handoff.",
            "Proceed to package publication or verifier/generator validation if other gates are green.",
        ]
        watchouts = [
            "A passing simulator report is not runtime proof; it only validates likely baseline-agent consumption against reviewed probes.",
        ]

    deterministic = {
        "title": f"Simulator Feedback: {project_name}",
        "summary": f"Latest simulator status is {status}; {summary.get('passed', 0)} passed and {summary.get('failed', failed_count)} failed.",
        "focused_answer": focused_answer,
        "action_label": "Open Developer Coverage",
        "action_path": f"/design/projects/{project_id}/developer/coverage",
        "highlights": [
            f"Simulator runtime: {(simulation_evidence.get('simulator_runtime') or {}).get('provider', 'unknown')}/{(simulation_evidence.get('simulator_runtime') or {}).get('model', 'unknown')}.",
            f"Failed probes: {failed_count}.",
            *(
                [f"Unreviewed readiness findings: {len(unresolved_readiness_findings)}."]
                if unresolved_readiness_findings
                else []
            ),
            *(
                [f"High-risk confirmations unresolved: {high_risk_unresolved}."]
                if high_risk_unresolved
                else []
            ),
            *[
                f"{case.get('probe_id')}: expected {case.get('expected_outcome')}, simulated {case.get('actual_outcome')}."
                for case in failed_cases[:2]
                if isinstance(case, dict)
            ],
        ][:4],
        "watchouts": watchouts[:4],
        "next_steps": next_steps[:4],
    }

    try:
        model_result = await try_model_assistant_response(
            "analyze_agent_consumption_simulation",
            {
                "project": {
                    "id": project_id,
                    "name": project_name,
                    "domain": project.get("domain"),
                    "summary": project.get("summary"),
                },
                "question": question,
                "agent_consumption_simulation": simulation_evidence,
                "agent_consumption_readiness": readiness,
                "deterministic_draft": deterministic,
            },
        )
    except Exception:
        deterministic["watchouts"] = [
            "LLM provider failed while analyzing simulator evidence. Studio is showing deterministic simulator feedback instead.",
            *deterministic.get("watchouts", []),
        ][:4]
        model_result = None
    if model_result:
        merged = _merge_explanation(deterministic, model_result)
        if failed_cases or unresolved_readiness_findings or high_risk_unresolved or focused_high_risk_items:
            merged["focused_answer"] = deterministic["focused_answer"]
            merged["next_steps"] = _merged_string_list(
                deterministic["next_steps"] + merged.get("next_steps", []),
                deterministic["next_steps"],
                limit=4,
            )
            merged["highlights"] = _merged_string_list(
                deterministic["highlights"] + merged.get("highlights", []),
                deterministic["highlights"],
                limit=4,
            )
        return merged
    return deterministic


async def _interpret_project_intent(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    intent = str(params.get("intent", "") or "").strip()
    source_requirements_id = str(params.get("source_requirements_id", "") or "").strip() or None

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            source_requirements = (
                get_requirements(conn, project_id, source_requirements_id)
                if source_requirements_id
                else None
            )
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    if source_requirements is not None:
        source_data = source_requirements.get("data") or {}
        source_document = source_data.get("source_document") or {}
        business_spec = source_data.get("business_spec") or {}
        intent_parts = [
            _string_value(business_spec.get("summary"), ""),
            "Business goals: " + "; ".join(_string_list(business_spec.get("business_goal", []))),
            "Behavior classes: " + "; ".join(_string_list(business_spec.get("behavior_classes", []))),
            "Non-goals: " + "; ".join(_string_list(business_spec.get("non_goals", []))),
        ]
        source_intent = " ".join(part for part in intent_parts if part and not part.endswith(": "))
        if source_document.get("path"):
            source_intent = f"{source_intent} Source document: {source_document['path']}".strip()
        if source_intent:
            intent = source_intent

    if not intent:
        raise _invalid("Provide an intent brief or a source requirements artifact.")

    words = set(_normalized_words(intent))
    project_name = project.get("name", project_id)
    consumer_mode = params.get("consumer_mode")
    consumer_mode = normalize_consumer_mode(str(consumer_mode).strip().lower()) if consumer_mode is not None else consumer_mode_from_labels(project.get("labels"))
    consumer_label = consumer_mode_label(consumer_mode)

    has_budget = _contains_any(words, "budget", "cost", "spend", "price", "pricing")
    has_approval = _contains_any(words, "approval", "approve", "approver", "escalate", "escalation")
    has_verification = _contains_any(words, "verify", "verification", "confirm", "confirmation", "reconcile")
    has_refresh = _contains_any(words, "refresh", "stale", "quote", "revalidate", "expiry", "expired")
    has_async = _contains_any(words, "async", "asynchronous", "later", "followup", "follow", "notification", "webhook")
    has_handoff = _contains_any(words, "handoff", "handoffs", "multi", "multiple", "estate", "services", "service")
    has_risk = _contains_any(words, "risk", "danger", "dangerous", "delete", "irreversible", "destructive")
    has_audit = _contains_any(words, "audit", "trace", "lineage", "history", "explain")

    recommended_shape_type = "single_service"
    if has_handoff or has_async or (has_approval and has_verification):
        recommended_shape_type = "multi_service"

    recommended_shape_reason = (
        "A multi-service shape is worth exploring because the brief implies handoffs, delayed follow-up, or clearly separable responsibilities."
        if recommended_shape_type == "multi_service"
        else "A single service is the best starting point because the brief reads like one tightly coupled responsibility that should stay easy to reason about."
    )

    requirements_focus: list[str] = []
    if has_budget:
        requirements_focus.append("Make cost visibility and over-budget behavior explicit before shaping the service.")
    if has_approval:
        requirements_focus.append("State clearly when the system should block, escalate, or require approval.")
    if has_verification:
        requirements_focus.append("Capture how completion should be verified instead of assuming success is enough.")
    if has_refresh:
        requirements_focus.append("Define what should happen when a stale quote, stale state, or expired input is encountered.")
    if has_risk:
        requirements_focus.append("Make destructive or high-risk actions explicit so authority and recovery posture are clear.")
    if has_audit:
        requirements_focus.append("Preserve lineage and explainability so later investigation does not depend on UI or prompt glue.")
    if not requirements_focus:
        requirements_focus.append("Start by defining what must always be true, what can block action, and what the system must explain afterward.")
    if consumer_mode == "agent_anip":
        requirements_focus.insert(0, "Bias the first design toward machine-usable capability boundaries, explicit blocked-action meaning, and low-glue ANIP consumption.")
    elif consumer_mode == "human_app":
        requirements_focus.insert(0, "Bias the first design toward a clear human-facing flow, understandable blocked states, and operator-friendly explanations.")
    else:
        requirements_focus.insert(0, "Bias the first design toward a hybrid flow where both people and ANIP consumers can follow the same bounded service logic.")

    scenario_starters: list[str] = [
        "Describe the normal success path that the service should handle cleanly."
    ]
    if has_budget:
        scenario_starters.append("Add a scenario where the action is over budget and the system must decide whether to block, escalate, or seek broader authority.")
    if has_approval:
        scenario_starters.append("Add a scenario where approval is required so the service shape can show where that responsibility should live.")
    if has_refresh:
        scenario_starters.append("Add a scenario where the required input is stale or expired and the system must refresh or revalidate before acting.")
    if has_verification:
        scenario_starters.append("Add a scenario where the system must verify the outcome after the initial action completes.")
    if has_async or has_handoff:
        scenario_starters.append("Add a follow-up or handoff scenario so the design is pressured across service boundaries, not only inside one request.")
    if consumer_mode == "agent_anip":
        scenario_starters.append("Add a scenario where an agent or tool must discover permissions, handle a blocked action, and continue without UI-only context.")
    elif consumer_mode == "human_app":
        scenario_starters.append("Add a scenario where a human needs the system to explain why work was blocked, delayed, or routed for review.")
    else:
        scenario_starters.append("Add a scenario where a person starts the work and an agent or tool continues it through a bounded handoff.")

    concept_map = {
        "flight": "Flight",
        "destination": "Destination",
        "booking": "Booking",
        "quote": "Quote",
        "approval": "Approval",
        "budget": "Budget",
        "payment": "Payment",
        "order": "Order",
        "invoice": "Invoice",
        "deployment": "Deployment",
        "cluster": "Cluster",
        "incident": "Incident",
        "customer": "Customer",
        "notification": "Notification",
        "policy": "Policy",
        "ticket": "Ticket",
    }
    domain_concepts = _unique([label for key, label in concept_map.items() if key in words])
    if not domain_concepts:
        domain_concepts = ["Primary business object", "Approval or control object", "Outcome or verification object"]

    service_suggestions: list[str] = []
    if recommended_shape_type == "single_service":
        service_suggestions.append("Start with one primary service that owns the main action and its control checks together.")
    else:
        service_suggestions.append("Keep the primary action in one service and separate approval, verification, or follow-up only where the brief clearly demands it.")
    if consumer_mode == "agent_anip":
        service_suggestions.append("Keep the machine-facing capability surface explicit so consumers do not have to recover workflow meaning from prompts or UI assumptions.")
    elif consumer_mode == "human_app":
        service_suggestions.append("Keep the first boundary legible for PMs, support, and operations instead of splitting the design earlier than the product needs.")
    else:
        service_suggestions.append("Treat the design as hybrid: keep the human workflow understandable while preserving ANIP-friendly capability and audit boundaries underneath.")
    if has_approval:
        service_suggestions.append("Consider an approval responsibility only if approvals need a distinct lifecycle or separate authority boundary.")
    if has_verification:
        service_suggestions.append("If verification is materially different from the initial action, treat it as a separate responsibility in the shape.")
    if has_refresh:
        service_suggestions.append("Make refresh or revalidation an explicit capability instead of hiding it inside UI or retry glue.")

    next_steps = [
        "Turn the requirements focus into the first requirements set.",
        "Capture two or three scenario starters that should pressure the design early.",
        f"Create a {'multi-service' if recommended_shape_type == 'multi_service' else 'single-service'} shape and assign the main domain concepts to it.",
        "Run evaluation after the first shape draft and use the result to tighten the boundaries.",
    ]

    summary = (
        f"This brief for {project_name} points toward a "
        f"{'multi-service' if recommended_shape_type == 'multi_service' else 'single-service'} starting shape. "
        f"It is being shaped primarily for {consumer_label.lower()}. "
        f"The main pressure points are {', '.join(item.split(' ')[0].lower() for item in requirements_focus[:3])}."
    )

    deterministic = {
        "title": f"Intent Interpretation: {project_name}",
        "summary": summary,
        "recommended_shape_type": recommended_shape_type,
        "recommended_shape_reason": recommended_shape_reason,
        "requirements_focus": requirements_focus[:5],
        "scenario_starters": scenario_starters[:5],
        "domain_concepts": domain_concepts[:6],
        "service_suggestions": service_suggestions[:5],
        "next_steps": next_steps,
    }

    model_result = await try_model_assistant_response(
        "interpret_project_intent",
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
                "labels": project.get("labels") or [],
                "consumer_mode": consumer_mode,
            },
            "intent": intent,
            "deterministic_draft": deterministic,
        },
    )
    if model_result:
        return _merge_intent_interpretation(deterministic, model_result)
    return deterministic


async def _propose_requirements(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            source_requirements = (
                get_requirements(conn, project_id, source_requirements_id)
                if source_requirements_id
                else None
            )
            pm_artifacts = _safe_call(list_pm_artifacts, conn, project_id) or []
            requirements = _safe_call(list_requirements, conn, project_id) or []
            scenarios = _safe_call(list_scenarios, conn, project_id) or []
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    source_text = _requirements_source_text(source_requirements, source_document_text)
    if not source_text:
        raise _invalid_request("Provide source_document_text or source_requirements_id")

    words = set(_normalized_words(source_text))
    project_name = project.get("name", project_id)
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, len(requirements), len(scenarios)), ["product_summary", "actor_model", "business_areas"])
    section_questions = (section or {}).get("questions") or []

    candidate_items = [
        _proposal_item(
            "req-product-purpose",
            "Define the product purpose as a governed, bounded system outcome",
            "State what the product must help users accomplish, which work it should stop short of performing automatically, and what bounded outcomes users should trust it to deliver.",
            "Every later PM and Developer artifact depends on a stable statement of purpose and operating boundary.",
            "high",
        ),
        _proposal_item(
            "req-actor-behavior",
            "Make actor, authority, and visibility differences explicit",
            "List the distinct caller or user roles, what each role may see, and where the system should restrict, deny, clarify, or require approval.",
            "Runtime policy bindings and verification are much easier when PM intent already distinguishes actor posture explicitly.",
            "high",
        ),
        _proposal_item(
            "req-scenario-coverage",
            "Define the highest-value recurring question or task families",
            "Capture the top recurring business asks that the product must answer or support, using concrete examples rather than generic feature language.",
            "Scenario-driven design is stronger when requirements already anchor the recurring business asks.",
            "medium",
        ),
    ]

    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        candidate_items.append(
            _proposal_item(
                "req-approval-boundary",
                "Make approval boundaries explicit",
                "Define which actions or outcomes require an approval boundary and what the system must return before that boundary is crossed.",
                "The source text already hints at approvals, so this should become an explicit requirement rather than remain implicit.",
                "high",
            )
        )
    if _contains_any(words, "audit", "trace", "history", "lineage", "explain"):
        candidate_items.append(
            _proposal_item(
                "req-auditability",
                "Preserve explanation and auditability",
                "Require the system to preserve enough explanation, lineage, or traceability that a reviewer can understand why a result or stop condition occurred.",
                "The source text suggests explanation or audit pressure that should become an explicit requirement.",
                "medium",
            )
        )

    questions = section_questions[:3] or [item["prompt"] for item in _missing_business_questions_from_words(words)[:3]]
    watchouts = [
        "These are draft requirement candidates only. They should be accepted, edited, or rejected individually before persistence.",
        "If the business brief is thin, scenario quality will still depend on clarification before Product Design is stable.",
    ]
    next_steps = [
        "Review the requirement candidates and accept or edit the ones that belong in the first PM draft.",
        "Run missing-business-info assistance next if key authority, scope, or actor posture is still unclear.",
    ]

    deterministic = _proposal_envelope(
        title=f"Requirement Proposal: {project_name}",
        summary="Draft candidate requirements derived from the provided business brief. These are intended to accelerate PM authoring, not replace review.",
        capability="propose_requirements",
        questions_for_user=questions,
        watchouts=watchouts,
        next_steps=next_steps,
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "requirements",
            "items": candidate_items,
        },
        mode="pm",
    )

    return await _model_or_deterministic(
        "propose_requirements",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _propose_scenarios(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            source_requirements = (
                get_requirements(conn, project_id, source_requirements_id)
                if source_requirements_id
                else None
            )
            pm_artifacts = _safe_call(list_pm_artifacts, conn, project_id) or []
            requirements = _safe_call(list_requirements, conn, project_id) or []
            scenarios = _safe_call(list_scenarios, conn, project_id) or []
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    source_text = _requirements_source_text(source_requirements, source_document_text)
    if not source_text:
        raise _invalid_request("Provide source_document_text or source_requirements_id")

    words = set(_normalized_words(source_text))
    project_name = project.get("name", project_id)
    default_service_id = _slugify_label(project_name) or "primary-service"
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, len(requirements), len(scenarios)), ["product_summary", "actor_model", "permission_intent"])
    section_questions = (section or {}).get("questions") or []

    scenario_items = [
        _proposal_item(
            "scenario-review-governed-risk",
            "Review a bounded business risk question and explain the next safe action",
            "Describe how a user asks for a high-value business assessment, what governed result they receive, and when the system must clarify, restrict, or stop for approval instead of acting automatically.",
            "This anchors the main PM scenario around a concrete user ask and a bounded outcome rather than generic feature language.",
            "high",
            _scenario_structured_data(
                name="Review a bounded business risk question and explain the next safe action",
                category="business_review",
                narrative="A user asks for a high-value business assessment and receives a bounded result or safe next step, with clarification, restriction, or approval surfaced explicitly when required.",
                actor_context="Authorized business user",
                business_scope="Recurring governed business assessment",
                capability="answer_governed_business_question",
                service_id=default_service_id,
                outcome_type="completed",
                stop_condition="complete",
            ),
        ),
        _proposal_item(
            "scenario-actor-differentiation",
            "Show how two actor roles receive different outcomes from the same business ask",
            "Capture one scenario where a broader actor can proceed and another where a narrower actor is restricted, denied, or given a reduced result for the same underlying question.",
            "This makes actor-aware behavior testable early instead of treating visibility and authority as abstract policy notes.",
            "high",
            _scenario_structured_data(
                name="Show how two actor roles receive different outcomes from the same business ask",
                category="policy",
                narrative="Two actors ask the same underlying business question; the broader actor receives the governed result while the narrower actor receives a restricted, denied, or reduced outcome.",
                actor_context="Two roles with different authority or visibility",
                business_scope="Actor-aware access and result shaping",
                capability="answer_governed_business_question",
                service_id=default_service_id,
                outcome_type="safe_stop",
                stop_condition="safe_stop",
            ),
        ),
        _proposal_item(
            "scenario-clarification-before-action",
            "Show the clarification loop before the system continues",
            "Describe a case where the user intent is incomplete or ambiguous and the system must request missing information before returning a stable result.",
            "Clarification scenarios help later formalization avoid silent defaults and make required inputs explicit.",
            "medium",
            _scenario_structured_data(
                name="Show the clarification loop before the system continues",
                category="clarification",
                narrative="A user asks an incomplete or ambiguous question and the system stops for the minimum missing information before producing a stable governed result.",
                actor_context="User with otherwise valid access",
                business_scope="Required input completion before execution",
                capability="answer_governed_business_question",
                service_id=default_service_id,
                outcome_type="clarification_required",
                stop_condition="clarification_required",
            ),
        ),
    ]

    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        scenario_items.append(
            _proposal_item(
                "scenario-approval-stop",
                "Show the approval stop before a high-impact change",
                "Capture a scenario where the system prepares a proposed action or recommendation but stops at an explicit approval boundary before any high-impact change is carried out.",
                "The source text already implies approval posture, so PM scenarios should make that stop condition concrete.",
                "high",
                _scenario_structured_data(
                    name="Show the approval stop before a high-impact change",
                    category="approval",
                    narrative="The system prepares a governed proposed action but stops at an approval boundary before any high-impact or write-adjacent change is carried out.",
                    actor_context="User allowed to prepare but not necessarily approve",
                    business_scope="Approval-gated operational preparation",
                    capability="prepare_governed_next_action",
                    service_id=default_service_id,
                    outcome_type="approval_required",
                    stop_condition="approval_required",
                ),
            )
        )
    if _contains_any(words, "audit", "trace", "history", "lineage", "explain"):
        scenario_items.append(
            _proposal_item(
                "scenario-audit-explanation",
                "Explain why the system reached a governed result or stop condition",
                "Describe how a reviewer asks why the system restricted, denied, or stopped a flow and what explanation or trace evidence they should receive.",
                "This turns auditability from a vague requirement into a scenario the product can later verify.",
                "medium",
                _scenario_structured_data(
                    name="Explain why the system reached a governed result or stop condition",
                    category="audit",
                    narrative="A reviewer asks why the system restricted, denied, clarified, approved, or completed a flow and receives the explanation and trace evidence needed for review.",
                    actor_context="Reviewer or operator inspecting governed behavior",
                    business_scope="Explanation and auditability of governed outcomes",
                    capability="explain_governed_outcome",
                    service_id=default_service_id,
                    outcome_type="completed",
                    stop_condition="complete",
                ),
            )
        )

    deterministic = _proposal_envelope(
        title=f"Scenario Proposal: {project_name}",
        summary="Draft candidate PM scenarios derived from the business brief. These are intended to accelerate scenario authoring, not replace review.",
        capability="propose_scenarios",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are draft scenario candidates only. They should be accepted, edited, or rejected individually before persistence.",
            "Good PM scenarios should describe bounded behavior, actor posture, and stop conditions, not implementation details.",
        ],
        next_steps=[
            "Accept the scenario candidates that belong in the first PM draft and reject the rest explicitly.",
            "After scenario selection, formalize actor and approval differences so Developer Design has stable behavioral input.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "scenarios",
            "items": scenario_items,
        },
        mode="pm",
    )

    return await _model_or_deterministic(
        "propose_scenarios",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _propose_business_summary(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, clarification_answers = _pm_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        "product_summary",
    )
    project_name = project.get("name", project_id)
    question_families = _pm_question_family_candidates(words)
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count), ["product_summary"])
    section_questions = (section or {}).get("questions") or []

    deterministic = _proposal_envelope(
        title=f"Business Summary Proposal: {project_name}",
        summary="Draft PM-facing business summary edits derived from the supplied brief. Review these before saving them into Product Design.",
        capability="propose_business_summary",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are draft summary edits only. They should be reviewed and promoted into the canonical Business Summary artifact explicitly.",
            "Keep the Business Summary in PM language; save implementation detail for Developer Design.",
        ],
        next_steps=[
            "Accept the business summary edits that match the intended PM framing.",
            "Promote them into Business Summary and refine the language before treating the artifact as stable.",
        ],
        proposal={
            "proposal_kind": "patch_candidates",
            "artifact_type": "product_summary",
            "patches": [
                _patch_candidate("/product_purpose", "replace", f"Help users get bounded, reviewable answers or prepared next steps for {project_name} without bypassing governed approval and visibility boundaries.", "A stable purpose statement keeps PM intent legible across the rest of the flow."),
                _patch_candidate("/business_problem", "replace", f"Teams working around {project_name} currently depend on manual interpretation, uneven visibility, or inconsistent stop conditions before they can act with confidence.", "Business Summary should state the business problem in outcome language, not technical architecture language."),
                _patch_candidate("/business_goals/-", "add", "Answer recurring business questions with bounded, explainable results.", "This keeps the product focused on a concrete user outcome."),
                _patch_candidate("/business_goals/-", "add", "Preserve actor-aware visibility and governed next actions instead of collapsing everyone into the same result.", "Actor differences should stay explicit at the PM level."),
                _patch_candidate("/supported_question_families/-", "add", question_families[0], "Question families give Product Design a stable behavioral focus."),
                _patch_candidate("/supported_question_families/-", "add", question_families[-1], "Multiple question families help PM verify the product is covering the right recurring asks."),
                _patch_candidate("/governed_behavior_summary", "replace", "Return bounded answers or prepared next steps, clarify missing inputs, restrict or deny when the actor or scope does not permit more, and stop at explicit approval boundaries for higher-impact outcomes.", "This captures the core governed behavior Studio should preserve."),
                _patch_candidate("/approval_posture_summary", "replace", "The system should proceed directly for low-risk or read-oriented work, but prepare and stop at explicit approval boundaries before high-impact changes or escalations.", "Approval posture should be explicit in Product Design before Developer Design formalizes it."),
                _patch_candidate("/multi_step_composition_rules/-", "add", "Only compose multiple steps when the bounded intermediate result is visible and each stop condition remains explicit.", "Multi-step composition rules should stay legible to PMs."),
                _patch_candidate("/why_now", "replace", f"{project_name} needs a clearer governed operating model now so teams stop relying on ad hoc interpretation or hidden escalation paths.", "Why-now framing should justify the work in business terms."),
                _patch_candidate("/success_outcome_summary", "replace", "Users can get reliable bounded answers faster, while PM and reviewers can still see where the system clarified, restricted, denied, or stopped for approval.", "Success summary should stay anchored to user and governance outcomes."),
            ],
        },
        mode="pm",
    )
    if _use_deterministic_assistant(params):
        return deterministic
    return await _model_or_deterministic("propose_business_summary", params, deterministic, {"project": {"id": project_id, "name": project_name, "domain": project.get("domain"), "summary": project.get("summary")}, "source_document_text": source_text, "section_clarification_answers": clarification_answers, "deterministic_draft": deterministic}, source_text)


async def _propose_actor_model(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, clarification_answers = _pm_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        "actor_model",
    )
    project_name = project.get("name", project_id)
    actors = _pm_actor_entries(source_text, words)
    patches = [_patch_candidate("/actors/-", "add", actor, "Actor entries should stay in business language and preserve visibility, action, and approval expectations.") for actor in actors]
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count), ["actor_model"])
    section_questions = (section or {}).get("questions") or []

    deterministic = _proposal_envelope(
        title=f"Actor Model Proposal: {project_name}",
        summary="Draft PM-facing actor model edits derived from the supplied brief. Review these before saving them into Product Design.",
        capability="propose_actor_model",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Actor entries should reflect business roles, not implementation users or backend principals.",
            "If two actors behave the same way, do not invent a split just to add surface area.",
        ],
        next_steps=[
            "Accept the actor entries that reflect real business roles.",
            "Promote them into Actor Model and tighten any fuzzy visibility or approval language.",
        ],
        proposal={
            "proposal_kind": "patch_candidates",
            "artifact_type": "actor_model",
            "patches": patches,
        },
        mode="pm",
    )
    if _use_deterministic_assistant(params):
        return deterministic
    return await _model_or_deterministic("propose_actor_model", params, deterministic, {"project": {"id": project_id, "name": project_name, "domain": project.get("domain"), "summary": project.get("summary")}, "source_document_text": source_text, "section_clarification_answers": clarification_answers, "deterministic_draft": deterministic}, source_text)


async def _propose_business_areas(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, clarification_answers = _pm_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        "business_areas",
    )
    project_name = project.get("name", project_id)
    source_area_ids = _source_declared_business_area_ids(source_text)
    if source_area_ids:
        entries = [_source_business_area_entry(area_id) for area_id in source_area_ids]
    else:
        entries = _fronting_business_area_entries(source_text, words) or _pm_business_area_entries(words)
    patches = [_patch_candidate("/entries/-", "add", entry, "Business areas give PM and downstream formalization a stable vocabulary for governed responsibilities.") for entry in entries]
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count), ["business_areas"])
    section_questions = (section or {}).get("questions") or []

    deterministic = _proposal_envelope(
        title=f"Business Areas Proposal: {project_name}",
        summary="Draft PM-facing business area edits derived from the supplied brief. Review these before saving them into Product Design.",
        capability="propose_business_areas",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Business areas should be stable identifiers, not temporary project tasks.",
            "If a label will confuse PM and Dev later, rename it now before it spreads into formalization.",
        ],
        next_steps=[
            "Accept the business areas that reflect durable PM vocabulary.",
            "Promote them into Business Areas and normalize ids before treating them as canonical.",
        ],
        proposal={
            "proposal_kind": "patch_candidates",
            "artifact_type": "business_areas",
            "patches": patches,
        },
        mode="pm",
    )
    if _use_deterministic_assistant(params):
        return deterministic
    return await _model_or_deterministic("propose_business_areas", params, deterministic, {"project": {"id": project_id, "name": project_name, "domain": project.get("domain"), "summary": project.get("summary")}, "source_document_text": source_text, "section_clarification_answers": clarification_answers, "deterministic_draft": deterministic}, source_text)


async def _propose_permission_intent(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, clarification_answers = _pm_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        "permission_intent",
    )
    project_name = project.get("name", project_id)
    business_area_id = "governance_review" if _contains_any(words, "approval", "approve", "approved", "review", "escalate") else "core_workflow"
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count), ["permission_intent"])
    section_questions = (section or {}).get("questions") or []
    canonical_actor_ids: list[str] = []
    canonical_business_area_ids: list[str] = []
    for artifact in pm_artifacts:
        data = artifact.get("data") if isinstance(artifact, dict) else None
        if not isinstance(data, dict):
            continue
        if data.get("artifact_type") == "actor_model":
            actors = data.get("actors") if isinstance(data.get("actors"), list) else []
            canonical_actor_ids = [
                str(actor.get("actor_id", "")).strip()
                for actor in actors
                if isinstance(actor, dict) and str(actor.get("actor_id", "")).strip()
            ]
        elif data.get("artifact_type") == "business_areas":
            entries = data.get("entries") if isinstance(data.get("entries"), list) else []
            canonical_business_area_ids = [
                str(entry.get("business_area_id", "")).strip()
                for entry in entries
                if isinstance(entry, dict) and str(entry.get("business_area_id", "")).strip()
            ]
    actor_ids = canonical_actor_ids or _source_declared_actor_ids(source_text)
    if not actor_ids:
        actor_ids = [entry["actor_id"] for entry in _fronting_actor_entries(source_text, words)]
    business_area_ids = canonical_business_area_ids or _source_declared_business_area_ids(source_text)
    if not business_area_ids:
        business_area_ids = [entry["business_area_id"] for entry in _fronting_business_area_entries(source_text, words)]
    if not business_area_ids:
        business_area_ids = [business_area_id]
    primary_actor_id = actor_ids[0] if actor_ids else "primary_operator"
    approval_actor_id = next(
        (actor_id for actor_id in actor_ids if any(term in actor_id for term in ("leader", "manager", "owner", "admin"))),
        actor_ids[0] if actor_ids else "reviewing_manager",
    )
    primary_business_area_id = business_area_ids[0] if business_area_ids else "core_workflow"
    approval_business_area_id = (
        "governance_review"
        if "governance_review" in business_area_ids or business_area_id == "governance_review"
        else primary_business_area_id
    )

    patches = [
        _patch_candidate("/policy_summary", "replace", "Actor access should remain bounded by business area, with explicit differences between direct results, restricted outcomes, denials, clarification stops, and approval stops.", "Permission Intent should state reviewed business control posture before developers formalize it."),
    ]
    fronting_rules = _fronting_permission_rule_values(actor_ids, business_area_ids)
    if fronting_rules:
        patches.extend(
            _patch_candidate("/rules/-", "add", rule, "Governed fronting permission rules should make bounded reads, prepared previews, approval stops, clarification, denial, and audit review explicit.")
            for rule in fronting_rules
        )
    else:
        patches.append(
            _patch_candidate("/rules/-", "add", {"actor_id": primary_actor_id, "business_area": primary_business_area_id, "access_posture": "bounded", "governed_outcome_type": "bounded_result", "governed_outcome": "Return the bounded answer or prepared next step the actor is allowed to use directly.", "notes": "Use this as the default business-facing rule when the business brief does not differentiate actors more precisely."}, "The default actor rule should preserve bounded outcomes instead of unrestricted access.")
        )
        if business_area_id == "governance_review":
            patches.append(
                _patch_candidate("/rules/-", "add", {"actor_id": approval_actor_id, "business_area": approval_business_area_id, "access_posture": "approval_required", "governed_outcome_type": "approval_stop", "governed_outcome": "Prepare the recommendation and stop for explicit review before the product continues.", "notes": "Use this when business approval boundaries must be preserved explicitly."}, "Approval-bound flows should be explicit in product intent, not buried later in Dev policy."))

    deterministic = _proposal_envelope(
        title=f"Permission Intent Proposal: {project_name}",
        summary="Draft PM-facing permission intent edits derived from the supplied brief. Review these before saving them into Product Design.",
        capability="propose_permission_intent",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Permission Intent is about reviewed business trust posture, not low-level auth mechanism details.",
            "If actor ids or business area ids are still changing, stabilize them before treating permission rules as final.",
        ],
        next_steps=[
            "Accept the permission-intent edits that match the desired PM trust posture.",
            "Promote them into Permission Intent and align actor or business-area ids with the rest of Product Design.",
        ],
        proposal={
            "proposal_kind": "patch_candidates",
            "artifact_type": "permission_intent",
            "patches": patches,
        },
        mode="pm",
    )
    if _use_deterministic_assistant(params):
        return deterministic
    return await _model_or_deterministic("propose_permission_intent", params, deterministic, {"project": {"id": project_id, "name": project_name, "domain": project.get("domain"), "summary": project.get("summary")}, "canonical_product_vocabulary": {"actor_ids": canonical_actor_ids, "business_area_ids": canonical_business_area_ids}, "source_document_text": source_text, "section_clarification_answers": clarification_answers, "deterministic_draft": deterministic}, source_text)


async def _propose_non_goals(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, clarification_answers = _pm_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        "non_goals",
    )
    project_name = project.get("name", project_id)
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count), ["non_goals"])
    section_questions = (section or {}).get("questions") or []
    patches = [
        _patch_candidate("/entries/-", "add", {"statement": "Do not hide approval or stop conditions behind automatic execution.", "rationale": "PM should be explicit when the system must stop short of taking higher-impact action automatically."}, "This keeps the product bounded instead of drifting into silent automation."),
        _patch_candidate("/entries/-", "add", {"statement": "Do not collapse actor-specific visibility into one broad result for every user.", "rationale": "Actor-aware outcomes are usually central to governed product behavior."}, "Visibility posture should stay explicit and testable."),
    ]
    if _contains_any(words, "export", "download", "sync", "send"):
        patches.append(_patch_candidate("/entries/-", "add", {"statement": "Do not treat external export or downstream delivery as automatic unless PM explicitly approves it.", "rationale": "External delivery changes the product boundary and often raises governance expectations."}, "Exports or downstream pushes should not become default behavior accidentally."))

    deterministic = _proposal_envelope(
        title=f"Non-Goals Proposal: {project_name}",
        summary="Draft PM-facing non-goal edits derived from the supplied brief. Review these before saving them into Product Design.",
        capability="propose_non_goals",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Non-goals should be explicit guardrails, not vague future wishlist notes.",
            "If the brief already implies a risky extension, say so directly here instead of hoping the team remembers later.",
        ],
        next_steps=[
            "Accept the non-goals that belong in the first PM boundary definition.",
            "Promote them into Non-Goals and tighten the wording until each one reads like a durable guardrail.",
        ],
        proposal={
            "proposal_kind": "patch_candidates",
            "artifact_type": "non_goals",
            "patches": patches,
        },
        mode="pm",
    )
    if _use_deterministic_assistant(params):
        return deterministic
    return await _model_or_deterministic("propose_non_goals", params, deterministic, {"project": {"id": project_id, "name": project_name, "domain": project.get("domain"), "summary": project.get("summary")}, "source_document_text": source_text, "section_clarification_answers": clarification_answers, "deterministic_draft": deterministic}, source_text)


async def _propose_success_criteria(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, clarification_answers = _pm_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        "success_criteria",
    )
    project_name = project.get("name", project_id)
    section = _first_matching_card(_product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count), ["success_criteria"])
    section_questions = (section or {}).get("questions") or []
    patches = [
        _patch_candidate("/entries/-", "add", {"statement": "Users can get the intended bounded answer or prepared next step without needing manual interpretation first.", "evidence": "Representative scenario reviews show the product returns a usable governed outcome for the main PM question family.", "priority": "high", "review_method": "Scenario review and PM signoff"}, "Success criteria should prove the main business outcome is actually delivered."),
        _patch_candidate("/entries/-", "add", {"statement": "The product preserves visible clarification, restriction, denial, and approval boundaries when they matter.", "evidence": "Evaluation or PM review shows stop conditions and approval boundaries appear explicitly instead of being hidden.", "priority": "high", "review_method": "Verification review"}, "Governed stop conditions should be part of success, not treated as edge cases."),
    ]
    if _contains_any(words, "audit", "trace", "history", "lineage", "explain"):
        patches.append(_patch_candidate("/entries/-", "add", {"statement": "Reviewers can understand why a result or stop condition happened without reconstructing the whole system manually.", "evidence": "PM or verification review can point to explicit explanation or trace signals for a representative flow.", "priority": "medium", "review_method": "Audit and support review"}, "If the business brief implies explanation pressure, success criteria should make that evidence explicit."))

    deterministic = _proposal_envelope(
        title=f"Success Criteria Proposal: {project_name}",
        summary="Draft PM-facing success criteria edits derived from the supplied brief. Review these before saving them into Product Design.",
        capability="propose_success_criteria",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Success criteria should point to reviewable evidence, not only aspirational statements.",
            "If a criterion cannot be reviewed or observed, it will be weak input for later verification.",
        ],
        next_steps=[
            "Accept the success criteria that match the real PM evidence bar.",
            "Promote them into Success Criteria and refine the evidence language so it can be reviewed later.",
        ],
        proposal={
            "proposal_kind": "patch_candidates",
            "artifact_type": "success_criteria",
            "patches": patches,
        },
        mode="pm",
    )
    if _use_deterministic_assistant(params):
        return deterministic
    return await _model_or_deterministic("propose_success_criteria", params, deterministic, {"project": {"id": project_id, "name": project_name, "domain": project.get("domain"), "summary": project.get("summary")}, "source_document_text": source_text, "section_clarification_answers": clarification_answers, "deterministic_draft": deterministic}, source_text)


async def _propose_service_design(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "service_identity_topology",
    )
    project_name = project.get("name", project_id)
    topology_preference = _service_topology_preference(params, service_names)
    explicit_capability_ids = _explicit_capability_ids(source_text)
    explicit_service_ids = _explicit_service_ids(source_text)
    source_capability_inventory = _canonical_capability_inventory_from_source(source_text)
    if not source_capability_inventory:
        source_capability_inventory = _source_declared_service_capability_inventory(source_text)
    owned_capability_inventory = [
        entry
        for entry in source_capability_inventory
        if str(entry.get("service_id") or "").strip() and str(entry.get("capability_id") or "").strip()
    ]
    deterministic_shape = _deterministic_service_shape(
        project_name,
        service_names,
        topology_preference,
        explicit_service_ids=explicit_service_ids,
        explicit_capability_ids=explicit_capability_ids,
        source_capability_inventory=owned_capability_inventory,
        source_text=source_text,
    )
    service_label = ", ".join(service_names[:4]) if service_names else "the selected service design"
    section = _first_matching_card(_developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count), ["service_identity_topology"])
    section_questions = (section or {}).get("questions") or []
    if explicit_capability_ids:
        section_questions = [
            *section_questions,
            "Confirm which source-declared capability IDs are canonical and which service owns each one before locking Developer Design: "
            + ", ".join(explicit_capability_ids[:20]),
        ]
    if explicit_service_ids:
        section_questions = [
            *section_questions,
            "Confirm whether these source-declared service IDs are canonical service boundaries before generation: "
            + ", ".join(explicit_service_ids[:12]),
        ]

    items = [
        _proposal_item(
            "svc-owning-boundaries",
            "Draft a concrete service shape from the available product intent",
            f"Create the service boundaries, owned capabilities, owned concepts, and coordination edges that {service_label} needs for this product intent.",
            "Developer Design needs a concrete service shape before generation can produce useful service contracts.",
            "high",
            {
                "shape": {
                    **deterministic_shape,
                }
            },
        ),
        _proposal_item(
            "svc-capability-surface",
            "Formalize the capability surface each service must expose",
            "Define the stable capability contracts each service is expected to own, including which actions are read-only, which require approval, and which must stop for clarification.",
            "The generator and verifier need stable capability ownership, not only narrative service descriptions.",
            "high",
        ),
        _proposal_item(
            "svc-coordination-edges",
            "Describe the required coordination edges between services",
            "Capture where one service depends on another for bounded context, approvals, or downstream execution so coordination can be represented explicitly instead of as hidden glue.",
            "Coordination edges are easier to validate when they are declared before implementation.",
            "medium",
        ),
    ]

    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        items.append(
            _proposal_item(
                "svc-approval-boundary",
                "Keep approval boundaries outside the main happy path",
                "Identify which service should prepare a proposed action and which surface or role must approve it before the mutation boundary is crossed.",
                "Approval semantics should be explicit in service design rather than buried in one implementation path.",
                "high",
            )
        )
    if _contains_any(words, "audit", "trace", "history", "lineage", "explain"):
        items.append(
            _proposal_item(
                "svc-observability-posture",
                "Preserve explanation and traceability across service boundaries",
                "Define which service boundaries must preserve explanation, lineage, or durable evidence so later verification can reconstruct why a result or stop condition occurred.",
                "Cross-service traceability should be deliberate, not inferred after implementation exists.",
                "medium",
            )
        )

    deterministic = _proposal_envelope(
        title=f"Service Design Proposal: {project_name}",
        summary="Draft developer-facing service design guidance derived from the locked PM baseline and current service shape. These are review candidates, not final truth.",
        capability="propose_service_design",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are candidate developer design blocks only. They should be accepted, edited, or rejected individually before persistence.",
            "Service design proposals should preserve PM intent, not invent new business behavior.",
        ],
        next_steps=[
            "Accept the service design candidates that belong in the current developer pass.",
            "After service ownership is stable, formalize capability contracts and governance bindings against those boundaries.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "service_design",
            "items": items,
        },
        mode="dev",
    )
    owned_capability_ids = {
        str(entry.get("capability_id") or "").strip()
        for entry in owned_capability_inventory
        if str(entry.get("capability_id") or "").strip()
    }
    explicit_capability_id_set = set(explicit_capability_ids)
    if owned_capability_ids and explicit_capability_id_set and explicit_capability_id_set.issubset(owned_capability_ids):
        return deterministic

    return await _model_or_deterministic(
        "propose_service_design",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "source_declared_capability_id_candidates": explicit_capability_ids,
            "source_declared_service_id_candidates": explicit_service_ids,
            "source_declared_service_capability_inventory": owned_capability_inventory,
            "service_topology_preference": topology_preference,
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        },
        source_text,
        service_topology_preference=topology_preference,
    )


async def _propose_capability_formalization(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "capability_contracts",
    )
    project_name = project.get("name", project_id)
    service_label = ", ".join(service_names[:4]) if service_names else "the selected service design"
    section = _first_matching_card(_developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count), ["capability_contracts"])
    section_questions = (section or {}).get("questions") or []
    simulation_evidence = _agent_consumption_simulation_evidence(pm_artifacts)
    explicit_capability_ids = _explicit_capability_ids(source_text)
    explicit_service_ids = _explicit_service_ids(source_text)
    canonical_capability_inventory = _canonical_capability_inventory_from_source(source_text)
    expected_capability_ids = [
        str(entry.get("capability_id") or "").strip()
        for entry in canonical_capability_inventory
        if str(entry.get("capability_id") or "").strip()
    ] or explicit_capability_ids
    if expected_capability_ids:
        canonical_capability_inventory = _merge_capability_inventory_entries(
            canonical_capability_inventory,
            _capability_input_inventory_from_artifacts(pm_artifacts, expected_capability_ids),
        )
    canonical_input_inventory_present = any(isinstance(entry.get("inputs"), list) and entry.get("inputs") for entry in canonical_capability_inventory)
    canonical_contract_issues = _incomplete_capability_contracts({"capabilities": canonical_capability_inventory})
    canonical_contract_complete = bool(canonical_capability_inventory) and not canonical_contract_issues
    if expected_capability_ids:
        saved_capability_inventory = _capability_contract_inventory_from_artifacts(pm_artifacts, expected_capability_ids)
        if len(saved_capability_inventory) == len(expected_capability_ids) and not canonical_contract_complete:
            return _capability_formalization_from_inventory(
                project_name,
                saved_capability_inventory,
                section_questions,
            )
    if (
        _source_declares_canonical_capability_inventory(source_text)
        and explicit_capability_ids
        and not canonical_contract_complete
        and _has_concrete_capability_input_evidence(pm_artifacts)
        and not clarification_answers
    ):
        questions = [
            {
                "question_id": "capability-runtime-governance-and-composition",
                "prompt": (
                    "For each source-owned capability, provide reviewed capability formalization: "
                    "kind, operation_type, side_effect_level, produced effects, forbidden effects, "
                    "grant policy where approval/write-adjacent, and composition metadata where the "
                    "capability coordinates other capabilities."
                ),
                "why_it_matters": (
                    "Input contracts are present, but generation also needs reviewed runtime governance "
                    "and composition boundaries. Studio must not silently default capabilities to "
                    "atomic/read/read."
                ),
                "target_artifact": "capability_contracts",
            }
        ]
        return _proposal_envelope(
            title=f"Capability Governance Clarification: {project_name}",
            summary=(
                "Studio has reviewed input contracts, but not enough reviewed capability governance and "
                "composition evidence to draft a publishable Developer Design safely."
            ),
            capability="propose_capability_formalization",
            questions_for_user=[question["prompt"] for question in questions],
            watchouts=[
                "Do not accept atomic/read/read defaults for capabilities whose provider contract prepares approvals, drafts, routing previews, or composed outcomes.",
                "Composed capabilities need explicit steps, mappings, authority boundary, and failure policy before generation.",
            ],
            next_steps=[
                "Answer the capability governance and composition clarification.",
                "Rerun Capability Formalization so Studio can draft from reviewed contract evidence instead of guessing.",
            ],
            proposal={
                "proposal_kind": "clarification_questions",
                "mode": "dev",
                "section_key": "capability_contracts",
                "questions": questions,
            },
            mode="dev",
        )
    if (
        _source_declares_canonical_capability_inventory(source_text)
        and explicit_capability_ids
        and not canonical_input_inventory_present
        and not clarification_answers
        and not _has_concrete_capability_input_evidence(pm_artifacts)
    ):
        questions = [
            {
                "question_id": "capability-input-contracts-runtime-surface",
                "prompt": "For the source-owned capabilities, what are the reviewed runtime input names, types, required flags, defaults, and allowed values that generated services must expose?",
                "why_it_matters": "Capability IDs alone are not enough for generation. If Studio invents input names, generated services can look valid while failing regression and language parity.",
                "target_artifact": "capability_contracts",
            },
            {
                "question_id": "capability-input-contracts-ownership",
                "prompt": "Which input contract details are developer-owned implementation surface versus business-owned wording or aliases?",
                "why_it_matters": "Business docs should not carry implementation field names, but Developer Design needs a reviewed interface before package generation.",
                "target_artifact": "capability_contracts",
            },
        ]
        return _proposal_envelope(
            title=f"Capability Input Clarification: {project_name}",
            summary="Studio found canonical capability IDs, but not enough reviewed implementation input-contract detail to draft a publishable Developer Design safely.",
            capability="propose_capability_formalization",
            questions_for_user=[question["prompt"] for question in questions],
            watchouts=[
                "Autopilot, Guided Mode, and manual generation use the same readiness boundary here.",
                "Do not turn PM business specs into runtime interface specs; capture these answers as developer clarification or Developer Design evidence.",
            ],
            next_steps=[
                "Answer the implementation input-contract clarification.",
                "Rerun Capability Formalization so Studio can draft from reviewed input-contract evidence instead of guessing.",
            ],
            proposal={
                "proposal_kind": "clarification_questions",
                "mode": "dev",
                "section_key": "capability_contracts",
                "questions": questions,
            },
            mode="dev",
        )
    if explicit_capability_ids:
        section_questions = [
            *section_questions,
            "Confirm whether these source-declared capability IDs are the canonical contract IDs, and reject any paraphrased duplicates before generation: "
            + ", ".join(explicit_capability_ids[:20]),
        ]

    if canonical_contract_complete:
        return _capability_formalization_from_inventory(
            project_name,
            canonical_capability_inventory,
            section_questions,
        )

    items = [
        _proposal_item(
            "capability-stable-ids",
            "Define stable capability identifiers for each bounded action",
            f"List the bounded actions the services in {service_label} must expose and define stable capability ids that later generation and verification can rely on.",
            "Capability ids should become part of the durable technical contract, not an implementation afterthought.",
            "high",
        ),
        _proposal_item(
            "capability-input-contracts",
            "Make required inputs and clarification posture explicit",
            "Describe which inputs must be present for each capability, what ambiguity requires clarification, and which defaults are unsafe to assume automatically.",
            "Capability formalization is where required input contracts become explicit instead of hidden in runtime heuristics.",
            "high",
        ),
        _proposal_item(
            "capability-side-effects",
            "Separate read-only, approval-gated, and side-effecting capability posture",
            "Identify which capability contracts are read-only, which prepare proposals for approval, and which should only execute after a separate approval boundary is crossed.",
            "Side-effect level should be formalized before adapters or generated handlers are chosen.",
            "medium",
        ),
    ]

    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        items.append(
            _proposal_item(
                "capability-approval-rules",
                "Bind approval-sensitive capabilities explicitly",
                "Call out the capabilities that should return approval-required outcomes and the role or boundary responsible for the approval decision.",
                "Approval semantics should be attached to specific capability contracts, not only described in broad governance language.",
                "high",
            )
        )
    if _contains_any(words, "trace", "audit", "lineage", "explain"):
        items.append(
            _proposal_item(
                "capability-evidence-shape",
                "Preserve evidence and explanation shape in capability outputs",
                "Describe which capability contracts must preserve enough explanation or lineage for later review and verification.",
                "Capability outputs should carry the evidence posture the verifier and PM review will later depend on.",
                "medium",
            )
        )
    if simulation_evidence and simulation_evidence.get("status") == "fail":
        failed_cases = simulation_evidence.get("failed_cases") if isinstance(simulation_evidence.get("failed_cases"), list) else []
        items.append(
            _proposal_item(
                "capability-simulator-feedback",
                "Use simulator failures as capability-consumption review evidence",
                "Review failed agent-consumption probes and decide whether each failure needs clearer required inputs, unsupported business effects, approval posture, reviewed consumability metadata, or explicit app glue.",
                "Simulator evidence should feed the contract review loop before generation or publication, without hardcoding package-specific behavior into the generic runtime.",
                "high" if failed_cases else "medium",
            )
        )

    deterministic = _proposal_envelope(
        title=f"Capability Formalization Proposal: {project_name}",
        summary="Draft developer-facing capability formalization guidance derived from the locked PM baseline and current service design. These are review candidates, not final truth.",
        capability="propose_capability_formalization",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are candidate formalization blocks only. They should be accepted, edited, or rejected individually before persistence.",
            "Capability proposals should preserve the selected service boundaries and PM intent rather than redefining them.",
        ],
        next_steps=[
            "Accept the formalization candidates that belong in the current developer pass.",
            "Use the accepted guidance to refine Developer Capability Formalization and Governance Bindings explicitly.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "capability_formalization",
            "items": items,
        },
        mode="dev",
    )

    return await _model_or_deterministic(
        "propose_capability_formalization",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "canonical_capability_inventory": canonical_capability_inventory,
            "source_declared_capability_id_candidates": explicit_capability_ids,
            "source_declared_service_id_candidates": explicit_service_ids,
            "section_clarification_answers": clarification_answers,
            "agent_consumption_simulation": simulation_evidence,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _propose_runtime_policy_bindings(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "authority_and_approval",
    )
    project_name = project.get("name", project_id)
    service_label = ", ".join(service_names[:4]) if service_names else "the selected service design"
    section = _first_matching_card(_developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count), ["authority_and_approval"])
    section_questions = (section or {}).get("questions") or []

    items = [
        _proposal_item(
            "policy-actor-boundaries",
            "Make actor-specific allow, restrict, deny, and approval outcomes explicit",
            f"Describe which actors interacting with {service_label} should be allowed, restricted, denied, or stopped for approval at runtime, and what outcome each should receive.",
            "Runtime policy bindings should attach explicit outcomes to actors and capabilities, not leave those differences to interpretation.",
            "high",
        ),
        _proposal_item(
            "policy-scope-constraints",
            "Bind scope constraints to the runtime posture directly",
            "Call out which runtime bindings depend on region, ownership, tenant, queue, or other bounded scope constraints so the generated runtime posture can remain deterministic.",
            "Scope constraints should become machine-readable policy bindings rather than narrative caveats.",
            "high",
        ),
        _proposal_item(
            "policy-clarification-stops",
            "Separate clarification-required from denial and approval behavior",
            "Identify which runtime situations should produce clarification_required instead of deny or require_approval, especially when inputs are incomplete or ambiguous.",
            "Clarification boundaries are part of the contract and should be formalized before runtime behavior is generated.",
            "medium",
        ),
    ]

    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        items.append(
            _proposal_item(
                "policy-approval-decision-point",
                "Define who or what grants the approval decision",
                "Describe the approval decision point for high-impact operations, including whether the approver is a user, manager, or explicit policy checkpoint.",
                "Approval-required outcomes are incomplete until the approval authority is formalized.",
                "high",
            )
        )
    if _contains_any(words, "audit", "trace", "lineage", "explain"):
        items.append(
            _proposal_item(
                "policy-evidence-posture",
                "Preserve evidence posture on governed runtime outcomes",
                "Define which runtime restrictions, denials, and approval stops must return enough explanation or evidence for later review.",
                "Evidence posture should be explicit on governed outcomes, not left to ad hoc runtime formatting.",
                "medium",
            )
        )

    deterministic = _proposal_envelope(
        title=f"Runtime Policy Binding Proposal: {project_name}",
        summary="Draft developer-facing runtime policy binding guidance derived from the locked PM baseline and current service design. These are review candidates, not final truth.",
        capability="propose_runtime_policy_bindings",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are candidate runtime policy blocks only. They should be accepted, edited, or rejected individually before persistence.",
            "Runtime policy proposals should formalize PM intent and service boundaries, not invent new business roles or hidden privileges.",
        ],
        next_steps=[
            "Accept the runtime policy candidates that belong in the current developer pass.",
            "Use the accepted guidance to refine Governance Bindings and runtime principals explicitly.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "runtime_policy_bindings",
            "items": items,
        },
        mode="dev",
    )

    return await _model_or_deterministic(
        "propose_runtime_policy_bindings",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _propose_input_contracts(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "capability_contracts",
    )
    project_name = project.get("name", project_id)
    service_label = ", ".join(service_names[:4]) if service_names else "the selected service design"
    section = _first_matching_card(_developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count), ["capability_contracts"])
    section_questions = (section or {}).get("questions") or []

    items = [
        _proposal_item(
            "input-required-fields",
            "Make required inputs explicit for each bounded capability",
            f"List the inputs that each bounded capability in {service_label} requires so the runtime does not depend on hidden defaults or prompt-era assumptions.",
            "Required inputs should be explicit in the contract before generation and verification proceed.",
            "high",
        ),
        _proposal_item(
            "input-allowed-values",
            "Define allowed values and normalization expectations",
            "Call out any input fields that need enumerated values, normalization hints, or alias handling so the runtime can stay deterministic while still accepting real user phrasing.",
            "Allowed-value and normalization posture belongs in the contract rather than hidden runtime heuristics.",
            "high",
        ),
        _proposal_item(
            "input-reference-shape",
            "Separate entity references from scalar inputs",
            "State which inputs represent named entities, lists of entities, time windows, queues, or other structured references so the runtime can extract them consistently.",
            "Entity-targeted inputs should be explicit so the generated runtime can bind and validate them safely.",
            "medium",
        ),
        _proposal_item(
            "input-semantic-classification",
            "Classify input semantics before locking",
            "For every required input, record whether it is a time scope, entity reference, business category, quantity limit, or plain scalar. If the assistant cannot infer that safely from source material, it should ask the PM/dev to decide.",
            "Semantic classification is reviewed project data; Studio and generated runtimes must consume it instead of guessing from field names.",
            "high",
        ),
    ]

    if _contains_any(words, "clarify", "clarification", "missing", "ambiguous", "incomplete"):
        items.append(
            _proposal_item(
                "input-clarification-thresholds",
                "Define when missing or ambiguous inputs should stop for clarification",
                "Describe which missing fields should trigger clarification_required instead of defaulting or guessing.",
                "Clarification behavior depends on explicit input contract thresholds, not runtime guesswork.",
                "medium",
            )
        )
    if _contains_any(words, "approval", "approve", "approved", "escalate", "escalation"):
        items.append(
            _proposal_item(
                "input-approval-evidence",
                "Preserve the inputs needed at approval boundaries",
                "Call out which inputs must survive into approval review so approvers can see the same bounded request context the runtime used.",
                "Approval-ready payloads depend on stable input contracts and explicit evidence posture.",
                "medium",
            )
        )

    questions_for_user = section_questions[:3] or [
        "Which required inputs are business scopes, entity references, time scopes, categories, or simple scalar values?",
        "Which missing inputs should stop for clarification instead of being defaulted or inferred?",
        "Which inputs may be selected by the consuming app rather than stated directly by the end user?",
    ]
    canonical_capability_inventory = _canonical_capability_inventory_from_source(source_text)
    inventory_capability_ids = [
        str(entry.get("capability_id") or "").strip()
        for entry in canonical_capability_inventory
        if str(entry.get("capability_id") or "").strip()
    ]
    explicit_capability_ids = _explicit_capability_ids(source_text) if _source_declares_canonical_capability_inventory(source_text) else []
    expected_capability_ids = inventory_capability_ids or explicit_capability_ids
    inventory_has_inputs = any(isinstance(entry.get("inputs"), list) and entry.get("inputs") for entry in canonical_capability_inventory)
    inventory_input_issues = _input_contract_proposal_issues({"capabilities": canonical_capability_inventory}, expected_capability_ids)
    if inventory_has_inputs and not inventory_input_issues:
        return _input_contracts_from_inventory(project_name, canonical_capability_inventory, questions_for_user)

    input_evidence_issues = _capability_input_evidence_issues(pm_artifacts, expected_capability_ids)
    if expected_capability_ids and not input_evidence_issues:
        saved_input_inventory = _capability_input_inventory_from_artifacts(pm_artifacts, expected_capability_ids)
        if len(saved_input_inventory) == len(expected_capability_ids):
            return _input_contracts_from_inventory(project_name, saved_input_inventory, questions_for_user)
    if (
        expected_capability_ids
        and not clarification_answers
        and input_evidence_issues
    ):
        missing_evidence = input_evidence_issues
        questions = [
            {
                "question_id": "developer-input-contract-evidence-needed",
                "prompt": (
                    "Provide developer-owned runtime input-contract evidence for the source-declared "
                    "capabilities: input names, types, required flags, defaults, allowed values, "
                    "semantic types, and missing-input behavior."
                ),
                "why_it_matters": "Developer Design must not infer these as final contract truth from PM/business prose. Missing evidence: " + "; ".join(missing_evidence[:8]),
                "target_artifact": "capability_contracts",
            }
        ]
        return _proposal_envelope(
            title=f"Input Contract Clarification: {project_name}",
            summary=(
                "Studio found canonical source-declared capabilities, but no developer-owned runtime "
                "input-contract evidence. Add developer source docs or answer the implementation questions "
                "before Developer Design can safely save a revision."
            ),
            capability="propose_input_contracts",
            questions_for_user=questions_for_user,
            watchouts=[
                "Business and PM sources should not be forced to define runtime input schemas.",
                "The assistant may draft candidates only after developer evidence or explicit developer answers are available.",
            ],
            next_steps=[
                "Upload developer source docs such as service interface notes, OpenAPI/MCP/GraphQL schemas, semantic models, or runtime input-contract evidence.",
                "Or answer the missing input-contract questions and rerun this Developer Design section.",
            ],
            proposal={
                "proposal_kind": "clarification_questions",
                "mode": "dev",
                "section_key": "capability_contracts",
                "questions": questions,
            },
            mode="dev",
        )
    deterministic = _proposal_envelope(
        title=f"Input Contract Proposal: {project_name}",
        summary="Draft developer-facing input contract guidance derived from the locked PM baseline and current service design. These are review candidates, not final truth.",
        capability="propose_input_contracts",
        questions_for_user=questions_for_user,
        watchouts=[
            "These are candidate input-contract blocks only. They should be accepted, edited, or rejected individually before persistence.",
            "Input contract proposals should formalize required runtime behavior without inventing new business intent.",
        ],
        next_steps=[
            "Accept the input-contract candidates that belong in the current developer pass.",
            "Use the accepted guidance to refine Developer Capability Formalization and capability input metadata explicitly.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "input_contracts",
            "items": items,
        },
        mode="dev",
    )
    if expected_capability_ids and not _use_deterministic_assistant(params):
        return await _chunked_model_input_contracts(
            project_name=project_name,
            project=project,
            params=params,
            deterministic=deterministic,
            source_text=source_text,
            service_names=service_names,
            canonical_capability_inventory=canonical_capability_inventory,
            expected_capability_ids=expected_capability_ids,
            clarification_answers=clarification_answers,
            questions_for_user=questions_for_user,
        )

    return await _model_or_deterministic(
        "propose_input_contracts",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "canonical_capability_inventory": canonical_capability_inventory,
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _propose_verification_expectations(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "audit_and_lineage",
    )
    project_name = project.get("name", project_id)
    service_label = ", ".join(service_names[:4]) if service_names else "the selected service design"
    section = _first_matching_card(_developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count), ["audit_and_lineage"])
    section_questions = (section or {}).get("questions") or []

    items = [
        _proposal_item(
            "verification-question-family-evidence",
            "Bind supported question families to explicit verification evidence",
            f"Describe how the services in {service_label} should prove they answer the intended question families correctly, including what evidence the verifier should inspect.",
            "Question-family verification should be explicit before generation and runtime evaluation are treated as credible.",
            "high",
        ),
        _proposal_item(
            "verification-business-goal-checks",
            "Define how business goals are verified against bounded runtime behavior",
            "State which runtime outcomes or review artifacts demonstrate that the intended business goals are being met without overreaching the contract.",
            "Business-goal verification should point to bounded evidence, not only narrative confidence.",
            "high",
        ),
        _proposal_item(
            "verification-non-goal-guards",
            "Make non-goal guard checks explicit",
            "Call out how verification should prove the system avoids unsupported, unsafe, or out-of-scope behavior as the contract evolves.",
            "Non-goal guards are part of delivery truth and should be formalized before signoff.",
            "medium",
        ),
    ]

    if _contains_any(words, "success", "criteria", "evidence", "measure", "measurable"):
        items.append(
            _proposal_item(
                "verification-success-evidence",
                "Tie success criteria to explicit evidence signals",
                "Describe the checks, runtime evidence, or review artifacts that demonstrate each success criterion has been met.",
                "Success criteria should have explicit evidence posture instead of remaining subjective.",
                "high",
            )
        )
    if _contains_any(words, "scenario", "scenarios", "pack", "coverage", "family"):
        items.append(
            _proposal_item(
                "verification-scenario-pack",
                "Define scenario-pack verification expectations",
                "Identify what scenario categories, coverage depth, or review posture the verification pass must preserve before the contract is treated as stable.",
                "Scenario-pack expectations should be explicit so verification does not drift into ad hoc sampling.",
                "medium",
            )
        )

    deterministic = _proposal_envelope(
        title=f"Verification Expectations Proposal: {project_name}",
        summary="Draft developer-facing verification expectation guidance derived from the locked PM baseline and current service design. These are review candidates, not final truth.",
        capability="propose_verification_expectations",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are candidate verification expectation blocks only. They should be accepted, edited, or rejected individually before persistence.",
            "Verification proposals should formalize evidence and guard posture, not redefine PM intent or service boundaries.",
        ],
        next_steps=[
            "Accept the verification candidates that belong in the current developer pass.",
            "Use the accepted guidance to refine Verification Expectations and coverage review explicitly.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "verification_expectations",
            "items": items,
        },
        mode="dev",
    )

    return await _model_or_deterministic(
        "propose_verification_expectations",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _propose_backend_bindings(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "backend_bindings",
    )
    project_name = project.get("name", project_id)
    service_label = ", ".join(service_names[:4]) if service_names else "the selected service design"
    section = _first_matching_card(_developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count), ["backend_bindings"])
    section_questions = (section or {}).get("questions") or []

    items = [
        _proposal_item(
            "backend-data-access-target",
            "Name the governed data backend targets explicitly",
            f"Describe which read-model, warehouse, or governed data targets the services in {service_label} should bind to so generated backends do not rely on hidden environment assumptions.",
            "Backend target labels should be explicit in the contract before code generation and deployment wiring happen.",
            "high",
        ),
        _proposal_item(
            "backend-integration-system",
            "Define the application integration system and adapter target",
            "State which downstream system, adapter target, or integration surface the generated runtime should call when application-side behavior is needed.",
            "Integration system names and adapter targets should be explicit instead of buried in implementation notes.",
            "high",
        ),
        _proposal_item(
            "backend-service-overrides",
            "Call out per-service backend overrides from the shared defaults",
            "Identify which services should diverge from the shared backend defaults so the generated estate preserves the intended runtime posture per service.",
            "Per-service overrides are easier to validate when they are formalized before generation.",
            "medium",
        ),
    ]

    if _contains_any(words, "auth", "oauth", "token", "secret", "credential"):
        items.append(
            _proposal_item(
                "backend-auth-posture",
                "Make backend authentication posture explicit",
                "Describe what authentication type the generated integration path should expect so deployment and runtime configuration do not rely on unstated assumptions.",
                "Authentication posture belongs in backend bindings, not hidden environment setup.",
                "medium",
            )
        )
    if _contains_any(words, "environment", "staging", "production", "sandbox"):
        items.append(
            _proposal_item(
                "backend-environment-target",
                "Specify the backend environment target explicitly",
                "State whether generated integration bindings should target production, staging, sandbox, or another explicit environment label.",
                "Environment targeting should be explicit before generated code or manifests are trusted.",
                "medium",
            )
        )

    deterministic = _proposal_envelope(
        title=f"Backend Binding Proposal: {project_name}",
        summary="Draft developer-facing backend binding guidance derived from the locked PM baseline and current service design. These are review candidates, not final truth.",
        capability="propose_backend_bindings",
        questions_for_user=section_questions[:3],
        watchouts=[
            "These are candidate backend-binding blocks only. They should be accepted, edited, or rejected individually before persistence.",
            "Backend binding proposals should formalize implementation targets without redefining PM behavior or service boundaries.",
        ],
        next_steps=[
            "Accept the backend-binding candidates that belong in the current developer pass.",
            "Use the accepted guidance to refine Generation Settings and backend bindings explicitly.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "backend_bindings",
            "items": items,
        },
        mode="dev",
    )

    return await _model_or_deterministic(
        "propose_backend_bindings",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


def _fronting_tokens(value: Any) -> list[str]:
    return _normalized_words(str(value or ""))


def _fronting_identifier(value: str, fallback: str) -> str:
    words = _fronting_tokens(value)
    identifier = ".".join(words[:5]).strip(".")
    return identifier or fallback


def _fronting_action(operation_id: str, method: str, side_effect_level: str) -> str:
    text = f"{operation_id} {method} {side_effect_level}".lower()
    if any(term in text for term in ("delete", "remove", "destroy")):
        return "delete"
    if any(term in text for term in ("transition", "move", "approve", "close", "done")):
        return "transition"
    if any(term in text for term in ("create", "post", "insert", "publish", "send")):
        return "create"
    if any(term in text for term in ("update", "patch", "put", "comment", "assign")):
        return "update"
    if any(term in text for term in ("search", "list", "query", "find")):
        return "search"
    if any(term in text for term in ("get", "read", "fetch", "retrieve")):
        return "read"
    return "operate"


def _fronting_posture(action: str, side_effect_level: str) -> tuple[str, str, list[str], list[str]]:
    level = (side_effect_level or "").lower()
    if action in {"delete", "transition"} or level in {"write", "destructive", "mutation"}:
        return "approval_gated", "write", ["approval.required_for_state_change"], ["deny.unsupported_or_unscoped_write"]
    if action in {"create", "update"} or level in {"write_adjacent", "effect"}:
        return "prepare_then_approve", "write_adjacent", ["approval.required_before_execution"], ["deny.direct_execution_without_approval"]
    return "read_only", "read", [], ["deny.raw_export_or_overbroad_access"]


def _fronting_candidate_title(action: str, operation_id: str) -> str:
    words = [word for word in _fronting_tokens(operation_id) if word not in {"api", "mcp", "rest"}]
    subject = " ".join(words[-3:]) if words else "backend context"
    verb = {
        "search": "Search governed",
        "read": "Read governed",
        "create": "Prepare governed",
        "update": "Prepare governed",
        "transition": "Request governed",
        "delete": "Request governed",
    }.get(action, "Use governed")
    return f"{verb} {subject}".strip().title()


def _fronting_capability_item(
    *,
    project_domain: str,
    record: dict[str, Any],
    index: int,
    default_connection_ref: str,
) -> dict[str, Any]:
    operation_id = str(record.get("operation_id") or record.get("id") or f"operation_{index + 1}")
    method = str(record.get("method") or "")
    side_effect_level = str(record.get("side_effect_level") or "read")
    backend_kind = str(record.get("backend_kind") or "native_api")
    input_summary = record.get("input_schema_summary") if isinstance(record.get("input_schema_summary"), dict) else {}
    required_inputs = [str(item) for item in input_summary.get("required", []) if str(item).strip()]
    optional_inputs = [str(item) for item in input_summary.get("optional", []) if str(item).strip()]
    action = _fronting_action(operation_id, method, side_effect_level)
    execution_posture, normalized_side_effect, approval_refs, denial_refs = _fronting_posture(action, side_effect_level)
    service_id = _fronting_identifier(project_domain, "governed-service")
    capability_suffix = _fronting_identifier(operation_id, f"operation.{index + 1}")
    capability_id = f"{service_id}.{capability_suffix}"
    title = _fronting_candidate_title(action, operation_id)
    connection_ref = str(record.get("connection_id") or default_connection_ref or "")
    clarification_refs = [f"clarify.{item}" for item in required_inputs[:4]]
    body = (
        f"Expose {operation_id} through a governed ANIP capability instead of giving agents direct raw backend access. "
        f"The generated service should enforce semantic inputs, policy checks, outbound controls, and audit before calling the backend."
    )
    verification_scenarios = [
        {
            "name": f"{capability_id}.happy_path",
            "expected": "allowed",
            "purpose": "The capability can call the mapped backend operation when required context and policy are satisfied.",
        },
        {
            "name": f"{capability_id}.missing_context",
            "expected": "clarification_required",
            "purpose": "Missing semantic inputs produce a clarification instead of guessing backend arguments.",
        },
    ]
    if approval_refs:
        verification_scenarios.append(
            {
                "name": f"{capability_id}.approval_gate",
                "expected": "approval_required",
                "purpose": "Write-adjacent or state-changing behavior stops at preview or approval before execution.",
            }
        )
    structured_data = {
        "capability_id": capability_id,
        "service_id": service_id,
        "service_name": f"{service_id.replace('.', ' ').title()} Service",
        "title": title,
        "intent": body,
        "backend_bindings": [
            {
                "backend_kind": backend_kind,
                "connection_ref": connection_ref,
                "raw_operation_refs": [operation_id],
                "backend_input_mode": "implicit",
            }
        ],
        "required_inputs": required_inputs,
        "optional_inputs": optional_inputs,
        "execution_posture": execution_posture,
        "side_effect_level": normalized_side_effect,
        "approval_rule_refs": approval_refs,
        "denial_rule_refs": denial_refs,
        "clarification_rule_refs": clarification_refs,
        "outbound_controls": {
            "deny_raw_export": True,
            "sensitive_data_policy": "apply service-side filtering before downstream calls",
            "credentials_policy": "use connection references only; never store secrets in the project",
        },
        "verification_scenarios": verification_scenarios,
    }
    return _proposal_item(
        f"governed-fronting-{index + 1}",
        title,
        body,
        "Raw backend operations should become curated governed capabilities, not direct agent tools.",
        "high" if record.get("id") else "medium",
        structured_data,
    )


async def _propose_governed_fronting_capabilities(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    project, source_text, words, pm_artifacts, requirements_count, scenarios_count, shapes_count, service_names, clarification_answers = _dev_source_context(
        project_id,
        source_document_text,
        source_requirements_id,
        source_shape_id,
        "integration_fronting",
    )
    project_name = project.get("name", project_id)
    project_domain = str(project.get("domain") or project.get("slug") or project.get("name") or "governed").strip()
    integration_profile = project.get("integration_profile") if isinstance(project.get("integration_profile"), dict) else {}
    default_connection_ref = ""
    systems = integration_profile.get("systems") if isinstance(integration_profile.get("systems"), list) else []
    if systems and isinstance(systems[0], dict):
        default_connection_ref = str(systems[0].get("connection_ref") or "")

    discovery_records: list[dict[str, Any]] = []
    try:
        with get_pool().connection() as conn:
            discovery_records = [dict(row) for row in (_safe_call(list_integration_discovery_records, conn, project_id) or [])]
    except NotFoundError:
        discovery_records = []

    items = [
        _fronting_capability_item(
            project_domain=project_domain,
            record=record,
            index=index,
            default_connection_ref=default_connection_ref,
        )
        for index, record in enumerate(discovery_records[:8])
    ]

    if not items:
        generic_records = [
            {
                "id": "search-context",
                "operation_id": "search_backend_context",
                "backend_kind": integration_profile.get("kind") or "native_api",
                "side_effect_level": "read",
                "input_schema_summary": {"required": ["query", "scope"], "optional": ["limit"]},
            },
            {
                "id": "prepare-write",
                "operation_id": "prepare_backend_change",
                "backend_kind": integration_profile.get("kind") or "native_api",
                "side_effect_level": "write_adjacent",
                "input_schema_summary": {"required": ["target", "change_summary"], "optional": ["reason"]},
            },
            {
                "id": "request-transition",
                "operation_id": "request_backend_transition",
                "backend_kind": integration_profile.get("kind") or "native_api",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["target", "requested_state"], "optional": ["approval_note"]},
            },
        ]
        items = [
            _fronting_capability_item(
                project_domain=project_domain,
                record=record,
                index=index,
                default_connection_ref=default_connection_ref,
            )
            for index, record in enumerate(generic_records)
        ]

    section = _first_matching_card(
        _developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count),
        ["integration_fronting", "backend_bindings", "capability_contracts"],
    )
    section_questions = (section or {}).get("questions") or []
    if not section_questions:
        section_questions = [
            "Which raw backend operations should be exposed to agents through governed capabilities?",
            "Should write-adjacent operations stop at preview, require approval, or execute after policy passes?",
            "Which sensitive fields or scopes must be filtered before downstream backend calls?",
        ]

    deterministic = _proposal_envelope(
        title=f"Govern API / MCP Proposal: {project_name}",
        summary="Draft governed capability candidates that sit in front of selected raw backend operations. These are review candidates only; accepting a mapping remains an explicit developer action.",
        capability="propose_governed_fronting_capabilities",
        questions_for_user=section_questions[:3],
        watchouts=[
            "Do not expose every raw MCP tool or API endpoint as an ANIP capability. Curate the small behavior surface agents should actually use.",
            "Skills and prompts can help UX, but authority, approval, clarification, denial, outbound controls, and audit belong in the governed service contract.",
            "Project metadata should reference connection IDs and policy expectations only; credentials and tokens stay outside the package.",
        ],
        next_steps=[
            "Review the candidate capabilities and edit the governed mapping form for the ones that belong in this project.",
            "Add explicit approval, denial, clarification, and outbound-control rules before treating the fronting contract as generation-ready.",
            "Run Developer Definition validation and verifier scenarios after saving accepted mappings.",
        ],
        proposal={
            "proposal_kind": "candidate_blocks",
            "artifact_type": "governed_fronting_capabilities",
            "items": items,
        },
        mode="dev",
    )

    return await _model_or_deterministic(
        "propose_governed_fronting_capabilities",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
                "integration_profile": integration_profile,
            },
            "source_document_text": source_text,
            "source_shape_services": service_names,
            "integration_discovery_records": discovery_records,
            "section_clarification_answers": clarification_answers,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _identify_missing_business_info(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            source_requirements = (
                get_requirements(conn, project_id, source_requirements_id)
                if source_requirements_id
                else None
            )
            pm_artifacts = _safe_call(list_pm_artifacts, conn, project_id) or []
            requirements = _safe_call(list_requirements, conn, project_id) or []
            scenarios = _safe_call(list_scenarios, conn, project_id) or []
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    source_text = _requirements_source_text(source_requirements, source_document_text)
    if not source_text:
        raise _invalid_request("Provide source_document_text or source_requirements_id")

    words = set(_normalized_words(source_text))
    project_name = project.get("name", project_id)
    sufficiency_cards = _product_design_sufficiency(project_id, project, pm_artifacts, len(requirements), len(scenarios))
    questions = [
        {
            "question_id": f"{card['key']}-clarification-{index}",
            "prompt": question,
            "why_it_matters": f"{card['title']} cannot be drafted confidently without this decision.",
            "target_artifact": card["key"],
        }
        for card in sufficiency_cards
        if card["status"] == "needs_clarification"
        for index, question in enumerate(card["questions"][:3], start=1)
    ]
    if not questions:
        questions = _missing_business_questions_from_words(words)
    if not questions:
        questions = [
            {
                "question_id": "confirm-business-readiness",
                "prompt": "Which business decision is still most likely to change implementation behavior if it stays implicit?",
                "why_it_matters": "Even when the brief looks strong, making the highest-risk ambiguity explicit improves PM review and Developer Design quality.",
                "target_artifact": "pm_review",
            }
        ]

    deterministic = _proposal_envelope(
        title=f"Missing Business Information: {project_name}",
        summary="Questions the PM should answer before the design is treated as stable enough for downstream formalization.",
        capability="identify_missing_business_info",
        questions_for_user=[question["prompt"] for question in questions[:4]],
        watchouts=[
            "These questions are intentionally focused on business decisions that change design or verification, not generic brainstorming prompts."
        ],
        next_steps=[
            "Answer or reject the clarification questions explicitly in Product Design before locking the baseline.",
            "After the clarifications are resolved, rerun requirement and scenario proposal to improve draft quality.",
        ],
        proposal={
            "proposal_kind": "clarification_questions",
            "questions": questions,
        },
        mode="pm",
    )

    return await _model_or_deterministic(
        "identify_missing_business_info",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "source_document_text": source_text,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


async def _clarify_design_section(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    mode = str(params.get("mode", "") or "").strip().lower()
    section_key = str(params.get("section_key", "") or "").strip()
    if mode not in {"pm", "dev"}:
        raise _invalid_request("mode must be pm or dev")
    if not section_key:
        raise _invalid_request("section_key is required")

    source_document_text = _optional_param(params, "source_document_text")
    source_requirements_id = _optional_param(params, "source_requirements_id") or None
    source_shape_id = _optional_param(params, "source_shape_id") or None

    if mode == "pm":
        project, source_text, _words, pm_artifacts, requirements_count, scenarios_count, _clarification_answers = _pm_source_context(
            project_id,
            source_document_text,
            source_requirements_id,
            section_key,
        )
        card = _first_matching_card(
            _product_design_sufficiency(project_id, project, pm_artifacts, requirements_count, scenarios_count),
            [section_key],
        )
    else:
        project, source_text, _words, pm_artifacts, requirements_count, scenarios_count, shapes_count, _service_names, _clarification_answers = _dev_source_context(
            project_id,
            source_document_text,
            source_requirements_id,
            source_shape_id,
            section_key,
        )
        card = _first_matching_card(
            _developer_definition_sufficiency(project_id, pm_artifacts, requirements_count, scenarios_count, shapes_count),
            [section_key],
        )

    if not card:
        raise _invalid_request("Unknown section_key for the selected mode")

    questions = _card_clarification_questions(card)
    if not questions:
        questions = [
            {
                "question_id": f"{section_key}-confirm-readiness",
                "prompt": f"What is still ambiguous in {card['title']} that would change downstream behavior if left implicit?",
                "why_it_matters": f"{card['title']} looks largely draftable already, so the only worthwhile clarification is the one that would change contract or runtime behavior materially.",
                "target_artifact": section_key,
            }
        ]

    deterministic = _proposal_envelope(
        title=f"Clarification Questions: {project.get('name', project_id)}",
        summary=f"Targeted clarification questions for {card['title']}. This is intentionally narrow so Studio asks only for the decisions that still change the design materially.",
        capability="clarify_design_section",
        questions_for_user=[question["prompt"] for question in questions[:3]],
        watchouts=[
            "This clarification set is section-scoped on purpose. Resolve the ambiguity here before widening the assistant surface again.",
            "Do not answer more than the section actually needs; the rest should still be drafted from source or baseline.",
        ],
        next_steps=[
            f"Answer or reject the clarification questions for {card['title']}.",
            "Then rerun the recommended draft action so Studio can continue from the updated deterministic state.",
        ],
        proposal={
            "proposal_kind": "clarification_questions",
            "mode": mode,
            "section_key": section_key,
            "questions": questions,
        },
        mode=mode,
    )

    return await _model_or_deterministic(
        "clarify_design_section",
        params,
        deterministic,
        {
            "project": {
                "id": project_id,
                "name": project.get("name", project_id),
                "domain": project.get("domain"),
                "summary": project.get("summary"),
            },
            "mode": mode,
            "section_key": section_key,
            "section_title": card["title"],
            "section_status": card["status"],
            "source_document_text": source_text,
            "deterministic_draft": deterministic,
        },
        source_text,
    )


def _focus_answer_from_question(question: str, *, summary: str, mappings: list[tuple[tuple[str, ...], list[str] | str]]) -> str | None:
    q = question.strip().lower()
    if not q:
        return None
    for keywords, answer in mappings:
        if any(keyword in q for keyword in keywords):
            if isinstance(answer, list):
                if answer:
                    return " ".join(answer[:3])
            elif answer:
                return answer
    return summary


async def _explain_shape(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    shape_id = _required_param(params, "shape_id")
    question = str(params.get("question", "") or "").strip()

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            shape = get_shape(conn, project_id, shape_id)
            requirements = get_requirements(conn, project_id, shape["requirements_id"])
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    shape_data = shape["data"].get("shape", shape["data"])
    services = shape_data.get("services", [])
    coordination = shape_data.get("coordination", [])
    concepts = shape_data.get("domain_concepts", [])
    notes = _string_list(shape_data.get("notes", []))
    expectations = derive_contract_expectations(shape["data"], requirements["data"])

    type_label = "single-service" if shape_data.get("type") == "single_service" else "multi-service"
    project_name = project.get("name", project_id)
    shape_name = shape_data.get("name") or shape["title"]

    highlights: list[str] = [
        f"{shape_name} is a {type_label} design in {project_name}.",
        f"It currently defines {len(services)} service{'s' if len(services) != 1 else ''}, {len(concepts)} domain concept{'s' if len(concepts) != 1 else ''}, and {len(coordination)} coordination edge{'s' if len(coordination) != 1 else ''}.",
    ]
    if expectations:
        highlights.extend(
            f"Studio expects {item['surface']} because {item['reason']}."
            for item in expectations[:4]
        )
    elif services:
        highlights.append("This shape does not yet derive any explicit ANIP expectations from its current boundaries and requirements.")

    watchouts: list[str] = []
    if not services:
        watchouts.append("No services are defined yet, so this shape is not actionable.")
    if shape_data.get("type") == "multi_service" and not coordination:
        watchouts.append("This is marked as multi-service, but it does not yet describe how the services coordinate.")
    if not concepts:
        watchouts.append("No domain concepts are defined yet, so ownership and boundary reasoning will stay vague.")
    if not notes:
        watchouts.append("The shape does not yet record why these boundaries were chosen.")
    if any(not _string_list(service.get("capabilities", [])) for service in services):
        watchouts.append("At least one service has no listed capabilities yet, which makes the shape harder to evaluate.")

    next_steps: list[str] = []
    if not services:
        next_steps.append("Add the first service and state what it is responsible for.")
    if not concepts:
        next_steps.append("Add the main domain concepts so ownership and service boundaries become clearer.")
    if shape_data.get("type") == "multi_service" and not coordination:
        next_steps.append("Add coordination edges so the shape shows how work moves across services.")
    if not expectations:
        next_steps.append("Refine the shape until Studio can derive concrete ANIP expectations from it.")
    next_steps.append("Run evaluation against a key scenario after the next shape change.")

    summary = (
        f"This {type_label} shape is centered on {len(services)} service"
        f"{'s' if len(services) != 1 else ''}. "
        f"Studio currently derives {len(expectations)} expected ANIP exposure"
        f"{'s' if len(expectations) != 1 else ''} from the shape and requirements."
    )

    focused_answer = _focus_answer_from_question(
        question,
        summary=summary,
        mappings=[
            (("why", "decision", "choose"), notes or highlights),
            (("service", "boundary", "split"), highlights),
            (("concept", "entity", "domain"), [f"{concept.get('name', concept.get('id', 'concept'))} is owned by {concept.get('owner', 'shared')}." for concept in concepts]),
            (("anip", "protocol", "expose", "surface"), [f"{item['surface']}: {item['reason']}" for item in expectations]),
            (("risk", "approval", "authority"), [item["reason"] for item in expectations if item["surface"] == "authority_posture"] or watchouts),
            (("next", "change", "improve"), next_steps),
        ],
    )

    deterministic = {
        "title": f"Shape Explanation: {shape_name}",
        "summary": summary,
        "focused_answer": focused_answer,
        "highlights": highlights,
        "watchouts": watchouts,
        "next_steps": next_steps[:4],
    }

    model_result = await try_model_assistant_response(
        "explain_shape",
        {
            "project": {
                "id": project_id,
                "name": project_name,
            },
            "question": question,
            "shape": {
                "id": shape_id,
                "name": shape_name,
                "type": shape_data.get("type"),
                "services": services,
                "coordination": coordination,
                "domain_concepts": concepts,
                "notes": notes,
            },
            "requirements": requirements["data"],
            "derived_expectations": expectations,
            "deterministic_draft": deterministic,
        },
    )
    if model_result:
        return _merge_explanation(deterministic, model_result)
    return deterministic


def _evaluation_summary(result: str, handled: list[str], glue: list[str]) -> str:
    handled_count = len(handled)
    glue_count = len(glue)
    if result == "HANDLED":
        return (
            f"Result: {result}. This scenario is currently handled by the design. "
            f"Studio found {handled_count} handled area{'s' if handled_count != 1 else ''} and no required custom integration."
        )
    if result == "PARTIAL":
        return (
            f"Result: {result}. This scenario is partially supported. "
            f"Studio found {handled_count} handled area{'s' if handled_count != 1 else ''} and {glue_count} remaining integration gap{'s' if glue_count != 1 else ''}."
        )
    return (
        f"Result: {result}. This scenario still requires significant custom work. "
        f"Studio found {glue_count} integration gap{'s' if glue_count != 1 else ''} that the current design does not yet cover."
    )


async def _explain_evaluation(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    evaluation_id = _required_param(params, "evaluation_id")
    question = str(params.get("question", "") or "").strip()

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            evaluation_row = get_evaluation(conn, project_id, evaluation_id)
            scenario = get_scenario(conn, project_id, evaluation_row["scenario_id"])
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    payload = evaluation_row["data"].get("evaluation", {})
    result = payload.get("result", evaluation_row.get("result", "REQUIRES_GLUE"))
    handled = _string_list(payload.get("handled_by_anip", []))
    glue = _string_list(payload.get("glue_you_will_still_write", []))
    why = _string_list(payload.get("why", []))
    improve = _string_list(payload.get("what_would_improve", []))
    notes = _string_list(payload.get("notes", []))

    project_name = project.get("name", project_id)
    scenario_name = scenario["data"].get("scenario", {}).get("name") or scenario["title"]

    highlights: list[str] = [
        f"{scenario_name} was evaluated inside {project_name} and returned {result}.",
    ]
    highlights.extend(why[:3] or handled[:3])

    watchouts: list[str] = []
    if evaluation_row.get("is_stale"):
        stale = evaluation_row.get("stale_artifacts", []) or ["linked artifacts"]
        watchouts.append(f"This explanation is based on a stale evaluation because {', '.join(stale)} changed.")
    watchouts.extend(glue[:3])
    if not watchouts and notes:
        watchouts.extend(notes[:2])

    next_steps = improve[:4]
    if not next_steps and glue:
        next_steps.append("Reduce or eliminate the remaining integration gaps before treating this scenario as covered.")
    if not next_steps:
        next_steps.append("Keep pressure-testing this shape with additional scenarios.")

    summary = _evaluation_summary(result, handled, glue)
    focused_answer = _focus_answer_from_question(
        question,
        summary=summary,
        mappings=[
            (("why", "decision", "result"), why or highlights),
            (("supported", "handled", "works"), handled or highlights),
            (("glue", "gap", "missing"), glue or watchouts),
            (("next", "change", "improve"), next_steps),
            (("risk", "concern", "watch"), watchouts),
        ],
    )

    deterministic = {
        "title": f"Evaluation Explanation: {scenario_name}",
        "summary": summary,
        "focused_answer": focused_answer,
        "highlights": highlights,
        "watchouts": watchouts,
        "next_steps": next_steps,
    }

    model_result = await try_model_assistant_response(
        "explain_evaluation",
        {
            "project": {
                "id": project_id,
                "name": project_name,
            },
            "question": question,
            "scenario": {
                "id": scenario["id"],
                "title": scenario["title"],
                "data": scenario["data"],
            },
            "evaluation": {
                "id": evaluation_id,
                "result": result,
                "handled_by_anip": handled,
                "glue_you_will_still_write": glue,
                "why": why,
                "what_would_improve": improve,
                "notes": notes,
                "is_stale": evaluation_row.get("is_stale", False),
                "stale_artifacts": evaluation_row.get("stale_artifacts", []),
            },
            "deterministic_draft": deterministic,
        },
    )
    if model_result:
        return _merge_explanation(deterministic, model_result)
    return deterministic


def _review_session_id(project_id: str, shape_id: str | None, scenario_id: str | None) -> str:
    shape_part = shape_id or "current-shape"
    scenario_part = scenario_id or "default-scenario"
    return f"review::{project_id}::{shape_part}::{scenario_part}"


async def _start_design_review_session(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    shape_id = str(params.get("shape_id", "") or "").strip() or None
    scenario_id = str(params.get("scenario_id", "") or "").strip() or None

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    project_name = project.get("name", project_id)
    session_id = _review_session_id(project_id, shape_id, scenario_id)
    review_focus = [
        "Explain the service boundary in PM-friendly language.",
        "Call out the most important handoff or verification point.",
        "Highlight one thing the PM should pressure next.",
    ]
    if scenario_id:
        review_focus.append("Keep the active scenario in view while reviewing the design.")

    return {
        "session_id": session_id,
        "title": f"Design Review Session: {project_name}",
        "summary": "A bounded continuation-style review session is ready. Use the session id to stream the walkthrough.",
        "review_focus": review_focus,
        "next_step": "Call stream_design_review with this session id to walk the design progressively.",
    }


async def _stream_design_review(ctx: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    session_id = _required_param(params, "session_id")
    question = str(params.get("question", "") or "").strip()

    parts = session_id.split("::")
    if len(parts) != 4 or parts[0] != "review":
        raise _invalid_request("session_id must come from start_design_review_session")
    _, session_project_id, shape_part, scenario_part = parts
    if session_project_id != project_id:
        raise _invalid_request("session_id does not belong to the provided project_id")

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    project_name = project.get("name", project_id)
    highlights = [
        "The review keeps the current design bounded to one clear PM-facing walkthrough.",
        "Cross-service boundaries remain explicit instead of being hidden in assistant prose.",
        "The next step should come out of evaluation pressure, not from ad hoc guesswork.",
    ]
    if shape_part != "current-shape":
        highlights.insert(0, f"The walkthrough is anchored to shape {shape_part}.")
    if scenario_part != "default-scenario":
        highlights.append(f"The walkthrough keeps scenario {scenario_part} in view.")

    next_steps = [
        "Test the current design against a real scenario after this review.",
        "Capture what needs to change before widening the service boundary.",
        "Keep the shared business and engineering artifacts aligned with the reviewed design.",
    ]
    if question:
        next_steps.insert(0, f"Address the focus question directly: {question}")

    progress_events = [
        {"stage": "context", "message": f"Loading review context for {project_name}."},
        {"stage": "boundary", "message": "Explaining the current service boundary and why it exists."},
        {"stage": "next", "message": "Summarizing the next product decision to pressure."},
    ]
    for payload in progress_events:
        await ctx.emit_progress(payload)
        await asyncio.sleep(0.01)

    return {
        "session_id": session_id,
        "summary": f"Review complete for {project_name}. The design is ready for scenario pressure with a continuation-style review trail.",
        "highlights": highlights,
        "next_steps": next_steps,
    }
