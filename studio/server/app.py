"""Thin validation API wrapping the ANIP evaluator, plus project workspace API."""

from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add tooling to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tooling" / "bin"))
from anip_design_validate import evaluate, validate_payload  # noqa: E402
from .derivation import build_shape_backed_proposal  # noqa: E402

from .db import get_pool, init_db  # noqa: E402
from .repository import load_vocabulary_defaults  # noqa: E402
from .routers import projects, artifacts, shapes, vocabulary, import_export, workspaces  # noqa: E402

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "tooling" / "schemas"
VOCAB_DEFAULTS_PATH = Path(__file__).parent / "vocabulary_defaults.json"


class ValidateRequest(BaseModel):
    requirements: dict
    proposal: dict
    scenario: dict


class ValidateShapeRequest(BaseModel):
    requirements: dict
    shape: dict
    scenario: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with get_pool().connection() as conn:
        load_vocabulary_defaults(conn, str(VOCAB_DEFAULTS_PATH))
    yield


app = FastAPI(title="ANIP Studio Validation API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include routers ---
app.include_router(projects.router)
app.include_router(workspaces.router)
app.include_router(artifacts.router)
app.include_router(shapes.router)
app.include_router(vocabulary.router)
app.include_router(import_export.router)


# --- Existing endpoints (unchanged) ---

@app.post("/api/validate")
async def validate_endpoint(req: ValidateRequest):
    try:
        validate_payload(req.requirements, SCHEMA_DIR / "requirements.schema.json")
        validate_payload(req.proposal, SCHEMA_DIR / "proposal.schema.json")
        validate_payload(req.scenario, SCHEMA_DIR / "scenario.schema.json")
        result = evaluate(req.requirements, req.proposal, req.scenario)
        validate_payload(result, SCHEMA_DIR / "evaluation.schema.json")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/validate-shape")
async def validate_shape_endpoint(req: ValidateShapeRequest):
    try:
        validate_payload(req.requirements, SCHEMA_DIR / "requirements.schema.json")
        validate_payload(req.shape, SCHEMA_DIR / "shape.schema.json")
        validate_payload(req.scenario, SCHEMA_DIR / "scenario.schema.json")
        proposal = build_shape_backed_proposal(req.shape, req.requirements)
        validate_payload(proposal, SCHEMA_DIR / "proposal.schema.json")
        result = evaluate(req.requirements, proposal, req.scenario)
        validate_payload(result, SCHEMA_DIR / "evaluation.schema.json")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/health")
async def health():
    return {"status": "ok"}
