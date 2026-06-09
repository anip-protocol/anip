"""CRUD routes for persisted data-access design drafts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from ..db import get_pool
from ..data_access_types import (
    CreateDataAccessProjectRequest,
    DataAccessProjectRecord,
    DataAccessProjectSummary,
    UpdateDataAccessProjectRequest,
)
from ..repository import NotFoundError
from .. import repository

router = APIRouter(prefix="/api/data-access-projects", tags=["data-access-projects"])


def _record(row: dict) -> DataAccessProjectRecord:
    return DataAccessProjectRecord(
        id=row["id"],
        name=row["name"],
        studio_project_id=row.get("studio_project_id"),
        state=row["state"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


def _summary(row: dict) -> DataAccessProjectSummary:
    return DataAccessProjectSummary(
        id=row["id"],
        name=row["name"],
        studio_project_id=row.get("studio_project_id"),
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


@router.get("", response_model=list[DataAccessProjectSummary])
def list_data_access_projects(studio_project_id: str | None = Query(default=None)):
    with get_pool().connection() as conn:
        return [_summary(row) for row in repository.list_data_access_projects(conn, studio_project_id)]


@router.post("", response_model=DataAccessProjectRecord, status_code=201)
def create_data_access_project(body: CreateDataAccessProjectRequest):
    try:
        with get_pool().connection() as conn:
            row = repository.create_data_access_project(
                conn,
                body.id,
                body.state.model_dump(mode="json"),
                studio_project_id=body.studio_project_id,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Data access project {body.id!r} already exists")
    return _record(row)


@router.get("/{project_id}", response_model=DataAccessProjectRecord)
def get_data_access_project(project_id: str):
    try:
        with get_pool().connection() as conn:
            row = repository.get_data_access_project(conn, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _record(row)


@router.put("/{project_id}", response_model=DataAccessProjectRecord)
def update_data_access_project(project_id: str, body: UpdateDataAccessProjectRequest):
    try:
        with get_pool().connection() as conn:
            row = repository.update_data_access_project(
                conn,
                project_id,
                body.state.model_dump(mode="json"),
                studio_project_id=body.studio_project_id,
            )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _record(row)


@router.delete("/{project_id}", status_code=204)
def delete_data_access_project(project_id: str):
    try:
        with get_pool().connection() as conn:
            repository.delete_data_access_project(conn, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
