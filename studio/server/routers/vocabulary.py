"""Routes for /api/vocabulary."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from psycopg.errors import UniqueViolation

from ..db import get_pool
from ..models import CreateVocabulary, VocabularyOut
from ..repository import NotFoundError
from .. import repository

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("", response_model=list[VocabularyOut])
def list_vocabulary(
    category: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
):
    with get_pool().connection() as conn:
        return repository.list_vocabulary(
            conn, category=category, project_id=project_id,
        )


@router.post("", response_model=VocabularyOut, status_code=201)
def create_vocabulary(body: CreateVocabulary):
    try:
        with get_pool().connection() as conn:
            return repository.create_vocabulary(
                conn,
                project_id=body.project_id,
                category=body.category,
                value=body.value,
                origin=body.origin,
                description=body.description,
            )
    except UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail=f"Vocabulary entry ({body.category}, {body.value}) already exists",
        )


@router.delete("/{vocab_id}", status_code=204)
def delete_vocabulary(vocab_id: int):
    try:
        with get_pool().connection() as conn:
            repository.delete_vocabulary(conn, vocab_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
