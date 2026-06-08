"""CRUD routes for project artifacts: requirements, scenarios, proposals, evaluations."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from psycopg.errors import CheckViolation, UniqueViolation

from ..db import get_pool
from ..models import (
    ApplyAssistantProposal,
    AppendAssistantAuditEvent,
    ArtifactOut,
    CreateArtifact,
    CreateEvaluation,
    CreateProjectDocument,
    CreateProposal,
    EvaluationOut,
    ProjectDocumentOut,
    ProposalOut,
    UpdateArtifact,
    SetRequirementsRole,
)
from ..repository import (
    NotFoundError,
    ProjectCoherenceError,
    ReferentialIntegrityError,
)
from ..shape_integrity import ShapeIntegrityError
from .. import repository

router = APIRouter(prefix="/api/projects/{pid}", tags=["artifacts"])
ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE = "assistant_audit_log"
ASSISTANT_AUDIT_LOG_EVENT_LIMIT = 500
INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE = "integration_fronting_capability_mapping"
_SAFE_SERVICE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Error translation helpers
# ---------------------------------------------------------------------------

def _handle_errors(fn):
    """Decorator that translates repository exceptions to HTTP errors."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ReferentialIntegrityError as e:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(e),
                    "blocked_by": e.blocked_by,
                    "refs": e.refs,
                },
            )
        except ProjectCoherenceError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except ShapeIntegrityError as e:
            raise HTTPException(
                status_code=422,
                detail={"message": str(e), "errors": e.errors},
            )
        except CheckViolation as e:
            constraint = getattr(e.diag, "constraint_name", None) or "database_check_constraint"
            raise HTTPException(status_code=422, detail=f"Artifact violates constraint: {constraint}")
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="Duplicate ID")

    return wrapper


# ---------------------------------------------------------------------------
# Requirements Sets
# ---------------------------------------------------------------------------

@router.get("/requirements", response_model=list[ArtifactOut])
@_handle_errors
def list_requirements(pid: str):
    with get_pool().connection() as conn:
        return repository.list_requirements(conn, pid)


@router.post("/requirements", response_model=ArtifactOut, status_code=201)
@_handle_errors
def create_requirements(pid: str, body: CreateArtifact):
    with get_pool().connection() as conn:
        return repository.create_requirements(
            conn, project_id=pid, req_id=body.id, title=body.title, data=body.data,
        )


@router.get("/requirements/{req_id}", response_model=ArtifactOut)
@_handle_errors
def get_requirements(pid: str, req_id: str):
    with get_pool().connection() as conn:
        return repository.get_requirements(conn, pid, req_id)


@router.put("/requirements/{req_id}", response_model=ArtifactOut)
@_handle_errors
def update_requirements(pid: str, req_id: str, body: UpdateArtifact):
    with get_pool().connection() as conn:
        return repository.update_requirements(
            conn, pid, req_id, **body.model_dump(exclude_unset=True),
        )


@router.delete("/requirements/{req_id}", status_code=204)
@_handle_errors
def delete_requirements(pid: str, req_id: str):
    with get_pool().connection() as conn:
        repository.delete_requirements(conn, pid, req_id)


@router.put("/requirements/{req_id}/role", response_model=ArtifactOut)
@_handle_errors
def set_requirements_role(pid: str, req_id: str, body: SetRequirementsRole):
    with get_pool().connection() as conn:
        return repository.set_requirements_role(conn, pid, req_id, body.role)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@router.get("/scenarios", response_model=list[ArtifactOut])
@_handle_errors
def list_scenarios(pid: str):
    with get_pool().connection() as conn:
        return repository.list_scenarios(conn, pid)


@router.post("/scenarios", response_model=ArtifactOut, status_code=201)
@_handle_errors
def create_scenario(pid: str, body: CreateArtifact):
    with get_pool().connection() as conn:
        return repository.create_scenario(
            conn, project_id=pid, scenario_id=body.id, title=body.title, data=body.data,
        )


@router.get("/scenarios/{scenario_id}", response_model=ArtifactOut)
@_handle_errors
def get_scenario(pid: str, scenario_id: str):
    with get_pool().connection() as conn:
        return repository.get_scenario(conn, pid, scenario_id)


