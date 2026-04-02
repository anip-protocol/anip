"""Thin validation API wrapping the ANIP evaluator."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
from pathlib import Path

# Add tooling to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tooling" / "bin"))
from anip_design_validate import evaluate, validate_payload, load_json

app = FastAPI(title="ANIP Studio Validation API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "tooling" / "schemas"

class ValidateRequest(BaseModel):
    requirements: dict
    proposal: dict
    scenario: dict

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

@app.get("/api/health")
async def health():
    return {"status": "ok"}
