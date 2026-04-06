"""ANIP-backed Studio workbench service for agentic design loops."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
for path in [
    ROOT / "tooling" / "bin",
    ROOT / "packages" / "python" / "anip-core" / "src",
    ROOT / "packages" / "python" / "anip-service" / "src",
]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    CrossServiceContract,
    CrossServiceContractEntry,
    ServiceCapabilityRef,
    SideEffect,
    SideEffectType,
)
from anip_service import ANIPError, ANIPService, Capability
from anip_design_validate import evaluate, validate_payload

from .db import get_pool
from .derivation import build_shape_backed_proposal
from .intent_drafts import (
    classify_change_target,
    make_requirements_fix_template,
    make_requirements_template_from_intent,
    make_scenario_fix_template,
    make_scenario_templates_from_intent,
    make_shape_fix_template,
    make_shape_template_from_intent,
    slugify,
)
from .repository import (
    NotFoundError,
    create_evaluation,
    create_project,
    create_requirements,
    create_scenario,
    create_shape,
    create_workspace,
    get_evaluation,
    get_project_detail,
    get_requirements,
    get_scenario,
    get_shape,
    list_evaluations,
    list_projects,
    list_requirements,
    list_scenarios,
    list_shapes,
)
from .shared_artifacts import build_business_brief, build_engineering_contract

SCHEMA_DIR = ROOT / "tooling" / "schemas"
BOOTSTRAP_BEARER = "studio-workbench-bootstrap"
WORKBENCH_SCOPES = [
    "studio.workbench.create_workspace",
    "studio.workbench.create_project",
    "studio.workbench.read_project_state",
    "studio.workbench.accept_first_design",
    "studio.workbench.evaluate_service_design",
    "studio.workbench.draft_fix_from_change",
    "studio.workbench.generate_business_brief",
    "studio.workbench.generate_engineering_contract",
]


def create_studio_workbench_service() -> ANIPService:
    return ANIPService(
        service_id="studio-workbench",
        capabilities=[
            _capability(
                "create_workspace",
                "Create a Studio workspace for a stress run or new design effort.",
                [("name", "string", True), ("summary", "string", False), ("workspace_id", "string", False)],
                ["workspace"],
                SideEffectType.WRITE,
                "PT1H",
                _create_workspace,
            ),
            _capability(
                "create_project",
                "Create a Studio project inside a workspace.",
                [
                    ("name", "string", True),
                    ("workspace_id", "string", False),
                    ("summary", "string", False),
                    ("domain", "string", False),
                    ("project_id", "string", False),
                ],
                ["project"],
                SideEffectType.WRITE,
                "PT1H",
                _create_project,
            ),
            _capability(
                "read_project_state",
                "Read the current Studio project state, including requirements, scenarios, shapes, and evaluations.",
                [("project_id", "string", True)],
                ["project", "requirements", "scenarios", "shapes", "evaluations"],
                SideEffectType.READ,
                "not_applicable",
                _read_project_state,
            ),
            _capability(
                "accept_first_design",
                "Persist the interpreted first design into real Studio artifacts.",
                [
                    ("project_id", "string", True),
                    ("source_intent", "string", True),
                    ("interpretation", "object", True),
                ],
                ["requirements", "scenarios", "shape"],
                SideEffectType.WRITE,
                "PT1H",
                _accept_first_design,
            ),
            _capability(
                "evaluate_service_design",
                "Evaluate a Studio service design against the selected requirements and scenario, then persist the result.",
                [
                    ("project_id", "string", True),
                    ("requirements_id", "string", True),
                    ("scenario_id", "string", True),
                    ("shape_id", "string", True),
                ],
                ["evaluation_id", "result", "evaluation"],
                SideEffectType.WRITE,
                "PT1H",
                _evaluate_service_design,
            ),
            _capability(
                "draft_fix_from_change",
                "Turn a change hint into a new draft requirements set, scenario, or service shape.",
                [
                    ("project_id", "string", True),
                    ("change", "string", True),
                    ("requirements_id", "string", False),
                    ("scenario_id", "string", False),
                    ("shape_id", "string", False),
                ],
                ["created_type", "created_id", "selection"],
                SideEffectType.WRITE,
                "PT1H",
                _draft_fix_from_change,
            ),
            _capability(
                "generate_business_brief",
                "Generate a PM-facing Business Brief from the current Studio state.",
                [
                    ("project_id", "string", True),
                    ("source_intent", "string", False),
                    ("requirements_id", "string", False),
                    ("scenario_id", "string", False),
                    ("shape_id", "string", False),
                    ("evaluation_id", "string", False),
                ],
                ["document"],
                SideEffectType.READ,
                "not_applicable",
                _generate_business_brief,
            ),
            _capability(
                "generate_engineering_contract",
                "Generate an engineering-facing contract from the current Studio state.",
                [
                    ("project_id", "string", True),
                    ("requirements_id", "string", False),
                    ("scenario_id", "string", False),
                    ("shape_id", "string", False),
                    ("evaluation_id", "string", False),
                ],
                ["document"],
                SideEffectType.READ,
                "not_applicable",
                _generate_engineering_contract,
            ),
        ],
        storage=":memory:",
        authenticate=_authenticate_bootstrap_bearer,
    )


def _capability(
    name: str,
    description: str,
    inputs: list[tuple[str, str, bool]],
    fields: list[str],
    side_effect_type: SideEffectType,
    rollback_window: str,
    handler,
) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description=description,
            inputs=[
                CapabilityInput(name=item[0], type=item[1], required=item[2], description=item[0].replace("_", " "))
                for item in inputs
            ],
            output=CapabilityOutput(type="object", fields=fields),
            side_effect=SideEffect(type=side_effect_type, rollback_window=rollback_window),
            minimum_scope=[f"studio.workbench.{name}"],
            cross_service_contract=(
                CrossServiceContract(
                    followup=[
                        CrossServiceContractEntry(
                            target=ServiceCapabilityRef(
                                service="studio-assistant",
                                capability="explain_evaluation",
                            ),
                            required_for_task_completion=False,
                            continuity="same_task",
                            completion_mode="downstream_acceptance",
                        )
                    ]
                )
                if name == "evaluate_service_design"
                else None
            ),
        ),
        handler=handler,
    )


def _authenticate_bootstrap_bearer(bearer: str) -> str | None:
    return "studio-agent" if bearer == BOOTSTRAP_BEARER else None


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


def _required_string(params: dict[str, Any], name: str) -> str:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _invalid_request(f"{name} is required")
    return value.strip()


def _optional_string(params: dict[str, Any], name: str) -> str | None:
    value = params.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _required_object(params: dict[str, Any], name: str) -> dict[str, Any]:
    value = params.get(name)
    if not isinstance(value, dict):
        raise _invalid_request(f"{name} must be an object")
    return value


def _serialize_artifact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row.get("title", ""),
        "status": row.get("status", ""),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
    }


def _serialize_evaluation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "result": row.get("result"),
        "scenario_id": row.get("scenario_id"),
        "requirements_id": row.get("requirements_id"),
        "shape_id": row.get("shape_id"),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        "is_stale": row.get("is_stale"),
    }


async def _create_workspace(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = _required_string(params, "name")
    summary = _optional_string(params, "summary") or ""
    workspace_id = _optional_string(params, "workspace_id") or f"ws-{slugify(name) or uuid4().hex[:8]}"
    with get_pool().connection() as conn:
        workspace = create_workspace(conn, workspace_id=workspace_id, name=name, summary=summary)
    return {"workspace": {"id": workspace["id"], "name": workspace["name"], "summary": workspace["summary"]}}


async def _create_project(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = _required_string(params, "name")
    workspace_id = _optional_string(params, "workspace_id")
    summary = _optional_string(params, "summary") or ""
    domain = _optional_string(params, "domain") or ""
    project_id = _optional_string(params, "project_id") or f"proj-{slugify(name) or 'project'}-{uuid4().hex[:8]}"
    with get_pool().connection() as conn:
        project = create_project(
            conn,
            project_id=project_id,
            workspace_id=workspace_id,
            name=name,
            summary=summary,
            domain=domain,
            labels=[],
        )
    return {"project": {"id": project["id"], "workspace_id": project["workspace_id"], "name": project["name"], "summary": project["summary"], "domain": project["domain"]}}


async def _read_project_state(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_string(params, "project_id")
    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            requirements = list_requirements(conn, project_id)
            scenarios = list_scenarios(conn, project_id)
            shapes = list_shapes(conn, project_id)
            evaluations = list_evaluations(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc
    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "summary": project["summary"],
            "domain": project["domain"],
            "counts": {
                "requirements": project["requirements_count"],
                "scenarios": project["scenarios_count"],
                "shapes": project["shapes_count"],
                "evaluations": project["evaluations_count"],
            },
        },
        "requirements": [_serialize_artifact(item) | {"role": item.get("role", "")} for item in requirements],
        "scenarios": [_serialize_artifact(item) for item in scenarios],
        "shapes": [_serialize_artifact(item) | {"requirements_id": item.get("requirements_id")} for item in shapes],
        "evaluations": [_serialize_evaluation(item) for item in evaluations[:10]],
    }


async def _accept_first_design(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_string(params, "project_id")
    source_intent = _required_string(params, "source_intent")
    interpretation = _required_object(params, "interpretation")
    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            requirements = create_requirements(
                conn,
                project_id=project_id,
                req_id=f"req-{uuid4()}",
                title="Requirements",
                data=make_requirements_template_from_intent(
                    interpretation,
                    source_intent,
                    project["name"],
                    project["domain"],
                ),
            )
            created_scenarios = []
            for template in make_scenario_templates_from_intent(interpretation):
                created = create_scenario(
                    conn,
                    project_id=project_id,
                    scenario_id=f"scn-{uuid4()}",
                    title=template["title"],
                    data=template["data"],
                )
                created_scenarios.append(created)
            shape = create_shape(
                conn,
                project_id=project_id,
                shape_id=f"shape-{uuid4()}",
                title="Service Shape",
                requirements_id=requirements["id"],
                data=make_shape_template_from_intent(interpretation, project["name"]),
            )
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc
    return {
        "requirements": _serialize_artifact(requirements) | {"role": requirements.get("role", "")},
        "scenarios": [_serialize_artifact(item) for item in created_scenarios],
        "shape": _serialize_artifact(shape) | {"requirements_id": shape.get("requirements_id")},
    }


async def _evaluate_service_design(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_string(params, "project_id")
    requirements_id = _required_string(params, "requirements_id")
    scenario_id = _required_string(params, "scenario_id")
    shape_id = _required_string(params, "shape_id")
    try:
        with get_pool().connection() as conn:
            requirements = get_requirements(conn, project_id, requirements_id)
            scenario = get_scenario(conn, project_id, scenario_id)
            shape = get_shape(conn, project_id, shape_id)
            validate_payload(requirements["data"], SCHEMA_DIR / "requirements.schema.json")
            validate_payload(shape["data"], SCHEMA_DIR / "shape.schema.json")
            validate_payload(scenario["data"], SCHEMA_DIR / "scenario.schema.json")
            proposal = build_shape_backed_proposal(shape["data"], requirements["data"])
            validate_payload(proposal, SCHEMA_DIR / "proposal.schema.json")
            evaluation = evaluate(requirements["data"], proposal, scenario["data"])
            validate_payload(evaluation, SCHEMA_DIR / "evaluation.schema.json")
            evaluation_row = create_evaluation(
                conn,
                project_id=project_id,
                eval_id=f"eval-{uuid4()}",
                proposal_id=None,
                scenario_id=scenario_id,
                requirements_id=requirements_id,
                shape_id=shape_id,
                source="live_validation",
                data=evaluation,
                input_snapshot={
                    "requirements": requirements["data"],
                    "shape": shape["data"],
                    "scenario": scenario["data"],
                    "proposal": proposal,
                },
            )
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc
    return {
        "evaluation_id": evaluation_row["id"],
        "result": evaluation_row["result"],
        "evaluation": evaluation.get("evaluation", evaluation),
    }


async def _draft_fix_from_change(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_string(params, "project_id")
    change = _required_string(params, "change")
    requirements_id = _optional_string(params, "requirements_id")
    scenario_id = _optional_string(params, "scenario_id")
    shape_id = _optional_string(params, "shape_id")
    target = classify_change_target(change)
    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            requirements = get_requirements(conn, project_id, requirements_id) if requirements_id else None
            scenario = get_scenario(conn, project_id, scenario_id) if scenario_id else None
            shape = get_shape(conn, project_id, shape_id) if shape_id else None
            if target == "requirements":
                created = create_requirements(
                    conn,
                    project_id=project_id,
                    req_id=f"req-{uuid4()}",
                    title=f"Requirements Fix {project['requirements_count'] + 1}",
                    data=make_requirements_fix_template(change, requirements["data"] if requirements else None),
                )
                return {
                    "created_type": "requirements",
                    "created_id": created["id"],
                    "selection": {"requirements_id": created["id"], "scenario_id": scenario_id, "shape_id": shape_id},
                }
            if target == "scenario":
                created = create_scenario(
                    conn,
                    project_id=project_id,
                    scenario_id=f"scn-{uuid4()}",
                    title=f"Scenario Fix {project['scenarios_count'] + 1}",
                    data=make_scenario_fix_template(change, scenario["data"] if scenario else None, project["scenarios_count"] + 1),
                )
                return {
                    "created_type": "scenario",
                    "created_id": created["id"],
                    "selection": {"requirements_id": requirements_id, "scenario_id": created["id"], "shape_id": shape_id},
                }
            requirements_ref = requirements_id or (requirements["id"] if requirements else None)
            if not requirements_ref:
                raise _invalid_request("requirements_id is required to draft a service shape fix")
            created = create_shape(
                conn,
                project_id=project_id,
                shape_id=f"shape-{uuid4()}",
                title=f"Service Shape Fix {project['shapes_count'] + 1}",
                requirements_id=requirements_ref,
                data=make_shape_fix_template(change, shape["data"] if shape else None),
            )
            return {
                "created_type": "shape",
                "created_id": created["id"],
                "selection": {"requirements_id": requirements_ref, "scenario_id": scenario_id, "shape_id": created["id"]},
            }
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc


def _resolve_context(conn: Any, project_id: str, params: dict[str, Any]) -> dict[str, Any]:
    project = get_project_detail(conn, project_id)
    requirements_id = _optional_string(params, "requirements_id")
    scenario_id = _optional_string(params, "scenario_id")
    shape_id = _optional_string(params, "shape_id")
    evaluation_id = _optional_string(params, "evaluation_id")
    requirements = get_requirements(conn, project_id, requirements_id) if requirements_id else (list_requirements(conn, project_id)[0] if project["requirements_count"] else None)
    scenario = get_scenario(conn, project_id, scenario_id) if scenario_id else (list_scenarios(conn, project_id)[0] if project["scenarios_count"] else None)
    shape = get_shape(conn, project_id, shape_id) if shape_id else (list_shapes(conn, project_id)[0] if project["shapes_count"] else None)
    evaluation = get_evaluation(conn, project_id, evaluation_id) if evaluation_id else (list_evaluations(conn, project_id)[0] if project["evaluations_count"] else None)
    return {
        "project": project,
        "requirements": requirements,
        "scenario": scenario,
        "shape": shape,
        "evaluation": evaluation,
    }


async def _generate_business_brief(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_string(params, "project_id")
    source_intent = _optional_string(params, "source_intent") or ""
    try:
        with get_pool().connection() as conn:
            context = _resolve_context(conn, project_id, params)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc
    return {"document": build_business_brief(context | {"source_intent": source_intent})}


async def _generate_engineering_contract(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_string(params, "project_id")
    try:
        with get_pool().connection() as conn:
            context = _resolve_context(conn, project_id, params)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc
    return {"document": build_engineering_contract(context)}
