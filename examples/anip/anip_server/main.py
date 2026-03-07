"""ANIP reference server — flight booking service."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .capabilities import book_flight, search_flights
from .primitives.delegation import register_token, validate_delegation
from .primitives.manifest import build_manifest
from .primitives.models import (
    ANIPFailure,
    DelegationToken,
    InvokeRequest,
    InvokeResponse,
    PermissionResponse,
    Resolution,
)
from .primitives.permissions import discover_permissions

app = FastAPI(
    title="ANIP Flight Service",
    description="Reference implementation of the Agent-Native Interface Protocol",
    version="0.1.0",
)

# Build manifest once at startup
_manifest = build_manifest()

# Capability registry — maps name to invoke function
_capability_handlers = {
    "search_flights": search_flights.invoke,
    "book_flight": book_flight.invoke,
}


# --- Profile Handshake ---


@app.get("/anip/manifest")
def get_manifest():
    """Profile handshake — returns the full ANIP manifest."""
    return _manifest.model_dump()


class ProfileRequirements(BaseModel):
    required_profiles: dict[str, str]  # e.g. {"core": "1.0", "cost": "1.0"}


@app.post("/anip/handshake")
def profile_handshake(requirements: ProfileRequirements):
    """Check if this service meets the agent's profile requirements."""
    service_profiles = _manifest.profile.model_dump(exclude_none=True)
    missing = {}
    for profile, required_version in requirements.required_profiles.items():
        if profile not in service_profiles:
            missing[profile] = f"not supported (required: {required_version})"
        elif service_profiles[profile] != required_version:
            missing[profile] = (
                f"version mismatch: have {service_profiles[profile]}, "
                f"need {required_version}"
            )

    return {
        "compatible": len(missing) == 0,
        "service_profiles": service_profiles,
        "missing": missing if missing else None,
    }


# --- Delegation Token Registration ---


@app.post("/anip/tokens/register")
def register_delegation_token(token: DelegationToken):
    """Register a delegation token with the service.

    In production, tokens would be cryptographically verified.
    In this demo, we trust-on-declaration (per ANIP v1 spec).
    """
    register_token(token)
    return {"registered": True, "token_id": token.token_id}


# --- Permission Discovery ---


@app.post("/anip/permissions", response_model=PermissionResponse)
def query_permissions(token: DelegationToken):
    """Discover what the agent can do given its delegation chain."""
    return discover_permissions(token, _manifest.capabilities)


# --- Capability Invocation ---


@app.post("/anip/invoke/{capability_name}", response_model=InvokeResponse)
def invoke_capability(capability_name: str, request: InvokeRequest):
    """Invoke an ANIP capability with full delegation chain validation."""
    # 1. Check capability exists
    if capability_name not in _capability_handlers:
        return InvokeResponse(
            success=False,
            failure=ANIPFailure(
                type="unknown_capability",
                detail=f"capability '{capability_name}' does not exist",
                resolution=Resolution(action="check_manifest"),
                retry=False,
            ),
        )

    # 2. Get the capability declaration for scope requirements
    cap_declaration = _manifest.capabilities[capability_name]

    # 3. Validate delegation chain
    delegation_failure = validate_delegation(
        token=request.delegation_token,
        required_scope=cap_declaration.required_scope,
        capability_name=capability_name,
    )
    if delegation_failure is not None:
        return InvokeResponse(success=False, failure=delegation_failure)

    # 4. Invoke the capability
    handler = _capability_handlers[capability_name]
    return handler(request.delegation_token, request.parameters)


# --- Capability Graph ---


@app.get("/anip/capabilities/{capability_name}/graph")
def capability_graph(capability_name: str):
    """Get the capability graph — prerequisites and composition."""
    if capability_name not in _manifest.capabilities:
        return {"error": f"capability '{capability_name}' not found"}

    cap = _manifest.capabilities[capability_name]
    return {
        "capability": capability_name,
        "requires": [r.model_dump() for r in cap.requires],
        "composes_with": [c.model_dump() for c in cap.composes_with],
    }


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
