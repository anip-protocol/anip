"""CRUD routes for persisted application-integration design drafts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from ..db import get_pool
from ..application_integration_types import (
    ApplicationIntegrationProjectRecord,
    ApplicationIntegrationProjectSummary,
    CreateApplicationIntegrationProjectRequest,
    UpdateApplicationIntegrationProjectRequest,
)
from ..repository import NotFoundError
from .. import repository

router = APIRouter(prefix="/api/application-integration-projects", tags=["application-integration-projects"])


def _record(row: dict) -> ApplicationIntegrationProjectRecord:
    return ApplicationIntegrationProjectRecord(
        id=row["id"],
        title=row["title"],
        studio_project_id=row.get("studio_project_id"),
        state=row["state"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


def _summary(row: dict) -> ApplicationIntegrationProjectSummary:
    return ApplicationIntegrationProjectSummary(
        id=row["id"],
        title=row["title"],
        studio_project_id=row.get("studio_project_id"),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


@router.get("", response_model=list[ApplicationIntegrationProjectSummary])
def list_application_integration_projects(studio_project_id: str | None = Query(default=None)):
    with get_pool().connection() as conn:
        return [_summary(row) for row in repository.list_application_integration_projects(conn, studio_project_id)]


@router.post("", response_model=ApplicationIntegrationProjectRecord, status_code=201)
def create_application_integration_project(body: CreateApplicationIntegrationProjectRequest):
    try:
        with get_pool().connection() as conn:
            row = repository.create_application_integration_project(
                conn,
                body.id,
                body.state.model_dump(mode="json"),
                studio_project_id=body.studio_project_id,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Application integration project {body.id!r} already exists")
    return _record(row)


@router.get("/{project_id}", response_model=ApplicationIntegrationProjectRecord)
def get_application_integration_project(project_id: str):
    try:
        with get_pool().connection() as conn:
            row = repository.get_application_integration_project(conn, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _record(row)


@router.put("/{project_id}", response_model=ApplicationIntegrationProjectRecord)
def update_application_integration_project(project_id: str, body: UpdateApplicationIntegrationProjectRequest):
    try:
        with get_pool().connection() as conn:
            row = repository.update_application_integration_project(
                conn,
                project_id,
                body.state.model_dump(mode="json"),
                studio_project_id=body.studio_project_id,
            )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _record(row)


@router.delete("/{project_id}", status_code=204)
def delete_application_integration_project(project_id: str):
    try:
        with get_pool().connection() as conn:
            repository.delete_application_integration_project(conn, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
