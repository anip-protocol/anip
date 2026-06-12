"""Generated prioritization service entrypoint with native approval routes."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from anip_fastapi import mount_anip
from anip_service import ANIPService

from ...capabilities import generated_capabilities_for_service
from ...runtime.actor import authenticate_bearer, parse_actor_principal
from ...runtime.approval_store import approve_request, list_approval_requests

SERVICE_ID = "gtm-prioritization-service"


def _authenticate(bearer: str) -> str | None:
    return authenticate_bearer(bearer) or ("human:local-developer" if bearer == "dev-admin-key" else None)


def create_service() -> ANIPService:
    return ANIPService(
        service_id=SERVICE_ID,
        capabilities=generated_capabilities_for_service(SERVICE_ID),
        storage=":memory:",
        trust="signed",
        authenticate=_authenticate,
    )


def _actor_from_request(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.startswith("Bearer ") else ""
    principal = _authenticate(bearer)
    if not principal:
        raise HTTPException(status_code=401, detail="Valid actor bearer required")
    return parse_actor_principal(principal)


def create_app() -> FastAPI:
    app = FastAPI()
    mount_anip(app, create_service(), health_endpoint=True)

    @app.get("/gtm/approvals")
    async def list_approvals(request: Request, status: str | None = None):
        actor = _actor_from_request(request)
        entries = list_approval_requests(status=status)
        if actor.get("can_approve_routing") or actor.get("can_approve_followup"):
            return {"entries": entries}
        actor_id = actor.get("actor_id")
        return {"entries": [item for item in entries if item.get("requested_by", {}).get("actor_id") == actor_id]}

    @app.post("/gtm/approvals/{approval_request_id}/approve")
    async def approve(approval_request_id: str, request: Request):
        actor = _actor_from_request(request)
        if not actor.get("can_approve_routing") and not actor.get("can_approve_followup"):
            raise HTTPException(status_code=403, detail="This actor cannot approve GTM actions")
        approval = approve_request(approval_request_id, actor)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval request not found")
        return {"approval": approval}

    return app


app = create_app()
