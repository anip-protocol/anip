"""Curated Studio seed projects for local demos and realistic artifact output."""

from __future__ import annotations

import json

from .runtime_paths import repo_root

_REPO_ROOT = repo_root()


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")


def _load_fronting_starter_definition(source_path: str) -> dict:
    path = _REPO_ROOT / source_path
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _fronting_input_names(operation: dict, *, required: bool) -> list[str]:
    return [
        str(item.get("name", "")).strip()
        for item in operation.get("inputs", [])
        if str(item.get("name", "")).strip() and bool(item.get("required")) is required
    ]


def _fronting_input_metadata(operation: dict) -> list[dict]:
    metadata: list[dict] = []
    for item in operation.get("inputs", []):
        input_name = str(item.get("name") or item.get("input_name") or "").strip()
        if not input_name:
            continue
        metadata.append(
            {
                **item,
                "input_name": input_name,
                "input_type": str(item.get("type") or item.get("input_type") or "string"),
                "required": bool(item.get("required")),
            }
        )
    return metadata


def _fronting_execution_posture(side_effect_level: str) -> str:
    if side_effect_level == "read":
        return "read_only"
    if side_effect_level == "write":
        return "approval_gated"
    return "prepare_only"


def _fronting_is_write_like(side_effect_level: str) -> bool:
    return side_effect_level in {"approval_required", "write", "write_adjacent"}


def _fronting_operation_type(operation: dict) -> str:
    return "write" if _fronting_is_write_like(str(operation.get("side_effect_level") or "read")) else "read"


def _fronting_contract_side_effect(operation: dict) -> str:
    return str(operation.get("side_effect_level") or "read").strip() or "read"


def _fronting_produces(operation: dict) -> str:
    side_effect_level = str(operation.get("side_effect_level") or "read")
    if _fronting_is_write_like(side_effect_level):
        return "approval.request, system.preview_mutation, content.draft"
    output_intent = str(operation.get("output_intent") or "").lower()
    if "draft" in output_intent or "notes" in output_intent:
        return "content.draft, data.aggregate"
    return "content.summary, data.read"


def _fronting_does_not_produce(operation: dict) -> str:
    side_effect_level = str(operation.get("side_effect_level") or "read")
    if _fronting_is_write_like(side_effect_level):
        return "approval.execute, system.mutation, raw_data_export"
    output_intent = str(operation.get("output_intent") or "").lower()
    if "draft" in output_intent or "notes" in output_intent:
        return "external_dispatch, system.mutation, raw_data_export"
    return "raw_data_export, system.mutation"


def _fronting_default_one_time_grant_policy() -> dict:
    return {
        "allowed_grant_types": ["one_time", "session_bound"],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1,
    }


def _fronting_markdown_cell(value: object) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|").strip()


def _fronting_resolution_value(input_item: dict, key: str) -> str:
    resolution = input_item.get("resolution")
    if not isinstance(resolution, dict):
        return ""
    return str(resolution.get(key) or "").strip()


def _fronting_capability_service_id(system_id: str, service_id: str, operation: dict) -> str:
    explicit = str(operation.get("service_id") or "").strip()
    if explicit:
        return explicit
    capability_id = str(operation.get("capability_id") or "")
    if ".adapter." in capability_id:
        return f"{system_id}.adapter"
    if _fronting_is_write_like(str(operation.get("side_effect_level") or "")) and capability_id.endswith(".request"):
        return f"{system_id}.governance"
    return f"{system_id}.fronting" if system_id else service_id


def _fronting_normalized_inputs(operation: dict) -> list[dict]:
    result: list[dict] = []
    for input_item in operation.get("inputs", []):
        input_name = str(input_item.get("name") or input_item.get("input_name") or "").strip()
        if not input_name:
            continue
        normalized = {
            "input_name": input_name,
            "input_type": str(input_item.get("type") or input_item.get("input_type") or "string"),
            "required": bool(input_item.get("required")),
            "default_value": str(input_item.get("default_value") or ""),
            "allowed_values": [
                str(item).strip()
                for item in input_item.get("allowed_values", [])
                if str(item).strip()
            ],
            "semantic_type": str(input_item.get("semantic_type") or ""),
            "entity_reference": bool(input_item.get("entity_reference")),
            "catalog_ref": str(input_item.get("catalog_ref") or ""),
            "resolution": input_item.get("resolution") if isinstance(input_item.get("resolution"), dict) else {},
        }
        result.append(normalized)
    return result


def _fronting_developer_evidence_markdown(system_id: str, display_name: str, service_id: str, definition: dict) -> str:
    capabilities = [
        *definition.get("operations", []),
        *definition.get("supporting_capabilities", []),
    ]
    normalized_capabilities: list[dict] = []
    for operation in capabilities:
        capability_id = str(operation.get("capability_id") or "").strip()
        if not capability_id:
            continue
        raw_operation_refs = [
            str(item).strip()
            for item in operation.get("raw_operation_refs", [])
            if str(item).strip()
        ]
        output_intent = str(operation.get("output_intent") or "governed_fronting_result")
        normalized_capabilities.append(
            {
                "capability_id": capability_id,
                "title": str(operation.get("title") or capability_id),
                "summary": str(operation.get("summary") or "Governed fronting capability."),
                "kind": "atomic",
                "source_kind": "application_integration",
                "service_id": _fronting_capability_service_id(system_id, service_id, operation),
                "operation_type": _fronting_operation_type(operation),
                "side_effect_level": _fronting_contract_side_effect(operation),
                "execution_posture": _fronting_execution_posture(str(operation.get("side_effect_level") or "read")),
                "grant_policy": _fronting_default_one_time_grant_policy() if _fronting_is_write_like(str(operation.get("side_effect_level") or "")) else None,
                "business_effects": {
                    "produces": [item.strip() for item in _fronting_produces(operation).split(",") if item.strip()],
                    "does_not_produce": [item.strip() for item in _fronting_does_not_produce(operation).split(",") if item.strip()],
                },
                "minimum_scope": [capability_id],
                "backend_operation": "; ".join(raw_operation_refs),
                "output_shape": f"{output_intent}_result",
                "output_intent": output_intent,
                "intent_type": _fronting_execution_posture(str(operation.get("side_effect_level") or "read")),
                "subject_kind": str(operation.get("subject_kind") or "fronted_resource"),
                "context_type": str(operation.get("context_type") or "fronting_context"),
                "inputs": _fronting_normalized_inputs(operation),
            }
        )

    summary_rows = [
        "| "
        + " | ".join(
            _fronting_markdown_cell(value)
            for value in [
                capability["capability_id"],
                capability["service_id"],
                capability["operation_type"],
                capability["side_effect_level"],
                len(capability["inputs"]),
                capability["backend_operation"],
            ]
        )
        + " |"
        for capability in normalized_capabilities
    ]

    return "\n".join(
        [
            f"# {display_name} Developer Evidence",
            "",
            "Imported from the fronting starter definition. This is developer-owned evidence for Studio Autopilot and generated-service review.",
            "",
            "This document turns starter operations into explicit ANIP runtime governance and input-contract evidence. Review it against the real integration before publishing.",
            "",
            "## Capability Evidence Summary",
            "",
            "| capability_id | service_id | operation_type | side_effect_level | inputs | backend_operation |",
            "| --- | --- | --- | --- | ---: | --- |",
            *summary_rows,
            "",
            "## Reviewed Developer Evidence",
            "",
            "```json",
            json.dumps({"capability_formalizations": normalized_capabilities}, separators=(",", ":")),
            "```",
        ]
    )


def _fronting_mapping_artifacts(
    *,
    project_id: str,
    service_id: str,
    service_name: str,
    native_connection: str,
    definition: dict,
) -> list[dict]:
    artifacts: list[dict] = []
    for operation in definition.get("operations", []):
        capability_id = str(operation.get("capability_id", "")).strip()
        if not capability_id:
            continue
        required_inputs = _fronting_input_names(operation, required=True)
        optional_inputs = _fronting_input_names(operation, required=False)
        raw_operation_refs = [
            str(item).strip()
            for item in operation.get("raw_operation_refs", [])
            if str(item).strip()
        ]
        side_effect_level = str(operation.get("side_effect_level") or "read")
        backend_input_mode = str(operation.get("backend_input_mode") or "explicit")
        artifacts.append(
            {
                "id": f"{project_id}-fronting-{_slug(capability_id)}",
                "title": f"{operation.get('title') or capability_id} Fronting Mapping",
                "data": {
                    "artifact_type": "integration_fronting_capability_mapping",
                    "id": f"{project_id}-fronting-{_slug(capability_id)}",
                    "capability_id": capability_id,
                    "title": str(operation.get("title") or capability_id),
                    "intent": str(operation.get("summary") or ""),
                    "summary": str(operation.get("summary") or ""),
                    "service_id": service_id,
                    "service_name": service_name,
                    "backend_kind": "native_api",
                    "connection_ref": native_connection,
                    "raw_operation_refs": raw_operation_refs,
                    "backend_bindings": [
                        {
                            "backend_kind": "native_api",
                            "connection_ref": native_connection,
                            "raw_operation_refs": raw_operation_refs,
                            "matched_discovery_record_ids": [
                                f"{project_id}-{_slug(ref)}" for ref in raw_operation_refs
                            ],
                            "explicit_required_backend_inputs": required_inputs if backend_input_mode == "explicit" else [],
                            "explicit_optional_backend_inputs": optional_inputs if backend_input_mode == "explicit" else [],
                            "derived_required_backend_inputs": required_inputs,
                            "derived_optional_backend_inputs": optional_inputs,
                            "backend_input_mode": backend_input_mode,
                            "status": "accepted",
                            "status_detail": "Reviewed native API backend supply for the governed ANIP capability.",
                        }
                    ],
                    "execution_posture": _fronting_execution_posture(side_effect_level),
                    "side_effect_level": side_effect_level,
                    "subject_kind": str(operation.get("subject_kind") or "fronting_subject"),
                    "context_type": str(operation.get("context_type") or "fronting_context"),
                    "output_intent": str(operation.get("output_intent") or "governed_fronting_result"),
                    "required_inputs": required_inputs,
                    "optional_inputs": optional_inputs,
                    "input_metadata": _fronting_input_metadata(operation),
                    "backend_input_mode": backend_input_mode,
                    "derived_required_backend_inputs": required_inputs,
                    "derived_optional_backend_inputs": optional_inputs,
                    "explicit_required_backend_inputs": required_inputs if backend_input_mode == "explicit" else [],
                    "explicit_optional_backend_inputs": optional_inputs if backend_input_mode == "explicit" else [],
                    "approval_rule_refs": [f"approval.{_slug(capability_id)}"] if side_effect_level != "read" else [],
                    "denial_rule_refs": ["deny.raw_backend_bypass", "deny.unapproved_scope"],
                    "clarification_rule_refs": [f"clarify.{_slug(capability_id)}.missing_required_inputs"],
                    "audit_required": True,
                    "outbound_controls": ["scope_check", "backend_options_bounds", "audit_receipt"],
                },
            }
        )
    return artifacts


def _fronting_discovery_records(project_id: str, native_connection: str, definition: dict) -> list[dict]:
    records: list[dict] = []
    for operation in definition.get("operations", []):
        side_effect_level = str(operation.get("side_effect_level") or "read")
        for ref in operation.get("raw_operation_refs", []):
            operation_ref = str(ref).strip()
            if not operation_ref:
                continue
            records.append(
                {
                    "id": f"{project_id}-{_slug(operation_ref)}",
                    "connection_id": native_connection,
                    "operation_id": operation_ref,
                    "backend_kind": "native_api",
                    "method": "POST",
                    "path_template": str(operation.get("path") or f"/{operation_ref.replace('.', '/')}"),
                    "side_effect_level": side_effect_level,
                    "input_schema_summary": {
                        "required": _fronting_input_names(operation, required=True),
                        "optional": _fronting_input_names(operation, required=False),
                    },
                    "risk_notes": [
                        "Backend operation is implementation supply only; the agent-facing surface is the governed ANIP capability."
                    ],
                    "data": {
                        "capability_id": str(operation.get("capability_id") or ""),
                        "backend_input_mode": str(operation.get("backend_input_mode") or "explicit"),
                    },
                }
            )
    return records


def _fronting_scenarios(system_id: str, display_name: str, definition: dict) -> list[dict]:
    operations = [operation for operation in definition.get("operations", []) if operation.get("capability_id")]
    selected = operations[:3] or [{"capability_id": f"{system_id}.fronting.review", "title": "Review governed fronting request"}]
    scenarios: list[dict] = []
    for index, operation in enumerate(selected, start=1):
        capability_id = str(operation.get("capability_id") or f"{system_id}.fronting.review")
        title = str(operation.get("title") or capability_id)
        scenarios.append(
            {
                "id": f"scenario-{system_id}-fronting-{index}",
                "title": title,
                "data": {
                    "scenario": {
                        "name": f"{system_id}_{_slug(capability_id).replace('-', '_')}",
                        "category": "orchestration",
                        "narrative": f"A consuming agent requests {title} through the governed {display_name} ANIP fronting layer.",
                        "context": {
                            "actor": f"{system_id}_fronting_consumer",
                            "capability": capability_id,
                            "backend_supply": "native_api",
                            "authority_boundary": "curated_anip_capabilities_only",
                        },
                        "participating_services": [f"{system_id}-governance-service"],
                        "orchestration_steps": [
                            "Classify the user request into a reviewed governed capability.",
                            "Clarify missing required inputs before any downstream call.",
                            "Use the native API adapter as backend supply.",
                            "Stop at preview or approval for write-adjacent actions.",
                        ],
                        "expected_behavior": [
                            "bound_downstream_context",
                            "clarify_missing_required_inputs",
                            "hide_raw_backend_operations",
                            "audit_every_governed_call",
                        ],
                        "expected_anip_support": [
                            "capability_contracts",
                            "input_resolution",
                            "approval_grants",
                            "audit_lineage",
                        ],
                    }
                },
            }
        )
    return scenarios


def _fronting_product_artifacts(system_id: str, display_name: str, domain: str, definition: dict) -> list[dict]:
    actor_id = f"{system_id}_fronting_consumer"
    business_area = f"{system_id}_governed_workspace"
    capability_ids = [
        str(operation.get("capability_id")).strip()
        for operation in definition.get("operations", [])
        if str(operation.get("capability_id", "")).strip()
    ]
    write_like = [
        operation
        for operation in definition.get("operations", [])
        if str(operation.get("side_effect_level") or "read") != "read"
    ]
    return [
        {
            "id": f"{system_id}-fronting-product-summary",
            "title": f"{display_name} Fronting Product Summary",
            "data": {
                "artifact_type": "product_summary",
                "product_purpose": f"Provide a governed ANIP fronting layer for {display_name} so agents use reviewed capabilities instead of raw API or MCP tools.",
                "business_problem": f"Raw {display_name} integration tools expose backend operations directly and push safety into prompts, recipes, or local skills.",
                "business_goals": [
                    "Expose curated governed capabilities.",
                    "Keep raw backend operations behind adapter seams.",
                    "Require clarification, denial, audit, and approval where needed.",
                ],
                "supported_question_families": capability_ids,
                "governed_behavior_summary": "The service accepts only reviewed capability calls, validates required inputs, denies backend bypass, and records audit lineage.",
                "approval_posture_summary": (
                    "Write-adjacent actions stop at preview or approval before downstream mutation."
                    if write_like
                    else "Read-only actions are bounded and audited."
                ),
                "multi_step_composition_rules": [
                    "Prefer native API adapters by default.",
                    "Treat MCP schemas as backend evidence or alternate adapter supply, not the public product contract.",
                ],
                "why_now": "Agent tool adoption is exposing raw backend operations without enough service-owned governance.",
                "success_outcome_summary": "Agents see governed ANIP capabilities with explicit outcomes, approvals, denials, and audit evidence.",
            },
        },
        {
            "id": f"{system_id}-fronting-actor-model",
            "title": f"{display_name} Fronting Actor Model",
            "data": {
                "artifact_type": "actor_model",
                "actors": [
                    {
                        "actor_id": actor_id,
                        "title": "Fronting Service Consumer",
                        "summary": f"Uses governed {display_name} capabilities through ANIP instead of raw backend tools.",
                        "visibility_expectations": "Can see bounded results, previews, approvals, and denial reasons inside actor-visible scope.",
                        "action_expectations": "Can request governed reads and prepare/request flows; cannot bypass approval or call raw backend tools directly.",
                        "approval_expectations": "Write-adjacent operations require preview or approval before mutation.",
                        "notes": "Seeded from reviewed fronting starter capability mappings.",
                    }
                ],
            },
        },
        {
            "id": f"{system_id}-fronting-business-areas",
            "title": f"{display_name} Fronting Business Areas",
            "data": {
                "artifact_type": "business_areas",
                "entries": [
                    {
                        "business_area_id": business_area,
                        "label": f"{display_name} governed workspace",
                        "description": f"Governed {display_name} access through curated ANIP capabilities.",
                    }
                ],
            },
        },
        {
            "id": f"{system_id}-fronting-permission-intent",
            "title": f"{display_name} Fronting Permission Intent",
            "data": {
                "artifact_type": "permission_intent",
                "policy_summary": f"Allow {actor_id} to use bounded {domain} fronting capabilities; deny raw export, backend bypass, and unapproved mutation.",
                "rules": [
                    {
                        "actor_id": actor_id,
                        "business_area": business_area,
                        "access_posture": "bounded",
                        "governed_outcome_type": "bounded_result",
                        "governed_outcome": f"Actor may invoke curated {display_name} ANIP capabilities with required input validation, audit, and approval boundaries.",
                        "notes": "No raw API or MCP tool access is granted by Product Design.",
                    }
                ],
            },
        },
    ]


