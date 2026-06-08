"""CRUD routes for /api/projects."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from ..db import get_pool
from ..models import CloneProject, CreateProject, ProjectDetail, ProjectOut, UpdateProject
from ..repository import NotFoundError

from .. import repository

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(workspace_id: str | None = Query(default=None)):
    with get_pool().connection() as conn:
        return repository.list_projects(conn, workspace_id=workspace_id)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: CreateProject):
    try:
        with get_pool().connection() as conn:
            return repository.create_project(
                conn,
                project_id=body.id,
                workspace_id=body.workspace_id,
                name=body.name,
                summary=body.summary,
                domain=body.domain,
                labels=body.labels,
                project_type=body.project_type,
                integration_profile=body.integration_profile,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Project {body.id!r} already exists")


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str):
    try:
        with get_pool().connection() as conn:
            return repository.get_project_detail(conn, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: UpdateProject):
    try:
        with get_pool().connection() as conn:
            return repository.update_project(
                conn, project_id, **body.model_dump(exclude_unset=True)
            )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/clone", response_model=ProjectOut, status_code=201)
def clone_project(project_id: str, body: CloneProject):
    try:
        with get_pool().connection() as conn:
            return repository.clone_project(
                conn,
                source_project_id=project_id,
                target_project_id=body.id,
                target_workspace_id=body.workspace_id,
                name=body.name,
                summary=body.summary,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Project {body.id!r} already exists")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str):
    try:
        with get_pool().connection() as conn:
            repository.delete_project(conn, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
