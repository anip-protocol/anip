"""Business-to-developer bridge helpers for Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .consumer_mode import consumer_mode_from_labels


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "project"


def _titleize(value: str) -> str:
    cleaned = value.replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split()) or value


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()]


def _get_requirements_root(requirements: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(requirements, dict):
        return {}
    data = requirements.get("data")
    if isinstance(data, dict) and isinstance(data.get("requirements"), dict):
        return data["requirements"]
    if isinstance(data, dict):
        return data
    return requirements


def _get_scenario_root(scenario: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(scenario, dict):
        return {}
    data = scenario.get("data")
    if isinstance(data, dict) and isinstance(data.get("scenario"), dict):
        return data["scenario"]
    if isinstance(data, dict):
        return data
    return scenario


def _get_shape_root(shape: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(shape, dict):
        return {}
    data = shape.get("data")
    if isinstance(data, dict) and isinstance(data.get("shape"), dict):
        return data["shape"]
    if isinstance(data, dict):
        return data
    return shape


def _get_evaluation_root(evaluation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(evaluation, dict):
        return {}
    data = evaluation.get("data")
    if isinstance(data, dict) and isinstance(data.get("evaluation"), dict):
        return data["evaluation"]
    if isinstance(data, dict):
        return data
    return evaluation


def _get_runtime_observations(evaluation_root: dict[str, Any]) -> dict[str, Any]:
    observations = evaluation_root.get("runtime_observations")
    if isinstance(observations, dict):
        return observations
    history = evaluation_root.get("runtime_observation_history")
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                return item
    return {}


def _get_metadata_comparison(context: dict[str, Any]) -> dict[str, Any]:
    comparison = context.get("metadata_comparison")
    return comparison if isinstance(comparison, dict) else {}


def _summarize_metadata_mismatch(
    missing_capabilities: list[str],
    extra_capabilities: list[str],
) -> str | None:
    details: list[str] = []
    if missing_capabilities:
        details.append(f"missing intended capabilities: {', '.join(missing_capabilities)}")
    if extra_capabilities:
        details.append(f"extra observed capabilities: {', '.join(extra_capabilities)}")
    return "; ".join(details) if details else None


class BusinessPacketSource(BaseModel):
    studio_area: Literal["product_design"] = "product_design"
    project_id: str
    project_name: str
    requirements_id: str | None = None
    scenario_id: str | None = None
    shape_id: str | None = None
    evaluation_id: str | None = None


class BusinessPacketIntent(BaseModel):
    problem_statement: str
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    intended_consumers: list[str] = Field(default_factory=list)


class BusinessPacketConstraints(BaseModel):
    business: list[str] = Field(default_factory=list)
    operational: list[str] = Field(default_factory=list)
    risk: list[str] = Field(default_factory=list)
    backend_preferences: list[str] = Field(default_factory=list)


class BusinessPacketScenario(BaseModel):
    id: str
    title: str
    description: str
    expected_outcome: str | None = None


class BusinessPacketCurrentPosture(BaseModel):
    recommended_shape: str | None = None
    working_well: list[str] = Field(default_factory=list)
    needs_change: list[str] = Field(default_factory=list)


class BusinessPacketReferences(BaseModel):
    requirements_snapshot: dict[str, Any] = Field(default_factory=dict)
    scenario_snapshot: dict[str, Any] = Field(default_factory=dict)
    shape_snapshot: dict[str, Any] = Field(default_factory=dict)
    evaluation_snapshot: dict[str, Any] = Field(default_factory=dict)


class BusinessPacketPayload(BaseModel):
    intent: BusinessPacketIntent
    constraints: BusinessPacketConstraints
    scenarios: list[BusinessPacketScenario] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    current_posture: BusinessPacketCurrentPosture
    references: BusinessPacketReferences


class BusinessPacket(BaseModel):
    packet_kind: Literal["business_packet"] = "business_packet"
    version: Literal[1] = 1
    profile: str = "generic_service_design"
    source: BusinessPacketSource
    generated_at: str
    payload: BusinessPacketPayload


class DerivationReport(BaseModel):
    mapped_fields: list[str] = Field(default_factory=list)
    suggested_fields: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GlueDiagnosticEvidence(BaseModel):
    capability_id: str | None = None
    reason_code: str | None = None
    agent_behavior: str | None = None
    backend_context: str | None = None
    observation_source: str | None = None
    observed_at: str | None = None
    service_metadata_artifact_id: str | None = None
    service_metadata_mismatch: str | None = None


class DriftAnalysis(BaseModel):
    scenario_id: str
    expected_outcome: str | None = None
    observed_outcome: str | None = None
    gap_category: Literal[
        "business_intent_underspecified",
        "developer_binding_incomplete",
        "service_metadata_insufficient",
        "agent_planning_misaligned",
        "clarification_loop_detected",
        "restriction_mapping_missing",
        "approval_control_missing",
        "backend_semantics_mismatch",
    ]
    likely_owner: Literal[
        "business_design",
        "developer_design",
        "service_implementation",
        "adapter",
        "consuming_agent",
        "backend",
    ]
    fix_priority: Literal["low", "medium", "high"]
    recommended_fix: str
    diagnostic_evidence: GlueDiagnosticEvidence


GlueAnalysis = DriftAnalysis


def _scenario_design_driving_context_notes(scenario_root: dict[str, Any]) -> list[str]:
    entries = scenario_root.get("additional_context")
    if not isinstance(entries, list):
        return []

    notes: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("role") or "").strip().lower() != "design_driving":
            continue

        description = str(entry.get("description") or "").strip()
        key = str(entry.get("key") or "").strip()
        value = str(entry.get("value") or "").strip()

        if description:
            notes.append(description)
        elif key and value:
            notes.append(f"{key}: {value}")

    return notes


def generate_business_packet_from_context(context: dict[str, Any]) -> BusinessPacket:
    project = context.get("project") or {}
    requirements = context.get("requirements")
    scenario = context.get("scenario")
    shape = context.get("shape")
    evaluation = context.get("evaluation")

    requirements_root = _get_requirements_root(requirements)
    scenario_root = _get_scenario_root(scenario)
    shape_root = _get_shape_root(shape)
    evaluation_root = _get_evaluation_root(evaluation)

    consumer_mode = consumer_mode_from_labels(project.get("labels"))
    if consumer_mode == "human_app":
        intended_consumers = ["people"]
    elif consumer_mode == "agent_anip":
        intended_consumers = ["agents"]
    else:
        intended_consumers = ["people", "agents"]

    problem_statement = str(project.get("summary") or requirements_root.get("summary") or f"{project.get('name', 'Project')} needs a clearer governed design.").strip()

    scenario_description = str(
        scenario_root.get("narrative")
        or " ".join(_list_of_strings(scenario_root.get("expected_behavior")))
        or scenario_root.get("name")
        or ""
    ).strip()

    primary_scenarios: list[BusinessPacketScenario] = []
    if scenario:
        primary_scenarios.append(
            BusinessPacketScenario(
                id=str(scenario.get("id")),
                title=str(scenario.get("title") or scenario_root.get("name") or "Primary Scenario"),
                description=scenario_description or "Review the current primary scenario.",
                expected_outcome=(str(evaluation_root.get("result")).lower() if evaluation_root.get("result") else None),
            )
        )

    constraints = BusinessPacketConstraints(
        business=_list_of_strings(requirements_root.get("business_goals")) + _list_of_strings(requirements_root.get("business_constraints")),
        operational=_list_of_strings(scenario_root.get("expected_behavior"))
        + _list_of_strings(requirements_root.get("operational_constraints"))
        + _scenario_design_driving_context_notes(scenario_root),
        risk=_list_of_strings(evaluation_root.get("watchouts")) + _list_of_strings(evaluation_root.get("what_would_improve")),
        backend_preferences=[],
    )

    if requirements_root.get("shape_preference"):
        constraints.backend_preferences.append(str(requirements_root.get("shape_preference")))
    if any("semantic" in item.lower() for item in constraints.business + constraints.operational + constraints.risk):
        constraints.backend_preferences.append("semantic layer if available")

    packet = BusinessPacket(
        source=BusinessPacketSource(
            project_id=str(project.get("id")),
            project_name=str(project.get("name") or "Studio Project"),
            requirements_id=str(requirements.get("id")) if isinstance(requirements, dict) and requirements.get("id") else None,
            scenario_id=str(scenario.get("id")) if isinstance(scenario, dict) and scenario.get("id") else None,
            shape_id=str(shape.get("id")) if isinstance(shape, dict) and shape.get("id") else None,
            evaluation_id=str(evaluation.get("id")) if isinstance(evaluation, dict) and evaluation.get("id") else None,
        ),
        generated_at=_now_iso(),
        payload=BusinessPacketPayload(
            intent=BusinessPacketIntent(
                problem_statement=problem_statement,
                goals=_list_of_strings(requirements_root.get("goals")) or _list_of_strings(requirements_root.get("requirements_focus")),
                non_goals=_list_of_strings(requirements_root.get("non_goals")),
                intended_consumers=intended_consumers,
            ),
            constraints=constraints,
            scenarios=primary_scenarios,
            success_criteria=_list_of_strings(scenario_root.get("expected_behavior")) or _list_of_strings(evaluation_root.get("handled_by_anip")),
            current_posture=BusinessPacketCurrentPosture(
                recommended_shape=str(shape_root.get("type") or requirements_root.get("shape_preference") or "") or None,
                working_well=_list_of_strings(evaluation_root.get("handled_by_anip")),
                needs_change=_list_of_strings(evaluation_root.get("what_would_improve")) or _list_of_strings(evaluation_root.get("glue_you_will_still_write")),
            ),
            references=BusinessPacketReferences(
                requirements_snapshot=requirements_root,
                scenario_snapshot=scenario_root,
                shape_snapshot=shape_root,
                evaluation_snapshot=evaluation_root,
            ),
        ),
    )
    return packet


def _joined_lower(values: list[str]) -> str:
    return " ".join(item.lower() for item in values if item).strip()


def _infer_expected_outcome(packet: BusinessPacket) -> str | None:
    scenario = packet.payload.scenarios[0] if packet.payload.scenarios else None
    clues = _joined_lower(
        packet.payload.constraints.operational
        + packet.payload.success_criteria
        + ([scenario.description] if scenario else [])
    )
    if any(term in clues for term in ("approval", "approve", "before execution", "before mutation")):
        return "approval_required"
    if any(term in clues for term in ("clarify", "clarification", "ask instead of guessing", "ambiguous")):
        return "clarification_required"
    if any(term in clues for term in ("restrict", "narrow", "safe reduced", "aggregate instead")):
        return "restricted"
    if any(term in clues for term in ("deny", "refuse", "out of scope", "forbidden")):
        return "denied"
    if scenario and scenario.expected_outcome:
        return scenario.expected_outcome
    return "available"


def _infer_observed_outcome(evaluation_root: dict[str, Any], expected_outcome: str | None) -> str | None:
    runtime_observations = _get_runtime_observations(evaluation_root)
    runtime_outcome = runtime_observations.get("observed_outcome")
    if isinstance(runtime_outcome, str) and runtime_outcome.strip():
        return runtime_outcome.strip()

    result = str(evaluation_root.get("result") or "").upper()
    glue = _joined_lower(_list_of_strings(evaluation_root.get("glue_you_will_still_write")))
    improve = _joined_lower(_list_of_strings(evaluation_root.get("what_would_improve")))
    why = _joined_lower(_list_of_strings(evaluation_root.get("why")))
    combined = " ".join(part for part in (glue, improve, why) if part).strip()
    if result == "HANDLED":
        return expected_outcome or "available"
    if any(term in combined for term in ("approval", "approver", "approve", "routing")):
        return "approval_required"
    if any(term in combined for term in ("clarify", "clarification", "ambiguous", "missing input")):
        return "clarification_required"
    if any(term in combined for term in ("restrict", "narrow", "aggregate", "reduced scope", "limit results")):
        return "restricted"
    if any(term in combined for term in ("deny", "denied", "forbidden", "unsupported")):
        return "denied"
    if result == "PARTIAL":
        return expected_outcome or "restricted"
    if result == "REQUIRES_GLUE":
        return "denied" if expected_outcome == "denied" else expected_outcome or "denied"
    return expected_outcome


def generate_drift_analysis_from_context(context: dict[str, Any]) -> DriftAnalysis:
    packet = generate_business_packet_from_context(context)
    evaluation_root = _get_evaluation_root(context.get("evaluation"))
    runtime_observations = _get_runtime_observations(evaluation_root)
    metadata_comparison = _get_metadata_comparison(context)
    expected_outcome = _infer_expected_outcome(packet)
    observed_outcome = _infer_observed_outcome(evaluation_root, expected_outcome)

    glue = _list_of_strings(evaluation_root.get("glue_you_will_still_write"))
    improve = _list_of_strings(evaluation_root.get("what_would_improve"))
    why = _list_of_strings(evaluation_root.get("why"))
    combined = _joined_lower(glue + improve + why)

    gap_category: DriftAnalysis["gap_category"] = "developer_binding_incomplete"
    likely_owner: DriftAnalysis["likely_owner"] = "developer_design"
    fix_priority: DriftAnalysis["fix_priority"] = "medium"
    recommended_fix = "Tighten the developer binding so the implemented behavior matches the intended governed outcome."
    reason_code = "behavior_drift_detected"
    agent_behavior = None
    capability_id = None
    backend_context = "shape_first_service" if packet.payload.current_posture.recommended_shape else "unspecified"
    observation_source = None
    observed_at = None

    runtime_reason_code = str(runtime_observations.get("reason_code") or "").strip()
    runtime_capability = str(runtime_observations.get("invoked_capability") or "").strip()
    runtime_agent_behavior = str(runtime_observations.get("agent_behavior") or "").strip()
    runtime_backend_context = str(runtime_observations.get("backend_context") or "").strip()
    runtime_source = str(runtime_observations.get("source") or "").strip()
    runtime_observed_at = str(runtime_observations.get("observed_at") or "").strip()
    unresolved_inputs = _list_of_strings(runtime_observations.get("unresolved_inputs"))
    retry_without_progress = bool(runtime_observations.get("retry_without_progress"))
    service_metadata_artifact_id = str(context.get("service_metadata_artifact_id") or "").strip() or None
    observed_metadata = metadata_comparison.get("observed") if isinstance(metadata_comparison.get("observed"), dict) else {}
    metadata_missing_capabilities = _list_of_strings(metadata_comparison.get("missing_capabilities"))
    metadata_extra_capabilities = _list_of_strings(metadata_comparison.get("extra_capabilities"))
    conformance_checks = metadata_comparison.get("conformance_checks")
    if not isinstance(conformance_checks, list):
        conformance_checks = []
    failed_conformance_checks = [
        item for item in conformance_checks
        if isinstance(item, dict) and str(item.get("status") or "").strip() == "non_conformant"
    ]
    incomplete_conformance_checks = [
        item for item in conformance_checks
        if isinstance(item, dict) and str(item.get("status") or "").strip() == "insufficient_metadata"
    ]
    metadata_mismatch = _summarize_metadata_mismatch(
        metadata_missing_capabilities,
        metadata_extra_capabilities,
    )

    if runtime_capability:
        capability_id = runtime_capability
    if runtime_agent_behavior:
        agent_behavior = runtime_agent_behavior
    if runtime_backend_context:
        backend_context = runtime_backend_context
    if runtime_source:
        observation_source = runtime_source
    if runtime_observed_at:
        observed_at = runtime_observed_at
    if not observation_source and isinstance(observed_metadata.get("source"), str):
        observation_source = str(observed_metadata.get("source")).strip() or None
    if not observed_at and isinstance(observed_metadata.get("observed_at"), str):
        observed_at = str(observed_metadata.get("observed_at")).strip() or None

    runtime_reason_lower = runtime_reason_code.lower()

    if runtime_reason_lower:
        reason_code = runtime_reason_code
        if "approval" in runtime_reason_lower:
            gap_category = "approval_control_missing"
            likely_owner = "developer_design"
            fix_priority = "high"
            recommended_fix = "Make approval routing and approval-bound execution explicit so the write path stops cleanly before mutation."
        elif unresolved_inputs and (retry_without_progress or "clarification_loop" in runtime_reason_lower):
            gap_category = "clarification_loop_detected"
            likely_owner = "consuming_agent"
            fix_priority = "high"
            recommended_fix = "Stop retrying until the unresolved inputs are collected or the service clarifies the next required fields more explicitly."
        elif unresolved_inputs or "clarification" in runtime_reason_lower or "missing_input" in runtime_reason_lower:
            gap_category = "service_metadata_insufficient"
            likely_owner = "service_implementation"
            fix_priority = "high"
            recommended_fix = "Expose unresolved inputs and clarification targets explicitly in the service metadata so the next retry can be resolved safely."
        elif "restriction" in runtime_reason_lower or "narrow" in runtime_reason_lower:
            gap_category = "restriction_mapping_missing"
            likely_owner = "developer_design"
            fix_priority = "medium"
            recommended_fix = "Encode the restricted path explicitly so broad requests narrow safely instead of failing at runtime."
        elif "planning" in runtime_reason_lower or "capability" in runtime_reason_lower:
            gap_category = "agent_planning_misaligned"
            likely_owner = "consuming_agent"
            fix_priority = "medium"
            recommended_fix = "Guide the consuming agent toward the right capability and next safe step before retrying."
        elif "backend" in runtime_reason_lower or "semantic" in runtime_reason_lower or "adapter" in runtime_reason_lower:
            gap_category = "backend_semantics_mismatch"
            likely_owner = "backend"
            fix_priority = "medium"
            recommended_fix = "Review backend semantics and adapter mappings so runtime behavior matches the intended governed capability."

    elif failed_conformance_checks:
        gap_category = "service_metadata_insufficient"
        likely_owner = "service_implementation"
        fix_priority = "high"
        first_failed = failed_conformance_checks[0]
        failed_label = str(first_failed.get("label") or first_failed.get("id") or "ANIP conformance checks").strip()
        recommended_fix = (
            f"Bring the observed ANIP metadata into conformance for {failed_label.lower()} before treating this "
            "implementation as aligned."
        )
        reason_code = "anip_conformance_check_failed"
        if metadata_mismatch:
            backend_context = metadata_mismatch
    elif incomplete_conformance_checks:
        gap_category = "service_metadata_insufficient"
        likely_owner = "service_implementation"
        fix_priority = "medium"
        first_incomplete = incomplete_conformance_checks[0]
        incomplete_label = str(first_incomplete.get("label") or first_incomplete.get("id") or "ANIP conformance checks").strip()
        recommended_fix = (
            f"Expose fuller ANIP manifest and discovery metadata for {incomplete_label.lower()} so Studio can validate "
            "conformance directly."
        )
        reason_code = "anip_conformance_metadata_incomplete"
        if metadata_mismatch:
            backend_context = metadata_mismatch
    elif metadata_missing_capabilities:
        gap_category = "service_metadata_insufficient"
        likely_owner = "service_implementation"
        fix_priority = "high"
        recommended_fix = (
            "Expose the missing intended capabilities in the observed service metadata and implementation so validation "
            "reflects the actual governed capability surface."
        )
        reason_code = "service_metadata_missing_capability"
        capability_id = capability_id or metadata_missing_capabilities[0]
        if metadata_mismatch:
            backend_context = metadata_mismatch
    elif metadata_extra_capabilities:
        gap_category = "developer_binding_incomplete"
        likely_owner = "developer_design"
        fix_priority = "medium"
        recommended_fix = (
            "Align the intended capability design with the broader observed service surface or narrow the implementation "
            "boundary so the designed capability matches the exposed service surface."
        )
        reason_code = "service_metadata_extra_capability_surface"
        if metadata_mismatch:
            backend_context = metadata_mismatch
    elif any(term in combined for term in ("approval", "approver", "approve", "routing")):
        gap_category = "approval_control_missing"
        likely_owner = "developer_design"
        fix_priority = "high"
        recommended_fix = "Make approval routing and binding explicit in the developer packet and execution path."
        reason_code = "approval_control_missing"
    elif any(term in combined for term in ("clarification loop", "kept asking", "repeated clarification", "without progress")):
        gap_category = "clarification_loop_detected"
        likely_owner = "consuming_agent"
        fix_priority = "high"
        recommended_fix = "Reduce repeated clarification by exposing the missing fields more explicitly and requiring the consuming agent to resolve them before retry."
        reason_code = "clarification_loop_detected"
        agent_behavior = "retried without resolving clarification"
    elif any(term in combined for term in ("ambiguous", "unclear", "clarify", "missing input")):
        gap_category = "service_metadata_insufficient"
        likely_owner = "developer_design"
        fix_priority = "medium"
        recommended_fix = "Expose required inputs and clarification targets more explicitly so the agent can resolve ambiguity safely."
        reason_code = "clarification_contract_missing"
    elif any(term in combined for term in ("restrict", "narrow", "aggregate", "reduced scope")):
        gap_category = "restriction_mapping_missing"
        likely_owner = "developer_design"
        fix_priority = "medium"
        recommended_fix = "Add an explicit restricted path so broad requests narrow safely instead of drifting or overexposing data."
        reason_code = "restriction_mapping_missing"
    elif any(term in combined for term in ("backend", "semantic", "adapter", "query", "cube")):
        gap_category = "backend_semantics_mismatch"
        likely_owner = "backend"
        fix_priority = "medium"
        recommended_fix = "Review backend semantics and adapter mapping so the implemented surface still reflects the intended business behavior."
        reason_code = "backend_semantics_mismatch"
    elif expected_outcome and observed_outcome and expected_outcome != observed_outcome:
        gap_category = "service_metadata_insufficient"
        likely_owner = "service_implementation"
        fix_priority = "medium"
        recommended_fix = "Bring the runtime service behavior back into line with the expected outcome and expose clearer metadata for the next safe step."
        reason_code = "expected_observed_mismatch"

    scenario_id = packet.payload.scenarios[0].id if packet.payload.scenarios else (packet.source.scenario_id or "unknown_scenario")

    return DriftAnalysis(
        scenario_id=scenario_id,
        expected_outcome=expected_outcome,
        observed_outcome=observed_outcome,
        gap_category=gap_category,
        likely_owner=likely_owner,
        fix_priority=fix_priority,
        recommended_fix=recommended_fix,
        diagnostic_evidence=GlueDiagnosticEvidence(
            capability_id=capability_id,
            reason_code=reason_code,
            agent_behavior=agent_behavior,
            backend_context=backend_context,
            observation_source=observation_source,
            observed_at=observed_at,
            service_metadata_artifact_id=service_metadata_artifact_id,
            service_metadata_mismatch=metadata_mismatch,
        ),
    )


def generate_glue_analysis_from_context(context: dict[str, Any]) -> GlueAnalysis:
    return generate_drift_analysis_from_context(context)