SEED_PROJECTS = [
    {
        "workspace": {
            "id": "ws-anip-showcases",
            "name": "ANIP Public Showcases",
            "summary": (
                "Curated public read-only showcase projects for the GTM Agent and governed fronting starters."
            ),
        },
        "project": {
            "id": "gtm-pipeline-q2-review",
            "workspace_id": "ws-anip-showcases",
            "name": "GTM Pipeline Q2 Review",
            "domain": "revenue_operations",
            "labels": ["showcase", "gtm-agent", "generated-services"],
            "summary": (
                "PM brief: Revenue operations needs a governed GTM agent system that can answer pipeline health, "
                "enrichment, prioritization, and outreach-support questions across four bounded ANIP services while "
                "preserving actor-aware visibility, explicit service handoffs, approval stops, and auditable behavior."
            ),
        },
        "seed_profiles": ["legacy_showcase"],
        "seed_update_policy": "replace_seed_artifacts",
        "static_pm_artifacts_path": "studio/server/seed_data/gtm_developer_artifacts.json",
        "pm_artifacts": [
            {
                "id": "gtm-pipeline-q2-review-product_summary",
                "title": "GTM Pipeline Product Summary",
                "data": {
                    "artifact_type": "product_summary",
                    "product_purpose": (
                        "Provide a governed GTM revenue-operations assistant system that uses four bounded ANIP "
                        "services for pipeline analytics, enrichment, prioritization, and outreach support without "
                        "exposing raw data or executing downstream changes directly."
                    ),
                    "business_problem": (
                        "Revenue teams need fast, explainable GTM insight and operational preparation, but unmanaged "
                        "agent access can overexpose CRM and enrichment data, guess missing scope, cross service "
                        "boundaries implicitly, or mutate operational systems without approval."
                    ),
                    "business_goals": [
                        "Answer bounded pipeline health and forecast questions with evidence.",
                        "Enrich selected accounts and identify lookalikes with bounded context.",
                        "Prioritize accounts and leads through explainable scoring and routing recommendations.",
                        "Draft outreach support while keeping content generation bounded and reviewable.",
                        "Identify at-risk accounts and stalled opportunities with explainable reasons.",
                        "Prepare follow-up and reassignment plans while stopping before mutation until approval is granted.",
                    ],
                    "supported_question_families": [
                        "Pipeline health and forecast summaries",
                        "Stage bottleneck and sales team performance summaries",
                        "At-risk account and stalled opportunity review",
                        "Account enrichment and lookalike analysis",
                        "Lead and account prioritization",
                        "Outreach drafting and objection-response support",
                        "Approval-gated follow-up and reassignment preparation",
                    ],
                    "governed_behavior_summary": (
                        "Return bounded service-specific outputs, ask for missing quarter, account scope, ranking basis, "
                        "or audience context, deny broad raw exports, preserve service handoff boundaries, and preserve "
                        "approval stops for write-adjacent work."
                    ),
                    "approval_posture_summary": (
                        "Direct reads are allowed when scoped; high-risk follow-up task and reassignment preparation must "
                        "produce a preview and stop for approval before downstream execution."
                    ),
                    "multi_step_composition_rules": [
                        "Compose pipeline review, enrichment, prioritization, and outreach only through explicit service boundaries.",
                        "Carry actor, task, and scope lineage across service handoffs.",
                        "Do not turn a preview into an execution step without a recorded approval decision.",
                    ],
                    "why_now": (
                        "The GTM showcase needs a realistic enterprise workflow that proves ANIP can govern useful agent behavior "
                        "without hiding policy in prompts."
                    ),
                    "success_outcome_summary": (
                        "PM can validate that all four bounded services are represented, ambiguous requests clarify, unsafe exports "
                        "are denied, service handoffs are explicit, and write-adjacent workflows stop for approval."
                    ),
                },
            },
            {
                "id": "gtm-pipeline-q2-review-actor_model",
                "title": "GTM Pipeline Actor Model",
                "data": {
                    "artifact_type": "actor_model",
                    "actors": [
                        {
                            "actor_id": "sales_leader",
                            "title": "Sales Leader",
                            "summary": "Reviews company-wide pipeline posture, risk, enrichment, prioritization, and outreach support.",
                            "visibility_expectations": "Can see bounded company-wide summaries and evidence across the GTM workflow.",
                            "action_expectations": "Can request bounded reads, draft previews, routing preparation, and approval-governed operational preparation.",
                            "approval_expectations": "Can approve governed follow-up, reassignment, and routing preparation when an approval grant is required.",
                            "notes": "Matches the runtime actor profile used by the generated GTM services.",
                        },
                        {
                            "actor_id": "rev_ops_manager",
                            "title": "RevOps Manager",
                            "summary": "Runs governed revenue-operations analysis and prepares operational changes for approval.",
                            "visibility_expectations": "Can see bounded company-wide pipeline, enrichment, prioritization, and outreach-support evidence.",
                            "action_expectations": "Can prepare follow-up, reassignment, and routing previews but does not execute or approve final mutations.",
                            "approval_expectations": "Write-adjacent requests must stop at approval_required for a sales leader or equivalent approver.",
                            "notes": "Primary operator for approval-stop scenarios.",
                        },
                        {
                            "actor_id": "account_manager_east",
                            "title": "East Account Manager",
                            "summary": "Reviews East-region pipeline, account context, prioritization, and outreach drafts within bounded scope.",
                            "visibility_expectations": "Can see bounded East-region evidence and scoped enrichment/outreach support.",
                            "action_expectations": "Can request bounded reads and draft/preparation flows within the actor-visible scope.",
                            "approval_expectations": "Operational changes must stop at approval_required before downstream mutation.",
                            "notes": "Scoped actor used to validate actor-aware regional behavior.",
                        },
                        {
                            "actor_id": "sales_analyst",
                            "title": "Sales Analyst",
                            "summary": "Inspects bounded read-only summaries with masked or limited authority.",
                            "visibility_expectations": "Can view bounded, masked analysis where allowed, but cannot prepare governed operational actions.",
                            "action_expectations": "Can request read-only summaries; preparation, routing, lookalike, and outreach-variant authority is denied.",
                            "approval_expectations": "Cannot approve or prepare governed downstream actions.",
                            "notes": "Restricted actor used to validate denial boundaries.",
                        },
                    ],
                },
            },
            {
                "id": "gtm-pipeline-q2-review-business_areas",
                "title": "GTM Pipeline Business Areas",
                "data": {
                    "artifact_type": "business_areas",
                    "entries": [
                        {
                            "business_area_id": "pipeline_review",
                            "label": "Pipeline Review",
                            "description": "Bounded pipeline health, forecast, bottleneck, performance, and product summaries.",
                        },
                        {
                            "business_area_id": "account_risk",
                            "label": "Account Risk",
                            "description": "Explainable at-risk account and stalled opportunity review.",
                        },
                        {
                            "business_area_id": "operational_preparation",
                            "label": "Operational Preparation",
                            "description": "Approval-gated follow-up task and reassignment plan preparation.",
                        },
                    ],
                },
            },
            {
                "id": "gtm-pipeline-q2-review-permission_intent",
                "title": "GTM Pipeline Permission Intent",
                "data": {
                    "artifact_type": "permission_intent",
                    "policy_summary": (
                        "Allow bounded, scoped pipeline reads; clarify missing scope; deny broad raw exports; stop write-adjacent "
                        "operational preparation at approval boundaries."
                    ),
                    "rules": [
                        {
                            "actor_id": "sales_leader",
                            "business_area": "pipeline_review",
                            "access_posture": "bounded",
                            "governed_outcome_type": "bounded_result",
                            "governed_outcome": "Return scoped summaries with evidence and no raw row-level export.",
                            "notes": "Quarter and ranking basis must be explicit or clarified.",
                        },
                        {
                            "actor_id": "rev_ops_manager",
                            "business_area": "pipeline_review",
                            "access_posture": "bounded",
                            "governed_outcome_type": "bounded_result",
                            "governed_outcome": "Return scoped summaries with evidence and no raw row-level export.",
                            "notes": "Quarter and ranking basis must be explicit or clarified.",
                        },
                        {
                            "actor_id": "account_manager_east",
                            "business_area": "pipeline_review",
                            "access_posture": "bounded",
                            "governed_outcome_type": "bounded_result",
                            "governed_outcome": "Return scoped East-region summaries with evidence and no raw row-level export.",
                            "notes": "Actor-visible scope must be preserved.",
                        },
                        {
                            "actor_id": "sales_analyst",
                            "business_area": "pipeline_review",
                            "access_posture": "bounded",
                            "governed_outcome_type": "bounded_result",
                            "governed_outcome": "Return bounded or masked read-only summaries where policy permits.",
                            "notes": "Preparation and raw exports remain denied.",
                        },
                        {
                            "actor_id": "sales_leader",
                            "business_area": "operational_preparation",
                            "access_posture": "approval_required",
                            "governed_outcome_type": "approval_stop",
                            "governed_outcome": "Prepare a preview and stop before downstream mutation unless an explicit approval grant is issued.",
                            "notes": "Covers follow-up tasks, reassignment planning, and routing preparation.",
                        },
                        {
                            "actor_id": "rev_ops_manager",
                            "business_area": "operational_preparation",
                            "access_posture": "approval_required",
                            "governed_outcome_type": "approval_stop",
                            "governed_outcome": "Prepare a preview and stop before any downstream mutation.",
                            "notes": "Covers follow-up tasks, reassignment planning, and routing preparation.",
                        },
                        {
                            "actor_id": "account_manager_east",
                            "business_area": "operational_preparation",
                            "access_posture": "approval_required",
                            "governed_outcome_type": "approval_stop",
                            "governed_outcome": "Prepare a scoped preview and stop before any downstream mutation.",
                            "notes": "Actor-visible scope must be preserved.",
                        },
                        {
                            "actor_id": "sales_analyst",
                            "business_area": "operational_preparation",
                            "access_posture": "denied",
                            "governed_outcome_type": "deny_request",
                            "governed_outcome": "Deny governed preparation, routing, and downstream mutation requests.",
                            "notes": "Sales analysts have read-only authority in this showcase.",
                        },
                    ],
                },
            },
            {
                "id": "gtm-pipeline-q2-review-non_goals",
                "title": "GTM Pipeline Non-Goals",
                "data": {
                    "artifact_type": "non_goals",
                    "entries": [
                        {
                            "statement": "Do not expose broad raw row-level CRM exports.",
                            "rationale": "The first release is a bounded summary and preparation workflow, not a data extraction tool.",
                        },
                        {
                            "statement": "Do not execute follow-up tasks or reassignment changes without explicit approval.",
                            "rationale": "Write-adjacent GTM actions must remain preview-and-approve in the governed contract.",
                        },
                        {
                            "statement": "Do not guess missing quarter, pipeline scope, or ranking basis.",
                            "rationale": "Ambiguous operational requests should clarify instead of silently choosing defaults.",
                        },
                    ],
                },
            },
            {
                "id": "gtm-pipeline-q2-review-success_criteria",
                "title": "GTM Pipeline Success Criteria",
                "data": {
                    "artifact_type": "success_criteria",
                    "entries": [
                        {
                            "statement": "Bounded pipeline and account-risk questions return useful answers with evidence.",
                            "evidence": "Regression questions for pipeline summary, forecast, bottlenecks, performance, products, and risk pass.",
                            "priority": "high",
                            "review_method": "Run the Studio verification harness and inspect answer evidence.",
                        },
                        {
                            "statement": "Ambiguous requests ask targeted clarifying questions instead of guessing.",
                            "evidence": "Missing quarter and missing ranking-basis scenarios return clarification outcomes.",
                            "priority": "high",
                            "review_method": "Run clarification-path regression scenarios.",
                        },
                        {
                            "statement": "Unsafe exports are denied and write-adjacent work stops for approval.",
                            "evidence": "Raw export requests deny; follow-up and reassignment flows produce approval-stop previews.",
                            "priority": "high",
                            "review_method": "Run denial and approval-gated regression scenarios.",
                        },
                    ],
                },
            },
        ],
        "requirements": {
            "id": "req-gtm-pipeline-q2-review",
            "title": "GTM pipeline review requirements",
            "data": {
                "system": {
                    "name": "gtm-pipeline-q2-review",
                    "domain": "revenue_operations",
                    "deployment_intent": "multi_service_estate",
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
                    "pm_defines_behavior_families_not_every_utterance": True,
                    "raw_row_level_exports_are_out_of_scope": True,
                    "followup_execution_must_stop_for_approval": True,
                    "q2_pipeline_review_must_be_reproducible_locally": True,
                    "multi_service_handoffs_must_be_explicit": True,
                    "approval_expected_for_high_risk": True,
                    "recovery_sensitive": True,
                    "blocked_failure_posture": "human_review_for_unresolved_or_approval_gated_work",
                    "clarification_required_for_missing_quarter": True,
                    "clarification_required_for_missing_ranking_basis": True,
                    "raw_export_posture": "deny_raw_row_level_exports",
                },
                "services": [
                    {
                        "name": "GTM Pipeline Service",
                        "role": "bounded pipeline review and follow-up preparation",
                    },
                    {
                        "name": "GTM Enrichment Service",
                        "role": "bounded account enrichment and lookalike analysis",
                    },
                    {
                        "name": "GTM Prioritization Service",
                        "role": "explainable account and lead scoring, prioritization, and routing recommendations",
                    },
                    {
                        "name": "GTM Outreach Service",
                        "role": "bounded outreach drafting and objection-response support",
                    },
                ],
                "risk_profile": {
                    "gtm.pipeline_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                    "gtm.pipeline_forecast_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.stage_bottleneck_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.sales_team_performance_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.product_pipeline_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.prepare_reassignment_plan": {
                        "side_effect": "reversible",
                        "high_risk": True,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": True,
                    },
                    "gtm.stalled_opportunity_review": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                    "gtm.account_risk_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                    "gtm.prepare_followup_tasks": {
                        "side_effect": "reversible",
                        "high_risk": True,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": True,
                    },
                    "gtm.account_enrichment_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                    "gtm.lookalike_accounts": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                    "gtm.score_leads": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.prioritize_accounts": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.route_leads": {
                        "side_effect": "reversible",
                        "high_risk": True,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": True,
                    },
                    "gtm.draft_outreach_message": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.suggest_followup_content": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                    "gtm.objection_response_variants": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": True,
                        "recovery_guidance_required": False,
                    },
                },
                "behavior_translation": {
                    "source_artifact_id": "req-gtm-revenue-operations-business-spec",
                    "goal_translation": [
                        "bounded_pipeline_health_summary",
                        "bounded_pipeline_forecast_summary",
                        "bounded_stage_bottleneck_summary",
                        "bounded_sales_team_performance_summary",
                        "bounded_product_pipeline_summary",
                        "bounded_account_enrichment_summary",
                        "explainable_lookalike_analysis",
                        "explainable_lead_and_account_prioritization",
                        "bounded_outreach_drafting",
                        "approval_gated_reassignment_preview",
                        "stalled_opportunity_review",
                        "account_risk_with_explainable_evidence",
                        "approval_gated_followup_preparation",
                    ],
                    "behavior_families": [
                        {
                            "class": "clear_in_scope_bounded_read",
                            "studio_expectation": "available_with_bounded_evidence",
                        },
                        {
                            "class": "ambiguity_requiring_clarification",
                            "studio_expectation": "clarification_required_without_guessing",
                        },
                        {
                            "class": "broad_or_unsafe_data_request",
                            "studio_expectation": "phase_1_denial_for_raw_row_level_export",
                        },
                        {
                            "class": "operational_write_preparation",
                            "studio_expectation": "approval_required_before_mutation",
                        },
                        {
                            "class": "explicit_service_handoff",
                            "studio_expectation": "cross_service_lineage_and_actor_scope_are_preserved",
                        },
                        {
                            "class": "out_of_scope_request",
                            "studio_expectation": "denied_without_improvisation",
                        },
                    ],
                    "representative_requests": [
                        "Which deals in our Q2 pipeline are at risk this quarter, and why?",
                        "What is our risk-adjusted pipeline forecast for 2017-Q2?",
                        "Where are the biggest stage bottlenecks in our 2017-Q2 pipeline?",
                        "How are our sales teams performing in 2017-Q2?",
                        "Show product pipeline performance for 2017-Q2.",
                        "Summarize firmographic context for the top at-risk accounts.",
                        "Find accounts that look like Acme Corporation.",
                        "Prioritize the at-risk accounts for follow-up.",
                        "Draft outreach for selected accounts using approved context only.",
                        "Prepare a reassignment plan for overloaded managers in 2017-Q2.",
                        "Show me all opportunities stuck longer than 30 days.",
                        "Rank the highest-risk accounts in our Q2 pipeline.",
                        "Prepare follow-up tasks for the highest-risk accounts in my Q2 pipeline.",
                        "Show me raw row-level records for our Q2 pipeline.",
                    ],
                },
                "source_documents": [
                    {
                        "artifact_id": "req-gtm-revenue-operations-business-spec",
                        "title": "Full GTM revenue operations business spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-pipeline-business-spec",
                        "title": "Canonical GTM business spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-pipeline-forecast-business-spec",
                        "title": "Pipeline forecast capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/pipeline-forecast-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-stage-bottleneck-business-spec",
                        "title": "Stage bottleneck capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/stage-bottleneck-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-prepare-reassignment-business-spec",
                        "title": "Reassignment preview capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/prepare-reassignment-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-sales-team-performance-business-spec",
                        "title": "Sales team performance capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/sales-team-performance-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-product-pipeline-business-spec",
                        "title": "Product pipeline capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/product-pipeline-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-pipeline-q2-review-enrichment-business-spec",
                        "title": "GTM enrichment capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/enrichment-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-pipeline-q2-review-prioritization-business-spec",
                        "title": "GTM prioritization capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/prioritization-business-spec.md",
                    },
                    {
                        "artifact_id": "req-gtm-pipeline-q2-review-outreach-business-spec",
                        "title": "GTM outreach capability spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/outreach-business-spec.md",
                    },
                ],
                "derivation": {
                    "derived_from_business_spec": True,
                    "translation_goal": (
                        "Convert the PM-readable revenue-operations business spec into bounded capability "
                        "requirements, service boundaries, behavior families, and validation expectations for "
                        "the full four-service GTM estate."
                    ),
                },
                "scale": {
                    "shape_preference": "multi_service_estate",
                    "high_availability": False,
                },
            },
        },
        "additional_requirements": [
            {
                "id": "req-gtm-revenue-operations-business-spec",
                "title": "Full GTM revenue operations business spec",
                "data": {
                    "system": {
                        "name": "gtm-revenue-operations-business-spec",
                        "domain": "revenue_operations",
                        "deployment_intent": "business_source_document",
                    },
                    "transports": {"http": False, "stdio": False, "grpc": False},
                    "trust": {"mode": "not_applicable", "checkpoints": False},
                    "auth": {},
                    "permissions": {},
                    "audit": {},
                    "lineage": {},
                    "source_document": {
                        "kind": "business_spec",
                        "format": "markdown",
                        "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                    },
                    "business_spec": {
                        "title": "GTM Revenue Operations Showcase Business Spec",
                        "summary": (
                            "Umbrella PM-readable source document for the complete GTM ANIP showcase across "
                            "pipeline analytics, enrichment, prioritization, and outreach drafting."
                        ),
                        "business_goal": [
                            "inspect pipeline health, forecast posture, risk, and bottlenecks",
                            "enrich account context and identify lookalikes",
                            "score and prioritize inbound or at-risk work",
                            "draft bounded outreach content",
                            "prepare follow-up and reassignment plans without executing mutations automatically",
                        ],
                        "services": [
                            "gtm-pipeline-service",
                            "gtm-enrichment-service",
                            "gtm-prioritization-service",
                            "gtm-outreach-service",
                        ],
                        "behavior_classes": [
                            "clear_in_scope_bounded_read",
                            "ambiguity_requiring_clarification",
                            "broad_or_unsafe_data_request",
                            "explicit_service_handoff",
                            "approval_required_before_mutation",
                            "deny_out_of_scope_requests",
                        ],
                        "non_goals": [
                            "no raw CRM or enrichment exports",
                            "no hidden cross-service composition",
                            "no downstream mutation without approval",
                            "no outreach sending from draft-only capabilities",
                        ],
                    },
                    "scale": {
                        "shape_preference": "multi_service_estate",
                        "high_availability": False,
                    },
                },
            },
            {
                "id": "req-gtm-pipeline-business-spec",
                "title": "Canonical GTM business spec",
                "data": {
                    "system": {
                        "name": "gtm-showcase-business-spec",
                        "domain": "revenue_operations",
                        "deployment_intent": "business_source_document",
                    },
                    "transports": {"http": False, "stdio": False, "grpc": False},
                    "trust": {"mode": "not_applicable", "checkpoints": False},
                    "auth": {},
                    "permissions": {},
                    "audit": {},
                    "lineage": {},
                    "source_document": {
                        "kind": "business_spec",
                        "format": "markdown",
                        "path": "docs/examples/gtm-showcase/business-spec.md",
                    },
                    "business_spec": {
                        "title": "GTM Showcase Business Spec",
                        "summary": (
                            "Canonical PM-readable source document for the GTM showcase. "
                            "This artifact exists so Studio can point back to a business document "
                            "instead of pretending the translated requirements are the source of truth."
                        ),
                        "business_goal": [
                            "summarize bounded pipeline health",
                            "summarize bounded pipeline forecast",
                            "summarize bounded stage bottlenecks",
                            "summarize bounded sales team performance",
                            "summarize bounded product pipeline",
                            "identify stalled opportunities",
                            "identify at-risk accounts with explicit evidence",
                            "prepare follow-up work without executing mutations automatically",
                        ],
                        "behavior_classes": [
                            "clear_in_scope_read",
                            "clarification_required_for_missing_scope",
                            "deny_raw_row_level_exports",
                            "approval_required_before_followup_execution",
                            "deny_out_of_scope_requests",
                        ],
                        "non_goals": [
                            "no raw enrichment export",
                            "no opaque lead-scoring internals",
                            "no outreach sending from draft-only capabilities",
                            "no unconstrained raw CRM access",
                        ],
                    },
                    "scale": {
                        "shape_preference": "production_single_service",
                        "high_availability": False,
                    },
                },
            },
        ],
        "scenario": {
            "id": "scn-gtm-pipeline-q2-review",
            "title": "Hero path: at-risk Q2 deals to approval stop",
            "data": {
                "scenario": {
                    "name": "at_risk_q2_deals_followup_preparation",
                    "category": "orchestration",
                    "narrative": (
                        "A revenue operator asks which deals in the Q2 pipeline are at risk, expects clarification when the "
                        "scope is underspecified, wants bounded evidence for why the accounts are risky, then asks the "
                        "system to prepare follow-up tasks and stop before any downstream mutation until approval exists."
                    ),
                    "context": {
                        "quarter": "2017-Q2",
                        "ranking_basis": "risk_score",
                        "owner_scope": "company",
                        "hero_flow": True,
                    },
                    "derived_from": {
                        "artifact_id": "req-gtm-revenue-operations-business-spec",
                        "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                    },
                    "expected_behavior": [
                        "quarter_and_ranking_basis_are_not_guessed_when_missing",
                        "risk_evidence_is_bounded_and_explainable",
                        "row_level_exports_are_denied",
                        "followup_plan_stops_at_approval_required",
                    ],
                    "expected_anip_support": [
                        "signed_manifest_and_discovery",
                        "purpose_bound_tokens",
                        "bounded_capability_contracts",
                        "service_metadata_validation",
                        "runtime_evidence_and_drift_analysis",
                    ],
                }
            },
        },
        "additional_scenarios": [
            {
                "id": "scn-gtm-pipeline-clarification",
                "title": "Clarification path: missing quarter or ranking basis",
                "data": {
                    "scenario": {
                        "name": "clarification_for_missing_pipeline_scope",
                        "category": "safety",
                        "narrative": (
                            "A GTM user asks for at-risk deals or top accounts without specifying the quarter or ranking basis. "
                            "The service must ask for the missing quarter or ranking basis instead of guessing."
                        ),
                        "context": {
                            "missing_parameters": ["quarter", "ranking_basis"],
                            "scope": "company",
                            "derived_from_business_spec": True,
                        },
                        "derived_from": {
                            "artifact_id": "req-gtm-revenue-operations-business-spec",
                            "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                        },
                        "expected_behavior": [
                            "clarification_required_for_missing_quarter",
                            "clarification_required_for_missing_ranking_basis",
                            "no_implicit_scope_guessing",
                        ],
                        "expected_anip_support": [
                            "clarification_required_outcome",
                            "missing_input_visibility",
                            "bounded_capability_contracts",
                        ],
                    }
                },
            },
            {
                "id": "scn-gtm-pipeline-stalled-opportunities",
                "title": "Clear read: stalled opportunities over 30 days",
                "data": {
                    "scenario": {
                        "name": "stalled_opportunity_review_over_30_days",
                        "category": "orchestration",
                        "narrative": (
                            "A GTM user asks for opportunities stuck longer than 30 days. "
                            "The service should return a bounded review of stalled opportunities with supporting evidence."
                        ),
                        "context": {
                            "quarter": "2017-Q2",
                            "stalled_days": 30,
                            "scope": "company",
                        },
                        "derived_from": {
                            "artifact_id": "req-gtm-revenue-operations-business-spec",
                            "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                        },
                        "expected_behavior": [
                            "available_for_bounded_stalled_opportunity_review",
                            "bounded_evidence_for_stall_reasoning",
                        ],
                        "expected_anip_support": [
                            "bounded_capability_contracts",
                            "auditable_read_path",
                            "service_metadata_validation",
                        ],
                    }
                },
            },
            {
                "id": "scn-gtm-pipeline-raw-export-denial",
                "title": "Phase 1 denial: raw row-level export request",
                "data": {
                    "scenario": {
                        "name": "phase_1_raw_row_level_export_denial",
                        "category": "safety",
                        "narrative": (
                            "A GTM user asks for raw row-level CRM records for the Q2 pipeline. "
                            "For Phase 1, the service must deny this request rather than improvising a narrower interpretation."
                        ),
                        "context": {
                            "quarter": "2017-Q2",
                            "requested_output": "raw_row_level_export",
                            "phase": "phase_1",
                        },
                        "derived_from": {
                            "artifact_id": "req-gtm-revenue-operations-business-spec",
                            "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                        },
                        "expected_behavior": [
                            "denied_for_raw_row_level_export",
                            "no_silent_restriction_without_policy",
                        ],
                        "expected_anip_support": [
                            "denied_outcome_visibility",
                            "policy_reason_visibility",
                            "auditable_denial_path",
                        ],
                    }
                },
            },
            {
                "id": "scn-gtm-pipeline-out-of-scope",
                "title": "Out-of-scope denial: outreach drafting request",
                "data": {
                    "scenario": {
                        "name": "phase_1_out_of_scope_outreach_drafting",
                        "category": "safety",
                        "narrative": (
                            "A GTM user asks the Phase 1 pipeline service to draft outreach content. "
                            "The service must deny the request because outreach drafting is intentionally out of scope."
                        ),
                        "context": {
                            "requested_capability": "outreach_drafting",
                            "phase": "phase_1",
                            "scope": "pipeline_service_only",
                        },
                        "derived_from": {
                            "artifact_id": "req-gtm-revenue-operations-business-spec",
                            "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                        },
                        "expected_behavior": [
                            "denied_for_phase_1_out_of_scope_request",
                            "no_improvised_cross_capability_behavior",
                        ],
                        "expected_anip_support": [
                            "denied_outcome_visibility",
                            "bounded_capability_contracts",
                            "service_metadata_validation",
                        ],
                    }
                },
            },
        ],
        "proposal": {
            "id": "prop-gtm-pipeline-q2-review",
            "title": "GTM revenue operations multi-service proposal",
            "data": {
                "proposal": {
                    "recommended_shape": "multi_service_estate",
                    "rationale": [
                        "the current GTM benchmark is a four-service estate, not a phase-1 pipeline-only service",
                        "pipeline analytics, enrichment, prioritization, and outreach have different backend shapes and governance boundaries",
                        "service-to-service composition must be explicit so actor scope, task lineage, approval posture, and audit evidence survive handoffs",
                    ],
                    "required_components": [
                        "postgres_seed_data",
                        "dbt_modeled_tables",
                        "cube_semantic_layer",
                        "enrichment_data_access_service",
                        "prioritization_rest_fronting_service",
                        "outreach_mcp_fronting_service",
                        "signed_manifest",
                        "permission_discovery",
                        "cross_service_lineage",
                        "searchable_audit",
                    ],
                    "declared_surfaces": {
                        "binding_requirements": True,
                        "authority_posture": True,
                        "followup_via": True,
                        "cross_service_handoff": True,
                    },
                    "derived_from": {
                        "artifact_id": "req-gtm-revenue-operations-business-spec",
                        "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                    },
                    "developer_translation": {
                        "source_artifact_id": "req-gtm-pipeline-q2-review",
                        "translation_goal": (
                            "Turn the PM-owned GTM revenue-operations behavior specification into a bounded four-service "
                            "ANIP estate with explicit clarification, denial, approval, service handoff, metadata, and "
                            "implementation expectations."
                        ),
                        "translation_principles": [
                            "represent pipeline, enrichment, prioritization, and outreach as separate service boundaries",
                            "encode clarification, denial, and approval_required in the service contract instead of agent glue",
                            "use Postgres plus dbt plus Cube as implementation internals for data services, not as the external capability surface",
                            "front REST and MCP backends through explicit ANIP service contracts",
                            "keep follow-up work at prepare-only until downstream mutation approval exists",
                        ],
                        "service_contract_decisions": [
                            "GTM Pipeline Service owns bounded pipeline analytics, risk, and preparation capabilities",
                            "GTM Enrichment Service owns bounded account enrichment and lookalike capabilities",
                            "GTM Prioritization Service owns explainable scoring, prioritization, and routing recommendation capabilities",
                            "GTM Outreach Service owns bounded draft-only outreach support capabilities",
                            "all read capabilities require bounded evidence rather than raw row-level export",
                            "follow-up preparation is exposed as approval-gated work, not automatic execution",
                            "raw CRM, enrichment, scoring-feature, and outreach-source exports are denied rather than narrowed silently",
                            "manifest, discovery, and runtime evidence must be sufficient for Studio conformance validation",
                        ],
                        "service_behavior_coverage": [
                            "missing quarter or ranking basis yields clarification_required in the service contract",
                            "raw row-level export requests are denied by the bounded pipeline service contract",
                            "actors asking for broader pipeline scope receive explicit restricted outcomes",
                            "actors without follow-up preparation authority are denied at the service boundary",
                            "authorized follow-up preparation returns approval_required with a durable approval request instead of mutating downstream systems",
                            "financially bounded actors receive masked values while keeping the bounded answer shape intact",
                        ],
                        "orchestration_contract_coverage": [
                            "the runtime carries actor identity into ANIP token issuance without deciding the actor-specific business outcome itself",
                            "pipeline-to-enrichment, enrichment-to-prioritization, and prioritization-to-outreach handoffs preserve task and actor lineage",
                            "approval review and audit lookup remain explicit runtime surfaces over service-recorded state",
                        ],
                        "runtime_glue_inventory": [
                            "mechanical quarter normalization still happens in the runtime before invocation",
                            "mechanical account-name and target-cohort normalization still happens in the runtime before cross-service invocation",
                            "runtime composition still selects service order, but each service owns its own bounded authority decision",
                        ],
                        "actor_policy_model": {
                            "identity_source": "delegation.root_principal claims carried through ANIP token issuance",
                            "policy_axes": [
                                "actor role",
                                "declared business scope",
                                "financial visibility level",
                                "follow-up preparation authority",
                                "follow-up approval authority",
                            ],
                            "visibility_rules": [
                                {
                                    "when": "an actor asks for a pipeline scope broader than the scope encoded in their claims",
                                    "outcome": "restricted",
                                    "rationale": "The service should return the actor-safe scope posture explicitly instead of silently broadening access.",
                                },
                                {
                                    "when": "an analytical actor lacks full financial visibility",
                                    "outcome": "success with masked financial values",
                                    "rationale": "The same bounded answer shape can remain available while sensitive values are redacted.",
                                },
                            ],
                            "approval_rules": [
                                {
                                    "action": "prepare follow-up tasks",
                                    "requester_posture": "authorized operators may receive approval_required with a durable approval request",
                                    "approver_requirement": "a separate actor with follow-up approval authority must approve the request before execution can proceed",
                                    "notes": [
                                        "request preparation authority is distinct from approval authority",
                                        "approval requests must remain queryable and auditable after creation",
                                    ],
                                }
                            ],
                            "approval_surface": {
                                "list_path": "/gtm/approvals",
                                "approve_path_template": "/gtm/approvals/{approvalRequestId}/approve",
                                "notes": [
                                    "Studio can review the durable request state through the linked approval surface.",
                                    "The approval surface is service-defined and intentionally separate from the ANIP invoke path.",
                                ],
                            },
                            "audit_expectations": [
                                "the actor identity used for the invocation must remain visible in the audit trail",
                                "different actor outcomes for the same request must remain reviewable after the fact",
                                "approval state transitions must remain durable and queryable",
                            ],
                        },
                    },
                    "expected_glue_reduction": {
                        "safety": [
                            "unbounded_raw_export_requests",
                            "improvised_followup_execution",
                        ],
                        "orchestration": [
                            "ad_hoc_pipeline_question_to_sql_translation",
                        ],
                        "observability": [
                            "manual_reconstruction_of_why_a_followup_plan_stopped",
                        ],
                    },
                }
            },
        },
        "shape": {
            "id": "shape-gtm-pipeline-q2-review",
            "title": "GTM revenue operations service estate design",
            "data": {
                "shape": {
                    "id": "gtm-revenue-operations-estate-shape",
                    "name": "GTM Revenue Operations Service Estate",
                    "type": "multi_service_estate",
                    "notes": [
                        "Represent the live GTM benchmark as four bounded ANIP services.",
                        "Clarification, denial, approval stops, and service handoffs must be visible in the contract itself.",
                    ],
                    "derived_from": {
                        "artifact_id": "req-gtm-revenue-operations-business-spec",
                        "path": "docs/examples/gtm-showcase/gtm-revenue-operations-business-spec.md",
                    },
                    "implementation_contract": {
                        "implementation_language": "python",
                        "runtime_profile": "mixed_anip_service_estate",
                        "transport_profile": "http_rest_anip_and_mcp_fronting",
                        "semantic_backends": [
                            "postgres_raw_tables",
                            "dbt_modeled_pipeline_views",
                            "cube_semantic_queries",
                            "rest_prioritization_backend",
                            "mcp_outreach_backend",
                        ],
                        "implementation_root": "examples/showcase/gtm",
                        "runtime_entrypoint": "examples/showcase/gtm/docker-compose.yml",
                        "generated_from": {
                            "studio_flow": "business_spec -> business_design -> developer_design -> generated_service_estate",
                            "generated_artifacts": [
                                "pipeline_service",
                                "enrichment_service",
                                "prioritization_service",
                                "outreach_service",
                            ],
                            "showcase_runtime_files": [
                                "examples/showcase/gtm/services/gtm_pipeline/app.py",
                                "examples/showcase/gtm/services/gtm_pipeline/capabilities.py",
                                "examples/showcase/gtm/services/gtm_pipeline/data.py",
                                "examples/showcase/gtm/services/gtm_enrichment/data.py",
                                "examples/showcase/gtm/services/gtm_prioritization_backend/app.py",
                                "examples/showcase/gtm/services/gtm_outreach_mcp_backend/app.py",
                            ],
                        },
                    },
                    "capability_contracts": [
                        {
                            "id": "gtm.pipeline_summary",
                            "purpose": "Return a bounded pipeline health summary for a quarter and optional scope.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for the pipeline summary.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to summarize, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask for the region, team, owner, or company-wide scope if the requested comparison depends on it.",
                                },
                                {
                                    "input_name": "detail_level",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "summary",
                                    "allowed_values": ["summary", "stage_breakdown"],
                                    "summary": "Reviewed PM/dev input: response detail level.",
                                    "semantic_type": "business_category",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                                "scope is underspecified for the requested comparison",
                            ],
                            "denied_when": [
                                "the user asks for raw row-level export instead of a bounded summary",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "stage mix",
                                "pipeline totals",
                                "bounded risk indicators",
                            ],
                            "implementation_notes": [
                                "read from dbt-modeled pipeline views",
                                "use Cube measures for bounded aggregations",
                            ],
                        },
                        {
                            "id": "gtm.pipeline_forecast_summary",
                            "purpose": "Return a bounded forecast summary for open pipeline with likely, best-case, and risk-adjusted views.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for the forecast.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to forecast, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "forecast_mode",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "risk_adjusted",
                                    "allowed_values": ["risk_adjusted", "likely", "best_case"],
                                    "summary": "Reviewed PM/dev input: forecast scenario to summarize.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum contributing accounts to return.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                            ],
                            "denied_when": [
                                "the user asks for raw row-level forecast export instead of a bounded summary",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "forecast totals",
                                "stage-level forecast mix",
                                "top contributing accounts",
                            ],
                            "implementation_notes": [
                                "read aggregate forecast slices through Cube over dbt-modeled GTM opportunities",
                                "mask financial forecast values when actor policy does not allow them",
                            ],
                        },
                        {
                            "id": "gtm.stage_bottleneck_summary",
                            "purpose": "Return a bounded stage bottleneck summary for open pipeline by an allowed slice.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for bottleneck analysis.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to analyze, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "slice_by",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "regional_office",
                                    "allowed_values": ["regional_office", "manager_name", "product_name"],
                                    "summary": "Reviewed PM/dev input: allowed bottleneck grouping.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum bottleneck rows to return.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                            ],
                            "denied_when": [
                                "the user asks for raw export or unsupported slicing instead of a bounded bottleneck summary",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "open opportunity accumulation by stage",
                                "average days open by allowed slice",
                                "average risk concentration by allowed slice",
                            ],
                            "implementation_notes": [
                                "read aggregate stage bottleneck slices through Cube over dbt-modeled GTM opportunities",
                                "mask financial values when actor policy does not allow them",
                            ],
                        },
                        {
                            "id": "gtm.sales_team_performance_summary",
                            "purpose": "Return a bounded sales team performance summary for a quarter and optional scope.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for team performance.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to summarize, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "slice_by",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "manager_name",
                                    "allowed_values": ["manager_name", "regional_office"],
                                    "summary": "Reviewed PM/dev input: allowed team-performance grouping.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum team rows to return.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                            ],
                            "denied_when": [
                                "the user asks for raw export or unsupported slicing instead of a bounded team performance summary",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "open pipeline by team",
                                "won revenue by team",
                                "open risk and stall indicators by team",
                            ],
                            "implementation_notes": [
                                "read aggregate team performance slices through Cube over dbt-modeled GTM pipeline views",
                                "mask financial values when actor policy does not allow them",
                            ],
                        },
                        {
                            "id": "gtm.product_pipeline_summary",
                            "purpose": "Return a bounded product pipeline summary for a quarter and optional scope.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for product pipeline performance.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to summarize, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "product_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional product focus.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum product rows to return.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                            ],
                            "denied_when": [
                                "the user asks for raw export instead of a bounded product summary",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "open pipeline by product",
                                "won revenue by product",
                                "loss and risk posture by product",
                            ],
                            "implementation_notes": [
                                "read aggregate product slices through Cube over dbt-modeled GTM opportunities",
                                "mask financial values when actor policy does not allow them",
                            ],
                        },
                        {
                            "id": "gtm.stalled_opportunity_review",
                            "purpose": "Return stalled open opportunities with bounded evidence and explainable stall reasoning.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for stalled-opportunity review.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to review, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "min_days_open",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: minimum open duration threshold.",
                                    "semantic_type": "quantity_limit",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum opportunities to return.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "stalled-days threshold is missing when the request is ambiguous",
                            ],
                            "denied_when": [
                                "the user asks for unconstrained raw pipeline export",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "days in stage",
                                "owner",
                                "account",
                                "amount bucket",
                            ],
                            "implementation_notes": [
                                "derive stall duration from modeled opportunity dates",
                            ],
                        },
                        {
                            "id": "gtm.account_risk_summary",
                            "purpose": "Rank at-risk accounts with explicit evidence for why they need attention.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for account-risk ranking.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to analyze, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: risk ranking basis.",
                                    "default_value": "risk_score",
                                    "allowed_values": ["risk_score"],
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum number of accounts to include.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                                "ranking basis is missing",
                            ],
                            "denied_when": [
                                "the request asks for unconstrained export or out-of-scope outreach work",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "open opportunity count",
                                "stalled opportunity indicators",
                                "risk score components",
                            ],
                            "implementation_notes": [
                                "risk ranking must stay explainable in the response payload",
                            ],
                        },
                        {
                            "id": "gtm.prepare_followup_tasks",
                            "purpose": "Prepare follow-up tasks for high-risk accounts without executing downstream mutations.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated write contract; the Phase 1 runtime returns an approval_required preview until approval exists",
                            "minimum_scope": ["gtm.pipeline.followup"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for follow-up preview selection.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to use for follow-up preparation, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: risk ranking basis.",
                                    "default_value": "risk_score",
                                    "allowed_values": ["risk_score"],
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum number of follow-up task previews to include.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "target accounts or quarter are missing",
                            ],
                            "denied_when": [
                                "the request asks to execute CRM mutations directly in phase 1",
                            ],
                            "approval_required_when": [
                                "any downstream task creation or CRM mutation would occur",
                            ],
                            "bounded_evidence": [
                                "proposed task preview",
                                "target account list",
                                "reason each task was suggested",
                            ],
                            "implementation_notes": [
                                "return approval_required with a preview payload instead of mutating downstream systems",
                            ],
                        },
                        {
                            "id": "gtm.prepare_reassignment_plan",
                            "purpose": "Prepare a reassignment preview for overloaded pipeline coverage without executing downstream mutations.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated write contract; the runtime returns an approval_required preview until approval exists",
                            "minimum_scope": ["gtm.pipeline.reassign"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for reassignment preview.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to use for reassignment preparation, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "selection_basis",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "manager_capacity",
                                    "allowed_values": ["manager_capacity", "stalled_risk_mix"],
                                    "summary": "Reviewed PM/dev input: reassignment candidate selection basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum reassignment candidates to include.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                            ],
                            "denied_when": [
                                "the request asks to execute assignment mutations directly",
                            ],
                            "approval_required_when": [
                                "any downstream reassignment execution would occur",
                            ],
                            "bounded_evidence": [
                                "proposed reassignment preview",
                                "source and target managers",
                                "reason each reassignment was suggested",
                            ],
                            "implementation_notes": [
                                "return approval_required with a preview payload instead of mutating assignment ownership",
                            ],
                        },
                        {
                            "id": "gtm.at_risk_followup_preparation",
                            "purpose": "Compose at-risk account review into approval-gated follow-up preparation when the target accounts must be derived safely.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated follow-up preparation contract; execution requires explicit approval",
                            "minimum_scope": ["gtm.pipeline.read", "gtm.pipeline.followup"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for at-risk account selection.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to use for at-risk follow-up preparation, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": True,
                                    "default_value": "risk_score",
                                    "allowed_values": ["risk_score"],
                                    "summary": "Reviewed PM/dev input: at-risk account ranking basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum at-risk accounts to consider.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                                "the requested at-risk account scope is underspecified",
                            ],
                            "denied_when": [
                                "the request asks to execute follow-up tasks directly or export raw account rows",
                            ],
                            "approval_required_when": [
                                "the service must prepare follow-up tasks for derived at-risk accounts",
                            ],
                            "bounded_evidence": [
                                "derived at-risk accounts",
                                "risk reasons",
                                "follow-up task preview",
                                "approval request",
                            ],
                            "implementation_notes": [
                                "compose account_risk_summary with prepare_followup_tasks inside the pipeline service boundary",
                                "return approval_required before any downstream follow-up mutation",
                            ],
                        },
                        {
                            "id": "gtm.at_risk_reassignment_preparation",
                            "purpose": "Compose at-risk account review into approval-gated reassignment preparation when the reassignment targets must be derived safely.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated reassignment preparation contract; execution requires explicit approval",
                            "minimum_scope": ["gtm.pipeline.read", "gtm.pipeline.reassign"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for at-risk account selection.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to use for at-risk reassignment preparation, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": True,
                                    "default_value": "risk_score",
                                    "allowed_values": ["risk_score"],
                                    "summary": "Reviewed PM/dev input: at-risk account ranking basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum at-risk accounts to consider.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                                "the requested at-risk account scope is underspecified",
                            ],
                            "denied_when": [
                                "the request asks to execute reassignment directly or export raw account rows",
                            ],
                            "approval_required_when": [
                                "the service must prepare reassignment recommendations for derived at-risk accounts",
                            ],
                            "bounded_evidence": [
                                "derived at-risk accounts",
                                "risk reasons",
                                "reassignment preview",
                                "approval request",
                            ],
                            "implementation_notes": [
                                "compose account_risk_summary with prepare_reassignment_plan inside the pipeline service boundary",
                                "return approval_required before any downstream reassignment mutation",
                            ],
                        },
                        {
                            "id": "gtm.account_enrichment_summary",
                            "purpose": "Return bounded firmographic and account context for selected accounts.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.enrichment.read"],
                            "inputs": [
                                {
                                    "input_name": "account_names",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: selected account cohort provided by user or app glue before enrichment.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                    "reference_catalog": ["Acme Corporation", "Codehow", "Condax"],
                                    "clarification_hint": "Ask which accounts should be enriched when no explicit account cohort is available.",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum number of accounts to summarize.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "account scope is missing",
                            ],
                            "denied_when": [
                                "the request asks for raw enrichment export or vendor-source details",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "firmographic summary",
                                "fit and intent context",
                                "approved account identifiers",
                            ],
                            "implementation_notes": [
                                "return bounded enrichment fields over selected accounts only",
                            ],
                        },
                        {
                            "id": "gtm.lookalike_accounts",
                            "purpose": "Return explainable lookalike accounts for an approved reference account or cohort.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.enrichment.read"],
                            "inputs": [
                                {
                                    "input_name": "reference_account",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: reference account name for lookalike matching.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask for the reference account when the user asks for lookalikes without naming one.",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum number of lookalike accounts to return.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "reference account or comparison basis is missing",
                            ],
                            "denied_when": [
                                "the request asks for raw similarity features or unconstrained account export",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "lookalike account list",
                                "similarity explanation",
                                "bounded fit signals",
                            ],
                            "implementation_notes": [
                                "preserve explainability and avoid raw feature export",
                            ],
                        },
                        {
                            "id": "gtm.at_risk_account_enrichment_summary",
                            "purpose": "Enrich accounts selected from a bounded at-risk account review without exposing raw enrichment data.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read", "gtm.enrichment.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for at-risk account selection.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to use for at-risk account enrichment, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "risk_score",
                                    "allowed_values": ["risk_score"],
                                    "summary": "Reviewed PM/dev input: at-risk account ranking basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum accounts to enrich.",
                                    "semantic_type": "quantity_limit",
                                },
                            ],
                            "clarification_required_when": [
                                "quarter is missing",
                            ],
                            "denied_when": [
                                "the request asks for raw enrichment export or unsupported outreach behavior",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "at-risk account list",
                                "bounded enrichment summary",
                                "fit and context evidence",
                            ],
                            "implementation_notes": [
                                "derive the account set from the bounded account-risk review before enrichment",
                            ],
                        },
                        {
                            "id": "gtm.score_leads",
                            "purpose": "Score bounded leads or accounts with explainable reasons.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.prioritization.read"],
                            "inputs": [
                                {
                                    "input_name": "cohort_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["inbound_last_week", "webinar_q2"],
                                    "summary": "Reviewed PM/dev input: approved lead cohort reference.",
                                    "semantic_type": "cohort_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which approved lead cohort should be scored.",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum leads to return.",
                                    "semantic_type": "quantity_limit",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional actor-safe ownership scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "target lead or account cohort is missing",
                            ],
                            "denied_when": [
                                "the request asks for raw model features or opaque scoring internals",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "score band",
                                "reason codes",
                                "approved target cohort",
                            ],
                            "implementation_notes": [
                                "front the prioritization REST backend through ANIP with bounded scoring evidence",
                            ],
                        },
                        {
                            "id": "gtm.prioritize_accounts",
                            "purpose": "Prioritize bounded accounts for GTM action with explainable ranking.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.prioritization.read"],
                            "inputs": [
                                {
                                    "input_name": "cohort_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["expansion_candidates_q2", "at_risk_q2"],
                                    "summary": "Reviewed PM/dev input: approved account cohort reference.",
                                    "semantic_type": "cohort_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which approved account cohort should be prioritized.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "deal_likelihood",
                                    "allowed_values": ["deal_likelihood"],
                                    "summary": "Reviewed PM/dev input: account prioritization ranking basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum accounts to return.",
                                    "semantic_type": "quantity_limit",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional actor-safe ownership scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "ranking basis or account cohort is missing",
                            ],
                            "denied_when": [
                                "the request asks for unconstrained account export or raw scoring internals",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "ranked account list",
                                "reason codes",
                                "priority bands",
                            ],
                            "implementation_notes": [
                                "ranking must stay explainable and actor-scoped",
                            ],
                        },
                        {
                            "id": "gtm.route_leads",
                            "purpose": "Prepare bounded routing recommendations without executing downstream assignment mutations.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated routing recommendation contract; execution requires explicit approval",
                            "minimum_scope": ["gtm.prioritization.route"],
                            "inputs": [
                                {
                                    "input_name": "cohort_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["inbound_last_week", "webinar_q2"],
                                    "summary": "Reviewed PM/dev input: approved lead cohort reference for routing.",
                                    "semantic_type": "cohort_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which approved lead cohort should be routed.",
                                },
                                {
                                    "input_name": "target_queue",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["sales", "sdr"],
                                    "summary": "Reviewed PM/dev input: destination queue or team.",
                                    "semantic_type": "business_category",
                                    "clarification_hint": "Ask which queue or team should receive the routing recommendation.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional actor-safe ownership scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "routing target cohort or routing objective is missing",
                            ],
                            "denied_when": [
                                "the request asks to execute routing directly without approval",
                            ],
                            "approval_required_when": [
                                "any downstream routing mutation would occur",
                            ],
                            "bounded_evidence": [
                                "routing recommendation preview",
                                "target owner or queue",
                                "reason each route was suggested",
                            ],
                            "implementation_notes": [
                                "return approval_required for any operational route execution",
                            ],
                        },
                        {
                            "id": "gtm.prioritized_routing_preparation",
                            "purpose": "Compose lead scoring into approval-gated routing preparation when routing targets must be derived safely.",
                            "side_effect_type": "write",
                            "side_effect_detail": "approval-gated prioritized routing preparation contract; execution requires explicit approval",
                            "minimum_scope": ["gtm.prioritization.read", "gtm.prioritization.route"],
                            "inputs": [
                                {
                                    "input_name": "cohort_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["inbound_last_week", "webinar_q2"],
                                    "summary": "Reviewed PM/dev input: approved lead cohort to score before routing.",
                                    "semantic_type": "cohort_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which approved lead cohort should be scored before routing.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "deal_likelihood",
                                    "allowed_values": ["deal_likelihood"],
                                    "summary": "Reviewed PM/dev input: prioritization ranking basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum leads to consider for routing.",
                                    "semantic_type": "quantity_limit",
                                },
                                {
                                    "input_name": "target_queue",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "sales",
                                    "allowed_values": ["sales", "sdr"],
                                    "summary": "Reviewed PM/dev input: destination queue or team for the routing recommendation.",
                                    "semantic_type": "business_category",
                                    "clarification_hint": "Ask which queue or team should receive the routing recommendation only when the user rejects the default sales queue.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional actor-safe ownership scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "lead cohort is missing",
                            ],
                            "denied_when": [
                                "the request asks to execute routing directly or bypass approval",
                            ],
                            "approval_required_when": [
                                "the service must prepare routing recommendations for derived prioritized leads",
                            ],
                            "bounded_evidence": [
                                "scored lead list",
                                "routing recommendation preview",
                                "approval request",
                            ],
                            "implementation_notes": [
                                "compose score_leads with route_leads inside the prioritization service boundary",
                                "return approval_required before any downstream routing mutation",
                            ],
                        },
                        {
                            "id": "gtm.draft_outreach_message",
                            "purpose": "Draft bounded outreach content for approved account or contact context.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.outreach.draft"],
                            "inputs": [
                                {
                                    "input_name": "target_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: lead or account reference for the draft.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which lead or account the draft should target.",
                                },
                                {
                                    "input_name": "objective",
                                    "input_type": "string",
                                    "required": True,
                                    "default_value": "first_touch",
                                    "allowed_values": ["first_touch", "follow_up", "revive_stalled"],
                                    "summary": "Reviewed PM/dev input: outreach objective.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "channel",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "email",
                                    "allowed_values": ["email", "linkedin", "call_follow_up"],
                                    "summary": "Reviewed PM/dev input: draft channel.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "persona",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: target persona or audience.",
                                    "semantic_type": "audience_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "audience, account context, or outreach objective is missing",
                            ],
                            "denied_when": [
                                "the request asks to send outreach or use unapproved context",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "draft message",
                                "source context summary",
                                "review notes",
                            ],
                            "implementation_notes": [
                                "front the outreach MCP backend through ANIP as draft-only support",
                            ],
                        },
                        {
                            "id": "gtm.suggest_followup_content",
                            "purpose": "Suggest bounded follow-up content for an approved outreach or account context.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.outreach.draft"],
                            "inputs": [
                                {
                                    "input_name": "target_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: lead or account reference for follow-up content.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which lead or account the follow-up content should target.",
                                },
                                {
                                    "input_name": "variant_count",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum variants to return.",
                                    "semantic_type": "quantity_limit",
                                },
                                {
                                    "input_name": "persona",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: target persona or audience.",
                                    "semantic_type": "audience_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "follow-up context or objective is missing",
                            ],
                            "denied_when": [
                                "the request asks to send messages or bypass review",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "suggested content",
                                "reasoning summary",
                                "approved context references",
                            ],
                            "implementation_notes": [
                                "content suggestions remain draft-only and reviewable",
                            ],
                        },
                        {
                            "id": "gtm.objection_response_variants",
                            "purpose": "Generate bounded objection-response variants for a known account or outreach scenario.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.outreach.draft"],
                            "inputs": [
                                {
                                    "input_name": "objection_theme",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["pricing", "competitor", "implementation_risk"],
                                    "summary": "Reviewed PM/dev input: objection category selected by the consuming app or provided by the user.",
                                    "semantic_type": "business_category",
                                    "clarification_hint": "Ask which objection category applies if the request does not make it clear.",
                                },
                                {
                                    "input_name": "target_ref",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional account or lead reference.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "persona",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: target persona or audience.",
                                    "semantic_type": "audience_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "objection, audience, or account context is missing",
                            ],
                            "denied_when": [
                                "the request asks to send responses or invent unsupported claims",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "response variants",
                                "approved claims",
                                "review caveats",
                            ],
                            "implementation_notes": [
                                "variants must stay within approved business context and remain draft-only",
                            ],
                        },
                        {
                            "id": "gtm.prioritized_outreach_draft",
                            "purpose": "Prioritize a bounded account cohort, include bounded enrichment context for the top accounts, and draft one outreach message for the highest-priority account.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.prioritization.read", "gtm.outreach.read"],
                            "inputs": [
                                {
                                    "input_name": "cohort_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "allowed_values": ["expansion_candidates_q2", "at_risk_q2"],
                                    "summary": "Reviewed PM/dev input: approved account cohort to prioritize before drafting.",
                                    "semantic_type": "cohort_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which approved account cohort should be prioritized before drafting outreach.",
                                },
                                {
                                    "input_name": "ranking_basis",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "deal_likelihood",
                                    "allowed_values": ["deal_likelihood"],
                                    "summary": "Reviewed PM/dev input: prioritization ranking basis.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "limit",
                                    "input_type": "integer",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: maximum accounts to consider before drafting.",
                                    "semantic_type": "quantity_limit",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "objective",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "first_touch",
                                    "allowed_values": ["first_touch", "follow_up", "revive_stalled"],
                                    "summary": "Reviewed PM/dev input: outreach objective.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "channel",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "email",
                                    "allowed_values": ["email", "linkedin", "call_follow_up"],
                                    "summary": "Reviewed PM/dev input: requested outreach channel.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "persona",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: target persona or audience.",
                                    "semantic_type": "audience_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "account cohort is missing",
                            ],
                            "denied_when": [
                                "the request asks to send outreach or execute downstream mutations",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "prioritized account list",
                                "bounded enrichment context",
                                "selected draft target",
                                "draft outreach content",
                            ],
                            "implementation_notes": [
                                "select the top bounded account from the prioritization result, include bounded enrichment context, then draft outreach",
                            ],
                        },
                        {
                            "id": "gtm.bottleneck_account_outreach_draft",
                            "purpose": "Draft outreach for a specific account selected from a bounded bottleneck or at-risk account review.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read", "gtm.outreach.read"],
                            "inputs": [
                                {
                                    "input_name": "quarter",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: business quarter for bottleneck context.",
                                    "semantic_type": "time_scope",
                                    "input_format": "business_quarter",
                                    "validation_pattern": "^\\d{4}-Q[1-4]$",
                                    "clarification_hint": "Ask which quarter to use for bottleneck-based outreach drafting, using a value like 2017-Q2.",
                                },
                                {
                                    "input_name": "target_ref",
                                    "input_type": "string",
                                    "required": True,
                                    "summary": "Reviewed PM/dev input: specific account selected from the bottleneck or at-risk review.",
                                    "semantic_type": "entity_reference",
                                    "entity_reference": True,
                                    "clarification_hint": "Ask which specific account should receive the draft, or request approval for target selection.",
                                },
                                {
                                    "input_name": "owner_scope",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: optional region, team, owner, or company-wide scope.",
                                    "semantic_type": "scope_reference",
                                    "entity_reference": True,
                                },
                                {
                                    "input_name": "objective",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "first_touch",
                                    "allowed_values": ["first_touch", "follow_up", "revive_stalled"],
                                    "summary": "Reviewed PM/dev input: outreach objective.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "channel",
                                    "input_type": "string",
                                    "required": False,
                                    "default_value": "email",
                                    "allowed_values": ["email", "linkedin", "call_follow_up"],
                                    "summary": "Reviewed PM/dev input: requested outreach channel.",
                                    "semantic_type": "business_category",
                                },
                                {
                                    "input_name": "persona",
                                    "input_type": "string",
                                    "required": False,
                                    "summary": "Reviewed PM/dev input: target persona or audience.",
                                    "semantic_type": "audience_reference",
                                    "entity_reference": True,
                                },
                            ],
                            "clarification_required_when": [
                                "quarter or selected account is missing",
                            ],
                            "denied_when": [
                                "the request asks to send outreach or execute downstream mutations",
                            ],
                            "approval_required_when": [
                                "the service must choose a target account before drafting outreach",
                            ],
                            "bounded_evidence": [
                                "selected account",
                                "bottleneck or risk context",
                                "draft outreach content",
                            ],
                            "implementation_notes": [
                                "return approval_required when no explicit selected account exists",
                            ],
                        },
                    ],
                    "metadata_contract": {
                        "manifest_required": True,
                        "discovery_required": True,
                        "signature_required": True,
                        "jwks_uri_required": True,
                        "purpose_bound_tokens_required": True,
                        "audit_evidence_required": True,
                        "conformance_checks": [
                            "service identities match the intended four-service GTM estate",
                            "all bounded pipeline, enrichment, prioritization, and outreach capabilities are declared",
                            "approval-gated write posture is visible for gtm.prepare_followup_tasks",
                            "approval-gated write posture is visible for gtm.prepare_reassignment_plan",
                            "approval-gated routing posture is visible for gtm.route_leads",
                            "cross-service handoff lineage is represented explicitly",
                            "manifest and discovery expose enough metadata for Studio validation",
                        ],
                    },
                    "implementation_trace": {
                        "business_source_artifact_id": "req-gtm-revenue-operations-business-spec",
                        "requirements_artifact_id": "req-gtm-pipeline-q2-review",
                        "scenario_artifact_id": "scn-gtm-pipeline-q2-review",
                        "proposal_artifact_id": "prop-gtm-pipeline-q2-review",
                        "shape_artifact_id": "shape-gtm-pipeline-q2-review",
                        "generated_code_used_for_showcase": True,
                        "running_service_id": "anip-gtm-revenue-operations-showcase",
                        "validation_method": [
                            "Studio compares intended service estate design against observed manifest and discovery metadata",
                            "Studio uses saved runtime evidence to confirm the hero paths stay within the developer contract",
                        ],
                    },
                    "services": [
                        {
                            "id": "gtm-pipeline-service",
                            "name": "GTM Pipeline Service",
                            "role": "answers bounded pipeline review questions and prepares follow-up and reassignment previews",
                            "responsibilities": [
                                "Summarize pipeline health for a given quarter and optional region scope.",
                                "Summarize bounded pipeline forecast for a given quarter and optional region scope.",
                                "Summarize bounded stage bottlenecks for a given quarter and allowed slice.",
                                "Summarize bounded sales team performance for a given quarter and allowed slice.",
                                "Summarize bounded product pipeline performance for a given quarter and allowed scope.",
                                "Identify stalled open opportunities and rank risky accounts with explicit evidence.",
                                "Prepare reassignment previews but stop safely before downstream assignment mutation when approval is missing.",
                                "Prepare follow-up tasks but stop safely before downstream mutation when approval is missing.",
                            ],
                            "capabilities": [
                                "gtm.pipeline_summary",
                                "gtm.pipeline_forecast_summary",
                                "gtm.stage_bottleneck_summary",
                                "gtm.sales_team_performance_summary",
                                "gtm.product_pipeline_summary",
                                "gtm.prepare_reassignment_plan",
                                "gtm.stalled_opportunity_review",
                                "gtm.account_risk_summary",
                                "gtm.prepare_followup_tasks",
                                "gtm.at_risk_followup_preparation",
                                "gtm.at_risk_reassignment_preparation",
                            ],
                            "owns_concepts": ["pipeline-review", "account-risk", "followup-plan", "reassignment-plan"],
                        },
                        {
                            "id": "gtm-enrichment-service",
                            "name": "GTM Enrichment Service",
                            "role": "answers bounded account enrichment and lookalike questions over approved account scope",
                            "responsibilities": [
                                "Summarize firmographic and account context for selected accounts.",
                                "Return explainable lookalike accounts without raw enrichment export.",
                                "Preserve account scope and actor identity from upstream pipeline handoffs.",
                            ],
                            "capabilities": [
                                "gtm.account_enrichment_summary",
                                "gtm.lookalike_accounts",
                                "gtm.at_risk_account_enrichment_summary",
                            ],
                            "owns_concepts": ["account-enrichment", "lookalike-account"],
                        },
                        {
                            "id": "gtm-prioritization-service",
                            "name": "GTM Prioritization Service",
                            "role": "scores and prioritizes bounded GTM work with explainable routing recommendations",
                            "responsibilities": [
                                "Score bounded leads or accounts with reason codes.",
                                "Prioritize approved account cohorts for follow-up.",
                                "Prepare routing recommendations but stop before downstream mutation without approval.",
                            ],
                            "capabilities": [
                                "gtm.score_leads",
                                "gtm.prioritize_accounts",
                                "gtm.route_leads",
                                "gtm.prioritized_routing_preparation",
                            ],
                            "owns_concepts": ["lead-score", "account-priority", "routing-plan"],
                        },
                        {
                            "id": "gtm-outreach-service",
                            "name": "GTM Outreach Service",
                            "role": "provides bounded draft-only outreach support through an MCP-fronted backend",
                            "responsibilities": [
                                "Draft outreach messages using approved context only.",
                                "Suggest follow-up content without sending messages.",
                                "Generate objection-response variants that stay within approved claims.",
                            ],
                            "capabilities": [
                                "gtm.draft_outreach_message",
                                "gtm.suggest_followup_content",
                                "gtm.objection_response_variants",
                                "gtm.prioritized_outreach_draft",
                                "gtm.bottleneck_account_outreach_draft",
                            ],
                            "owns_concepts": ["outreach-draft", "followup-content", "objection-response"],
                        },
                    ],
                    "domain_concepts": [
                        {
                            "id": "pipeline-review",
                            "name": "Pipeline Review",
                            "meaning": "A bounded summary of pipeline health for a quarter and scope.",
                            "owner": "gtm-pipeline-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "account-risk",
                            "name": "Account Risk",
                            "meaning": "An explainable ranking of open accounts that need attention.",
                            "owner": "gtm-pipeline-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "followup-plan",
                            "name": "Follow-up Plan",
                            "meaning": "A prepared set of recommended tasks that still requires approval before downstream execution.",
                            "owner": "gtm-pipeline-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "reassignment-plan",
                            "name": "Reassignment Plan",
                            "meaning": "A prepared set of reassignment recommendations that still requires approval before downstream execution.",
                            "owner": "gtm-pipeline-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "account-enrichment",
                            "name": "Account Enrichment",
                            "meaning": "Bounded firmographic and account context for approved accounts.",
                            "owner": "gtm-enrichment-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "lookalike-account",
                            "name": "Lookalike Account",
                            "meaning": "An account similar to an approved reference account with explainable similarity signals.",
                            "owner": "gtm-enrichment-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "lead-score",
                            "name": "Lead Score",
                            "meaning": "A bounded score band and reason-code summary for a lead or account.",
                            "owner": "gtm-prioritization-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "account-priority",
                            "name": "Account Priority",
                            "meaning": "An explainable ordering of accounts for GTM action.",
                            "owner": "gtm-prioritization-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "routing-plan",
                            "name": "Routing Plan",
                            "meaning": "A prepared routing recommendation that requires approval before mutation.",
                            "owner": "gtm-prioritization-service",
                            "sensitivity": "high",
                        },
                        {
                            "id": "outreach-draft",
                            "name": "Outreach Draft",
                            "meaning": "Draft-only outreach content generated from approved context.",
                            "owner": "gtm-outreach-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "followup-content",
                            "name": "Follow-up Content",
                            "meaning": "Suggested follow-up messaging content that remains review-only.",
                            "owner": "gtm-outreach-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "objection-response",
                            "name": "Objection Response",
                            "meaning": "Bounded response variants using approved claims and account context.",
                            "owner": "gtm-outreach-service",
                            "sensitivity": "medium",
                        },
                    ],
                    "coordination": [
                        {
                            "from": "gtm-pipeline-service",
                            "to": "gtm-enrichment-service",
                            "relationship": "account_scope_handoff",
                            "description": "Pipeline risk outputs may pass bounded account identifiers into enrichment while preserving actor and task lineage.",
                        },
                        {
                            "from": "gtm-enrichment-service",
                            "to": "gtm-prioritization-service",
                            "relationship": "enriched_context_handoff",
                            "description": "Approved enrichment summaries may inform prioritization without exposing raw enrichment features.",
                        },
                        {
                            "from": "gtm-prioritization-service",
                            "to": "gtm-outreach-service",
                            "relationship": "prioritized_outreach_context_handoff",
                            "description": "Approved prioritized accounts may inform draft-only outreach generation without sending messages.",
                        },
                    ],
                }
            },
        },
        "evaluation": {
            "id": "eval-gtm-pipeline-q2-review",
            "source": "imported",
            "data": {
                "evaluation": {
                    "scenario_name": "at_risk_q2_deals_followup_preparation",
                    "result": "HANDLED",
                    "handled_by_anip": [
                        "bounded capability selection",
                        "clarification_required for missing quarter or ranking basis",
                        "denied for raw row-level export attempts",
                        "approval_required stop before downstream follow-up execution",
                        "explicit multi-service boundaries for enrichment, prioritization, and outreach",
                        "service metadata-backed validation inside Studio",
                    ],
                    "glue_you_will_still_write": [
                        "the final operator workflow for executing approved operational actions still remains outside draft/preparation capabilities",
                    ],
                    "glue_category": ["service_metadata"],
                    "why": [
                        "The service estate exposes bounded contracts instead of raw SQL, enrichment, scoring, or outreach backends.",
                        "Studio can compare intended GTM service boundaries against observed service metadata and runtime evidence.",
                    ],
                    "what_would_improve": [
                        "Generate all four service bundles from the registry-backed service definition.",
                        "Capture signed manifest and JWKS metadata in the live showcase runtime so the developer contract validates without caveats.",
                    ],
                    "conformance_status": "partial",
                    "confidence": "high",
                }
            },
        },
        "service_metadata": [
            {
                "id": "service-metadata-anip-gtm-pipeline-showcase",
                "title": "Observed Service Metadata: anip-gtm-pipeline-showcase",
                "data": {
                    "source": "showcase_seed",
                    "observed_at": "2026-04-12T12:00:00Z",
                    "service_id": "anip-gtm-pipeline-showcase",
                    "protocol": "anip/0.24",
                    "manifest_signature_present": False,
                    "jwks_uri_present": False,
                    "capabilities": [
                        {
                            "id": "gtm.pipeline_summary",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.pipeline_forecast_summary",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.stage_bottleneck_summary",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.sales_team_performance_summary",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.product_pipeline_summary",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.prepare_reassignment_plan",
                            "side_effect_type": "write",
                            "minimum_scope": ["gtm.pipeline.reassign"],
                        },
                        {
                            "id": "gtm.stalled_opportunity_review",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.account_risk_summary",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.pipeline.read"],
                        },
                        {
                            "id": "gtm.prepare_followup_tasks",
                            "side_effect_type": "write",
                            "minimum_scope": ["gtm.pipeline.followup"],
                        },
                        {
                            "id": "gtm.at_risk_followup_preparation",
                            "side_effect_type": "write",
                            "minimum_scope": ["gtm.pipeline.read", "gtm.pipeline.followup"],
                        },
                        {
                            "id": "gtm.at_risk_reassignment_preparation",
                            "side_effect_type": "write",
                            "minimum_scope": ["gtm.pipeline.read", "gtm.pipeline.reassign"],
                        },
                    ],
                },
            },
            {
                "id": "service-metadata-anip-gtm-enrichment-showcase",
                "title": "Observed Service Metadata: anip-gtm-enrichment-showcase",
                "data": {
                    "source": "showcase_seed",
                    "observed_at": "2026-04-12T12:00:00Z",
                    "service_id": "anip-gtm-enrichment-showcase",
                    "protocol": "anip/0.24",
                    "manifest_signature_present": False,
                    "jwks_uri_present": False,
                    "capabilities": [
                        {"id": "gtm.account_enrichment_summary", "side_effect_type": "read", "minimum_scope": ["gtm.enrichment.read"]},
                        {"id": "gtm.lookalike_accounts", "side_effect_type": "read", "minimum_scope": ["gtm.enrichment.read"]},
                        {"id": "gtm.at_risk_account_enrichment_summary", "side_effect_type": "read", "minimum_scope": ["gtm.pipeline.read", "gtm.enrichment.read"]},
                    ],
                },
            },
            {
                "id": "service-metadata-anip-gtm-prioritization-showcase",
                "title": "Observed Service Metadata: anip-gtm-prioritization-showcase",
                "data": {
                    "source": "showcase_seed",
                    "observed_at": "2026-04-12T12:00:00Z",
                    "service_id": "anip-gtm-prioritization-showcase",
                    "protocol": "anip/0.24",
                    "manifest_signature_present": False,
                    "jwks_uri_present": False,
                    "capabilities": [
                        {"id": "gtm.score_leads", "side_effect_type": "read", "minimum_scope": ["gtm.prioritization.read"]},
                        {"id": "gtm.prioritize_accounts", "side_effect_type": "read", "minimum_scope": ["gtm.prioritization.read"]},
                        {"id": "gtm.route_leads", "side_effect_type": "write", "minimum_scope": ["gtm.prioritization.route"]},
                        {
                            "id": "gtm.prioritized_routing_preparation",
                            "side_effect_type": "write",
                            "minimum_scope": ["gtm.prioritization.read", "gtm.prioritization.route"],
                        },
                    ],
                },
            },
            {
                "id": "service-metadata-anip-gtm-outreach-showcase",
                "title": "Observed Service Metadata: anip-gtm-outreach-showcase",
                "data": {
                    "source": "showcase_seed",
                    "observed_at": "2026-04-12T12:00:00Z",
                    "service_id": "anip-gtm-outreach-showcase",
                    "protocol": "anip/0.24",
                    "manifest_signature_present": False,
                    "jwks_uri_present": False,
                    "capabilities": [
                        {"id": "gtm.draft_outreach_message", "side_effect_type": "read", "minimum_scope": ["gtm.outreach.draft"]},
                        {"id": "gtm.suggest_followup_content", "side_effect_type": "read", "minimum_scope": ["gtm.outreach.draft"]},
                        {"id": "gtm.objection_response_variants", "side_effect_type": "read", "minimum_scope": ["gtm.outreach.draft"]},
                        {"id": "gtm.prioritized_outreach_draft", "side_effect_type": "read", "minimum_scope": ["gtm.prioritization.read", "gtm.outreach.read"]},
                        {"id": "gtm.bottleneck_account_outreach_draft", "side_effect_type": "read", "minimum_scope": ["gtm.pipeline.read", "gtm.outreach.read"]},
                    ],
                },
            },
        ],
    },
    {
        "project": {
            "id": "gtm-account-enrichment",
            "name": "GTM Account Enrichment",
            "domain": "revenue_operations",
            "summary": (
                "PM brief: Revenue operations needs a bounded enrichment service that can add firmographic context "
                "to selected accounts and return explainable lookalike accounts, without exposing unconstrained raw "
                "enrichment data or mixing in scoring and outreach behavior."
            ),
        },
        "requirements": {
            "id": "req-gtm-account-enrichment",
            "title": "GTM account enrichment requirements",
            "data": {
                "system": {
                    "name": "gtm-account-enrichment",
                    "domain": "revenue_operations",
                    "deployment_intent": "production_single_service",
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
                    "cross_service_reconstruction_required": False,
                },
                "lineage": {
                    "invocation_id": True,
                    "client_reference_id": True,
                    "task_id": True,
                    "parent_invocation_id": True,
                    "cross_service_continuity_required": True,
                },
                "business_constraints": {
                    "pm_defines_behavior_families_not_every_utterance": True,
                    "service_must_remain_read_only": True,
                    "raw_enrichment_exports_are_out_of_scope": True,
                    "clarification_required_for_missing_account_scope": True,
                    "clarification_required_for_missing_reference_account": True,
                    "phase_2_service_must_stay_bounded": True,
                    "blocked_failure_posture": "clean_denial_or_clarification_before_human_review",
                },
                "services": [
                    {
                        "name": "GTM Enrichment Service",
                        "role": "bounded account enrichment and lookalike analysis",
                    },
                ],
                "risk_profile": {
                    "gtm.account_enrichment_summary": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                    "gtm.lookalike_accounts": {
                        "side_effect": "none",
                        "high_risk": False,
                        "cost_visibility_required": False,
                        "recovery_guidance_required": False,
                    },
                },
                "behavior_translation": {
                    "source_artifact_id": "req-gtm-enrichment-business-spec",
                    "goal_translation": [
                        "bounded_account_enrichment_summary",
                        "explainable_lookalike_analysis",
                    ],
                    "behavior_families": [
                        {
                            "class": "clear_in_scope_bounded_enrichment_read",
                            "studio_expectation": "available_with_bounded_evidence",
                        },
                        {
                            "class": "ambiguity_requiring_clarification",
                            "studio_expectation": "clarification_required_without_guessing",
                        },
                        {
                            "class": "broad_or_unsafe_data_request",
                            "studio_expectation": "denied_for_raw_enrichment_export",
                        },
                        {
                            "class": "bounded_similarity_analysis",
                            "studio_expectation": "available_with_explainable_similarity",
                        },
                        {
                            "class": "out_of_scope_request",
                            "studio_expectation": "denied_without_improvisation",
                        },
                    ],
                    "representative_requests": [
                        "Summarize firmographic context for Acme Corporation and Codehow.",
                        "Show enrichment context for the top 5 at-risk accounts from the current pipeline review.",
                        "Find lookalike accounts similar to Acme Corporation.",
                        "Export the full raw enrichment dataset for every account.",
                    ],
                },
                "source_documents": [
                    {
                        "artifact_id": "req-gtm-enrichment-business-spec",
                        "title": "Canonical GTM enrichment business spec",
                        "kind": "business_spec",
                        "path": "docs/examples/gtm-showcase/enrichment-business-spec.md",
                    },
                ],
                "derivation": {
                    "derived_from_business_spec": True,
                    "translation_goal": (
                        "Convert the PM-readable enrichment business spec into bounded capability requirements "
                        "and validation expectations for the Phase 2 GTM enrichment service."
                    ),
                },
                "scale": {
                    "shape_preference": "production_single_service",
                    "high_availability": False,
                },
            },
        },
        "additional_requirements": [
            {
                "id": "req-gtm-enrichment-business-spec",
                "title": "Canonical GTM enrichment business spec",
                "data": {
                    "system": {
                        "name": "gtm-enrichment-business-spec",
                        "domain": "revenue_operations",
                        "deployment_intent": "business_source_document",
                    },
                    "transports": {"http": False, "stdio": False, "grpc": False},
                    "trust": {"mode": "not_applicable", "checkpoints": False},
                    "auth": {},
                    "permissions": {},
                    "audit": {},
                    "lineage": {},
                    "source_document": {
                        "kind": "business_spec",
                        "format": "markdown",
                        "path": "docs/examples/gtm-showcase/enrichment-business-spec.md",
                    },
                    "business_spec": {
                        "title": "GTM Enrichment Service Business Spec",
                        "summary": (
                            "Canonical PM-readable source document for the Phase 2 GTM enrichment service."
                        ),
                        "business_goal": [
                            "summarize bounded firmographic context for selected accounts",
                            "explain fit and intent context",
                            "return bounded lookalike accounts",
                        ],
                        "behavior_classes": [
                            "clear_in_scope_enrichment_read",
                            "clarification_required_for_missing_account_scope",
                            "deny_raw_enrichment_exports",
                            "bounded_lookalike_analysis",
                            "deny_out_of_scope_requests",
                        ],
                        "non_goals": [
                            "no scoring in this service",
                            "no outreach drafting in this service",
                            "no downstream mutation",
                            "no unconstrained raw enrichment export",
                        ],
                    },
                    "scale": {
                        "shape_preference": "production_single_service",
                        "high_availability": False,
                    },
                },
            },
        ],
        "scenario": {
            "id": "scn-gtm-account-enrichment",
            "title": "Hero path: enrich selected accounts after pipeline review",
            "data": {
                "scenario": {
                    "name": "bounded_account_enrichment_after_pipeline_review",
                    "category": "orchestration",
                    "narrative": (
                        "A GTM user has already identified a small set of risky accounts from the pipeline service and "
                        "now asks for bounded firmographic context plus explainable lookalike accounts."
                    ),
                    "context": {
                        "source_service": "gtm-pipeline-service",
                        "account_scope": ["Acme Corporation", "Codehow"],
                        "hero_flow": True,
                    },
                    "derived_from": {
                        "artifact_id": "req-gtm-enrichment-business-spec",
                        "path": "docs/examples/gtm-showcase/enrichment-business-spec.md",
                    },
                    "expected_behavior": [
                        "account_scope_is_not_guessed_when_missing",
                        "enrichment_evidence_is_bounded_and_explainable",
                        "lookalikes_use_bounded_similarity_logic",
                        "raw_enrichment_exports_are_denied",
                    ],
                    "expected_anip_support": [
                        "signed_manifest_and_discovery",
                        "purpose_bound_tokens",
                        "bounded_capability_contracts",
                        "service_metadata_validation",
                    ],
                }
            },
        },
        "proposal": {
            "id": "prop-gtm-account-enrichment",
            "title": "GTM enrichment single-service proposal",
            "data": {
                "proposal": {
                    "recommended_shape": "production_single_service",
                    "rationale": [
                        "enrichment should remain a separate bounded service instead of broadening the pipeline service",
                        "the first phase 2 proof should stay on non-mutating enrichment and similarity analysis",
                        "the service should work over modeled account-enrichment views rather than raw vendor export access",
                    ],
                    "required_components": [
                        "postgres_modeled_enrichment_views",
                        "signed_manifest",
                        "permission_discovery",
                        "searchable_audit",
                    ],
                    "declared_surfaces": {
                        "binding_requirements": True,
                        "authority_posture": True,
                        "followup_via": False,
                        "cross_service_handoff": True,
                    },
                    "cross_service_contract": {
                        "handoff": [
                            {
                                "target": {
                                    "service": "gtm-enrichment-service",
                                    "capability": "gtm.account_enrichment_summary",
                                },
                                "required_for_task_completion": False,
                                "continuity": "same_task",
                                "completion_mode": "downstream_acceptance",
                                "carry_fields": ["account_name"],
                                "rationale": "A bounded pipeline risk result may hand off selected account identifiers into enrichment when the user explicitly asks for enrichment context.",
                            }
                        ],
                        "followup": [],
                        "verification": [],
                    },
                    "derived_from": {
                        "artifact_id": "req-gtm-enrichment-business-spec",
                        "path": "docs/examples/gtm-showcase/enrichment-business-spec.md",
                    },
                    "developer_translation": {
                        "source_artifact_id": "req-gtm-account-enrichment",
                        "translation_goal": (
                            "Turn the PM-owned enrichment behavior specification into one bounded ANIP service contract "
                            "with explicit clarification, denial, metadata, and implementation expectations."
                        ),
                        "translation_principles": [
                            "keep the service read-only in this phase",
                            "encode account-scope clarification and export denial in the service contract instead of agent glue",
                            "use Postgres plus dbt modeled enrichment views as implementation internals, not the external capability surface",
                        ],
                        "service_contract_decisions": [
                            "one GTM Enrichment Service owns phase 2 enrichment and lookalike capabilities",
                            "all capabilities return bounded evidence instead of raw enrichment export",
                            "manifest, discovery, and runtime evidence must be sufficient for Studio conformance validation",
                        ],
                        "service_behavior_coverage": [
                            "missing account scope yields clarification_required in gtm.account_enrichment_summary",
                            "missing reference account yields clarification_required in gtm.lookalike_accounts",
                            "raw unconstrained enrichment export is denied by the bounded enrichment service contract",
                            "lookalike analysis returns explainable bounded similarity output instead of a raw model dump",
                        ],
                        "orchestration_contract_coverage": [
                            "the runtime may resolve top at-risk accounts from the pipeline service before calling the enrichment service",
                            "only bounded account identifiers may cross the pipeline-to-enrichment handoff",
                            "cross-service flow must record prior service calls so Studio can review the handoff path",
                        ],
                        "runtime_glue_inventory": [
                            "mechanical account-name normalization still happens in the runtime before enrichment invocation",
                            "generic phrases like 'our best customer' still normalize to clarification triggers before service invocation",
                            "lead-scoring and outreach prompts still deny at runtime because those services are not live yet",
                        ],
                        "actor_policy_model": {
                            "identity_source": "delegation.root_principal claims carried through ANIP token issuance",
                            "policy_axes": [
                                "actor role",
                                "enrichment visibility level",
                                "lookalike-analysis authority",
                            ],
                            "visibility_rules": [
                                {
                                    "when": "an actor has bounded enrichment visibility",
                                    "outcome": "success with bounded enrichment fields only",
                                    "rationale": "The service should redact sensitive enrichment fields without inventing a separate workflow.",
                                },
                                {
                                    "when": "an actor lacks lookalike-analysis authority",
                                    "outcome": "denied",
                                    "rationale": "Similarity analysis remains a governed capability, not a fallback side effect of enrichment summary.",
                                },
                            ],
                            "approval_rules": [],
                            "audit_expectations": [
                                "bounded enrichment responses should remain auditable per actor",
                                "lookalike denial and success paths should remain distinguishable in audit review",
                                "cross-service handoff into enrichment should preserve actor and task continuity",
                            ],
                        },
                    },
                }
            },
        },
        "shape": {
            "id": "shape-gtm-account-enrichment",
            "title": "GTM enrichment service design",
            "data": {
                "shape": {
                    "id": "gtm-enrichment-service-shape",
                    "name": "GTM Enrichment Service",
                    "type": "production_single_service",
                    "notes": [
                        "Keep the service centered on bounded firmographic context and similarity analysis.",
                        "Do not let enrichment become a raw vendor-export or scoring surface.",
                    ],
                    "derived_from": {
                        "artifact_id": "req-gtm-enrichment-business-spec",
                        "path": "docs/examples/gtm-showcase/enrichment-business-spec.md",
                    },
                    "implementation_contract": {
                        "implementation_language": "python",
                        "runtime_profile": "fastapi_anip_service",
                        "transport_profile": "http_rest_anip",
                        "semantic_backends": [
                            "postgres_modeled_enrichment_views",
                            "curated_sql_account_enrichment_views",
                        ],
                    },
                    "capability_contracts": [
                        {
                            "id": "gtm.account_enrichment_summary",
                            "purpose": "Return bounded firmographic context and fit signals for selected accounts.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.enrichment.read"],
                            "clarification_required_when": [
                                "account scope is missing",
                            ],
                            "denied_when": [
                                "the request asks for raw unconstrained enrichment export",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "sector",
                                "region",
                                "revenue band",
                                "employee band",
                                "fit signal",
                                "intent signal",
                            ],
                            "implementation_notes": [
                                "return only bounded fields from the modeled enrichment view",
                            ],
                        },
                        {
                            "id": "gtm.lookalike_accounts",
                            "purpose": "Return bounded lookalike accounts using explainable similarity logic.",
                            "side_effect_type": "read",
                            "minimum_scope": ["gtm.enrichment.read"],
                            "clarification_required_when": [
                                "reference account is missing",
                            ],
                            "denied_when": [
                                "the request asks for unconstrained similarity export or scoring workflow",
                            ],
                            "approval_required_when": [],
                            "bounded_evidence": [
                                "reference profile",
                                "shared segment signals",
                                "bounded lookalike list",
                            ],
                            "implementation_notes": [
                                "similarity must remain explainable from modeled account attributes",
                            ],
                        },
                    ],
                    "metadata_contract": {
                        "manifest_required": True,
                        "discovery_required": True,
                        "signature_required": True,
                        "jwks_uri_required": True,
                        "purpose_bound_tokens_required": True,
                        "audit_evidence_required": True,
                        "conformance_checks": [
                            "service identity matches the intended GTM enrichment service",
                            "both bounded enrichment capabilities are declared",
                            "the service remains read-only",
                            "manifest and discovery expose enough metadata for Studio validation",
                        ],
                    },
                    "implementation_trace": {
                        "business_source_artifact_id": "req-gtm-enrichment-business-spec",
                        "requirements_artifact_id": "req-gtm-account-enrichment",
                        "scenario_artifact_id": "scn-gtm-account-enrichment",
                        "proposal_artifact_id": "prop-gtm-account-enrichment",
                        "shape_artifact_id": "shape-gtm-account-enrichment",
                        "generated_code_used_for_showcase": True,
                        "running_service_id": "anip-gtm-enrichment-showcase",
                    },
                    "services": [
                        {
                            "id": "gtm-enrichment-service",
                            "name": "GTM Enrichment Service",
                            "role": "adds bounded firmographic context and lookalike analysis for selected accounts",
                            "responsibilities": [
                                "Return bounded enrichment summaries for selected accounts.",
                                "Return explainable lookalike accounts using modeled profile similarity.",
                            ],
                            "capabilities": [
                                "gtm.account_enrichment_summary",
                                "gtm.lookalike_accounts",
                            ],
                            "owns_concepts": ["account-enrichment", "lookalike-analysis"],
                        },
                    ],
                    "domain_concepts": [
                        {
                            "id": "account-enrichment",
                            "name": "Account Enrichment",
                            "meaning": "Bounded firmographic context and fit signals for selected GTM accounts.",
                            "owner": "gtm-enrichment-service",
                            "sensitivity": "medium",
                        },
                        {
                            "id": "lookalike-analysis",
                            "name": "Lookalike Analysis",
                            "meaning": "A bounded similarity view over modeled account attributes.",
                            "owner": "gtm-enrichment-service",
                            "sensitivity": "medium",
                        },
                    ],
                }
            },
        },
        "evaluation": {
            "id": "eval-gtm-account-enrichment",
            "source": "imported",
            "data": {
                "evaluation": {
                    "scenario_name": "bounded_account_enrichment_after_pipeline_review",
                    "result": "HANDLED",
                    "handled_by_anip": [
                        "bounded capability selection",
                        "clarification_required for missing account scope",
                        "denied for raw enrichment export attempts",
                        "service metadata-backed validation inside Studio",
                    ],
                    "glue_you_will_still_write": [
                        "the cross-service orchestration from risk review into enrichment selection still belongs to the agent/runtime layer",
                    ],
                    "glue_category": ["service_metadata", "cross_service_handoff"],
                    "why": [
                        "The enrichment service exposes bounded capabilities instead of a raw enrichment dataset endpoint.",
                        "Studio can compare the intended enrichment behavior against observed service metadata and runtime evidence.",
                    ],
                    "what_would_improve": [
                        "Add the real external enrichment dataset after the bounded local enrichment loop is proven end to end.",
                    ],
                    "conformance_status": "partial",
                    "confidence": "medium",
                }
            },
        },
    },
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

