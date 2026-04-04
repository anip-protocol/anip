"""CRUD routes for /api/workspaces."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from psycopg.errors import UniqueViolation

from .. import repository
from ..db import get_pool
from ..models import CreateWorkspace, UpdateWorkspace, WorkspaceDetail, WorkspaceOut
from ..repository import NotFoundError

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceDetail])
def list_workspaces():
    with get_pool().connection() as conn:
        return repository.list_workspaces(conn)


@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(body: CreateWorkspace):
    try:
        with get_pool().connection() as conn:
            return repository.create_workspace(
                conn,
                workspace_id=body.id,
                name=body.name,
                summary=body.summary,
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Workspace {body.id!r} already exists")


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(workspace_id: str):
    try:
        with get_pool().connection() as conn:
            return repository.get_workspace(conn, workspace_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(workspace_id: str, body: UpdateWorkspace):
    try:
        with get_pool().connection() as conn:
            return repository.update_workspace(
                conn, workspace_id, **body.model_dump(exclude_unset=True)
            )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str):
    try:
        with get_pool().connection() as conn:
            repository.delete_workspace(conn, workspace_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
