"""Shareable Studio output builders for PM and engineering collaboration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .consumer_mode import consumer_mode_from_labels, consumer_mode_label


def build_business_brief(context: dict[str, Any]) -> str:
    project = context.get("project") or {}
    source_intent = context.get("source_intent") or ""
    requirements = context.get("requirements") or {}
    scenario = context.get("scenario") or {}
    shape = context.get("shape") or {}
    evaluation = context.get("evaluation") or {}
    requirement_data = unwrap(requirements.get("data"), "requirements")
    scenario_data = unwrap(scenario.get("data"), "scenario")
    shape_data = unwrap(shape.get("data"), "shape")
    evaluation_data = (evaluation.get("data") or {}).get("evaluation", {})
    business_constraints = truthy_labels(requirement_data.get("business_constraints", {}))
    design_summary = describe_business_shape(shape_data)
    service_names = named_services(shape_data)
    working_well = string_list(evaluation_data.get("handled_by_anip"))[:4]
    changes_next = (
        string_list(evaluation_data.get("what_would_improve"))
        or string_list(evaluation_data.get("glue_you_will_still_write"))
    )[:5]
    conformance_lines = validation_conformance_lines(context)
    parts = [
        f"# Business Brief: {project.get('name') or 'Unnamed Project'}",
        "",
        f"Generated: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
        "",
        "## Traceability",
        bullet_lines(traceability_lines(context, role="Canonical Business Brief")),
        "",
        "## What We Are Building",
        project.get("summary") or "No project summary has been written yet.",
        "",
    ]
    if source_intent:
        parts.extend(["### Original Plain-Language Brief", source_intent, ""])
    parts.extend(
        [
            "## What Matters Most",
            bullet_lines(business_constraints or ["The project still needs clearer business constraints before this brief becomes persuasive."]),
            "",
            "## Current Capability Design",
            design_summary,
            *(
                [
                    "",
                    "### Named Services",
                    bullet_lines(service_names),
                ]
                if service_names
                else []
            ),
            "",
            "## Real Situation Under Review",
            scenario.get("title") or "No active real situation selected yet.",
            "",
        ]
    )
    if scenario_data.get("narrative"):
        parts.extend([scenario_data["narrative"], ""])
    parts.extend(
        [
            "## Validation Decision Summary",
            f"Result: {evaluation.get('result')}." if evaluation else "No evaluation has been run yet.",
            "",
            "### Working Well",
            bullet_lines(working_well or ["No strong support areas have been recorded yet."]),
            "",
            "### ANIP Conformance Snapshot",
            bullet_lines(conformance_lines),
            "",
            "### Next Decisions",
            bullet_lines(changes_next or ["No concrete next changes are recorded yet."]),
        ]
    )
    return "\n".join(parts)


def build_pm_spec(context: dict[str, Any]) -> str:
    project = context.get("project") or {}
    source_requirements = context.get("source_requirements") or {}
    requirements = context.get("requirements") or {}
    scenarios = context.get("scenarios") or []
    scenario = context.get("scenario") or {}
    shape = context.get("shape") or {}
    evaluation = context.get("evaluation") or {}
    source_intent = context.get("source_intent") or ""

    source_requirement_data = source_requirements.get("data") or {}
    source_document = source_requirement_data.get("source_document") or {}
    business_spec = source_requirement_data.get("business_spec") or {}
    requirement_data = unwrap(requirements.get("data"), "requirements")
    scenario_data = unwrap(scenario.get("data"), "scenario")
    evaluation_data = (evaluation.get("data") or {}).get("evaluation", {})
    behavior_translation = requirement_data.get("behavior_translation") or {}
    scenario_records = scenarios or ([scenario] if scenario else [])

    goal_lines = string_list(business_spec.get("business_goal")) or [
        labelize(item) for item in string_list(behavior_translation.get("goal_translation"))
    ]
    behavior_family_lines = []
    for item in array(behavior_translation.get("behavior_families")):
        label = labelize(str(item.get("class") or "behavior_class"))
        expectation = str(item.get("studio_expectation") or "").strip()
        behavior_family_lines.append(f"{label} (Studio key: {expectation})" if expectation else label)

    representative_requests = string_list(behavior_translation.get("representative_requests")) or [
        str(item.get("title") or "").strip() for item in scenario_records if str(item.get("title") or "").strip()
    ]
    must_not = [sentenceize(item) for item in string_list(business_spec.get("non_goals"))]
    if (
        requirement_data.get("business_constraints", {}).get("approval_required")
        or requirement_data.get("business_constraints", {}).get("approval_expected_for_high_risk")
        or requirement_data.get("business_constraints", {}).get("followup_execution_must_stop_for_approval")
    ) and "No downstream mutations without approval" not in must_not:
        must_not.append("No downstream mutations without approval")
    validation_lines = [
        "this PM spec is representative, not exhaustive",
        "this business spec is visible as a source artifact",
        "Studio translates this spec into bounded requirements and scenarios",
        "Studio developer design derives an implementation shape from those requirements",
        "the running service code is generated from that design path, then completed and run",
        "Studio validates the running service against observed ANIP metadata and runtime behavior",
        "more than one agent runtime can consume the same governed service correctly",
    ]
    translation_lines = [
        f"Source artifact: {source_requirements.get('title') or 'None linked'}"
        + (f" ({source_document['path']})" if source_document.get("path") else ""),
        f"Translated requirements: {requirements.get('title') or 'None selected'}",
        f"Scenario pack size: {len(scenario_records)}",
        f"Active scenario: {scenario.get('title') or 'None selected'}",
        f"Service design: {shape.get('title') or 'None selected'}",
        f"Evaluation status: {describe_evaluation(evaluation)}",
    ]

    return "\n".join(
        [
            f"# PM Spec: {project.get('name') or source_requirements.get('title') or 'Unnamed Project'}",
            "",
            f"Generated: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
            "",
            "## Traceability",
            bullet_lines(traceability_lines(context, role="Canonical PM Spec")),
            "",
            "## Purpose",
            business_spec.get("summary")
            or "Canonical PM-readable business specification derived from the linked source business document and current Studio translation.",
            "",
            f"Source document: {source_document.get('path')}" if source_document.get("path") else "",
            "This PM spec captures behavior classes and representative scenario requests, not an exhaustive inventory of every possible user utterance.",
            "",
            "## Business Source",
            "",
            "### Problem",
            project.get("summary") or source_intent or "The business problem still needs to be described clearly.",
            "",
            "### Business Goal",
            bullet_lines(goal_lines or ["Define the bounded business goals for this capability."]),
            "",
            "### What The Agent Must Be Able To Do",
            bullet_lines(goal_lines or ["No bounded capability goals are captured yet."]),
            "",
            "### What It Must Not Do",
            bullet_lines(must_not or ["No explicit non-goals are recorded yet."]),
            "",
            "### Behavior Classes",
            bullet_lines(behavior_family_lines or ["No behavior families are recorded yet."]),
            "",
            "### Representative Scenario Requests",
            "These requests are representative, not exhaustive.",
            bullet_lines(representative_requests or ["No representative requests are recorded yet."]),
            "",
            "### Business Safety Posture",
            bullet_lines(pm_safety_posture_lines(requirement_data) or ["No explicit business safety posture is recorded yet."]),
            "",
            "## Validation Intent",
            bullet_lines(validation_lines),
            "",
            "## Studio Translation",
            bullet_lines(translation_lines),
            "",
            "### Active Scenario",
            scenario.get("title") or "None selected",
            "",
            "#### Business Behavior Expectations",
            bullet_lines(
                [
                    f"Narrative: {scenario_data.get('narrative')}" if scenario_data.get("narrative") else "Narrative not defined yet.",
                    *[f"Expected behavior: {item}" for item in string_list(scenario_data.get("expected_behavior"))],
                ]
            ),
            "",
            "#### ANIP / Implementation Expectations",
            bullet_lines(
                [f"Expected ANIP support: {item}" for item in string_list(scenario_data.get("expected_anip_support"))]
                or ["No explicit ANIP / implementation expectations are recorded yet."]
            ),
            "",
            "## Current Validation Readout",
            bullet_lines(
                [
                    pm_validation_status_line(context),
                    *validation_conformance_lines(context),
                    *[f"Next change: {item}" for item in string_list(evaluation_data.get("what_would_improve"))[:4]],
                ]
            ),
        ]
    )


def build_developer_spec(context: dict[str, Any]) -> str:
    project = context.get("project") or {}
    source_requirements = context.get("source_requirements") or {}
    requirements = context.get("requirements") or {}
    scenarios = context.get("scenarios") or []
    scenario = context.get("scenario") or {}
    proposal = context.get("proposal") or {}
    shape = context.get("shape") or {}
    evaluation = context.get("evaluation") or {}

    source_requirement_data = source_requirements.get("data") or {}
    source_document = source_requirement_data.get("source_document") or {}
    requirement_data = unwrap(requirements.get("data"), "requirements")
    scenario_data = unwrap(scenario.get("data"), "scenario")
    proposal_data = unwrap(proposal.get("data"), "proposal")
    shape_data = unwrap(shape.get("data"), "shape")
    evaluation_data = (evaluation.get("data") or {}).get("evaluation", {})
    scenario_records = scenarios or ([scenario] if scenario else [])

    developer_translation = proposal_data.get("developer_translation") or {}
    implementation_contract = shape_data.get("implementation_contract") or {}
    metadata_contract = shape_data.get("metadata_contract") or {}
    implementation_trace = shape_data.get("implementation_trace") or {}
    capability_contracts = array(shape_data.get("capability_contracts"))
    cross_service_contract = proposal_data.get("cross_service_contract") or shape_data.get("cross_service_contract") or {}
    service_behavior_coverage = string_list(developer_translation.get("service_behavior_coverage"))
    orchestration_contract_coverage = string_list(developer_translation.get("orchestration_contract_coverage"))
    runtime_glue_inventory = string_list(developer_translation.get("runtime_glue_inventory"))
    actor_policy_model = developer_translation.get("actor_policy_model") or {}

    translation_lines = [
        f"Source business spec: {source_requirements.get('title') or 'None linked'}"
        + (f" ({source_document['path']})" if source_document.get("path") else ""),
        f"Translated requirements: {requirements.get('title') or 'None selected'}",
        f"Active scenario: {scenario.get('title') or 'None selected'}",
        f"Proposal: {proposal.get('title') or 'None selected'}",
        f"Service design: {shape.get('title') or 'None selected'}",
        f"Evaluation status: {describe_evaluation(evaluation)}",
    ]
    requirement_signals = [
        *(
            [f"Deployment intent: {requirement_data['system']['deployment_intent']}"]
            if requirement_data.get("system", {}).get("deployment_intent")
            else []
        ),
        *[f"Business constraint: {item}" for item in developer_requirement_signals(requirement_data.get("business_constraints", {}))],
        *[f"Auth signal: {item}" for item in truthy_labels(requirement_data.get("auth", {}))],
        *[f"Permission signal: {item}" for item in developer_permission_signals(requirement_data.get("permissions", {}), requirement_data.get("business_constraints", {}))],
        *[f"Audit signal: {item}" for item in truthy_labels(requirement_data.get("audit", {}))],
    ]
    implementation_lines = [
        f"Implementation language: {implementation_contract.get('implementation_language') or 'not recorded'}",
        f"Runtime profile: {implementation_contract.get('runtime_profile') or 'not recorded'}",
        f"Transport profile: {implementation_contract.get('transport_profile') or 'not recorded'}",
        "Semantic backends: "
        + (", ".join(string_list(implementation_contract.get("semantic_backends"))) or "not recorded"),
        f"Implementation root: {implementation_contract.get('implementation_root') or 'not recorded'}",
        f"Runtime entrypoint: {implementation_contract.get('runtime_entrypoint') or 'not recorded'}",
    ]
    generated_lines = [
        f"Studio generation path: {(implementation_contract.get('generated_from') or {}).get('studio_flow') or 'not recorded'}",
        "Generated scaffolds: "
        + (", ".join(string_list((implementation_contract.get("generated_from") or {}).get("generated_artifacts"))) or "not recorded"),
        "Showcase runtime files: "
        + (", ".join(string_list((implementation_contract.get("generated_from") or {}).get("showcase_runtime_files"))) or "not recorded"),
    ]
    metadata_lines = [
        *[f"Requirement: {item}" for item in truthy_labels(metadata_contract)],
        *[f"Conformance check: {item}" for item in string_list(metadata_contract.get("conformance_checks"))],
    ]
    trace_lines = [
        f"Business source artifact: {implementation_trace.get('business_source_artifact_id') or 'not recorded'}",
        f"Requirements artifact: {implementation_trace.get('requirements_artifact_id') or 'not recorded'}",
        f"Scenario artifact: {implementation_trace.get('scenario_artifact_id') or 'not recorded'}",
        f"Proposal artifact: {implementation_trace.get('proposal_artifact_id') or 'not recorded'}",
        f"Shape artifact: {implementation_trace.get('shape_artifact_id') or 'not recorded'}",
        f"Generated code used for showcase: {yes_no(implementation_trace.get('generated_code_used_for_showcase'))}",
        f"Running service: {implementation_trace.get('running_service_id') or 'not recorded'}",
        *[f"Validation method: {item}" for item in string_list(implementation_trace.get("validation_method"))],
    ]

    return "\n".join(
        [
            f"# Developer Spec: {project.get('name') or 'Unnamed Project'}",
            "",
            f"Generated: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
            "",
            "## Traceability",
            bullet_lines(traceability_lines(context, role="Canonical Developer Spec")),
            "",
            "## Technical Purpose",
            developer_translation.get("translation_goal")
            or "Translate the bounded business behavior into an explicit service contract that can be implemented and validated.",
            "",
            "## Translation Chain",
            bullet_lines(translation_lines),
            "",
            "## Developer Enrichment",
            bullet_lines(
                [
                    *[f"Principle: {item}" for item in string_list(developer_translation.get("translation_principles"))],
                    *[f"Decision: {item}" for item in string_list(developer_translation.get("service_contract_decisions"))],
                ]
                or ["No explicit developer translation guidance is recorded yet."]
            ),
            "",
            "## Behavior Placement",
            "Studio should make behavior placement explicit. Important behavior should live in the service contract or an explicit orchestration contract. Remaining runtime glue should stay thin, mechanical, and visible.",
            "",
            "### Service-Covered Behavior",
            bullet_lines(service_behavior_coverage or ["No explicit service-covered behavior inventory is recorded yet."]),
            "",
            "### Orchestration-Covered Behavior",
            bullet_lines(orchestration_contract_coverage or ["No explicit orchestration-covered behavior inventory is recorded yet."]),
            "",
            "### Cross-Service Contract",
            format_cross_service_contract(cross_service_contract),
            "",
            "### Remaining Runtime Glue",
            bullet_lines(runtime_glue_inventory or ["No remaining runtime glue inventory is recorded yet."]),
            "",
            "## Actor, Authority, And Audit Policy",
            format_actor_policy_model(actor_policy_model),
            "",
            "## Requirements Signals",
            bullet_lines(requirement_signals or ["No structured requirement signals are recorded yet."]),
            "",
            "## Active Scenario Contract",
            bullet_lines(
                [
                    f"Narrative: {scenario_data.get('narrative')}" if scenario_data.get("narrative") else "Narrative not defined yet.",
                    *[f"Expected behavior: {item}" for item in string_list(scenario_data.get("expected_behavior"))],
                    *[f"Expected ANIP support: {item}" for item in string_list(scenario_data.get("expected_anip_support"))],
                    f"Scenario pack size: {len(scenario_records)}",
                ]
            ),
            "",
            "## Service Implementation Contract",
            bullet_lines(implementation_lines),
            "",
            "## Capability Contracts",
            format_capability_contracts(capability_contracts),
            "",
            "## Metadata And Conformance Requirements",
            bullet_lines(metadata_lines or ["No metadata contract is recorded yet."]),
            "",
            "## Generated Implementation Trace",
            bullet_lines(generated_lines + trace_lines),
            "",
            "## Current Runtime Validation",
            bullet_lines(
                [
                    developer_validation_status_line(context),
                    *validation_conformance_lines(context),
                    *[f"Runtime gap: {item}" for item in string_list(evaluation_data.get("glue_you_will_still_write"))[:4]],
                    *[f"Next change: {item}" for item in string_list(evaluation_data.get("what_would_improve"))[:4]],
                ]
            ),
        ]
    )


def build_engineering_contract(context: dict[str, Any]) -> str:
    project = context.get("project") or {}
    requirements = context.get("requirements") or {}
    scenario = context.get("scenario") or {}
    shape = context.get("shape") or {}
    evaluation = context.get("evaluation") or {}
    requirement_data = unwrap(requirements.get("data"), "requirements")
    scenario_data = unwrap(scenario.get("data"), "scenario")
    shape_data = unwrap(shape.get("data"), "shape")
    evaluation_data = (evaluation.get("data") or {}).get("evaluation", {})
    services = array(shape_data.get("services"))
    concepts = array(shape_data.get("domain_concepts"))
    coordination = array(shape_data.get("coordination"))
    derived_expectations = array(evaluation.get("derived_expectations"))
    requirement_signals = [
        *(
            [f"Deployment intent: {requirement_data['system']['deployment_intent']}"]
            if requirement_data.get("system", {}).get("deployment_intent")
            else []
        ),
        *[f"Auth: {item}" for item in truthy_labels(requirement_data.get("auth", {}))],
        *[f"Permissions: {item}" for item in truthy_labels(requirement_data.get("permissions", {}))],
        *[f"Audit: {item}" for item in truthy_labels(requirement_data.get("audit", {}))],
        *[f"Lineage: {item}" for item in truthy_labels(requirement_data.get("lineage", {}))],
        *[f"Constraint: {item}" for item in truthy_labels(requirement_data.get("business_constraints", {}))],
    ]
    service_lines = []
    for service in services:
        responsibilities = string_list(service.get("responsibilities"))
        capabilities = string_list(service.get("capabilities"))
        owns = string_list(service.get("owns_concepts"))
        service_lines.append(
            "\n".join(
                [
                    f"### {service.get('name') or service.get('id') or 'Unnamed service'}",
                    f"- Service ID: {service.get('id') or 'no-id'}",
                    "- Responsibilities:",
                    indented_bullet_lines(responsibilities or ["none listed"]),
                    "- Capabilities:",
                    indented_bullet_lines(capabilities or ["none listed"]),
                    "- Owns Concepts:",
                    indented_bullet_lines(owns or ["none listed"]),
                ]
            )
        )
    concept_lines = [
        f"- {concept.get('name') or concept.get('id') or 'Unnamed concept'}: owner={concept.get('owner') or 'shared'}, sensitivity={concept.get('sensitivity') or 'none'}"
        for concept in concepts
    ]
    coordination_lines = [
        f"- {edge.get('from') or 'unknown'} -> {edge.get('to') or 'unknown'} ({edge.get('relationship') or 'unspecified'}): {edge.get('description') or 'no description'}"
        for edge in coordination
    ]
    evaluation_lines = [
        f"Result: {evaluation.get('result')}" if evaluation else "No evaluation has been run yet.",
        *[f"Why: {item}" for item in string_list(evaluation_data.get("why"))[:4]],
        *[f"Gap: {item}" for item in string_list(evaluation_data.get("glue_you_will_still_write"))[:5]],
        *[f"Improve: {item}" for item in string_list(evaluation_data.get("what_would_improve"))[:5]],
    ]
    conformance_lines = validation_conformance_lines(context)
    return "\n".join(
        [
            f"# Engineering Contract: {project.get('name') or 'Unnamed Project'}",
            "",
            f"Generated: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
            "",
            "## Traceability",
            bullet_lines(traceability_lines(context, role="Canonical Engineering Contract")),
            "",
            "## Active Context",
            f"- Project: {project.get('name') or 'Unknown project'}",
            f"- Requirements: {requirements.get('title') or 'None selected'}",
            f"- Scenario: {scenario.get('title') or 'None selected'}",
            f"- Service Design: {shape.get('title') or 'None selected'}",
            f"- Evaluation: {describe_evaluation(evaluation)}",
            "",
            "## Requirements Signals",
            bullet_lines(requirement_signals or ["No strong structured requirement signals are available yet."]),
            "",
            "## Scenario Contract",
            bullet_lines(
                [
                    f"Narrative: {scenario_data.get('narrative')}" if scenario_data.get("narrative") else "Narrative not defined yet.",
                    *[f"Expected behavior: {item}" for item in string_list(scenario_data.get("expected_behavior"))],
                    *[f"Expected ANIP support: {item}" for item in string_list(scenario_data.get("expected_anip_support"))],
                ]
            ),
            "",
            "## Service Design",
            "\n".join(service_lines) if service_lines else "- No services defined yet.",
            "",
            "## Domain Concepts",
            "\n".join(concept_lines) if concept_lines else "- No domain concepts defined yet.",
            "",
            "## Coordination",
            "\n".join(coordination_lines) if coordination_lines else "- No coordination edges defined yet.",
            "",
            "## Derived Expectations",
            bullet_lines(
                [
                    f"{item.get('surface') or 'surface'}: {item.get('reason') or 'no reason recorded'}"
                    for item in derived_expectations
                ]
                or ["No derived expectations recorded yet."]
            ),
            "",
            "## Validation Readout",
            bullet_lines(evaluation_lines),
            "",
            "## ANIP Conformance Snapshot",
            bullet_lines(conformance_lines),
        ]
    )


def finalize_narrative_document(document: str, context: dict[str, Any], *, role: str, canonical_name: str) -> str:
    cleaned = document.strip()
    if not cleaned:
        return cleaned
    return "\n".join(
        [
            cleaned,
            "",
            "## Narrative Status",
            bullet_lines(
                [
                    f"Artifact role: {role}",
                    f"Canonical source of truth: {canonical_name}",
                    "This narrative is a human-readable interpretation of the current design packet. Use it for review and discussion; the deterministic artifact remains the canonical source of truth.",
                ]
            ),
            "",
            "## Traceability",
            bullet_lines(traceability_lines(context, role=role)),
        ]
    )


def unwrap(data: dict[str, Any] | None, key: str) -> dict[str, Any]:
    base = data or {}
    return base.get(key) or base


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        cleaned = str(item).strip()
        if cleaned:
            result.append(cleaned)
    return result


def array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def truthy_labels(record: dict[str, Any]) -> list[str]:
    result = []
    for key, value in record.items():
        if value is True:
            result.append(labelize(key))
        elif isinstance(value, str) and value.strip():
            result.append(f"{labelize(key)}: {value.strip()}")
    return result


def labelize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").replace("-", " ").split())


def bullet_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def indented_bullet_lines(items: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in items)


def describe_business_shape(shape_data: dict[str, Any]) -> str:
    services = array(shape_data.get("services"))
    concepts = array(shape_data.get("domain_concepts"))
    if not services:
        return "The service design has not been defined yet."
    kind = "multi-service" if shape_data.get("type") == "multi_service" else "single-service"
    return (
        f"The current design is a {kind} starting point with {len(services)} service"
        f"{'' if len(services) == 1 else 's'} and {len(concepts)} named domain concept"
        f"{'' if len(concepts) == 1 else 's'}."
    )


def named_services(shape_data: dict[str, Any]) -> list[str]:
    return [str(service.get("name")).strip() for service in array(shape_data.get("services")) if str(service.get("name", "")).strip()]


def validation_conformance_lines(context: dict[str, Any]) -> list[str]:
    evaluation = context.get("evaluation") or {}
    shape = context.get("shape") or {}
    scenario = context.get("scenario") or {}
    evaluation_snapshot = evaluation.get("input_snapshot") or {}
    observed = evaluation_snapshot.get("service_metadata") or {}
    shape_data = unwrap(shape.get("data"), "shape")
    scenario_data = unwrap(scenario.get("data"), "scenario")

    if not observed:
        return ["No observed ANIP service metadata was saved with the current evaluation."]

    intended_capabilities = []
    for service in array(shape_data.get("services")):
        intended_capabilities.extend(string_list(service.get("capabilities")))
    intended_capabilities.extend(string_list([scenario_data.get("context", {}).get("capability")]))
    intended_capabilities = dedupe_strings(intended_capabilities)

    observed_capabilities = [
        str(item.get("id")).strip()
        for item in array(observed.get("capabilities"))
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    ]
    observed_capabilities = dedupe_strings(observed_capabilities)

    missing_capabilities = [item for item in intended_capabilities if item not in observed_capabilities]
    extra_capabilities = [item for item in observed_capabilities if item not in intended_capabilities]

    signature_present = observed.get("signature_present")
    jwks_present = observed.get("jwks_uri_present")

    return [
        f"Observed metadata source: {observed.get('source') or 'unknown'}",
        f"Observed service: {observed.get('service_id') or observed.get('base_url') or 'unknown'}",
        f"Protocol declared: {observed.get('protocol') or 'missing'}",
        f"Manifest signature: {describe_presence(signature_present)}",
        f"JWKS URI: {describe_presence(jwks_present)}",
        "Missing intended capabilities: " + (", ".join(missing_capabilities) if missing_capabilities else "none"),
        "Broader than intended: " + (", ".join(extra_capabilities) if extra_capabilities else "none"),
    ]


def traceability_lines(context: dict[str, Any], *, role: str) -> list[str]:
    project = context.get("project") or {}
    requirements = context.get("requirements") or {}
    scenario = context.get("scenario") or {}
    shape = context.get("shape") or {}
    evaluation = context.get("evaluation") or {}
    consumer_mode = consumer_mode_from_labels(project.get("labels"))
    return [
        f"Artifact role: {role}",
        f"Project: {project.get('name') or project.get('id') or 'Unknown project'}",
        f"Primary consumer: {consumer_mode_label(consumer_mode)}",
        f"Requirements set: {requirements.get('title') or requirements.get('id') or 'None selected'}",
        f"Scenario: {scenario.get('title') or scenario.get('id') or 'None selected'}",
        f"Service design: {shape.get('title') or shape.get('id') or 'None selected'}",
        f"Evaluation: {describe_evaluation(evaluation)}",
    ]


def describe_evaluation(evaluation: dict[str, Any]) -> str:
    if not evaluation:
        return "Not run yet"
    eval_id = evaluation.get("id") or "unknown"
    result = evaluation.get("result") or (evaluation.get("data") or {}).get("evaluation", {}).get("result") or "not run yet"
    created = evaluation.get("created_at")
    if created and hasattr(created, "isoformat"):
        return f"{eval_id} ({result}, {created.isoformat()})"
    if created:
        return f"{eval_id} ({result}, {created})"
    return f"{eval_id} ({result})"


def describe_presence(value: Any) -> str:
    if value is True:
        return "present"
    if value is False:
        return "missing"
    return "not inspected"


def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def sentenceize(value: str) -> str:
    cleaned = str(value or "").replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:]


def developer_requirement_signals(record: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if record.get("pm_defines_behavior_families_not_every_utterance"):
        lines.append("PM defines behavior families and representative scenarios, not every user utterance")
    if record.get("raw_row_level_exports_are_out_of_scope"):
        lines.append("Raw row-level exports are out of scope for the Phase 1 service")
    if record.get("followup_execution_must_stop_for_approval"):
        lines.append("Follow-up execution must stop until approval exists")
    if record.get("q2_pipeline_review_must_be_reproducible_locally"):
        lines.append("Q2 pipeline review must stay reproducible locally")
    if record.get("approval_expected_for_high_risk"):
        lines.append("High-risk work requires approval review")
    if record.get("recovery_sensitive"):
        lines.append("Recovery-sensitive behavior must remain reviewable")
    posture = str(record.get("blocked_failure_posture") or "").strip()
    if posture == "human_review_for_unresolved_or_approval_gated_work":
        lines.append("Escalate to human review only for unresolved or approval-gated work")
    elif posture:
        lines.append(f"Blocked failure posture: {posture}")
    if record.get("clarification_required_for_missing_quarter"):
        lines.append("Quarter must be clarified when missing")
    if record.get("clarification_required_for_missing_ranking_basis"):
        lines.append("Ranking basis must be clarified when missing")
    export_posture = str(record.get("phase_1_export_posture") or "").strip()
    if export_posture == "deny_raw_row_level_exports":
        lines.append("Phase 1 export posture: deny raw row-level export requests")
    elif export_posture:
        lines.append(f"Phase 1 export posture: {export_posture}")
    return lines


def developer_permission_signals(permissions: dict[str, Any], constraints: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if permissions.get("preflight_discovery"):
        lines.append("Preflight discovery is required")
    if permissions.get("grantable_requirements"):
        lines.append("Grantable requirements are visible")
    if permissions.get("restricted_vs_denied"):
        if str(constraints.get("phase_1_export_posture") or "").strip() == "deny_raw_row_level_exports":
            lines.append("The permission model distinguishes restricted vs denied; Phase 1 export policy currently uses denied")
        else:
            lines.append("The permission model distinguishes restricted vs denied outcomes")
    return lines


def format_capability_contracts(items: list[Any]) -> str:
    if not items:
        return "- No capability contracts are recorded yet."
    blocks: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        blocks.append(
            "\n".join(
                [
                    f"### {item.get('id') or 'Unnamed capability'}",
                    f"- Purpose: {item.get('purpose') or 'not recorded'}",
                    f"- Side effect contract: {item.get('side_effect_detail') or item.get('side_effect_type') or 'not recorded'}",
                    f"- Minimum scope: {', '.join(string_list(item.get('minimum_scope'))) or 'not recorded'}",
                    "- Clarification required when:",
                    indented_bullet_lines(string_list(item.get("clarification_required_when")) or ["none recorded"]),
                    "- Denied when:",
                    indented_bullet_lines(string_list(item.get("denied_when")) or ["none recorded"]),
                    "- Approval required when:",
                    indented_bullet_lines(string_list(item.get("approval_required_when")) or ["none recorded"]),
                    "- Bounded evidence:",
                    indented_bullet_lines(string_list(item.get("bounded_evidence")) or ["none recorded"]),
                    "- Implementation notes:",
                    indented_bullet_lines(string_list(item.get("implementation_notes")) or ["none recorded"]),
                ]
            )
        )
    return "\n\n".join(blocks) if blocks else "- No capability contracts are recorded yet."


def format_cross_service_contract(contract: dict[str, Any]) -> str:
    if not isinstance(contract, dict) or not any(array(contract.get(key)) for key in ("handoff", "followup", "verification")):
        return "- No explicit cross-service contract is recorded yet."

    labels = {
        "handoff": "Handoff",
        "followup": "Follow-up",
        "verification": "Verification",
    }
    blocks: list[str] = []
    for key in ("handoff", "followup", "verification"):
        items = array(contract.get(key))
        if not items:
            continue
        lines = [f"#### {labels[key]}"]
        for item in items:
            if not isinstance(item, dict):
                continue
            target = item.get("target") or {}
            lines.extend(
                [
                    f"- Target service: {target.get('service') or 'not recorded'}",
                    f"- Target capability: {target.get('capability') or 'not recorded'}",
                    f"- Continuity: {item.get('continuity') or 'not recorded'}",
                    f"- Completion mode: {item.get('completion_mode') or 'not recorded'}",
                    f"- Required for task completion: {yes_no(item.get('required_for_task_completion'))}",
                ]
            )
            carry = string_list(item.get("carry_fields"))
            if carry:
                lines.extend(["- Carry fields:", indented_bullet_lines(carry)])
            rationale = str(item.get("rationale") or "").strip()
            if rationale:
                lines.append(f"- Rationale: {rationale}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) if blocks else "- No explicit cross-service contract is recorded yet."


def format_actor_policy_model(model: dict[str, Any]) -> str:
    if not isinstance(model, dict):
        return "- No explicit actor, authority, and audit policy is recorded yet."

    blocks: list[str] = []
    identity_source = str(model.get("identity_source") or "").strip()
    policy_axes = string_list(model.get("policy_axes"))
    visibility_rules = array(model.get("visibility_rules"))
    approval_rules = array(model.get("approval_rules"))
    audit_expectations = string_list(model.get("audit_expectations"))
    approval_surface = model.get("approval_surface") or {}

    overview_lines: list[str] = []
    if identity_source:
        overview_lines.append(f"- Identity source: {identity_source}")
    if policy_axes:
        overview_lines.extend(["- Policy axes:", indented_bullet_lines(policy_axes)])
    if overview_lines:
        blocks.append("\n".join(["### Actor Model", *overview_lines]))

    if visibility_rules:
        lines = ["### Visibility And Restriction Rules"]
        for rule in visibility_rules:
            if not isinstance(rule, dict):
                continue
            lines.extend(
                [
                    f"- Applies when: {rule.get('when') or 'not recorded'}",
                    f"- Governed outcome: {rule.get('outcome') or 'not recorded'}",
                ]
            )
            rationale = str(rule.get("rationale") or "").strip()
            if rationale:
                lines.append(f"- Rationale: {rationale}")
        blocks.append("\n".join(lines))

    if approval_rules:
        lines = ["### Approval Authority Rules"]
        for rule in approval_rules:
            if not isinstance(rule, dict):
                continue
            lines.extend(
                [
                    f"- Action: {rule.get('action') or 'not recorded'}",
                    f"- Requester posture: {rule.get('requester_posture') or 'not recorded'}",
                    f"- Approver requirement: {rule.get('approver_requirement') or 'not recorded'}",
                ]
            )
            notes = string_list(rule.get("notes"))
            if notes:
                lines.extend(["- Notes:", indented_bullet_lines(notes)])
        blocks.append("\n".join(lines))

    if audit_expectations:
        blocks.append("\n".join(["### Audit Review Expectations", bullet_lines(audit_expectations)]))

    if isinstance(approval_surface, dict) and (
        str(approval_surface.get("list_path") or "").strip()
        or str(approval_surface.get("approve_path_template") or "").strip()
    ):
        lines = ["### Linked Approval Review Surface"]
        list_path = str(approval_surface.get("list_path") or "").strip()
        approve_path_template = str(approval_surface.get("approve_path_template") or "").strip()
        if list_path:
            lines.append(f"- List path: {list_path}")
        if approve_path_template:
            lines.append(f"- Approve path template: {approve_path_template}")
        notes = string_list(approval_surface.get("notes"))
        if notes:
            lines.extend(["- Notes:", indented_bullet_lines(notes)])
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks) if blocks else "- No explicit actor, authority, and audit policy is recorded yet."


def pm_safety_posture_lines(requirement_data: dict[str, Any]) -> list[str]:
    constraints = requirement_data.get("business_constraints") or {}
    lines: list[str] = []
    if constraints.get("clarification_required_for_missing_quarter") or constraints.get("clarification_required_for_missing_ranking_basis"):
        lines.append("The system must not guess missing critical parameters such as quarter or ranking basis.")
    if constraints.get("phase_1_export_posture") == "deny_raw_row_level_exports" or constraints.get("raw_row_level_exports_are_out_of_scope"):
        lines.append("For Phase 1, the system must deny raw row-level exports instead of improvising a narrower interpretation.")
    if constraints.get("followup_execution_must_stop_for_approval") or constraints.get("approval_expected_for_high_risk"):
        lines.append("The system must not execute downstream mutations without approval.")
    if constraints.get("blocked_failure_posture"):
        lines.append("Unsafe, unresolved, or approval-gated work should stop cleanly and surface for human review when required.")
    return lines


def pm_validation_status_line(context: dict[str, Any]) -> str:
    evaluation = context.get("evaluation") or {}
    if not evaluation:
        return "Status: Not run yet"
    result = evaluation.get("result") or (evaluation.get("data") or {}).get("evaluation", {}).get("result") or "not run yet"
    observed = (evaluation.get("input_snapshot") or {}).get("service_metadata") or {}
    if observed:
        return f"Status: {result}"
    return f"Status: {result}, but no runtime metadata captured yet"


def developer_validation_status_line(context: dict[str, Any]) -> str:
    evaluation = context.get("evaluation") or {}
    if not evaluation:
        return "Status: Not run yet"
    result = evaluation.get("result") or (evaluation.get("data") or {}).get("evaluation", {}).get("result") or "not run yet"
    observed = (evaluation.get("input_snapshot") or {}).get("service_metadata") or {}
    evaluation_data = (evaluation.get("data") or {}).get("evaluation", {})
    conformance_status = str(evaluation_data.get("conformance_status") or "").strip().lower()
    if observed:
        if conformance_status == "partial":
            return f"Status: {result}; runtime metadata captured with open conformance gaps."
        return f"Status: {result}; runtime metadata captured and compared against the developer contract."
    return f"Status: {result}; runtime metadata has not been captured yet for this developer validation."


def yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"