SEED_PROJECTS.append(
    {
        "workspace": {
            "id": "ws-issue-tracker-fronting",
            "name": "Issue Tracker Fronting Showcase",
            "summary": "Governed ANIP fronting over the same issue-tracker behavior through native API and MCP-style backends.",
        },
        "project": {
            "id": "project-issue-tracker-fronting-showcase",
            "workspace_id": "ws-issue-tracker-fronting",
            "name": "Issue Tracker Native and MCP Fronting",
            "domain": "software_delivery",
            "summary": (
                "Show how ANIP fronts an existing issue-tracker integration so agents use curated governed capabilities "
                "instead of raw API or MCP tools. The example uses Jira/Rovo-style source evidence, but the Studio model "
                "stays generic across native APIs, MCP servers, databases, and hybrids."
            ),
            "labels": ["showcase", "integration-fronting", "native-api", "mcp"],
            "project_type": "governed_service_project",
            "integration_profile": {
                "kind": "hybrid",
                "systems": [
                    {
                        "system_id": "issue-tracker-native",
                        "display_name": "Issue Tracker Native API",
                        "backend_kind": "native_api",
                        "auth_mode": "service_delegated",
                        "connection_ref": "conn-issue-tracker-native-api",
                    },
                    {
                        "system_id": "issue-tracker-mcp",
                        "display_name": "Issue Tracker MCP Server",
                        "backend_kind": "mcp",
                        "auth_mode": "user_delegated",
                        "connection_ref": "conn-issue-tracker-mcp",
                    },
                ],
            },
        },
        "seed_profiles": ["local_demo"],
        "workspace_connections": [
            {
                "id": "conn-issue-tracker-native-api",
                "display_name": "Issue Tracker Native API",
                "backend_kind": "native_api",
                "system_kind": "issue_tracker",
                "endpoint_ref": "ISSUE_TRACKER_BASE_URL",
                "auth_mode": "service_delegated",
                "identity_provider_ref": "enterprise-sso",
                "secret_ref": "env:ISSUE_TRACKER_API_TOKEN",
                "allowed_project_refs": ["project-issue-tracker-fronting-showcase"],
                "metadata": {"example_system": "jira", "secret_material": "external"},
            },
            {
                "id": "conn-issue-tracker-mcp",
                "display_name": "Issue Tracker MCP Server",
                "backend_kind": "mcp",
                "system_kind": "issue_tracker",
                "endpoint_ref": "ISSUE_TRACKER_MCP_ENDPOINT",
                "auth_mode": "user_delegated",
                "identity_provider_ref": "enterprise-sso",
                "secret_ref": "",
                "allowed_project_refs": ["project-issue-tracker-fronting-showcase"],
                "metadata": {"example_system": "rovo_mcp", "secret_material": "delegated"},
            },
        ],
        "documents": [
            {
                "id": "issue-tracker-fronting-intent",
                "title": "Governed Issue Tracker Fronting Intent",
                "kind": "business_intent",
                "filename": "issue-tracker-fronting-intent.md",
                "source_path": "seed://issue-tracker/fronting-intent",
                "content": (
                    "# Governed issue-tracker fronting intent\n\n"
                    "Agents should help engineering teams search backlog context, prepare tickets, draft incident comments, "
                    "and request status transitions. They must not receive raw create/update/transition tools directly. "
                    "The ANIP layer must restrict project scope, redact sensitive incident text before outbound calls, "
                    "ask for missing required fields, and require approval for customer-impacting severity or direct workflow transitions."
                ),
            },
            {
                "id": "issue-tracker-native-api-docs",
                "title": "Issue Tracker Native API Evidence",
                "kind": "api_docs",
                "filename": "issue-tracker-native-api.md",
                "source_path": "seed://issue-tracker/native-api",
                "content": (
                    "# Native API evidence\n\n"
                    "The native API exposes search issues, create issue, add comment, and transition issue operations. "
                    "Create issue requires project key, issue type, summary, and description. Transition issue mutates workflow state. "
                    "Search is read-only but can return sensitive issue content, so queries and returned fields need governance."
                ),
            },
            {
                "id": "issue-tracker-mcp-schema",
                "title": "Issue Tracker MCP Surface Evidence",
                "kind": "mcp_schema",
                "filename": "issue-tracker-mcp-schema.md",
                "source_path": "seed://issue-tracker/mcp-schema",
                "content": (
                    "# MCP surface evidence\n\n"
                    "The MCP server exposes tools analogous to search, create issue, comment, and transition. "
                    "Those tools are integration inputs only; the agent-facing surface should be curated ANIP capabilities "
                    "with approval, denial, clarification, redaction, and audit semantics."
                ),
            },
            {
                "id": "issue-tracker-outbound-policy",
                "title": "Outbound Governance Policy",
                "kind": "policy_source",
                "filename": "issue-tracker-outbound-policy.md",
                "source_path": "seed://issue-tracker/outbound-policy",
                "content": (
                    "# Outbound governance policy\n\n"
                    "Do not send credentials, customer secrets, private stack traces, or raw incident logs to external systems. "
                    "Prepare write payloads first, show the outbound payload for approval when severity or customer impact is high, "
                    "and record a durable audit entry for every governed call."
                ),
            },
        ],
        "pm_artifacts": [
            {
                "id": "issue-tracker-fronting-product-summary",
                "title": "Issue Tracker Fronting Product Summary",
                "data": {
                    "artifact_type": "product_summary",
                    "product_purpose": "Provide a governed ANIP layer in front of existing issue-tracker API and MCP integrations.",
                    "business_problem": (
                        "Raw issue-tracker tools give agents broad access to search, create, comment, and transition operations, "
                        "leaving behavior, sensitive outbound data handling, and approval posture hidden in prompts or local skills."
                    ),
                    "business_goals": [
                        "Replace local skill glue with a central governed capability surface.",
                        "Control what agents can send to third-party issue-tracking systems.",
                        "Keep native API and MCP backends interchangeable behind the same ANIP contract.",
                    ],
                    "supported_question_families": [
                        "Search bounded team backlog context",
                        "Prepare story or bug ticket drafts",
                        "Request status transition previews",
                        "Prepare incident follow-up comments",
                    ],
                    "governed_behavior_summary": (
                        "Expose curated prepare/search/request capabilities, not raw backend operations. Clarify missing required fields, "
                        "deny unsupported projects, redact sensitive outbound data, and require approval for high-impact write-adjacent actions."
                    ),
                    "approval_posture_summary": (
                        "Read-only searches can run inside allowed project scope. Ticket creation, comments, and transitions are prepare-only "
                        "or approval-gated unless policy explicitly allows direct execution for the actor."
                    ),
                    "multi_step_composition_rules": [
                        "Search context may feed a prepared ticket draft, but raw issue creation remains behind approval.",
                        "Transition requests must preserve current state, requested state, actor, reason, and approval evidence.",
                    ],
                    "why_now": "MCP adoption is pushing broad raw integration surfaces to local agents without centralized governance.",
                    "success_outcome_summary": (
                        "The same ANIP Service Definition can front native API and MCP bindings while preserving outbound controls and audit."
                    ),
                },
            },
            {
                "id": "issue-tracker-fronting-actor-model",
                "title": "Issue Tracker Fronting Actor Model",
                "data": {
                    "artifact_type": "actor_model",
                    "actors": [
                        {
                            "actor_id": "engineering_operator",
                            "title": "Engineering Operator",
                            "summary": "Uses an AI assistant to prepare issue-tracker work without direct raw tool access.",
                            "visibility_expectations": "Can search bounded backlog context for allowed projects.",
                            "action_expectations": "Can prepare ticket drafts, comments, and transition requests.",
                            "approval_expectations": "Needs approval for high-impact outbound writes or workflow transitions.",
                            "notes": "Default interactive actor for the showcase.",
                        },
                        {
                            "actor_id": "engineering_manager",
                            "title": "Engineering Manager",
                            "summary": "Reviews high-impact prepared issue-tracker actions before they are sent.",
                            "visibility_expectations": "Can inspect prepared payload, redaction state, and policy decision evidence.",
                            "action_expectations": "Can approve or reject prepared outbound actions.",
                            "approval_expectations": "Acts as approval authority for severity/customer-impact thresholds.",
                            "notes": "Represents explicit approval authority rather than prompt-based etiquette.",
                        },
                    ],
                },
            },
            {
                "id": "issue-tracker-fronting-business-areas",
                "title": "Issue Tracker Fronting Business Areas",
                "data": {
                    "artifact_type": "business_areas",
                    "entries": [
                        {
                            "business_area_id": "backlog_search",
                            "label": "Backlog Search",
                            "description": "Bounded issue and project context retrieval.",
                        },
                        {
                            "business_area_id": "ticket_preparation",
                            "label": "Ticket Preparation",
                            "description": "Prepare story or bug ticket payloads without exposing raw create operations.",
                        },
                        {
                            "business_area_id": "workflow_transition",
                            "label": "Workflow Transition",
                            "description": "Request or execute issue status transitions under policy and approval controls.",
                        },
                        {
                            "business_area_id": "incident_followup",
                            "label": "Incident Follow-up",
                            "description": "Prepare issue comments and follow-up updates with outbound data controls.",
                        },
                    ],
                },
            },
            {
                "id": "issue-tracker-fronting-permission-intent",
                "title": "Issue Tracker Fronting Permission Intent",
                "data": {
                    "artifact_type": "permission_intent",
                    "policy_summary": (
                        "Allow scoped read/search. Prepare write-adjacent actions as drafts. Deny unsupported projects. "
                        "Clarify missing required fields. Require approval for high severity, customer impact, or workflow transitions."
                    ),
                    "rules": [
                        {
                            "actor_id": "engineering_operator",
                            "business_area": "backlog_search",
                            "access_posture": "bounded",
                            "governed_outcome_type": "bounded_result",
                            "governed_outcome": "Return scoped issue context with sensitive fields filtered according to policy.",
                            "notes": "Search remains read-only and project-scoped.",
                        },
                        {
                            "actor_id": "engineering_operator",
                            "business_area": "ticket_preparation",
                            "access_posture": "approval_required",
                            "governed_outcome_type": "approval_stop",
                            "governed_outcome": "Prepare a ticket payload and stop for approval when severity or customer impact crosses threshold.",
                            "notes": "Missing project, issue type, summary, or reproduction detail should clarify.",
                        },
                        {
                            "actor_id": "engineering_operator",
                            "business_area": "workflow_transition",
                            "access_posture": "approval_required",
                            "governed_outcome_type": "approval_stop",
                            "governed_outcome": "Request a transition preview and stop before mutating workflow state.",
                            "notes": "Direct transition to Done is not available to the agent surface.",
                        },
                        {
                            "actor_id": "engineering_manager",
                            "business_area": "incident_followup",
                            "access_posture": "bounded",
                            "governed_outcome_type": "direct_result",
                            "governed_outcome": "Approve or reject prepared incident comments after reviewing outbound payload controls.",
                            "notes": "Approval evidence must be auditable.",
                        },
                    ],
                },
            },
            {
                "id": "issue-tracker-fronting-search-mapping",
                "title": "Search Team Backlog",
                "data": {
                    "artifact_type": "integration_fronting_capability_mapping",
                    "id": "issue-tracker-fronting-search-mapping",
                    "capability_id": "issue_tracker.search_team_backlog",
                    "title": "Search Team Backlog",
                    "intent": "Search bounded issue-tracker backlog context without exposing raw search tools directly.",
                    "service_id": "issue-tracker-governance-service",
                    "service_name": "Issue Tracker Governance Service",
                    "backend_kind": "hybrid",
                    "connection_ref": "conn-issue-tracker-native-api",
                    "raw_operation_refs": ["issue_rest.search_issues"],
                    "backend_bindings": [
                        {
                            "backend_kind": "native_api",
                            "connection_ref": "conn-issue-tracker-native-api",
                            "raw_operation_refs": ["issue_rest.search_issues"],
                        },
                        {
                            "backend_kind": "mcp",
                            "connection_ref": "conn-issue-tracker-mcp",
                            "raw_operation_refs": ["issue_mcp.search_issues"],
                        },
                    ],
                    "execution_posture": "read_only",
                    "side_effect_level": "read",
                    "subject_kind": "issue",
                    "context_type": "team_backlog_context",
                    "output_intent": "bounded_issue_context",
                    "required_inputs": ["project_key", "query"],
                    "optional_inputs": ["fields", "limit"],
                    "backend_input_mode": "implicit",
                    "derived_required_backend_inputs": ["jql", "query"],
                    "derived_optional_backend_inputs": ["fields", "limit", "maxResults"],
                    "explicit_required_backend_inputs": [],
                    "explicit_optional_backend_inputs": [],
                    "approval_rule_refs": [],
                    "denial_rule_refs": ["deny.unsupported_project"],
                    "clarification_rule_refs": ["clarify.missing_project_or_query"],
                    "audit_required": True,
                    "outbound_controls": ["project_scope", "field_filtering"],
                },
            },
            {
                "id": "issue-tracker-fronting-ticket-mapping",
                "title": "Prepare Ticket",
                "data": {
                    "artifact_type": "integration_fronting_capability_mapping",
                    "id": "issue-tracker-fronting-ticket-mapping",
                    "capability_id": "issue_tracker.prepare_ticket",
                    "title": "Prepare Ticket",
                    "intent": "Prepare a governed issue ticket payload from a defect, story, or incident summary.",
                    "service_id": "issue-tracker-governance-service",
                    "service_name": "Issue Tracker Governance Service",
                    "backend_kind": "hybrid",
                    "connection_ref": "conn-issue-tracker-native-api",
                    "raw_operation_refs": ["issue_rest.create_issue"],
                    "backend_bindings": [
                        {
                            "backend_kind": "native_api",
                            "connection_ref": "conn-issue-tracker-native-api",
                            "raw_operation_refs": ["issue_rest.create_issue"],
                        },
                        {
                            "backend_kind": "mcp",
                            "connection_ref": "conn-issue-tracker-mcp",
                            "raw_operation_refs": ["issue_mcp.create_issue"],
                        },
                    ],
                    "execution_posture": "prepare_only",
                    "side_effect_level": "write_adjacent",
                    "subject_kind": "issue",
                    "context_type": "defect_story_or_incident_summary",
                    "output_intent": "approval_ready_ticket_draft",
                    "required_inputs": ["project_key", "issue_type", "summary", "description"],
                    "optional_inputs": ["severity", "customer_impact", "labels", "assignee"],
                    "backend_input_mode": "implicit",
                    "derived_required_backend_inputs": ["description", "issuetype", "issue_type", "project", "project_key", "summary"],
                    "derived_optional_backend_inputs": ["assignee", "customer_impact", "labels", "severity"],
                    "explicit_required_backend_inputs": [],
                    "explicit_optional_backend_inputs": [],
                    "approval_rule_refs": ["approval.high_severity_or_customer_impact"],
                    "denial_rule_refs": ["deny.unsupported_project"],
                    "clarification_rule_refs": ["clarify.missing_required_ticket_fields"],
                    "audit_required": True,
                    "outbound_controls": ["sensitive_data_redaction", "payload_preview"],
                },
            },
            {
                "id": "issue-tracker-fronting-transition-mapping",
                "title": "Request Status Transition",
                "data": {
                    "artifact_type": "integration_fronting_capability_mapping",
                    "id": "issue-tracker-fronting-transition-mapping",
                    "capability_id": "issue_tracker.request_status_transition",
                    "title": "Request Status Transition",
                    "intent": "Prepare and approve issue status transitions without exposing raw workflow mutation tools.",
                    "service_id": "issue-tracker-governance-service",
                    "service_name": "Issue Tracker Governance Service",
                    "backend_kind": "hybrid",
                    "connection_ref": "conn-issue-tracker-native-api",
                    "raw_operation_refs": ["issue_rest.transition_issue"],
                    "backend_bindings": [
                        {
                            "backend_kind": "native_api",
                            "connection_ref": "conn-issue-tracker-native-api",
                            "raw_operation_refs": ["issue_rest.transition_issue"],
                        },
                        {
                            "backend_kind": "mcp",
                            "connection_ref": "conn-issue-tracker-mcp",
                            "raw_operation_refs": ["issue_mcp.transition_issue"],
                        },
                    ],
                    "execution_posture": "approval_gated",
                    "side_effect_level": "write",
                    "subject_kind": "issue",
                    "context_type": "workflow_transition_request",
                    "output_intent": "approval_required_transition_preview",
                    "required_inputs": ["issue_key", "target_status", "reason"],
                    "optional_inputs": ["current_status", "approval_ref"],
                    "backend_input_mode": "implicit",
                    "derived_required_backend_inputs": ["issue_key", "target_status", "transition_id"],
                    "derived_optional_backend_inputs": ["approval_ref", "comment", "current_status"],
                    "explicit_required_backend_inputs": [],
                    "explicit_optional_backend_inputs": [],
                    "approval_rule_refs": ["approval.workflow_transition"],
                    "denial_rule_refs": ["deny.direct_done_transition"],
                    "clarification_rule_refs": ["clarify.missing_transition_reason"],
                    "audit_required": True,
                    "outbound_controls": ["workflow_state_check", "approval_evidence"],
                },
            },
            {
                "id": "issue-tracker-fronting-comment-mapping",
                "title": "Add Incident Comment",
                "data": {
                    "artifact_type": "integration_fronting_capability_mapping",
                    "id": "issue-tracker-fronting-comment-mapping",
                    "capability_id": "issue_tracker.add_incident_comment",
                    "title": "Add Incident Comment",
                    "intent": "Prepare or add governed incident follow-up comments with outbound content controls.",
                    "service_id": "issue-tracker-governance-service",
                    "service_name": "Issue Tracker Governance Service",
                    "backend_kind": "hybrid",
                    "connection_ref": "conn-issue-tracker-native-api",
                    "raw_operation_refs": ["issue_rest.add_comment"],
                    "backend_bindings": [
                        {
                            "backend_kind": "native_api",
                            "connection_ref": "conn-issue-tracker-native-api",
                            "raw_operation_refs": ["issue_rest.add_comment"],
                        },
                        {
                            "backend_kind": "mcp",
                            "connection_ref": "conn-issue-tracker-mcp",
                            "raw_operation_refs": ["issue_mcp.add_comment"],
                        },
                    ],
                    "execution_posture": "approval_gated",
                    "side_effect_level": "write",
                    "subject_kind": "issue",
                    "context_type": "incident_followup_comment",
                    "output_intent": "sanitized_comment_receipt",
                    "required_inputs": ["issue_key", "comment_body"],
                    "optional_inputs": ["incident_id", "approval_ref"],
                    "backend_input_mode": "implicit",
                    "derived_required_backend_inputs": ["body", "comment_body", "issue_key"],
                    "derived_optional_backend_inputs": ["approval_ref", "incident_id", "visibility"],
                    "explicit_required_backend_inputs": [],
                    "explicit_optional_backend_inputs": [],
                    "approval_rule_refs": ["approval.customer_impact_comment"],
                    "denial_rule_refs": ["deny.sensitive_outbound_content"],
                    "clarification_rule_refs": ["clarify.missing_issue_or_comment"],
                    "audit_required": True,
                    "outbound_controls": ["sensitive_data_redaction", "payload_preview", "audit_receipt"],
                },
            },
        ],
        "requirements": {
            "id": "req-issue-tracker-fronting",
            "title": "Issue tracker fronting requirements",
            "data": {
                "system": {
                    "name": "issue-tracker-governance-service",
                    "domain": "software_delivery",
                    "deployment_intent": "centralized_anip_fronting_service",
                },
                "transports": {
                    "http": True,
                    "mcp": True,
                },
                "trust": {
                    "mode": "actor_aware_governed_access",
                    "checkpoints": True,
                },
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
                    "raw_tools_not_agent_facing": True,
                    "supports_native_api_backends": True,
                    "supports_mcp_backends": True,
                    "centralized_outbound_governance": True,
                    "approval_required_for_state_changes": True,
                    "deny_out_of_scope_targets": True,
                    "clarify_missing_required_fields": True,
                    "redact_sensitive_outbound_content": True,
                    "audit_every_governed_call": True,
                },
                "scale": {
                    "shape_preference": "production_single_service",
                    "high_availability": True,
                },
                "services": [
                    {
                        "name": "Issue Tracker Governance Service",
                        "role": "Curated ANIP capability surface in front of issue-tracker native API and MCP operations.",
                    }
                ],
            },
        },
        "scenario": {
            "id": "scenario-issue-tracker-prepare-ticket",
            "title": "Prepare high-impact bug ticket",
            "data": {
                "scenario": {
                    "name": "prepare_high_impact_bug_ticket",
                    "summary": "An engineering operator asks the agent to create a Sev-2 bug from an incident summary.",
                    "actors": ["engineering_operator", "engineering_manager"],
                    "expected_outcome": "ANIP prepares a sanitized ticket draft, flags approval requirement, and does not call raw create issue directly.",
                    "capabilities": ["issue_tracker.prepare_ticket"],
                    "governed_behaviors": ["clarification", "redaction", "approval_stop", "audit"],
                }
            },
        },
        "additional_scenarios": [
            {
                "id": "scenario-issue-tracker-search-backlog",
                "title": "Search bounded backlog context",
                "data": {
                    "scenario": {
                        "name": "search_bounded_backlog_context",
                        "summary": "An operator searches allowed project backlog context before preparing follow-up work.",
                        "actors": ["engineering_operator"],
                        "expected_outcome": "ANIP runs bounded search only inside allowed project scope and filters sensitive fields.",
                        "capabilities": ["issue_tracker.search_team_backlog"],
                        "governed_behaviors": ["bounded_result", "field_filtering", "audit"],
                    }
                },
            },
            {
                "id": "scenario-issue-tracker-transition-request",
                "title": "Request workflow transition",
                "data": {
                    "scenario": {
                        "name": "request_workflow_transition",
                        "summary": "An operator asks the agent to move an issue to Done.",
                        "actors": ["engineering_operator", "engineering_manager"],
                        "expected_outcome": "ANIP prepares a transition request, denies direct Done mutation, and requires approval evidence.",
                        "capabilities": ["issue_tracker.request_status_transition"],
                        "governed_behaviors": ["denial", "approval_stop", "audit"],
                    }
                },
            },
        ],
        "integration_discovery_records": [
            {
                "id": "disc-native-search-issues",
                "connection_id": "conn-issue-tracker-native-api",
                "operation_id": "issue_rest.search_issues",
                "backend_kind": "native_api",
                "method": "GET",
                "path_template": "/rest/api/3/search",
                "side_effect_level": "read",
                "input_schema_summary": {"required": ["jql"], "optional": ["fields", "maxResults"]},
                "risk_notes": ["Read-only, but may return sensitive issue fields."],
            },
            {
                "id": "disc-native-create-issue",
                "connection_id": "conn-issue-tracker-native-api",
                "operation_id": "issue_rest.create_issue",
                "backend_kind": "native_api",
                "method": "POST",
                "path_template": "/rest/api/3/issue",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["project", "issuetype", "summary", "description"], "optional": ["labels", "assignee"]},
                "risk_notes": ["Creates durable external issue state.", "Must be governed through prepare/approval semantics."],
            },
            {
                "id": "disc-native-transition-issue",
                "connection_id": "conn-issue-tracker-native-api",
                "operation_id": "issue_rest.transition_issue",
                "backend_kind": "native_api",
                "method": "POST",
                "path_template": "/rest/api/3/issue/{issueIdOrKey}/transitions",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["issue_key", "transition_id"], "optional": ["comment"]},
                "risk_notes": ["Mutates workflow state.", "Direct Done transitions should not be exposed to agents."],
            },
            {
                "id": "disc-native-add-comment",
                "connection_id": "conn-issue-tracker-native-api",
                "operation_id": "issue_rest.add_comment",
                "backend_kind": "native_api",
                "method": "POST",
                "path_template": "/rest/api/3/issue/{issueIdOrKey}/comment",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["issue_key", "body"], "optional": ["visibility"]},
                "risk_notes": ["Sends comment content to external issue tracker.", "Outbound content must be sanitized."],
            },
            {
                "id": "disc-mcp-search-issues",
                "connection_id": "conn-issue-tracker-mcp",
                "operation_id": "issue_mcp.search_issues",
                "backend_kind": "mcp",
                "side_effect_level": "read",
                "input_schema_summary": {"required": ["query"], "optional": ["fields", "limit"]},
                "risk_notes": ["Raw MCP search tool is discovery input, not the final ANIP capability."],
            },
            {
                "id": "disc-mcp-create-issue",
                "connection_id": "conn-issue-tracker-mcp",
                "operation_id": "issue_mcp.create_issue",
                "backend_kind": "mcp",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["project_key", "issue_type", "summary", "description"], "optional": ["labels"]},
                "risk_notes": ["Raw MCP create tool must stay behind governed prepare/approval capability."],
            },
            {
                "id": "disc-mcp-transition-issue",
                "connection_id": "conn-issue-tracker-mcp",
                "operation_id": "issue_mcp.transition_issue",
                "backend_kind": "mcp",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["issue_key", "target_status"], "optional": ["comment"]},
                "risk_notes": ["Raw MCP workflow mutation must not be directly agent-facing."],
            },
            {
                "id": "disc-mcp-add-comment",
                "connection_id": "conn-issue-tracker-mcp",
                "operation_id": "issue_mcp.add_comment",
                "backend_kind": "mcp",
                "side_effect_level": "write",
                "input_schema_summary": {"required": ["issue_key", "comment_body"], "optional": ["visibility"]},
                "risk_notes": ["Comment payload needs outbound data governance before transmission."],
            },
        ],
    }
)


