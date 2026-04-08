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
            "## Current Service Design",
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
            "## Latest Design Readout",
            f"Result: {evaluation.get('result')}." if evaluation else "No evaluation has been run yet.",
            "",
            "### Working Well",
            bullet_lines(working_well or ["No strong support areas have been recorded yet."]),
            "",
            "### What Needs To Change",
            bullet_lines(changes_next or ["No concrete next changes are recorded yet."]),
        ]
    )
    return "\n".join(parts)


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
            "## Latest Evaluation",
            bullet_lines(evaluation_lines),
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
                    "This narrative is a human-readable interpretation of the current design packet. Canonical source of truth remains the deterministic artifact.",
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
    return [str(item).strip() for item in value] if isinstance(value, list) else []


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
        return "None selected"
    eval_id = evaluation.get("id") or "unknown"
    result = evaluation.get("result") or "unknown"
    created = evaluation.get("created_at")
    if created and hasattr(created, "isoformat"):
        return f"{eval_id} ({result}, {created.isoformat()})"
    if created:
        return f"{eval_id} ({result}, {created})"
    return f"{eval_id} ({result})"
