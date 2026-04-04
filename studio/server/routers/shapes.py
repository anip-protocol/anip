"""CRUD routes for project shapes + contract expectation derivation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from psycopg.errors import UniqueViolation

from ..db import get_pool
from ..derivation import derive_contract_expectations
from ..models import CreateShape, ShapeOut, UpdateShape
from ..repository import (
    NotFoundError,
    ProjectCoherenceError,
    ReferentialIntegrityError,
)
from ..shape_integrity import ShapeIntegrityError
from .. import repository

router = APIRouter(prefix="/api/projects/{pid}", tags=["shapes"])


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
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="Duplicate ID")

    return wrapper


# ---------------------------------------------------------------------------
# Shape CRUD
# ---------------------------------------------------------------------------

@router.get("/shapes", response_model=list[ShapeOut])
@_handle_errors
def list_shapes(pid: str):
    with get_pool().connection() as conn:
        return repository.list_shapes(conn, pid)


@router.post("/shapes", response_model=ShapeOut, status_code=201)
@_handle_errors
def create_shape(pid: str, body: CreateShape):
    with get_pool().connection() as conn:
        return repository.create_shape(
            conn,
            project_id=pid,
            shape_id=body.id,
            title=body.title,
            requirements_id=body.requirements_id,
            data=body.data,
        )


@router.get("/shapes/{shape_id}", response_model=ShapeOut)
@_handle_errors
def get_shape(pid: str, shape_id: str):
    with get_pool().connection() as conn:
        return repository.get_shape(conn, pid, shape_id)


@router.put("/shapes/{shape_id}", response_model=ShapeOut)
@_handle_errors
def update_shape(pid: str, shape_id: str, body: UpdateShape):
    with get_pool().connection() as conn:
        return repository.update_shape(
            conn, pid, shape_id, **body.model_dump(exclude_unset=True),
        )


@router.delete("/shapes/{shape_id}", status_code=204)
@_handle_errors
def delete_shape(pid: str, shape_id: str):
    with get_pool().connection() as conn:
        repository.delete_shape(conn, pid, shape_id)


# ---------------------------------------------------------------------------
# Contract Expectation Derivation
# ---------------------------------------------------------------------------

@router.get("/shapes/{shape_id}/expectations")
@_handle_errors
def get_shape_expectations(pid: str, shape_id: str):
    with get_pool().connection() as conn:
        shape = repository.get_shape(conn, pid, shape_id)
        req = repository.get_requirements(conn, pid, shape["requirements_id"])
        expectations = derive_contract_expectations(shape["data"], req["data"])
        return {"expectations": expectations}
