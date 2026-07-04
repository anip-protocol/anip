from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="GTM Agent Desktop API")


@app.get("/desktop/health")
def health() -> dict[str, str]:
    return {"status": "ok", "runtime": "gtm-agent-desktop"}


@app.get("/desktop/config")
def config() -> JSONResponse:
    has_key = bool(
        (os.getenv("ANIP_AGENT_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    )
    return JSONResponse(
        {
            "runtime": "gtm-agent-desktop",
            "requires_api_key": not has_key,
            "docker_required": False,
            "embedded_services": ["pipeline", "enrichment", "prioritization", "outreach"],
            "data_profile": "bundled_gtm_sample",
        }
    )
