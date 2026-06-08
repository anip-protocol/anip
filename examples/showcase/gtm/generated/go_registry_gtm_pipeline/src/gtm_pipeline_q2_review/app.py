"""Generated FastAPI application entrypoint."""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from anip_fastapi import mount_anip
from anip_service import ANIPService

from .capabilities import generated_capabilities
from .runtime_target import RUNTIME_TARGET

def _authenticate(bearer: str) -> str | None:
    return "human:local-developer" if bearer == "dev-admin-key" else None

def create_service() -> ANIPService:
    return ANIPService(
        service_id=RUNTIME_TARGET["system_name"],
        capabilities=generated_capabilities,
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
    uvicorn.run(app, host='127.0.0.1', port=4100)
