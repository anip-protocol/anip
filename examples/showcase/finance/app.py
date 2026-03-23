"""ANIP Financial Operations Showcase — all four HTTP surfaces."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_service.retention import RetentionPolicy
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http
from anip_studio import mount_anip_studio
from anip_server import CheckpointPolicy

from capabilities import (
    query_portfolio, get_market_data, execute_trade, transfer_funds, generate_report,
)

API_KEYS = {
    "compliance-key": "human:compliance-officer@example.com",
    "trader-key": "human:trader@example.com",
    "partner-key": "partner:external-fund@example.com",
}

service = ANIPService(
    service_id="anip-finance-showcase",
    capabilities=[query_portfolio, get_market_data, execute_trade, transfer_funds, generate_report],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "anchored"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
    disclosure_level="policy",
    disclosure_policy={
        "internal": "full",
        "partner": "reduced",
        "default": "redacted",
    },
    retention_policy=RetentionPolicy(
        tier_to_duration={
            "long": "P365D",
            "medium": "P90D",
            "short": "P7D",
            "aggregate_only": "P1D",
        },
    ),
    checkpoint_policy=CheckpointPolicy(interval_seconds=30),
)

app = FastAPI(title="ANIP Financial Operations Showcase")
mount_anip(app, service, health_endpoint=True)
mount_anip_rest(app, service)
mount_anip_graphql(app, service)
mount_anip_mcp_http(app, service)
mount_anip_studio(app, service)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
