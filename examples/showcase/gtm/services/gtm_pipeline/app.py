"""ANIP GTM pipeline service for the Phase 1 showcase."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from anip_service import ANIPService
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest, RouteOverride
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http
from anip_studio import mount_anip_studio

from capabilities import (
    pipeline_summary,
    stalled_opportunity_review,
    account_risk_summary,
    prepare_followup_tasks,
)


API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:gtm-baseline",
    "demo-readonly-key": "agent:gtm-readonly",
}


service = ANIPService(
    service_id="anip-gtm-pipeline-showcase",
    capabilities=[
        pipeline_summary,
        stalled_opportunity_review,
        account_risk_summary,
        prepare_followup_tasks,
    ],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "unsigned"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
)

app = FastAPI(title="ANIP GTM Pipeline Showcase")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ANIP-Signature"],
)

mount_anip(app, service, health_endpoint=True)
mount_anip_rest(
    app,
    service,
    routes={
        "gtm.pipeline_summary": RouteOverride(path="/gtm/pipeline/summary", method="POST"),
        "gtm.stalled_opportunity_review": RouteOverride(path="/gtm/pipeline/stalled", method="POST"),
        "gtm.account_risk_summary": RouteOverride(path="/gtm/pipeline/risk", method="POST"),
        "gtm.prepare_followup_tasks": RouteOverride(path="/gtm/pipeline/followup-tasks", method="POST"),
    },
)
mount_anip_graphql(app, service)
mount_anip_mcp_http(app, service)
mount_anip_studio(app, service)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9200")))
