"""Manifest-aware GTM agent runtime."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel


PIPELINE_SERVICE_URL = os.getenv("PIPELINE_SERVICE_URL", "http://127.0.0.1:9200")
UI_PATH = Path(__file__).resolve().parents[2] / "ui" / "app" / "index.html"
DEFAULT_YEAR = "2017"
CATALOG_TTL_SECONDS = int(os.getenv("CATALOG_TTL_SECONDS", "30"))
REGIONS = {"central": "Central", "east": "East", "west": "West", "company": "company"}
STOPWORDS = {
    "and", "are", "for", "from", "into", "our", "that", "the", "their", "this", "what", "which", "why",
    "with", "your", "have", "will", "them", "then", "than", "show",
}
CAPABILITY_HINTS = {
    "gtm.pipeline_summary": {"pipeline", "summary", "stage", "breakdown", "forecast"},
    "gtm.stalled_opportunity_review": {"stalled", "stuck", "days", "open", "aging"},
    "gtm.account_risk_summary": {"risk", "risky", "top", "rank", "probability", "close"},
    "gtm.prepare_followup_tasks": {"follow", "follow-up", "followup", "task", "tasks", "prepare"},
}
CATALOG_CACHE: dict[str, Any] = {"expires_at": 0.0, "catalog": {}}


class AskRequest(BaseModel):
    question: str


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


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
            "subject": "agent:gtm-manifest-aware",
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
    payload = response.json()
    if response.is_error and "failure" not in payload:
        response.raise_for_status()
    return payload


def _load_catalog() -> dict[str, dict[str, Any]]:
    now = time.time()
    if CATALOG_CACHE["catalog"] and CATALOG_CACHE["expires_at"] > now:
        return CATALOG_CACHE["catalog"]

    discovery = httpx.get(f"{PIPELINE_SERVICE_URL}/.well-known/anip", timeout=20.0).json()["anip_discovery"]
    manifest = httpx.get(f"{PIPELINE_SERVICE_URL}/anip/manifest", timeout=20.0).json()
    discovery_caps = discovery.get("capabilities", {})
    manifest_caps = manifest.get("capabilities", {})

    catalog: dict[str, dict[str, Any]] = {}
    for capability_id in sorted(set(discovery_caps) | set(manifest_caps)):
        discovery_cap = discovery_caps.get(capability_id, {})
        manifest_cap = manifest_caps.get(capability_id, {})
        input_names = [
            item.get("name")
            for item in manifest_cap.get("inputs", [])
            if isinstance(item, dict) and item.get("name")
        ]
        catalog[capability_id] = {
            "description": discovery_cap.get("description") or manifest_cap.get("description") or "",
            "minimum_scope": discovery_cap.get("minimum_scope") or manifest_cap.get("minimum_scope") or [],
            "inputs": input_names,
            "side_effect": discovery_cap.get("side_effect") or manifest_cap.get("side_effect", {}).get("type"),
        }

    CATALOG_CACHE["catalog"] = catalog
    CATALOG_CACHE["expires_at"] = now + CATALOG_TTL_SECONDS
    return catalog


def _score_capability(question: str, capability_id: str, metadata: dict[str, Any]) -> tuple[int, list[str]]:
    lowered = question.lower()
    question_tokens = _tokenize(question)
    text_tokens = _tokenize(" ".join([
        capability_id,
        metadata.get("description", ""),
        " ".join(metadata.get("inputs", [])),
    ]))
    overlap = sorted(question_tokens & text_tokens)
    score = len(overlap)

    hint_hits = sorted(question_tokens & CAPABILITY_HINTS.get(capability_id, set()))
    score += len(hint_hits) * 3

    evidence: list[str] = []
    if overlap:
        evidence.append(f"metadata overlap: {', '.join(overlap[:6])}")
    if hint_hits:
        evidence.append(f"hint hits: {', '.join(hint_hits)}")

    if "raw" in question_tokens and capability_id == "gtm.pipeline_summary":
        score += 2
        evidence.append("raw export requests map to bounded pipeline summary handling")

    if "at risk" in lowered and capability_id == "gtm.account_risk_summary":
        score += 4
        evidence.append("explicit at-risk phrasing")

    if "follow-up" in lowered and capability_id == "gtm.prepare_followup_tasks":
        score += 4
        evidence.append("explicit follow-up phrasing")

    return score, evidence


def _choose_capability(question: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    catalog = _load_catalog()
    scored: list[dict[str, Any]] = []
    for capability_id, metadata in catalog.items():
        score, evidence = _score_capability(question, capability_id, metadata)
        scored.append({
            "capability": capability_id,
            "score": score,
            "evidence": evidence,
            "minimum_scope": metadata.get("minimum_scope", []),
        })
    scored.sort(key=lambda item: (item["score"], item["capability"]), reverse=True)
    chosen = scored[0]["capability"] if scored else "gtm.pipeline_summary"
    return chosen, scored[:4], catalog.get(chosen, {})


def _build_parameters(question: str, capability: str) -> tuple[dict[str, Any], list[str]]:
    lowered = question.lower()
    quarter = _parse_quarter(question)
    region = _parse_region(question)
    params: dict[str, Any] = {}
    notes: list[str] = []

    if capability == "gtm.prepare_followup_tasks":
        params.update({"ranking_basis": "risk_score", "top_n": _parse_top_n(question, 5)})
    elif capability == "gtm.stalled_opportunity_review":
        params.update({"min_days_open": 30, "limit": _parse_top_n(question, 10)})
        if "negotiation" in lowered:
            notes.append("The Phase 1 dataset uses Prospecting and Engaging instead of Negotiation.")
    elif capability == "gtm.account_risk_summary":
        params.update({"ranking_basis": "risk_score", "top_n": _parse_top_n(question, 10)})
    else:
        params.update({"detail_level": "stage_breakdown" if "stage" in lowered or "breakdown" in lowered else "summary"})
        if "raw" in lowered or "row-level" in lowered or "row level" in lowered:
            params["detail_level"] = "raw_records"

    if quarter:
        params["quarter"] = quarter
    if region:
        params["owner_scope"] = region

    return params, notes


app = FastAPI(title="GTM Manifest-Aware Agent")


@app.get("/")
def index():
    return FileResponse(UI_PATH)


@app.post("/api/ask")
def ask(req: AskRequest):
    capability, scored, metadata = _choose_capability(req.question)
    parameters, notes = _build_parameters(req.question, capability)
    result = _invoke(capability=capability, parameters=parameters, scope=metadata.get("minimum_scope", []))
    return {
        "runtime": "manifest-aware",
        "question": req.question,
        "selected_capability": capability,
        "selection_candidates": scored,
        "parameters": parameters,
        "notes": notes,
        "anip_result": result,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9300")))
