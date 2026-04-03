"""CRUD routes for project artifacts: requirements, scenarios, proposals, evaluations."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from ..db import get_pool
from ..models import (
    ArtifactOut,
    CreateArtifact,
    CreateEvaluation,
    CreateProposal,
    EvaluationOut,
    ProposalOut,
    UpdateArtifact,
    SetRequirementsRole,
)
from ..repository import (
    NotFoundError,
    ProjectCoherenceError,
    ReferentialIntegrityError,
)
from .. import repository

router = APIRouter(prefix="/api/projects/{pid}", tags=["artifacts"])


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
):
    with get_pool().connection() as conn:
        return repository.list_evaluations(
            conn, pid, scenario_id=scenario_id, proposal_id=proposal_id,
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
