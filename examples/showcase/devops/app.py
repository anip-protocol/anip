"""ANIP DevOps Infrastructure Showcase — all four HTTP surfaces."""
import os
from fastapi import FastAPI
from anip_service import ANIPService, ANIPHooks, LoggingHooks
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http
from anip_studio import mount_anip_studio

from capabilities import (
    list_deployments, get_service_health, scale_replicas,
    update_config, rollback_deployment, delete_resource,
)

API_KEYS = {
    "platform-key": "human:platform-engineer@example.com",
    "appteam-key": "human:app-developer@example.com",
    "ci-key": "agent:ci-pipeline",
}

# --- Observability hooks: log on invocation start/complete ---
hooks = ANIPHooks(
    logging=LoggingHooks(
        on_invocation_start=lambda info: print(
            f"[ANIP] invoke-start  capability={info.get('capability')}  subject={info.get('subject')}"
        ),
        on_invocation_end=lambda info: print(
            f"[ANIP] invoke-end    capability={info.get('capability')}  success={info.get('success')}  duration_ms={info.get('duration_ms')}"
        ),
    ),
)

service = ANIPService(
    service_id="anip-devops-showcase",
    capabilities=[
        list_deployments, get_service_health, scale_replicas,
        update_config, rollback_deployment, delete_resource,
    ],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
    aggregation_window=60,
    hooks=hooks,
)

app = FastAPI(title="ANIP DevOps Infrastructure Showcase")
mount_anip(app, service, health_endpoint=True)
mount_anip_rest(app, service)
mount_anip_graphql(app, service)
mount_anip_mcp_http(app, service)
mount_anip_studio(app, service)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9100")))