@router.put("/scenarios/{scenario_id}", response_model=ArtifactOut)
@_handle_errors
def update_scenario(pid: str, scenario_id: str, body: UpdateArtifact):
    with get_pool().connection() as conn:
        return repository.update_scenario(
            conn, pid, scenario_id, **body.model_dump(exclude_unset=True),
        )


@router.delete("/scenarios/{scenario_id}", status_code=204)
@_handle_errors
def delete_scenario(pid: str, scenario_id: str):
    with get_pool().connection() as conn:
        repository.delete_scenario(conn, pid, scenario_id)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

@router.get("/service-metadata", response_model=list[ArtifactOut])
@_handle_errors
def list_service_metadata(pid: str):
    with get_pool().connection() as conn:
        return repository.list_service_metadata_artifacts(conn, pid)


@router.post("/service-metadata", response_model=ArtifactOut, status_code=201)
@_handle_errors
def create_service_metadata(pid: str, body: CreateArtifact):
    with get_pool().connection() as conn:
        return repository.create_service_metadata_artifact(
            conn, project_id=pid, artifact_id=body.id, title=body.title, data=body.data,
        )


@router.get("/service-metadata/{artifact_id}", response_model=ArtifactOut)
@_handle_errors
def get_service_metadata(pid: str, artifact_id: str):
    with get_pool().connection() as conn:
        return repository.get_service_metadata_artifact(conn, pid, artifact_id)


@router.put("/service-metadata/{artifact_id}", response_model=ArtifactOut)
@_handle_errors
def update_service_metadata(pid: str, artifact_id: str, body: UpdateArtifact):
    with get_pool().connection() as conn:
        return repository.update_service_metadata_artifact(
            conn, pid, artifact_id, **body.model_dump(exclude_unset=True),
        )


@router.delete("/service-metadata/{artifact_id}", status_code=204)
@_handle_errors
def delete_service_metadata(pid: str, artifact_id: str):
    with get_pool().connection() as conn:
        repository.delete_service_metadata_artifact(conn, pid, artifact_id)


# ---------------------------------------------------------------------------
# PM Artifacts
# ---------------------------------------------------------------------------

@router.get("/pm-artifacts", response_model=list[ArtifactOut])
@_handle_errors
def list_pm_artifacts(pid: str):
    with get_pool().connection() as conn:
        return repository.list_pm_artifacts(conn, pid)


@router.post("/pm-artifacts", response_model=ArtifactOut, status_code=201)
@_handle_errors
def create_pm_artifact(pid: str, body: CreateArtifact):
    with get_pool().connection() as conn:
        artifact = repository.create_pm_artifact(
            conn, project_id=pid, artifact_id=body.id, title=body.title, data=body.data,
        )
        _materialize_fronting_mappings_from_acceptance(conn, pid, body.data)
        return artifact


@router.get("/pm-artifacts/{artifact_id}", response_model=ArtifactOut)
@_handle_errors
def get_pm_artifact(pid: str, artifact_id: str):
    with get_pool().connection() as conn:
        return repository.get_pm_artifact(conn, pid, artifact_id)


@router.put("/pm-artifacts/{artifact_id}", response_model=ArtifactOut)
@_handle_errors
def update_pm_artifact(pid: str, artifact_id: str, body: UpdateArtifact):
    with get_pool().connection() as conn:
        artifact = repository.update_pm_artifact(
            conn, pid, artifact_id, **body.model_dump(exclude_unset=True),
        )
        data = body.data if body.data is not None else (artifact.get("data") if isinstance(artifact, dict) else None)
        if isinstance(data, dict):
            _materialize_fronting_mappings_from_acceptance(conn, pid, data)
        return artifact


@router.delete("/pm-artifacts/{artifact_id}", status_code=204)
@_handle_errors
def delete_pm_artifact(pid: str, artifact_id: str):
    with get_pool().connection() as conn:
        repository.delete_pm_artifact(conn, pid, artifact_id)


