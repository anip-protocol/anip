"""Baseline GTM agent runtime and minimal UI."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel


PIPELINE_SERVICE_URL = os.getenv("PIPELINE_SERVICE_URL", "http://127.0.0.1:9200")
UI_PATH = Path(__file__).resolve().parents[2] / "ui" / "app" / "index.html"
DEFAULT_YEAR = "2017"
REGIONS = {"central": "Central", "east": "East", "west": "West"}


class AskRequest(BaseModel):
    question: str


def _parse_quarter(text: str) -> str | None:
    text_upper = text.upper()
    match = re.search(r"(20\d{2})[-\s]?Q([1-4])", text_upper)
    if match:
        return f"{match.group(1)}-Q{match.group(2)}"
    match = re.search(r"\bQ([1-4])\b", text_upper)
    if match:
        return f"{DEFAULT_YEAR}-Q{match.group(1)}"
    return None


def _parse_region(text: str) -> str | None:
    lowered = text.lower()
    for key, value in REGIONS.items():
        if key in lowered:
            return value
    return None


def _parse_top_n(text: str, default: int) -> int:
    match = re.search(r"\btop\s+(\d+)\b", text.lower())
    if match:
        return int(match.group(1))
    return default


def _issue_token(capability: str, scope: list[str]) -> str:
    response = httpx.post(
        f"{PIPELINE_SERVICE_URL}/anip/tokens",
        json={
            "subject": "agent:gtm-baseline",
            "scope": scope,
            "capability": capability,
        },
        headers={"Authorization": "Bearer demo-human-key"},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("issued"):
        raise RuntimeError(f"Token issuance failed: {payload}")
    return payload["token"]


def _invoke(capability: str, parameters: dict[str, Any], scope: list[str]) -> dict[str, Any]:
    token = _issue_token(capability=capability, scope=scope)
    response = httpx.post(
        f"{PIPELINE_SERVICE_URL}/anip/invoke/{capability}",
        json={"parameters": parameters},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    try:
        payload = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError(f"Pipeline service returned non-JSON response: {response.text}") from None

    if response.is_error and "failure" not in payload:
        response.raise_for_status()

    return payload


def _route_question(question: str) -> tuple[str, dict[str, Any], list[str], list[str]]:
    lowered = question.lower()
    quarter = _parse_quarter(question)
    region = _parse_region(question)
    notes: list[str] = []

    if "follow-up" in lowered or "follow up" in lowered:
        capability = "gtm.prepare_followup_tasks"
        params = {"ranking_basis": "risk_score", "top_n": _parse_top_n(question, 5)}
        scope = ["gtm.pipeline.followup"]
    elif "stuck" in lowered or "stalled" in lowered:
        capability = "gtm.stalled_opportunity_review"
        params = {"min_days_open": 30, "limit": _parse_top_n(question, 10)}
        scope = ["gtm.pipeline.read"]
        if "negotiation" in lowered:
            notes.append("The Maven Phase 1 dataset uses Prospecting and Engaging rather than Negotiation.")
    elif "at risk" in lowered or "risk" in lowered or "top deals" in lowered or "close probability" in lowered:
        capability = "gtm.account_risk_summary"
        params = {"ranking_basis": "risk_score", "top_n": _parse_top_n(question, 10)}
        scope = ["gtm.pipeline.read"]
    else:
        capability = "gtm.pipeline_summary"
        params = {"detail_level": "summary"}
        scope = ["gtm.pipeline.read"]
        if "raw" in lowered or "row-level" in lowered or "row level" in lowered:
            params["detail_level"] = "raw_records"

    if quarter:
        params["quarter"] = quarter
    if region:
        params["owner_scope"] = region

    return capability, params, scope, notes


app = FastAPI(title="GTM Baseline Agent")


@app.get("/")
def index():
    return FileResponse(UI_PATH)


@app.post("/api/ask")
def ask(req: AskRequest):
    capability, params, scope, notes = _route_question(req.question)
    result = _invoke(capability=capability, parameters=params, scope=scope)
    return {
        "question": req.question,
        "selected_capability": capability,
        "parameters": params,
        "notes": notes,
        "anip_result": result,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9300")))