def _fronting_starter_project(
    *,
    system_id: str,
    display_name: str,
    domain: str,
    source_path: str,
    native_backend: str,
    native_endpoint_ref: str,
    native_secret_ref: str,
    mcp_endpoint_ref: str,
    mcp_secret_ref: str,
) -> dict:
    project_id = f"{system_id}-fronting-starter"
    native_connection = f"conn-{system_id}-native"
    mcp_connection = f"conn-{system_id}-mcp"
    service_id = f"{system_id}-governance-service"
    service_name = f"{display_name} Governance Service"
    starter_definition_path = source_path.replace("source-spec.md", "anip-fronting-starter.json")
    starter_definition = _load_fronting_starter_definition(starter_definition_path)
    scenarios = _fronting_scenarios(system_id, display_name, starter_definition)

    return {
        "workspace": {
            "id": "ws-anip-showcases",
            "name": "ANIP Public Showcases",
            "summary": (
                "Curated public read-only showcase projects for the GTM Agent and governed fronting starters."
            ),
        },
        "project": {
            "id": project_id,
            "workspace_id": "ws-anip-showcases",
            "name": f"{display_name} Fronting Starter",
            "domain": domain,
            "summary": (
                f"Starter project for placing a governed ANIP capability surface in front of {display_name} "
                "native API and MCP-style backend operations."
            ),
            "labels": ["showcase", "fronting-starter", system_id, "native-api", "mcp"],
            "project_type": "governed_service_project",
            "integration_profile": {
                "kind": "hybrid",
                "systems": [
                    {
                        "system_id": f"{system_id}-native",
                        "display_name": f"{display_name} Native API",
                        "backend_kind": native_backend,
                        "auth_mode": "service_delegated",
                        "connection_ref": native_connection,
                    },
                    {
                        "system_id": f"{system_id}-mcp",
                        "display_name": f"{display_name} MCP Server",
                        "backend_kind": "mcp",
                        "auth_mode": "user_delegated",
                        "connection_ref": mcp_connection,
                    },
                ],
            },
        },
        "seed_profiles": ["public_showcase"],
        "seed_update_policy": "replace_seed_artifacts",
        "workspace_connections": [
            {
                "id": native_connection,
                "display_name": f"{display_name} Native API",
                "backend_kind": native_backend,
                "system_kind": system_id,
                "endpoint_ref": native_endpoint_ref,
                "auth_mode": "service_delegated",
                "identity_provider_ref": "enterprise-sso",
                "secret_ref": native_secret_ref,
                "allowed_project_refs": [project_id],
                "metadata": {"seed_kind": "fronting_starter", "secret_material": "external"},
            },
            {
                "id": mcp_connection,
                "display_name": f"{display_name} MCP Server",
                "backend_kind": "mcp",
                "system_kind": system_id,
                "endpoint_ref": mcp_endpoint_ref,
                "auth_mode": "user_delegated",
                "identity_provider_ref": "enterprise-sso",
                "secret_ref": mcp_secret_ref,
                "allowed_project_refs": [project_id],
                "metadata": {"seed_kind": "fronting_starter", "secret_material": "delegated_or_external"},
            },
        ],
        "requirements": {
            "id": f"req-{system_id}-fronting-source",
            "title": f"{display_name} fronting source specification",
            "data": {
                "source_documents": [
                    {
                        "artifact_id": f"doc-{system_id}-fronting-source-spec",
                        "title": f"{display_name} Governed Fronting Source Specification",
                        "path": source_path,
                        "kind": "business_intent",
                    },
                    {
                        "artifact_id": f"doc-{system_id}-fronting-starter-contract",
                        "title": f"{display_name} Fronting Starter Contract",
                        "path": starter_definition_path,
                        "kind": "integration_contract",
                    }
                ],
                "system": {
                    "name": f"{display_name} governed fronting starter",
                    "domain": domain,
                    "deployment_intent": "centralized_anip_fronting_service",
                },
                "services": [
                    {
                        "name": service_name,
                        "role": f"Curated ANIP capability surface in front of {display_name} native API operations.",
                        "public_http": True,
                        "internal_only": False,
                    }
                ],
                "transports": {"http": True, "mcp": True, "stdio": False, "grpc": False},
                "trust": {"mode": "actor_aware_governed_access", "checkpoints": True},
                "auth": {
                    "delegation_tokens": True,
                    "purpose_binding": True,
                    "scoped_authority": True,
                    "service_to_service_handoffs": False,
                },
                "permissions": {
                    "preflight_discovery": True,
                    "restricted_vs_denied": True,
                    "grantable_requirements": True,
                },
                "audit": {
                    "durable": True,
                    "searchable": True,
                    "cross_service_reconstruction_required": False,
                },
                "lineage": {
                    "invocation_id": True,
                    "client_reference_id": True,
                    "task_id": True,
                    "parent_invocation_id": True,
                    "cross_service_continuity_required": False,
                },
                "business_constraints": {
                    "raw_tools_not_agent_facing": True,
                    "supports_native_api_backends": True,
                    "supports_mcp_backends": True,
                    "centralized_outbound_governance": True,
                    "approval_required_for_state_changes": True,
                    "deny_out_of_scope_targets": True,
                    "clarify_missing_required_fields": True,
                    "audit_every_governed_call": True,
                    "approval_expected_for_high_risk": True,
                    "blocked_failure_posture": "clarify_or_deny_before_downstream_call",
                },
                "scale": {
                    "shape_preference": "production_single_service",
                    "high_availability": True,
                },
                "risk_profile": {
                    _slug(str(operation.get("capability_id", "capability"))).replace("-", "_"): {
                        "side_effect": "none" if str(operation.get("side_effect_level") or "read") == "read" else "reversible",
                        "high_risk": str(operation.get("side_effect_level") or "read") != "read",
                        "approval_required": str(operation.get("side_effect_level") or "read") != "read",
                        "recovery_guidance_required": str(operation.get("side_effect_level") or "read") != "read",
                    }
                    for operation in starter_definition.get("operations", [])
                    if str(operation.get("capability_id", "")).strip()
                },
            },
        },
        "scenario": scenarios[0] if scenarios else None,
        "additional_scenarios": scenarios[1:],
        "integration_discovery_records": _fronting_discovery_records(project_id, native_connection, starter_definition),
        "pm_artifacts": [
            *_fronting_product_artifacts(system_id, display_name, domain, starter_definition),
            *_fronting_mapping_artifacts(
                project_id=project_id,
                service_id=service_id,
                service_name=service_name,
                native_connection=native_connection,
                definition=starter_definition,
            ),
            {
                "id": f"{project_id}-developer-baseline",
                "title": "Developer Baseline",
                "data": {
                    "artifact_type": "developer_baseline",
                    "source_inputs": {
                        "product_revision_artifact_id": None,
                        "product_revision_number": None,
                        "product_design_hash": None,
                        "requirements_id": f"req-{system_id}-fronting-source",
                        "requirements_hash": None,
                        "scenario_ids": [scenario["id"] for scenario in scenarios],
                        "primary_scenario_id": scenarios[0]["id"] if scenarios else None,
                        "scenario_set_hash": None,
                        "shape_id": None,
                        "shape_hash": None,
                    },
                    "locked_at": "2026-05-24T00:00:00.000Z",
                    "note": "Seeded public-preview baseline for reviewed fronting starter intent and accepted backend mappings.",
                },
            },
            {
                "id": f"{project_id}-traceability",
                "title": "Traceability Record",
                "data": {
                    "artifact_type": "design_traceability",
                    "source_inputs": {
                        "requirements_id": f"req-{system_id}-fronting-source",
                        "scenario_id": scenarios[0]["id"] if scenarios else None,
                        "scenario_ids": [scenario["id"] for scenario in scenarios],
                        "shape_id": None,
                        "baseline_locked_at": "2026-05-24T00:00:00.000Z",
                    },
                    "coverage": [],
                    "developer_status": "ready_for_pm_review",
                    "developer_note": "Seeded fronting starter has reviewed PM intent, scenarios, and accepted capability mappings.",
                    "developer_marked_at": "2026-05-24T00:00:00.000Z",
                },
            },
        ],
        "documents": [
            {
                "id": f"doc-{system_id}-fronting-intent",
                "title": f"{display_name} Fronting Starter Intent",
                "kind": "business_intent",
                "filename": f"{system_id}-fronting-intent.md",
                "source_path": f"seed://fronting-starters/{system_id}/intent",
                "content": (
                    f"# {display_name} fronting starter intent\n\n"
                    f"This starter exists to help teams model how ANIP can govern {display_name} access without handing "
                    "agents raw API or MCP tools. Complete the project by reviewing the imported source specification, "
                    "confirming capability boundaries, and selecting the implementation backend at generation time."
                ),
            },
            {
                "id": f"doc-{system_id}-developer-evidence",
                "title": f"{display_name} Developer Evidence",
                "kind": "api_docs",
                "filename": f"{system_id}-developer-evidence.template.md",
                "source_path": f"seed://fronting-starters/{system_id}/developer-evidence",
                "content": _fronting_developer_evidence_markdown(system_id, display_name, service_id, starter_definition),
            }
        ],
    }


