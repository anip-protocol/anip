"""Deterministic REST backend for GTM prioritization showcase flows."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


FIXTURES_PATH = Path(__file__).resolve().with_name("fixtures.json")
FIXTURES = json.loads(FIXTURES_PATH.read_text())


class ScoreRequest(BaseModel):
    cohort_ref: str
    limit: int | None = None
    owner_scope: str | None = None


class PrioritizeRequest(BaseModel):
    cohort_ref: str
    ranking_basis: str | None = None
    limit: int | None = None
    owner_scope: str | None = None


class RouteRequest(BaseModel):
    cohort_ref: str
    target_queue: str
    owner_scope: str | None = None
    dry_run: bool = True


def _require_auth(authorization: str | None) -> None:
    if not authorization or not authorization.strip().lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")


def _filter_scope(rows: list[dict[str, Any]], owner_scope: str | None) -> list[dict[str, Any]]:
    if not owner_scope or owner_scope in {"company", "all"}:
        return list(rows)
    return [row for row in rows if str(row.get("owner_scope") or "") == owner_scope]


def _bounded_limit(limit: int | None, default: int = 10, maximum: int = 25) -> int:
    return max(1, min(int(limit or default), maximum))


app = FastAPI(title="GTM Prioritization REST Backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/prioritization/score")
def score_leads(req: ScoreRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_auth(authorization)
    rows = FIXTURES["lead_cohorts"].get(req.cohort_ref)
    if rows is None:
        raise HTTPException(status_code=404, detail="Unknown cohort_ref")
    scoped = _filter_scope(rows, req.owner_scope)
    limit = _bounded_limit(req.limit)
    ordered = sorted(scoped, key=lambda item: (-int(item["priority_score"]), str(item["lead_id"])))[:limit]
    return {
        "cohort_ref": req.cohort_ref,
        "owner_scope": req.owner_scope or "company",
        "lead_scores": ordered,
    }


@app.post("/v1/prioritization/accounts")
def prioritize_accounts(req: PrioritizeRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_auth(authorization)
    rows = FIXTURES["account_cohorts"].get(req.cohort_ref)
    if rows is None:
        raise HTTPException(status_code=404, detail="Unknown cohort_ref")
    scoped = _filter_scope(rows, req.owner_scope)
    limit = _bounded_limit(req.limit)
    ordered = sorted(scoped, key=lambda item: (-int(item["priority_score"]), str(item["account_name"])))[:limit]
    return {
        "cohort_ref": req.cohort_ref,
        "owner_scope": req.owner_scope or "company",
        "ranking_basis": req.ranking_basis or "deal_likelihood",
        "accounts": ordered,
    }


@app.post("/v1/prioritization/route")
def route_leads(req: RouteRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_auth(authorization)
    rows = FIXTURES["lead_cohorts"].get(req.cohort_ref)
    if rows is None:
        raise HTTPException(status_code=404, detail="Unknown cohort_ref")
    scoped = _filter_scope(rows, req.owner_scope)
    preview = [
        {
            "lead_id": row["lead_id"],
            "account_name": row["account_name"],
            "owner_scope": row["owner_scope"],
            "priority_band": row["priority_band"],
            "priority_score": row["priority_score"],
            "recommended_queue": req.target_queue,
            "rationale": row["rationale"],
        }
        for row in sorted(scoped, key=lambda item: (-int(item["priority_score"]), str(item["lead_id"])))
    ]
    return {
        "cohort_ref": req.cohort_ref,
        "owner_scope": req.owner_scope or "company",
        "target_queue": req.target_queue,
        "dry_run": req.dry_run,
        "preview": preview,
    }
