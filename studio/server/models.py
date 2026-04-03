"""Pydantic request/response models for the ANIP Studio workspace API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class CreateProject(BaseModel):
    id: str
    name: str
    summary: str = ""
    domain: str = ""
    labels: list[str] = Field(default_factory=list)


class UpdateProject(BaseModel):
    name: Optional[str] = None
    summary: Optional[str] = None
    domain: Optional[str] = None
    labels: Optional[list[str]] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    summary: str
    domain: str
    labels: list[str]
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    requirements_count: int
    scenarios_count: int
    proposals_count: int
    evaluations_count: int


# ---------------------------------------------------------------------------
# Generic Artifacts (requirements_sets, scenarios)
# ---------------------------------------------------------------------------

class CreateArtifact(BaseModel):
    id: str
    title: str
    data: dict


class UpdateArtifact(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None


class ArtifactOut(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    data: dict
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

class CreateProposal(BaseModel):
    id: str
    title: str
    requirements_id: str
    data: dict


class ProposalOut(ArtifactOut):
    requirements_id: str


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

class CreateEvaluation(BaseModel):
    id: str
    proposal_id: str
    scenario_id: str
    requirements_id: str
    source: str = "manual"
    data: dict
    input_snapshot: dict


class EvaluationOut(BaseModel):
    id: str
    project_id: str
    proposal_id: str
    scenario_id: str
    requirements_id: str
    result: str
    source: str
    data: dict
    input_snapshot: dict
    created_at: datetime


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

class CreateVocabulary(BaseModel):
    project_id: Optional[str] = None
    category: str
    value: str
    origin: str = "custom"
    description: str = ""


class VocabularyOut(BaseModel):
    id: int
    project_id: Optional[str]
    category: str
    value: str
    origin: str
    description: str


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------

class ImportArtifact(BaseModel):
    type: str
    data: dict


class ImportRequest(BaseModel):
    artifacts: list[ImportArtifact]


class ImportResult(BaseModel):
    imported: int
    errors: list[str]