_ASSISTANT_ACCEPTANCE_ARTIFACT_BY_CAPABILITY = {
    "propose_requirements": "assistant_requirement_candidates",
    "propose_scenarios": "assistant_scenario_candidates",
    "propose_business_summary": "assistant_business_summary_candidates",
    "propose_actor_model": "assistant_actor_model_candidates",
    "propose_business_areas": "assistant_business_area_candidates",
    "propose_permission_intent": "assistant_permission_intent_candidates",
    "propose_non_goals": "assistant_non_goal_candidates",
    "propose_success_criteria": "assistant_success_criteria_candidates",
    "propose_service_design": "assistant_service_design_candidates",
    "propose_capability_formalization": "assistant_capability_formalization_candidates",
    "propose_runtime_policy_bindings": "assistant_runtime_policy_binding_candidates",
    "propose_input_contracts": "assistant_input_contract_candidates",
    "propose_verification_expectations": "assistant_verification_expectation_candidates",
    "propose_backend_bindings": "assistant_backend_binding_candidates",
    "identify_missing_business_info": "assistant_missing_business_info",
    "clarify_design_section": "assistant_section_clarifications",
}


def _accepted_proposal_payload(body: ApplyAssistantProposal) -> dict:
    proposal = body.proposal or {}
    proposal_kind = proposal.get("proposal_kind")
    accepted_payload: dict | list = {}

    if proposal_kind == "candidate_blocks":
        items = proposal.get("items") or []
        accepted_payload = [
            item
            for item in items
            if isinstance(item, dict) and item.get("client_id") in set(body.accepted_item_ids)
        ]
    elif proposal_kind == "clarification_questions":
        questions = proposal.get("questions") or []
        accepted_payload = [
            {
                **item,
                "answer": str(body.accepted_answers.get(str(item.get("question_id") or ""), "")).strip(),
            }
            for item in questions
            if isinstance(item, dict) and item.get("question_id") in set(body.accepted_item_ids)
        ]
    elif proposal_kind == "patch_candidates":
        patches = proposal.get("patches") or []
        accepted_payload = [
            item
            for index, item in enumerate(patches)
            if str(index) in set(body.accepted_item_ids)
        ]

    artifact_type = _ASSISTANT_ACCEPTANCE_ARTIFACT_BY_CAPABILITY.get(
        body.capability, "assistant_proposal_acceptance"
    )
    return {
        "artifact_type": artifact_type,
        "source_capability": body.capability,
        "proposal_kind": proposal_kind,
        "accepted_item_ids": body.accepted_item_ids,
        "rejected_item_ids": body.rejected_item_ids,
        "accepted_answers": body.accepted_answers,
        "accepted_payload": accepted_payload,
        "mode": proposal.get("mode"),
        "section_key": proposal.get("section_key"),
        "source_proposal": proposal,
        "notes": body.notes,
    }


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "item"


def _title_from_id(value: str) -> str:
    return " ".join(part for part in re.split(r"[^A-Za-z0-9]+", value) if part).title()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]+", value) if part.strip()]
    return []


def _fronting_public_capability_ids(conn: Any, project_id: str) -> set[str]:
    capability_ids: set[str] = set()
    for shape in repository.list_shapes(conn, project_id):
        data = shape.get("data") if isinstance(shape.get("data"), dict) else {}
        shape_data = data.get("shape") if isinstance(data.get("shape"), dict) else data
        for service in shape_data.get("services") or []:
            if not isinstance(service, dict):
                continue
            for capability_id in service.get("capabilities") or []:
                capability = str(capability_id or "").strip()
                if capability:
                    capability_ids.add(capability)
    return capability_ids


