"""ANIP Flight Demo — configured via the ANIP service runtime."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_fastapi import mount_anip

from anip_flight_demo.capabilities.search_flights import search_flights
from anip_flight_demo.capabilities.book_flight import book_flight

# Bootstrap authentication: API keys -> principal identities.
API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

service = ANIPService(
    service_id=os.getenv("ANIP_SERVICE_ID", "anip-flight-service"),
    capabilities=[search_flights, book_flight],
    storage=f"sqlite:///{os.getenv('ANIP_DB_PATH', 'anip.db')}",
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
)

app = FastAPI(title="ANIP Flight Service")
mount_anip(app, service)
