"""Server-side guards for Studio package publication lineage."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import repository
from .repository import NotFoundError


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _project_id_from_ref(value: str) -> str:
    text = _text(value)
    if text.startswith("studio:"):
        return text[len("studio:") :].strip()
    return text


def _artifact_type(row: dict[str, Any]) -> str:
    return _text(_as_dict(row.get("data")).get("artifact_type"))


def _latest_artifact_of_type(rows: list[dict[str, Any]], artifact_type: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if _artifact_type(row) == artifact_type]
    candidates.sort(key=lambda row: _text(row.get("updated_at") or row.get("created_at")), reverse=True)
    return candidates[0] if candidates else None


def _find_revision_artifact(
    conn: Any,
    project_id: str,
    revision_ref: str,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        row = repository.get_pm_artifact(conn, project_id, revision_ref)
        if _artifact_type(row) == "developer_definition_revision":
            return row
    except NotFoundError:
        pass

    for row in artifacts:
        data = _as_dict(row.get("data"))
        saved_revision = _as_dict(data.get("saved_revision"))
        if _artifact_type(row) == "developer_definition_revision" and _text(saved_revision.get("revision_artifact_id")) == revision_ref:
            return row

    raise HTTPException(
        status_code=422,
        detail=f"developer_revision_ref {revision_ref!r} does not point at a saved Developer Definition revision for this project.",
    )


def validate_publication_saved_revision(conn: Any, project_id: str, payload: dict[str, Any]) -> None:
    """Reject package publication that is not tied to the current saved revision.

    Studio package publication must not package transient page state. The selected
    Developer Definition revision, current saved Developer Definition pointer, and
    service definition signature all have to agree.
    """

    project_ref = _text(payload.get("project_ref"))
    normalized_project_id = _project_id_from_ref(project_id)
    normalized_project_ref = _project_id_from_ref(project_ref)
    if project_ref and normalized_project_ref != normalized_project_id:
        raise HTTPException(status_code=422, detail="project_ref must match the Studio project being published.")
    project_id = normalized_project_id

    developer_revision_ref = _text(payload.get("developer_revision_ref"))
    contract_signature = _text(payload.get("contract_signature"))
    if not developer_revision_ref:
        raise HTTPException(status_code=422, detail="developer_revision_ref is required for package publication.")
    if not contract_signature:
        raise HTTPException(status_code=422, detail="contract_signature is required for package publication.")

    service_definition = _as_dict(payload.get("service_definition"))
    service_signature = _text(_as_dict(service_definition.get("compiled_contract_identity")).get("signature"))
    if service_signature != contract_signature:
        raise HTTPException(
            status_code=422,
            detail="service_definition compiled contract signature must match contract_signature before publication.",
        )

    artifacts = repository.list_pm_artifacts(conn, project_id)
    current_definition = _latest_artifact_of_type(artifacts, "developer_definition")
    if current_definition is None:
        raise HTTPException(status_code=422, detail="Save Developer Definition before publishing a package.")

    current_data = _as_dict(current_definition.get("data"))
    current_saved_revision = _as_dict(current_data.get("saved_revision"))
    current_revision_ref = _text(current_saved_revision.get("revision_artifact_id"))
    current_signature = _text(_as_dict(current_data.get("compiled_contract_identity")).get("signature"))

    if not current_revision_ref:
        raise HTTPException(status_code=422, detail="Current Developer Definition has no immutable saved revision.")
    if current_revision_ref != developer_revision_ref:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Package publication selected {developer_revision_ref}, but the current saved Developer Definition "
                f"points at {current_revision_ref}. Save the current draft as a new revision before publishing."
            ),
        )
    if current_signature != contract_signature:
        raise HTTPException(
            status_code=422,
            detail="Package contract_signature must match the current saved Developer Definition signature.",
        )

    revision_artifact = _find_revision_artifact(conn, project_id, developer_revision_ref, artifacts)
    revision_data = _as_dict(revision_artifact.get("data"))
    revision_signature = _text(_as_dict(revision_data.get("compiled_contract_identity")).get("signature"))
    if revision_signature != contract_signature:
        raise HTTPException(
            status_code=422,
            detail="Selected Developer Definition revision signature does not match contract_signature.",
        )

    lineage = _as_dict(payload.get("lineage") or _as_dict(payload.get("manifest")).get("lineage") or _as_dict(payload.get("recommended_lock")).get("lineage"))
    developer_lineage = _as_dict(lineage.get("developer_revision"))
    lineage_revision_ref = _text(developer_lineage.get("artifact_id") or developer_lineage.get("ref"))
    lineage_signature = _text(developer_lineage.get("contract_signature"))
    if lineage_revision_ref and lineage_revision_ref != developer_revision_ref:
        raise HTTPException(status_code=422, detail="Package lineage developer revision does not match developer_revision_ref.")
    if lineage_signature and lineage_signature != contract_signature:
        raise HTTPException(status_code=422, detail="Package lineage developer contract signature does not match contract_signature.")

    current_source_inputs = _as_dict(current_data.get("source_inputs"))
    product_lineage = _as_dict(lineage.get("product_revision"))
    product_artifact_id = _text(product_lineage.get("artifact_id"))
    current_product_artifact_id = _text(current_source_inputs.get("product_revision_artifact_id"))
    if product_artifact_id and current_product_artifact_id and product_artifact_id != current_product_artifact_id:
        raise HTTPException(status_code=422, detail="Package lineage product revision does not match the saved Developer Definition source baseline.")