def _walk_capability_candidates(value: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        if str(node.get("capability_id") or "").strip():
            candidates.append(node)
        for item in node.values():
            visit(item)

    visit(value)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        capability_id = str(candidate.get("capability_id") or "").strip()
        if not capability_id or capability_id in seen:
            continue
        seen.add(capability_id)
        deduped.append(candidate)
    return deduped


def _project_fronting_system(project: dict[str, Any]) -> dict[str, Any]:
    profile = project.get("integration_profile") if isinstance(project.get("integration_profile"), dict) else {}
    systems = profile.get("systems") if isinstance(profile.get("systems"), list) else []
    for system in systems:
        if isinstance(system, dict) and str(system.get("system_id") or "").strip():
            return system
    domain = str(project.get("domain") or project.get("name") or "fronting").strip()
    return {"system_id": _slug(domain), "display_name": _title_from_id(domain), "backend_kind": "native_api"}


def _fronting_service_id(project: dict[str, Any], candidate: dict[str, Any]) -> str:
    candidate_service_id = str(candidate.get("service_id") or "").strip()
    if _SAFE_SERVICE_ID_RE.fullmatch(candidate_service_id):
        return candidate_service_id
    system_id = _slug(_project_fronting_system(project).get("system_id") or project.get("domain") or "fronting")
    return f"{system_id}-governance-service"


def _fronting_connection_ref(project_id: str, project: dict[str, Any], candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("connection_ref") or "").strip()
    if explicit:
        return explicit
    for binding in candidate.get("backend_bindings") or []:
        if isinstance(binding, dict) and str(binding.get("connection_ref") or "").strip():
            return str(binding.get("connection_ref")).strip()
    system = _project_fronting_system(project)
    return str(system.get("connection_ref") or f"{project_id}-{_slug(system.get('system_id') or 'fronting')}-api")


def _fronting_raw_operation_refs(candidate: dict[str, Any]) -> list[str]:
    refs = _string_list(candidate.get("raw_operation_refs"))
    if refs:
        return refs
    refs = _string_list(candidate.get("backend_operations"))
    if refs:
        return refs
    backend_operation = str(candidate.get("backend_operation") or "").strip()
    if backend_operation:
        return _string_list(backend_operation)
    capability_id = str(candidate.get("capability_id") or "").strip()
    return [capability_id] if capability_id else []


def _fronting_input_metadata(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for item in candidate.get("inputs") or []:
        if not isinstance(item, dict):
            continue
        input_name = str(item.get("input_name") or item.get("name") or "").strip()
        if not input_name:
            continue
        normalized = dict(item)
        normalized["input_name"] = input_name
        normalized["required"] = bool(item.get("required"))
        metadata.append(normalized)
    return metadata


def _fronting_execution_posture(candidate: dict[str, Any]) -> str:
    explicit = str(candidate.get("execution_posture") or "").strip()
    if explicit:
        return explicit
    operation_type = str(candidate.get("operation_type") or "").strip()
    side_effect = str(candidate.get("side_effect_level") or "").strip()
    if operation_type == "read" and side_effect == "read":
        return "read_only"
    if side_effect == "write":
        return "approval_gated"
    return "prepare_only"


def _fronting_mapping_from_capability(
    *,
    project_id: str,
    project: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    capability_id = str(candidate.get("capability_id") or "").strip()
    if not capability_id:
        return None
    inputs = _fronting_input_metadata(candidate)
    required_inputs = [item["input_name"] for item in inputs if item.get("required")]
    optional_inputs = [item["input_name"] for item in inputs if not item.get("required")]
    raw_operation_refs = _fronting_raw_operation_refs(candidate)
    if not raw_operation_refs:
        return None
    service_id = _fronting_service_id(project, candidate)
    service_name = str(candidate.get("service_name") or "").strip() or _title_from_id(service_id)
    side_effect = str(candidate.get("side_effect_level") or "").strip() or "read"
    operation_type = str(candidate.get("operation_type") or "").strip() or ("read" if side_effect == "read" else "write")
    backend_input_mode = str(candidate.get("backend_input_mode") or "").strip() or "explicit"
    connection_ref = _fronting_connection_ref(project_id, project, candidate)
    backend_kind = str(candidate.get("backend_kind") or _project_fronting_system(project).get("backend_kind") or "native_api")
    backend_kind = backend_kind if backend_kind in {"native_api", "mcp", "database", "hybrid"} else "native_api"
    mapping_id = f"{project_id}-mapping-{_slug(capability_id)}"
    approval_rule_refs = _string_list(candidate.get("approval_rule_refs"))
    if not approval_rule_refs and side_effect != "read":
        approval_rule_refs = [f"approval.{_slug(capability_id)}"]
    denial_rule_refs = _string_list(candidate.get("denial_rule_refs")) or ["deny.raw_backend_bypass"]
    clarification_rule_refs = _string_list(candidate.get("clarification_rule_refs")) or [
        f"clarify.{input_name}" for input_name in required_inputs
    ]
    return {
        "artifact_id": mapping_id,
        "title": f"{str(candidate.get('title') or _title_from_id(capability_id)).strip()} Fronting Mapping",
        "data": {
            "artifact_type": INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE,
            "id": mapping_id,
            "capability_id": capability_id,
            "title": str(candidate.get("title") or _title_from_id(capability_id)).strip(),
            "intent": str(candidate.get("summary") or candidate.get("intent") or "").strip(),
            "summary": str(candidate.get("summary") or candidate.get("intent") or "").strip(),
            "service_id": service_id,
            "service_name": service_name,
            "backend_kind": backend_kind,
            "connection_ref": connection_ref,
            "raw_operation_refs": raw_operation_refs,
            "backend_bindings": [
                {
                    "backend_kind": backend_kind,
                    "connection_ref": connection_ref,
                    "raw_operation_refs": raw_operation_refs,
                    "matched_discovery_record_ids": _string_list(candidate.get("matched_discovery_record_ids")),
                    "explicit_required_backend_inputs": required_inputs if backend_input_mode == "explicit" else [],
                    "explicit_optional_backend_inputs": optional_inputs if backend_input_mode == "explicit" else [],
                    "derived_required_backend_inputs": required_inputs,
                    "derived_optional_backend_inputs": optional_inputs,
                    "backend_input_mode": backend_input_mode,
                    "status": "accepted",
                    "status_detail": "Materialized from reviewed developer capability evidence.",
                }
            ],
            "operation_type": operation_type,
            "execution_posture": _fronting_execution_posture(candidate),
            "side_effect_level": side_effect,
            "subject_kind": str(candidate.get("subject_kind") or "fronting_subject").strip(),
            "context_type": str(candidate.get("context_type") or "fronting_context").strip(),
            "output_intent": str(candidate.get("output_intent") or candidate.get("output_shape") or "governed_fronting_result").strip(),
            "required_inputs": required_inputs,
            "optional_inputs": optional_inputs,
            "input_metadata": inputs,
            "backend_input_mode": backend_input_mode,
            "derived_required_backend_inputs": required_inputs,
            "derived_optional_backend_inputs": optional_inputs,
            "explicit_required_backend_inputs": required_inputs if backend_input_mode == "explicit" else [],
            "explicit_optional_backend_inputs": optional_inputs if backend_input_mode == "explicit" else [],
            "approval_rule_refs": approval_rule_refs,
            "denial_rule_refs": denial_rule_refs,
            "clarification_rule_refs": clarification_rule_refs,
            "audit_required": candidate.get("audit_required") is not False,
            "outbound_controls": candidate.get("outbound_controls") if isinstance(candidate.get("outbound_controls"), dict) else {
                "raw_backend_not_agent_visible": True,
                "redaction_required": True,
            },
            "review_status": "source_materialized",
        },
    }


def _materialize_fronting_mappings_from_acceptance(conn: Any, project_id: str, payload: dict[str, Any]) -> None:
    if payload.get("artifact_type") != "assistant_capability_formalization_candidates":
        return
    project = repository.get_project_detail(conn, project_id)
    if project.get("project_type") != "governed_service_project":
        return
    pm_artifacts = repository.list_pm_artifacts(conn, project_id)
    existing_mapping_capabilities = {
        str((artifact.get("data") or {}).get("capability_id") or "").strip()
        for artifact in pm_artifacts
        if (artifact.get("data") or {}).get("artifact_type") == INTEGRATION_FRONTING_MAPPING_ARTIFACT_TYPE
    }
    public_capability_ids = _fronting_public_capability_ids(conn, project_id)
    source_candidates = {
        "accepted_payload": payload.get("accepted_payload"),
        "source_proposal": payload.get("source_proposal"),
    }
    for candidate in _walk_capability_candidates(source_candidates):
        capability_id = str(candidate.get("capability_id") or "").strip()
        if not capability_id or capability_id in existing_mapping_capabilities:
            continue
        if public_capability_ids and capability_id not in public_capability_ids:
            continue
        mapping = _fronting_mapping_from_capability(project_id=project_id, project=project, candidate=candidate)
        if not mapping:
            continue
        try:
            repository.get_pm_artifact(conn, project_id, mapping["artifact_id"])
            repository.update_pm_artifact(
                conn,
                project_id,
                mapping["artifact_id"],
                title=mapping["title"],
                data=mapping["data"],
            )
        except NotFoundError:
            repository.create_pm_artifact(
                conn,
                project_id=project_id,
                artifact_id=mapping["artifact_id"],
                title=mapping["title"],
                data=mapping["data"],
            )
        existing_mapping_capabilities.add(capability_id)


@router.post("/assistant/proposals/apply", response_model=ArtifactOut, status_code=201)
@_handle_errors
def apply_assistant_proposal(pid: str, body: ApplyAssistantProposal):
    payload = _accepted_proposal_payload(body)
    with get_pool().connection() as conn:
        try:
            repository.get_pm_artifact(conn, pid, body.artifact_id)
            artifact = repository.update_pm_artifact(
                conn,
                pid,
                body.artifact_id,
                title=body.title,
                data=payload,
            )
            _materialize_fronting_mappings_from_acceptance(conn, pid, payload)
            return artifact
        except NotFoundError:
            artifact = repository.create_pm_artifact(
                conn,
                project_id=pid,
                artifact_id=body.artifact_id,
                title=body.title,
                data=payload,
            )
            _materialize_fronting_mappings_from_acceptance(conn, pid, payload)
            return artifact


@router.post("/assistant/audit-events", response_model=ArtifactOut, status_code=201)
@_handle_errors
def append_assistant_audit_event(pid: str, body: AppendAssistantAuditEvent):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_id = f"assistant-audit-log-{pid}"
    event = body.model_dump(exclude_none=True)
    event.update({
        "id": f"assistant-audit-{uuid4()}",
        "project_id": pid,
        "created_at": now,
    })

    with get_pool().connection() as conn:
        try:
            artifact = repository.get_pm_artifact(conn, pid, artifact_id)
            data = artifact.get("data") if isinstance(artifact.get("data"), dict) else {}
            events = data.get("events") if isinstance(data, dict) else []
            if not isinstance(events, list):
                events = []
            next_data = {
                "artifact_type": ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE,
                "events": [*events, event][-ASSISTANT_AUDIT_LOG_EVENT_LIMIT:],
                "updated_at": now,
            }
            return repository.update_pm_artifact(
                conn,
                pid,
                artifact_id,
                title="AI Assistant Audit Log",
                status="active",
                data=next_data,
            )
        except NotFoundError:
            return repository.create_pm_artifact(
                conn,
                project_id=pid,
                artifact_id=artifact_id,
                title="AI Assistant Audit Log",
                data={
                    "artifact_type": ASSISTANT_AUDIT_LOG_ARTIFACT_TYPE,
                    "events": [event],
                    "updated_at": now,
                },
            )


# ---------------------------------------------------------------------------
# Project Documents
# ---------------------------------------------------------------------------

@router.get("/documents", response_model=list[ProjectDocumentOut])
@_handle_errors
def list_documents(pid: str):
    with get_pool().connection() as conn:
        return repository.list_project_documents(conn, pid)


@router.post("/documents", response_model=ProjectDocumentOut, status_code=201)
@_handle_errors
def create_document(pid: str, body: CreateProjectDocument):
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid document payload: {exc}") from exc
    with get_pool().connection() as conn:
        return repository.create_project_document(
            conn,
            project_id=pid,
            document_id=body.id,
            title=body.title,
            kind=body.kind,
            filename=body.filename,
            media_type=body.media_type,
            source_path=body.source_path,
            content=content,
        )


@router.get("/documents/{document_id}", response_model=ProjectDocumentOut)
@_handle_errors
def get_document(pid: str, document_id: str):
    with get_pool().connection() as conn:
        row = repository.get_project_document(conn, pid, document_id)
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "title": row["title"],
            "kind": row["kind"],
            "filename": row["filename"],
            "media_type": row["media_type"],
            "source_path": row["source_path"],
            "content_hash": row["content_hash"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


@router.get("/documents/{document_id}/preview")
@_handle_errors
def preview_document(pid: str, document_id: str):
    with get_pool().connection() as conn:
        row = repository.get_project_document(conn, pid, document_id)
    media_type = str(row["media_type"] or "")
    filename = str(row["filename"] or "").lower()
    if not (
        media_type.startswith("text/")
        or media_type in {"application/json", "application/yaml", "application/x-yaml"}
        or filename.endswith((".md", ".markdown", ".txt", ".json", ".yaml", ".yml"))
    ):
        raise HTTPException(status_code=415, detail="Preview is only available for text documents")
    content = bytes(row["content"]).decode("utf-8", errors="replace")
    return {"content": content}


@router.get("/documents/{document_id}/download")
@_handle_errors
def download_document(pid: str, document_id: str):
    with get_pool().connection() as conn:
        row = repository.get_project_document(conn, pid, document_id)
    headers = {
        "Content-Disposition": f'attachment; filename="{row["filename"]}"',
    }
    return Response(content=bytes(row["content"]), media_type=row["media_type"], headers=headers)


@router.delete("/documents/{document_id}", status_code=204)
@_handle_errors
def delete_document(pid: str, document_id: str):
    with get_pool().connection() as conn:
        repository.delete_project_document(conn, pid, document_id)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

@router.get("/proposals", response_model=list[ProposalOut])
@_handle_errors
def list_proposals(pid: str):
    with get_pool().connection() as conn:
        return repository.list_proposals(conn, pid)


@router.post("/proposals", response_model=ProposalOut, status_code=201)
@_handle_errors
def create_proposal(pid: str, body: CreateProposal):
    with get_pool().connection() as conn:
        return repository.create_proposal(
            conn,
            project_id=pid,
            proposal_id=body.id,
            title=body.title,
            requirements_id=body.requirements_id,
            data=body.data,
        )


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
@_handle_errors
def get_proposal(pid: str, proposal_id: str):
    with get_pool().connection() as conn:
        return repository.get_proposal(conn, pid, proposal_id)


@router.put("/proposals/{proposal_id}", response_model=ProposalOut)
@_handle_errors
def update_proposal(pid: str, proposal_id: str, body: UpdateArtifact):
    with get_pool().connection() as conn:
        return repository.update_proposal(
            conn, pid, proposal_id, **body.model_dump(exclude_unset=True),
        )


@router.delete("/proposals/{proposal_id}", status_code=204)
@_handle_errors
def delete_proposal(pid: str, proposal_id: str):
    with get_pool().connection() as conn:
        repository.delete_proposal(conn, pid, proposal_id)


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

@router.get("/evaluations", response_model=list[EvaluationOut])
@_handle_errors
def list_evaluations(
    pid: str,
    scenario_id: Optional[str] = Query(None),
    proposal_id: Optional[str] = Query(None),
    shape_id: Optional[str] = Query(None),
):
    with get_pool().connection() as conn:
        return repository.list_evaluations(
            conn, pid, scenario_id=scenario_id, proposal_id=proposal_id,
            shape_id=shape_id,
        )


@router.post("/evaluations", response_model=EvaluationOut, status_code=201)
@_handle_errors
def create_evaluation(pid: str, body: CreateEvaluation):
    with get_pool().connection() as conn:
        return repository.create_evaluation(
            conn,
            project_id=pid,
            eval_id=body.id,
            proposal_id=body.proposal_id,
            scenario_id=body.scenario_id,
            requirements_id=body.requirements_id,
            source=body.source,
            data=body.data,
            input_snapshot=body.input_snapshot,
            shape_id=body.shape_id,
        )


@router.get("/evaluations/{eval_id}", response_model=EvaluationOut)
@_handle_errors
def get_evaluation(pid: str, eval_id: str):
    with get_pool().connection() as conn:
        return repository.get_evaluation(conn, pid, eval_id)


@router.delete("/evaluations/{eval_id}", status_code=204)
@_handle_errors
def delete_evaluation(pid: str, eval_id: str):
    with get_pool().connection() as conn:
        repository.delete_evaluation(conn, pid, eval_id)
