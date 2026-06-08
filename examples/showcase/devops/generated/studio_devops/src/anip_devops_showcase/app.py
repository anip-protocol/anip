"""Generated FastAPI application entrypoint."""
from __future__ import annotations

import os
import uvicorn
from fastapi import FastAPI
from anip_fastapi import mount_anip
from anip_service import ANIPService

from .capabilities import generated_capabilities_for_service
from .runtime_target import RUNTIME_TARGET

SERVICE_ID = "devops-infra-service"

def _authenticate(bearer: str) -> str | None:
    return "human:local-developer" if bearer == "dev-admin-key" else None

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
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '9130')))
