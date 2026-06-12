"""Generated FastAPI application entrypoint for one contract service."""
from __future__ import annotations

import os
import uvicorn
from fastapi import FastAPI
from anip_fastapi import mount_anip
from anip_service import ANIPService

from ...capabilities import generated_capabilities_for_service

SERVICE_ID = "gtm-enrichment-service"

def _api_keys() -> dict[str, str]:
    raw = os.getenv("ANIP_API_KEYS_JSON")
    if not raw:
        return {"dev-admin-key": "human:local-developer"}
    try:
        import json
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items()}
    except Exception:
        pass
    return {"dev-admin-key": "human:local-developer"}

def _authenticate(bearer: str) -> str | None:
    return _api_keys().get(bearer)

def create_service() -> ANIPService:
    return ANIPService(
        service_id=SERVICE_ID,
        capabilities=generated_capabilities_for_service(SERVICE_ID),
        storage=":memory:",
        trust="signed",
        authenticate=_authenticate,
    )

def create_app() -> FastAPI:
    app = FastAPI()
    mount_anip(app, create_service(), health_endpoint=True)
    return app

app = create_app()

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '4100')))
