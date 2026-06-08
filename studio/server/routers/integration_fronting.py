"""Routes for deterministic integration-fronting project metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from psycopg.errors import UniqueViolation

from .. import repository
from ..db import get_pool
from ..models import (
    CreateIntegrationDiscoveryRecord,
    CreateWorkspaceConnection,
    IntegrationDiscoveryRecordOut,
    UpdateIntegrationDiscoveryRecord,
    UpdateWorkspaceConnection,
    WorkspaceConnectionOut,
)
from ..repository import NotFoundError, ProjectCoherenceError

router = APIRouter(tags=["integration-fronting"])


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _bad_request(exc: ProjectCoherenceError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/api/workspaces/{workspace_id}/connections", response_model=list[WorkspaceConnectionOut])
def list_workspace_connections(workspace_id: str):
    try:
        with get_pool().connection() as conn:
            return repository.list_workspace_connections(conn, workspace_id)
    except NotFoundError as exc:
        raise _not_found(exc)


@router.post("/api/workspaces/{workspace_id}/connections", response_model=WorkspaceConnectionOut, status_code=201)
def create_workspace_connection(workspace_id: str, body: CreateWorkspaceConnection):
    try:
        with get_pool().connection() as conn:
            return repository.create_workspace_connection(
                conn,
                workspace_id=workspace_id,
                connection_id=body.id,
                display_name=body.display_name,
                backend_kind=body.backend_kind,
                system_kind=body.system_kind,
                endpoint_ref=body.endpoint_ref,
                auth_mode=body.auth_mode,
                identity_provider_ref=body.identity_provider_ref,
                secret_ref=body.secret_ref,
                allowed_project_refs=body.allowed_project_refs,
                metadata=body.metadata,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Workspace connection {body.id!r} already exists")
    except NotFoundError as exc:
        raise _not_found(exc)


@router.put("/api/workspaces/{workspace_id}/connections/{connection_id}", response_model=WorkspaceConnectionOut)
def update_workspace_connection(workspace_id: str, connection_id: str, body: UpdateWorkspaceConnection):
    try:
        with get_pool().connection() as conn:
            return repository.update_workspace_connection(
                conn,
                workspace_id,
                connection_id,
                **body.model_dump(exclude_unset=True),
            )
    except NotFoundError as exc:
        raise _not_found(exc)


@router.delete("/api/workspaces/{workspace_id}/connections/{connection_id}", status_code=204)
def delete_workspace_connection(workspace_id: str, connection_id: str):
    try:
        with get_pool().connection() as conn:
            repository.delete_workspace_connection(conn, workspace_id, connection_id)
    except NotFoundError as exc:
        raise _not_found(exc)


@router.get("/api/projects/{project_id}/integration-discovery-records", response_model=list[IntegrationDiscoveryRecordOut])
def list_integration_discovery_records(project_id: str):
    try:
        with get_pool().connection() as conn:
            return repository.list_integration_discovery_records(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(exc)


@router.post("/api/projects/{project_id}/integration-discovery-records", response_model=IntegrationDiscoveryRecordOut, status_code=201)
def create_integration_discovery_record(project_id: str, body: CreateIntegrationDiscoveryRecord):
    try:
        with get_pool().connection() as conn:
            return repository.create_integration_discovery_record(
                conn,
                project_id=project_id,
                record_id=body.id,
                connection_id=body.connection_id,
                operation_id=body.operation_id,
                backend_kind=body.backend_kind,
                method=body.method,
                path_template=body.path_template,
                side_effect_level=body.side_effect_level,
                input_schema_summary=body.input_schema_summary,
                risk_notes=body.risk_notes,
                data=body.data,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Integration discovery record {body.id!r} already exists")
    except NotFoundError as exc:
        raise _not_found(exc)
    except ProjectCoherenceError as exc:
        raise _bad_request(exc)


@router.put("/api/projects/{project_id}/integration-discovery-records/{record_id}", response_model=IntegrationDiscoveryRecordOut)
def update_integration_discovery_record(project_id: str, record_id: str, body: UpdateIntegrationDiscoveryRecord):
    try:
        with get_pool().connection() as conn:
            return repository.update_integration_discovery_record(
                conn,
                project_id,
                record_id,
                **body.model_dump(exclude_unset=True),
            )
    except NotFoundError as exc:
        raise _not_found(exc)
    except ProjectCoherenceError as exc:
        raise _bad_request(exc)


@router.delete("/api/projects/{project_id}/integration-discovery-records/{record_id}", status_code=204)
def delete_integration_discovery_record(project_id: str, record_id: str):
    try:
        with get_pool().connection() as conn:
            repository.delete_integration_discovery_record(conn, project_id, record_id)
    except NotFoundError as exc:
        raise _not_found(exc)