SEED_PROJECTS.extend(
    [
        _fronting_starter_project(
            system_id="jira",
            display_name="Jira",
            domain="software_delivery",
            source_path="docs/examples/jira-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="JIRA_BASE_URL",
            native_secret_ref="env:JIRA_API_TOKEN",
            mcp_endpoint_ref="ATLASSIAN_MCP_ENDPOINT",
            mcp_secret_ref="env:ATLASSIAN_MCP_TOKEN",
        ),
        _fronting_starter_project(
            system_id="github",
            display_name="GitHub",
            domain="software_delivery",
            source_path="docs/examples/github-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="GITHUB_API_URL",
            native_secret_ref="env:GITHUB_TOKEN",
            mcp_endpoint_ref="GITHUB_MCP_ENDPOINT",
            mcp_secret_ref="env:GITHUB_MCP_TOKEN",
        ),
        _fronting_starter_project(
            system_id="slack",
            display_name="Slack",
            domain="collaboration_operations",
            source_path="docs/examples/slack-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="SLACK_API_URL",
            native_secret_ref="env:SLACK_BOT_TOKEN",
            mcp_endpoint_ref="SLACK_MCP_ENDPOINT",
            mcp_secret_ref="env:SLACK_MCP_TOKEN",
        ),
        _fronting_starter_project(
            system_id="notion",
            display_name="Notion",
            domain="knowledge_operations",
            source_path="docs/examples/notion-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="NOTION_API_URL",
            native_secret_ref="env:NOTION_TOKEN",
            mcp_endpoint_ref="NOTION_MCP_ENDPOINT",
            mcp_secret_ref="env:NOTION_MCP_TOKEN",
        ),
        _fronting_starter_project(
            system_id="linear",
            display_name="Linear",
            domain="software_delivery",
            source_path="docs/examples/linear-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="LINEAR_GRAPHQL_URL",
            native_secret_ref="env:LINEAR_API_KEY",
            mcp_endpoint_ref="LINEAR_MCP_ENDPOINT",
            mcp_secret_ref="env:LINEAR_MCP_TOKEN",
        ),
        _fronting_starter_project(
            system_id="gitlab",
            display_name="GitLab",
            domain="software_delivery",
            source_path="docs/examples/gitlab-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="GITLAB_API_URL",
            native_secret_ref="env:GITLAB_TOKEN",
            mcp_endpoint_ref="GITLAB_MCP_ENDPOINT",
            mcp_secret_ref="env:GITLAB_MCP_TOKEN",
        ),
        _fronting_starter_project(
            system_id="superset",
            display_name="Superset",
            domain="analytics_operations",
            source_path="docs/examples/superset-fronting-showcase/source-spec.md",
            native_backend="native_api",
            native_endpoint_ref="SUPERSET_API_URL",
            native_secret_ref="env:SUPERSET_SERVICE_TOKEN",
            mcp_endpoint_ref="SUPERSET_MCP_ENDPOINT",
            mcp_secret_ref="env:SUPERSET_MCP_TOKEN",
        ),
    ]
)
