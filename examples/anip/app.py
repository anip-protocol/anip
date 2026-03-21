"""ANIP Flight Demo — configured via the ANIP service runtime."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_fastapi import mount_anip

from anip_flight_demo.capabilities.search_flights import search_flights
from anip_flight_demo.capabilities.book_flight import book_flight
from anip_flight_demo.oidc import OidcValidator

# Bootstrap authentication: API keys -> principal identities.
API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

SERVICE_ID = os.getenv("ANIP_SERVICE_ID", "anip-flight-service")

# Optional OIDC authentication — enabled when OIDC_ISSUER_URL is set
_oidc_validator = (
    OidcValidator(
        issuer_url=os.getenv("OIDC_ISSUER_URL", ""),
        audience=os.getenv("OIDC_AUDIENCE", SERVICE_ID),
        jwks_url=os.getenv("OIDC_JWKS_URL"),
    )
    if os.getenv("OIDC_ISSUER_URL")
    else None
)


def _authenticate(bearer: str) -> str | None:
    """Bootstrap auth: API keys, then OIDC (if configured).

    Synchronous — matches the ANIPService authenticate callback signature.
    """
    # 1. API key map
    principal = API_KEYS.get(bearer)
    if principal:
        return principal
    # 2. OIDC (if configured)
    if _oidc_validator:
        return _oidc_validator.validate(bearer)
    # 3. Not recognized — service will try ANIP JWT separately
    return None


service = ANIPService(
    service_id=SERVICE_ID,
    capabilities=[search_flights, book_flight],
    storage=f"sqlite:///{os.getenv('ANIP_DB_PATH', 'anip.db')}",
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=_authenticate,
)

app = FastAPI(title="ANIP Flight Service")
mount_anip(app, service)
