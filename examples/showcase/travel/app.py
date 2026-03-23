"""ANIP Travel Booking Showcase — all four HTTP surfaces."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http

from capabilities import search_flights, check_availability, book_flight, cancel_booking

API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

service = ANIPService(
    service_id="anip-travel-showcase",
    capabilities=[search_flights, check_availability, book_flight, cancel_booking],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
)

app = FastAPI(title="ANIP Travel Booking Showcase")
mount_anip(app, service, health_endpoint=True)
mount_anip_rest(app, service)
mount_anip_graphql(app, service)
mount_anip_mcp_http(app, service)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
