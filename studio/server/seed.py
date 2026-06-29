"""Seed Studio with curated built-in demo projects."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import repository
from . import project_snapshots
from .project_snapshots import import_showcase_snapshots_from_disk
from .runtime_paths import repo_root
from .seed_catalog import SEED_PROJECTS

_REPO_ROOT = repo_root()
PUBLIC_SHOWCASE_WORKSPACE = {
    "id": "ws-anip-showcases",
    "name": "ANIP Public Showcases",
    "summary": "Curated public read-only showcase projects restored from the packages and templates published in the ANIP Registry.",
}


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _seed_profile() -> str:
    configured = os.getenv("STUDIO_SEED_PROFILE", "").strip().lower()
    if configured:
        return configured
    if _env_bool("STUDIO_READ_ONLY"):
        return "public_showcase"
    if _env_bool("STUDIO_SEED_SHOWCASES"):
        return "public_showcase"
    return "all"


def _seed_item_enabled(item: dict[str, Any], profile: str) -> bool:
    if profile in {"public_showcase", "showcase_snapshots", "snapshot_showcase", "snapshots"}:
        return False
    if profile in {"all", "*"}:
        return True
    profiles = item.get("seed_profiles")
    if not isinstance(profiles, list):
        return False
    return profile in {str(value).strip().lower() for value in profiles}


def _merge_missing(existing: Any, incoming: Any) -> Any:
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = dict(existing)
        changed = False
        for key, value in incoming.items():
            if key not in merged:
                merged[key] = value
                changed = True
                continue
            merged_value = _merge_missing(merged[key], value)
            if merged_value != merged[key]:
                merged[key] = merged_value
                changed = True
        return merged if changed else existing

    if isinstance(existing, list) and isinstance(incoming, list):
        merged = list(existing)
        changed = False
        for item in incoming:
            if item not in merged:
                merged.append(item)
                changed = True
        return merged if changed else existing

    if existing in (None, "", [], {}):
        return incoming
    return existing


def _replace_seed_artifact_data(item: dict[str, Any]) -> bool:
    return item.get("seed_update_policy") == "replace_seed_artifacts"


def _seed_artifact_data(existing: Any, incoming: Any, item: dict[str, Any]) -> Any:
    if _replace_seed_artifact_data(item):
        return incoming
    return _merge_missing(existing, incoming)


def _ensure_requirements(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    requirements = item.get("requirements")
    if not requirements:
        return
    try:
        existing = repository.get_requirements(conn, project_id, requirements["id"])
        merged_data = _seed_artifact_data(existing["data"], requirements["data"], item)
        if merged_data != existing["data"]:
            repository.update_requirements(
                conn,
                project_id,
                requirements["id"],
                data=merged_data,
            )
    except repository.NotFoundError:
        repository.create_requirements(
            conn,
            project_id=project_id,
            req_id=requirements["id"],
            title=requirements["title"],
            data=requirements["data"],
        )

    for additional_requirements in item.get("additional_requirements", []):
        try:
            existing = repository.get_requirements(conn, project_id, additional_requirements["id"])
            merged_data = _seed_artifact_data(existing["data"], additional_requirements["data"], item)
            if merged_data != existing["data"]:
                repository.update_requirements(
                    conn,
                    project_id,
                    additional_requirements["id"],
                    data=merged_data,
                )
        except repository.NotFoundError:
            repository.create_requirements(
                conn,
                project_id=project_id,
                req_id=additional_requirements["id"],
                title=additional_requirements["title"],
                data=additional_requirements["data"],
            )


def _ensure_scenario(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    scenarios = []
    if item.get("scenario"):
        scenarios.append(item["scenario"])
    scenarios.extend(item.get("additional_scenarios", []))
    for scenario in scenarios:
        try:
            existing = repository.get_scenario(conn, project_id, scenario["id"])
            merged_data = _seed_artifact_data(existing["data"], scenario["data"], item)
            if merged_data != existing["data"]:
                repository.update_scenario(conn, project_id, scenario["id"], data=merged_data)
        except repository.NotFoundError:
            repository.create_scenario(
                conn,
                project_id=project_id,
                scenario_id=scenario["id"],
                title=scenario["title"],
                data=scenario["data"],
            )


def _ensure_proposal(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    proposal = item.get("proposal")
    requirements = item.get("requirements")
    if not proposal or not requirements:
        return
    try:
        existing = repository.get_proposal(conn, project_id, proposal["id"])
        merged_data = _seed_artifact_data(existing["data"], proposal["data"], item)
        if merged_data != existing["data"]:
            repository.update_proposal(conn, project_id, proposal["id"], data=merged_data)
    except repository.NotFoundError:
        repository.create_proposal(
            conn,
            project_id=project_id,
            proposal_id=proposal["id"],
            title=proposal["title"],
            requirements_id=requirements["id"],
            data=proposal["data"],
        )


def _ensure_shape(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    shape = item.get("shape")
    requirements = item.get("requirements")
    if not shape or not requirements:
        return
    try:
        existing = repository.get_shape(conn, project_id, shape["id"])
        merged_data = _seed_artifact_data(existing["data"], shape["data"], item)
        if merged_data != existing["data"]:
            repository.update_shape(conn, project_id, shape["id"], data=merged_data)
    except repository.NotFoundError:
        repository.create_shape(
            conn,
            project_id=project_id,
            shape_id=shape["id"],
            title=shape["title"],
            requirements_id=requirements["id"],
            data=shape["data"],
        )


def _ensure_evaluation(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    evaluation = item.get("evaluation")
    proposal = item.get("proposal")
    scenario = item.get("scenario")
    requirements = item.get("requirements")
    shape = item.get("shape")
    if not evaluation or not proposal or not scenario or not requirements or not shape:
        return
    try:
        repository.get_evaluation(conn, project_id, evaluation["id"])
    except repository.NotFoundError:
        input_snapshot = {
            "requirements": requirements["data"],
            "proposal": proposal["data"],
            "scenario": scenario["data"],
        }
        repository.create_evaluation(
            conn,
            project_id=project_id,
            eval_id=evaluation["id"],
            proposal_id=proposal["id"],
            scenario_id=scenario["id"],
            requirements_id=requirements["id"],
            source=evaluation["source"],
            data=evaluation["data"],
            input_snapshot=input_snapshot,
            shape_id=shape["id"],
        )


def _ensure_service_metadata(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    for service_metadata in item.get("service_metadata", []):
        try:
            repository.get_service_metadata_artifact(conn, project_id, service_metadata["id"])
        except repository.NotFoundError:
            repository.create_service_metadata_artifact(
                conn,
                project_id=project_id,
                artifact_id=service_metadata["id"],
                title=service_metadata["title"],
                data=service_metadata["data"],
            )


def _load_static_pm_artifacts(item: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = item.get("static_pm_artifacts_path")
    if not source_path:
        return []
    path = _REPO_ROOT / str(source_path)
    if not path.exists():
        raise RuntimeError(f"Seed static PM artifact file does not exist: {path}")
    content = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(content, list):
        raise RuntimeError(f"Seed static PM artifact file must contain a list: {path}")
    return content


def _ensure_pm_artifacts(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    artifacts = [*item.get("pm_artifacts", []), *_load_static_pm_artifacts(item)]
    for artifact in artifacts:
        try:
            existing = repository.get_pm_artifact(conn, project_id, artifact["id"])
            merged_data = _seed_artifact_data(existing["data"], artifact["data"], item)
            if merged_data != existing["data"]:
                repository.update_pm_artifact(conn, project_id, artifact["id"], data=merged_data)
        except repository.NotFoundError:
            repository.create_pm_artifact(
                conn,
                project_id=project_id,
                artifact_id=artifact["id"],
                title=artifact["title"],
                data=artifact["data"],
            )


def _scenario_set_hash(scenarios: list[dict[str, Any]]) -> str | None:
    if not scenarios:
        return None
    return "|".join(
        sorted(f"{scenario['id']}:{scenario['content_hash']}" for scenario in scenarios)
    )


def _approval_grant_policy() -> dict[str, Any]:
    return {
        "allowed_grant_types": ["one_time", "session_bound"],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1,
    }


def _input_resolution(input_data: dict[str, Any], *, required: bool) -> dict[str, str | None]:
    allowed_values = input_data.get("allowed_values") if isinstance(input_data.get("allowed_values"), list) else []
    default_value = str(input_data.get("default_value") or "").strip()
    if allowed_values:
        return {
            "mode": "closed_values",
            "resolver_ref": None,
            "on_missing": "use_default" if default_value else "omit",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify",
        }
    return {
        "mode": "clarify" if required else "explicit_only",
        "resolver_ref": None,
        "on_missing": "clarify" if required else "omit",
        "on_ambiguous": "clarify",
        "on_unresolved": "clarify",
    }


def _developer_input_formalization(input_data: dict[str, Any], *, required: bool) -> dict[str, Any]:
    input_name = str(input_data.get("input_name") or input_data.get("name") or "").strip()
    semantic_type = str(input_data.get("semantic_type") or "").strip()
    clarification_hint = str(input_data.get("clarification_hint") or "").strip()
    default_value = str(input_data.get("default_value") or "").strip()
    allowed_values = [
        str(value)
        for value in input_data.get("allowed_values", [])
        if str(value).strip()
    ]
    return {
        "input_name": input_name,
        "input_type": str(input_data.get("input_type") or input_data.get("type") or "string"),
        "required": required,
        "summary": str(input_data.get("summary") or input_data.get("description") or input_name),
        "default_value": default_value,
        "allowed_values": allowed_values,
        "semantic_type": semantic_type or ("business_context" if required else ""),
        "input_format": str(input_data.get("input_format") or input_data.get("format") or ""),
        "validation_pattern": str(input_data.get("validation_pattern") or input_data.get("pattern") or ""),
        "clarification_hint": clarification_hint or (f"Ask for {input_name} before invoking the capability." if required else ""),
        "entity_reference": bool(input_data.get("entity_reference")),
        "reference_catalog": list(input_data.get("reference_catalog", [])) if isinstance(input_data.get("reference_catalog"), list) else [],
        "semantic_aliases": list(input_data.get("semantic_aliases", [])) if isinstance(input_data.get("semantic_aliases"), list) else [],
        "normalization_hint": str(input_data.get("normalization_hint") or ""),
        "normalization_context": str(input_data.get("normalization_context") or ""),
        "allowed_value_semantics": list(input_data.get("allowed_value_semantics", [])) if isinstance(input_data.get("allowed_value_semantics"), list) else [],
        "resolution": _input_resolution(
            {
                **input_data,
                "allowed_values": allowed_values,
                "default_value": default_value,
            },
            required=required,
        ),
        "catalog_ref": str(input_data.get("catalog_ref") or ""),
    }


def _developer_capability_formalization(mapping: dict[str, Any]) -> dict[str, Any]:
    capability_id = str(mapping.get("capability_id") or "").strip()
    side_effect_level = str(mapping.get("side_effect_level") or "read")
    write_like = side_effect_level != "read"
    metadata_by_name = {
        str(item.get("input_name") or item.get("name") or "").strip(): item
        for item in mapping.get("input_metadata", [])
        if str(item.get("input_name") or item.get("name") or "").strip()
    }
    inputs = []
    for name in mapping.get("required_inputs", []):
        input_data = metadata_by_name.get(str(name), {"input_name": str(name)})
        inputs.append(_developer_input_formalization(input_data, required=True))
    for name in mapping.get("optional_inputs", []):
        input_data = metadata_by_name.get(str(name), {"input_name": str(name)})
        inputs.append(_developer_input_formalization(input_data, required=False))
    return {
        "id": f"integration_fronting:{capability_id}",
        "kind": "atomic",
        "composition": None,
        "grant_policy": _approval_grant_policy() if write_like else None,
        "source_kind": "application_integration",
        "service_id": str(mapping.get("service_id") or ""),
        "capability_id": capability_id,
        "title": str(mapping.get("title") or capability_id),
        "summary": str(mapping.get("summary") or mapping.get("intent") or capability_id),
        "entity_targeted": True,
        "subject_kind": str(mapping.get("subject_kind") or "fronting_subject"),
        "context_type": str(mapping.get("context_type") or "fronting_context"),
        "output_intent": str(mapping.get("output_intent") or "governed_fronting_result"),
        "intent_type": "approval_gated" if write_like else "read_only",
        "operation_type": "approval_gated" if write_like else "read",
        "side_effect_level": "approval_required" if write_like else "read",
        "minimum_scope": [capability_id],
        "backend_operation": (mapping.get("raw_operation_refs") or [capability_id])[0],
        "path_template": "",
        "output_shape": str(mapping.get("output_intent") or "governed_fronting_result"),
        "inputs": inputs,
        "business_effects": {
            "produces": ["approval.request", "system.preview_mutation"] if write_like else ["content.summary"],
            "does_not_produce": ["external_dispatch", "system.mutation"] if write_like else ["raw_backend_operation"],
        },
    }


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _aligned_backend_binding(
    binding: dict[str, Any],
    discovery_records: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_operation_refs = [
        str(value).strip()
        for value in binding.get("raw_operation_refs", [])
        if str(value).strip()
    ]
    backend_kind = str(binding.get("backend_kind") or "native_api")
    connection_ref = str(binding.get("connection_ref") or "")
    exact_matches = [
        record
        for record in discovery_records
        if record.get("backend_kind") == backend_kind
        and record.get("operation_id") in raw_operation_refs
        and (not record.get("connection_id") or record.get("connection_id") == connection_ref)
    ]
    matches = exact_matches or [
        record
        for record in discovery_records
        if record.get("backend_kind") == backend_kind
        and record.get("operation_id") in raw_operation_refs
    ]
    required = _ordered_unique(
        [
            str(value)
            for record in matches
            for value in (record.get("input_schema_summary", {}) or {}).get("required", [])
            if str(value).strip()
        ]
    )
    optional = [
        value
        for value in _ordered_unique(
            [
                str(value)
                for record in matches
                for value in (record.get("input_schema_summary", {}) or {}).get("optional", [])
                if str(value).strip()
            ]
        )
        if value not in required
    ]
    return {
        **binding,
        "derived_required_backend_inputs": required,
        "derived_optional_backend_inputs": optional,
        "matched_discovery_record_ids": [record["id"] for record in matches],
    }


def _aligned_fronting_mapping(
    mapping: dict[str, Any],
    discovery_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **mapping,
        "backend_bindings": [
            _aligned_backend_binding(binding, discovery_records)
            for binding in mapping.get("backend_bindings", [])
        ],
    }


def _developer_scenario_formalizations(scenarios: list[dict[str, Any]], service_id: str) -> list[dict[str, Any]]:
    formalizations: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_data = (scenario.get("data", {}) or {}).get("scenario", {}) or {}
        context = scenario_data.get("context", {}) if isinstance(scenario_data.get("context"), dict) else {}
        formalizations.append(
            {
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
                "scenario_key": str(scenario_data.get("name") or ""),
                "primary_capability": str(context.get("capability") or ""),
                "actor_context": str(context.get("actor") or ""),
                "business_scope": str(context.get("authority_boundary") or ""),
                "time_scope": "",
                "side_effect_formalization": "Read requests are bounded; write-adjacent requests stop at preview or approval.",
                "expected_cost_formalization": "Backend calls remain provider-owned and bounded by the governed capability.",
                "budget_guard_formalization": "Reject raw backend bypass and unbounded export behavior.",
                "permission_formalization": "Use fronting permission intent and capability-level side-effect posture.",
                "task_tracking_formalization": "Record invocation and audit lineage for every governed call.",
                "participating_service_ids": [service_id],
                "orchestration_steps": [
                    {
                        "id": "invoke_governed_capability",
                        "service_id": service_id,
                        "step_kind": "capability_execution",
                        "capability_id": str(context.get("capability") or ""),
                        "outcome_type": "available",
                        "stop_condition": "complete",
                    }
                ],
                "required_behaviors": scenario_data.get("expected_behavior", []),
                "required_anip_support": scenario_data.get("expected_anip_support", []),
                "implementation_notes": "Seeded from reviewed fronting starter scenario.",
            }
        )
    return formalizations


def _upsert_pm_artifact(conn: Any, project_id: str, artifact_id: str, title: str, data: dict[str, Any]) -> None:
    try:
        existing = repository.get_pm_artifact(conn, project_id, artifact_id)
        if existing["title"] != title or existing["data"] != data:
            repository.update_pm_artifact(conn, project_id, artifact_id, title=title, data=data)
    except repository.NotFoundError:
        repository.create_pm_artifact(
            conn,
            project_id=project_id,
            artifact_id=artifact_id,
            title=title,
            data=data,
        )


def _ensure_fronting_developer_seed(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    if item.get("project", {}).get("project_type") != "governed_service_project":
        return
    requirements_cfg = item.get("requirements") or {}
    req_id = requirements_cfg.get("id")
    if not req_id:
        return
    try:
        requirements = repository.get_requirements(conn, project_id, req_id)
    except repository.NotFoundError:
        return
    scenario_cfgs = [item["scenario"]] if item.get("scenario") else []
    scenario_cfgs.extend(item.get("additional_scenarios", []))
    scenarios: list[dict[str, Any]] = []
    for scenario_cfg in scenario_cfgs:
        try:
            scenarios.append(repository.get_scenario(conn, project_id, scenario_cfg["id"]))
        except repository.NotFoundError:
            continue
    pm_artifacts = repository.list_pm_artifacts(conn, project_id)
    mappings = [
        artifact["data"]
        for artifact in pm_artifacts
        if artifact.get("data", {}).get("artifact_type") == "integration_fronting_capability_mapping"
    ]
    if not mappings:
        return
    mappings.sort(key=lambda mapping: str(mapping.get("capability_id") or ""))
    discovery_records = repository.list_integration_discovery_records(conn, project_id)
    mappings = [
        _aligned_fronting_mapping(mapping, discovery_records)
        for mapping in mappings
    ]
    service_id = str(mappings[0].get("service_id") or f"{project_id}-governance-service")
    service_name = str(mappings[0].get("service_name") or "Governance Service")
    scenario_hash = _scenario_set_hash(scenarios)
    locked_at = "2026-05-24T00:00:00.000Z"
    source_inputs = {
        "product_revision_artifact_id": None,
        "product_revision_number": None,
        "product_design_hash": None,
        "requirements_id": requirements["id"],
        "requirements_hash": requirements["content_hash"],
        "scenario_ids": [scenario["id"] for scenario in scenarios],
        "primary_scenario_id": scenarios[0]["id"] if scenarios else None,
        "scenario_set_hash": scenario_hash,
        "shape_id": None,
        "shape_hash": None,
    }
    baseline = {
        "artifact_type": "developer_baseline",
        "source_inputs": source_inputs,
        "locked_at": locked_at,
        "note": "Seeded public-preview baseline for reviewed fronting starter intent and accepted backend mappings.",
    }
    _upsert_pm_artifact(conn, project_id, f"{project_id}-developer-baseline", "Developer Baseline", baseline)

    capabilities = [_developer_capability_formalization(mapping) for mapping in mappings]
    supported_question_bindings = [
        {
            "id": f"supported_question_family_{index}",
            "question_family": str(capability["title"]),
            "target_service_ids": [service_id],
            "verification_strategy": "Verify the capability preserves bounded fronting behavior, clarification, denial, approval, and audit posture.",
            "evidence_signal": str(capability["capability_id"]),
        }
        for index, capability in enumerate(capabilities)
    ]
    definition_source_inputs = {**source_inputs, "baseline_locked_at": locked_at}
    definition = {
        "artifact_type": "developer_definition",
        "source_inputs": definition_source_inputs,
        "product_alignment": {
            "governed_behavior_formalization": "Expose reviewed ANIP capabilities over backend operations, clarify missing required inputs, deny backend bypass, and audit each governed call.",
            "approval_posture_formalization": "Read operations are bounded; write-adjacent operations prepare previews or require approval before downstream mutation.",
        },
        "identity": {
            "system_name": item["project"]["name"],
            "domain_name": item["project"]["domain"],
            "delivery_model": "standalone_service",
            "architecture_shape": "single_service",
            "high_availability_required": True,
        },
        "authority": {
            "trust_mode": "actor_aware_governed_access",
            "trust_checkpoints_required": True,
            "spending_actions_present": False,
            "irreversible_actions_present": False,
            "cost_visibility_required": False,
            "preflight_authority_discovery": True,
            "grantable_restrictions": True,
            "restricted_vs_denied": True,
            "delegation_tokens": True,
            "scoped_authority": True,
            "purpose_binding": True,
            "approval_expectation": "approval_required_for_high_risk",
            "recovery_sensitive": False,
            "blocked_failure_posture": "clarify_or_deny_before_downstream_call",
        },
        "audit": {
            "durable_records_required": True,
            "searchable_history_required": True,
            "invocation_tracking": True,
            "task_tracking": True,
            "parent_invocation_tracking": True,
            "client_reference_ids": True,
            "service_handoffs_required": False,
            "cross_service_reconstruction_required": False,
            "cross_service_continuity_required": False,
        },
        "backend_bindings": [],
        "integration_fronting": {
            "project_type": "governed_service_project",
            "integration_profile": item["project"].get("integration_profile") or {"kind": "none", "systems": []},
            "capability_mappings": mappings,
        },
        "service_backend_bindings": [],
        "application_integration_governance": {
            "approval_rules": [],
            "clarification_rules": [],
            "denial_rules": [],
            "restriction_rules": [],
            "permission_rules": [],
            "safe_defaults": [],
        },
        "data_access_governance": {
            "metrics": [],
            "dimensions": [],
            "filters": [],
            "limit_rules": [],
            "use_rules": [],
            "clarification_rules": [],
        },
        "data_domain": {
            "domain_name": item["project"]["domain"],
            "source_systems": [],
            "primary_entities": [],
        },
        "domain_concept_bindings": [],
        "application_object_model": [],
        "capability_formalizations": capabilities,
        "service_topology_bindings": [
            {
                "id": service_id,
                "service_id": service_id,
                "service_name": service_name,
                "service_role": "Governed ANIP fronting service over native backend operations.",
                "source_capabilities": [capability["capability_id"] for capability in capabilities],
                "formalized_capability_ids": [capability["capability_id"] for capability in capabilities],
                "has_declared_responsibility": True,
            }
        ],
        "actor_expectations": [],
        "permission_intent_bindings": [],
        "scenario_formalizations": _developer_scenario_formalizations(scenarios, service_id),
        "composition_rules": [],
        "verification": {
            "supported_question_family_bindings": supported_question_bindings,
            "business_goal_bindings": [],
            "non_goal_guards": [],
            "success_criteria_checks": [],
            "data_access_scenario_pack": {
                "categories": ["allowed", "restricted", "clarification_required"],
                "target_count": 4,
            },
        },
        "generation": {
            "service_generation_mode": "from_service_design",
            "selected_service_ids": [service_id],
            "scalability_profile": "stateless_horizontal",
            "protocols": ["anip_http"],
            "codegen_adapter": "python_fastapi",
            "layout_strategy": "monorepo",
        },
        "naming": {
            "namespace": project_id.replace("-", "_"),
            "package_prefix": project_id.replace("-", "_"),
            "service_name_prefix": project_id.replace("-", "_"),
        },
        "rationale": "Seeded from reviewed fronting starter mappings for public read-only exploration.",
        "compiled_contract_identity": None,
        "saved_revision": {
            "revision_number": 1,
            "revision_artifact_id": f"{project_id}-developer-definition-revision-1",
            "saved_at": locked_at,
        },
        "saved_at": locked_at,
    }
    _upsert_pm_artifact(conn, project_id, f"{project_id}-developer-definition", "Developer Definition", definition)

    traceability = {
        "artifact_type": "design_traceability",
        "source_inputs": {
            "requirements_id": requirements["id"],
            "scenario_id": scenarios[0]["id"] if scenarios else None,
            "scenario_ids": [scenario["id"] for scenario in scenarios],
            "shape_id": None,
            "baseline_locked_at": locked_at,
        },
        "coverage": [],
        "developer_status": "ready_for_pm_review",
        "developer_note": "Seeded fronting starter has reviewed PM intent, scenarios, accepted capability mappings, and a saved developer definition.",
        "developer_marked_at": locked_at,
        "high_risk_confirmations": {
            "artifact_type": "high_risk_confirmations",
            "generated_at": locked_at,
            "summary": {
                "total": 2,
                "unresolved": 0,
                "confirmed": 2,
                "deferred": 0,
                "blockers": 0,
                "warnings": 0,
            },
            "items": [],
            "reviews": {
                "capability-identity:canonical-ids": {
                    "id": "capability-identity:canonical-ids",
                    "status": "confirmed",
                    "note": "Seeded fronting starter uses reviewed capability ids from the published starter contract.",
                    "reviewed_at": locked_at,
                },
                "capability-identity:service-ownership": {
                    "id": "capability-identity:service-ownership",
                    "status": "confirmed",
                    "note": "All seeded capabilities belong to the single governed fronting service boundary.",
                    "reviewed_at": locked_at,
                },
            },
        },
        "agent_consumption_readiness": {
            "finding_reviews": {},
        },
    }
    _upsert_pm_artifact(conn, project_id, f"{project_id}-traceability", "Traceability Record", traceability)


def _ensure_workspace(conn: Any, item: dict[str, Any]) -> None:
    workspace = item.get("workspace")
    if not workspace:
        return
    try:
        existing = repository.get_workspace(conn, workspace["id"])
        updates: dict[str, Any] = {}
        for key in ("name", "summary"):
            if workspace.get(key) and existing.get(key) != workspace[key]:
                updates[key] = workspace[key]
        if updates:
            repository.update_workspace(conn, workspace["id"], **updates)
    except repository.NotFoundError:
        repository.create_workspace(
            conn,
            workspace_id=workspace["id"],
            name=workspace["name"],
            summary=workspace.get("summary", ""),
        )


def _ensure_project_metadata(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    project = item["project"]
    fields: dict[str, Any] = {}
    for key in ("name", "summary", "domain", "labels", "project_type", "integration_profile"):
        if key in project:
            fields[key] = project[key]
    if fields:
        repository.update_project(conn, project_id, **fields)


def _seed_source_documents(item: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = item.get("requirements") or {}
    source_documents = requirements.get("data", {}).get("source_documents") or []
    documents: list[dict[str, Any]] = []

    for source in source_documents:
        source_path = source.get("path")
        artifact_id = source.get("artifact_id")
        if not source_path or not artifact_id:
            continue

        path = _REPO_ROOT / source_path
        documents.append(
            {
                "id": artifact_id,
                "title": source.get("title") or artifact_id,
                "kind": source.get("kind", "reference"),
                "filename": path.name,
                "media_type": source.get("media_type", "text/markdown"),
                "source_path": source_path,
                "content": path.read_text(encoding="utf-8"),
            }
        )

    return documents


def _iter_seed_documents(item: dict[str, Any]) -> list[dict[str, Any]]:
    documents = list(item.get("documents", []))
    existing_ids = {document.get("id") for document in documents}
    for document in _seed_source_documents(item):
        if document["id"] not in existing_ids:
            documents.append(document)
            existing_ids.add(document["id"])
    return documents


def _ensure_documents(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    for document in _iter_seed_documents(item):
        try:
            existing = repository.get_project_document(conn, project_id, document["id"])
            if _replace_seed_artifact_data(item):
                content = document["content"].encode("utf-8")
                digest = hashlib.sha256(content).hexdigest()
                updates = {
                    "title": document["title"],
                    "kind": document.get("kind", "reference"),
                    "filename": document.get("filename", f"{document['id']}.md"),
                    "media_type": document.get("media_type", "text/markdown"),
                    "source_path": document.get("source_path", ""),
                    "content": content,
                    "content_hash": digest,
                }
                if any(existing.get(key) != value for key, value in updates.items()):
                    conn.execute(
                        "UPDATE project_documents "
                        "SET title = %s, kind = %s, filename = %s, media_type = %s, source_path = %s, content = %s, content_hash = %s, updated_at = now() "
                        "WHERE project_id = %s AND id = %s",
                        (
                            updates["title"],
                            updates["kind"],
                            updates["filename"],
                            updates["media_type"],
                            updates["source_path"],
                            updates["content"],
                            updates["content_hash"],
                            project_id,
                            document["id"],
                        ),
                    )
                    conn.commit()
        except repository.NotFoundError:
            content = document["content"].encode("utf-8")
            repository.create_project_document(
                conn,
                project_id=project_id,
                document_id=document["id"],
                title=document["title"],
                kind=document.get("kind", "reference"),
                filename=document.get("filename", f"{document['id']}.md"),
                media_type=document.get("media_type", "text/markdown"),
                source_path=document.get("source_path", ""),
                content=content,
            )


def _ensure_workspace_connections(conn: Any, item: dict[str, Any]) -> None:
    workspace = item.get("workspace")
    if not workspace:
        return
    for connection in item.get("workspace_connections", []):
        try:
            existing = repository.get_workspace_connection(conn, workspace["id"], connection["id"])
            updates = {
                key: value
                for key, value in connection.items()
                if key != "id" and value != existing.get(key)
            }
            if updates:
                repository.update_workspace_connection(conn, workspace["id"], connection["id"], **updates)
        except repository.NotFoundError:
            repository.create_workspace_connection(
                conn,
                workspace_id=workspace["id"],
                connection_id=connection["id"],
                display_name=connection["display_name"],
                backend_kind=connection["backend_kind"],
                system_kind=connection.get("system_kind", ""),
                endpoint_ref=connection.get("endpoint_ref", ""),
                auth_mode=connection["auth_mode"],
                identity_provider_ref=connection.get("identity_provider_ref", ""),
                secret_ref=connection.get("secret_ref", ""),
                allowed_project_refs=connection.get("allowed_project_refs", []),
                metadata=connection.get("metadata", {}),
            )


def _ensure_integration_discovery(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    for record in item.get("integration_discovery_records", []):
        try:
            existing = repository.get_integration_discovery_record(conn, project_id, record["id"])
            updates = {
                key: value
                for key, value in record.items()
                if key != "id" and value != existing.get(key)
            }
            if updates:
                repository.update_integration_discovery_record(conn, project_id, record["id"], **updates)
        except repository.NotFoundError:
            repository.create_integration_discovery_record(
                conn,
                project_id=project_id,
                record_id=record["id"],
                connection_id=record.get("connection_id"),
                operation_id=record["operation_id"],
                backend_kind=record["backend_kind"],
                method=record.get("method", ""),
                path_template=record.get("path_template", ""),
                side_effect_level=record.get("side_effect_level", "read"),
                input_schema_summary=record.get("input_schema_summary", {}),
                risk_notes=record.get("risk_notes", []),
                data=record.get("data", {}),
            )


def _ensure_seed_artifacts(conn: Any, project_id: str, item: dict[str, Any]) -> None:
    _ensure_project_metadata(conn, project_id, item)
    _ensure_workspace_connections(conn, item)
    _ensure_documents(conn, project_id, item)
    _ensure_integration_discovery(conn, project_id, item)
    _ensure_requirements(conn, project_id, item)
    _ensure_scenario(conn, project_id, item)
    _ensure_proposal(conn, project_id, item)
    _ensure_shape(conn, project_id, item)
    _ensure_evaluation(conn, project_id, item)
    _ensure_service_metadata(conn, project_id, item)
    _ensure_pm_artifacts(conn, project_id, item)
    _ensure_fronting_developer_seed(conn, project_id, item)


def _remove_empty_default_workspace_for_public_showcase(conn: Any) -> None:
    conn.execute(
        "DELETE FROM workspaces "
        "WHERE id = %s "
        "AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.workspace_id = workspaces.id)",
        ("default",),
    )
    conn.commit()


def _seed_manifest_path() -> Path | None:
    configured = os.getenv("STUDIO_SEED_MANIFEST_PATH", "").strip()
    if configured:
        return Path(configured)
    data_dir = os.getenv("ANIP_STUDIO_DESKTOP_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir) / "public-showcase-seed-manifest.json"
    return None


def _showcase_snapshot_manifest() -> dict[str, Any]:
    snapshot_dir = project_snapshots._DEFAULT_SNAPSHOT_DIR
    snapshots = []
    if snapshot_dir.exists():
        for path in sorted(snapshot_dir.glob("*.studio-project-snapshot.json")):
            stat = path.stat()
            snapshots.append(
                {
                    "name": path.name,
                    "size": stat.st_size,
                }
            )
    return {
        "profile": "public_showcase",
        "snapshots": snapshots,
    }


def _read_seed_manifest(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_seed_manifest(path: Path | None, manifest: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _seed_public_showcase_snapshots(conn: Any) -> dict[str, Any]:
    manifest = _showcase_snapshot_manifest()
    manifest_path = _seed_manifest_path()
    if _read_seed_manifest(manifest_path) == manifest:
        return {
            "status": "skipped_unchanged",
            "snapshot_dir": str(project_snapshots._DEFAULT_SNAPSHOT_DIR),
            "imported": 0,
            "skipped": 0,
            "snapshots": [],
        }

    result = import_showcase_snapshots_from_disk(
        conn,
        replace_existing=True,
        latest_only=True,
        workspace_override=PUBLIC_SHOWCASE_WORKSPACE,
    )
    _write_seed_manifest(manifest_path, manifest)
    return {"status": "imported", **result}


def seed_from_examples(conn: Any) -> dict:
    """Create curated seed projects for local demos.

    Existing projects are matched by ID and skipped, making the seed
    operation idempotent.
    """

    created = 0
    skipped = 0

    profile = _seed_profile()

    for item in SEED_PROJECTS:
        if not _seed_item_enabled(item, profile):
            continue
        _ensure_workspace(conn, item)
        project = item["project"]
        project_id = project["id"]
        try:
            repository.get_project(conn, project_id)
            _ensure_seed_artifacts(conn, project_id, item)
            skipped += 1
            continue
        except repository.NotFoundError:
            pass

        repository.create_project(
            conn,
            project_id=project_id,
            name=project["name"],
            summary=project["summary"],
            domain=project["domain"],
            labels=project.get("labels"),
            workspace_id=project.get("workspace_id") or item.get("workspace", {}).get("id"),
            project_type=project.get("project_type", "standard"),
            integration_profile=project.get("integration_profile"),
        )
        _ensure_seed_artifacts(conn, project_id, item)

        created += 1

    snapshot_result: dict[str, Any] | None = None
    if profile == "public_showcase":
        snapshot_result = _seed_public_showcase_snapshots(conn)
    if profile in {"all", "*"}:
        snapshot_result = import_showcase_snapshots_from_disk(conn, replace_existing=True, latest_only=True)
    if profile in {"showcase_snapshots", "snapshot_showcase", "snapshots"}:
        snapshot_result = import_showcase_snapshots_from_disk(conn, replace_existing=True, latest_only=True)
    if profile in {"public_showcase", "showcase_snapshots", "snapshot_showcase", "snapshots"}:
        _remove_empty_default_workspace_for_public_showcase(conn)

    result = {"created_projects": created, "skipped": skipped}
    if snapshot_result is not None:
        result["snapshot_import"] = snapshot_result
    return result
