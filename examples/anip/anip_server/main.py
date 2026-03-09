"""ANIP reference server — flight booking service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel

from .capabilities import book_flight, search_flights
from .data.database import log_invocation, query_audit_log
from .primitives.delegation import (
    get_chain_token_ids,
    get_root_principal,
    register_token,
    validate_delegation,
)
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


# --- Discovery ---


@app.get("/.well-known/anip")
def discovery(request: Request):
    """ANIP discovery document — the single entry point to the protocol.

    Lightweight, cacheable. Tells the agent everything it needs to know
    to decide whether to fetch the full manifest.
    """
    profiles = _manifest.profile.model_dump(exclude_none=True)

    # Build capability summaries for discovery
    capabilities_summary = {
        name: {
            "description": cap.description,
            "side_effect": cap.side_effect.type.value,
            "minimum_scope": cap.minimum_scope,
            "financial": cap.cost.financial is not None,
            "contract": cap.contract_version,
        }
        for name, cap in _manifest.capabilities.items()
    }
    side_effect_types_present = sorted({
        cap.side_effect.type.value
        for cap in _manifest.capabilities.values()
    })

    # Determine compliance level from profile
    compliance = "anip-complete" if all([
        profiles.get("cost"),
        profiles.get("capability_graph"),
        profiles.get("state_session"),
        profiles.get("observability"),
    ]) else "anip-compliant"

    # Build base_url from the incoming request
    base_url = str(request.base_url).rstrip("/")

    return {
        "anip_discovery": {
            "protocol": _manifest.protocol,
            "compliance": compliance,
            "base_url": base_url,
            "profile": profiles,
            "auth": {
                "delegation_token_required": True,
                "supported_formats": ["anip-v1"],
                "minimum_scope_for_discovery": "none",
            },
            "capabilities": capabilities_summary,
            "endpoints": {
                "manifest": "/anip/manifest",
                "handshake": "/anip/handshake",
                "permissions": "/anip/permissions",
                "invoke": "/anip/invoke/{capability}",
                "tokens": "/anip/tokens",
                "graph": "/anip/graph/{capability}",
                "audit": "/anip/audit",
                "test": "/anip/test/{capability}",
            },
            "metadata": {
                "service_name": "Flight Booking Service",
                "service_description": "ANIP-compliant flight search and booking",
                "service_category": "travel.booking",
                "service_tags": ["flights", "booking", "irreversible-financial"],
                "capability_side_effect_types_present": side_effect_types_present,
                "max_delegation_depth": 5,
                "concurrent_branches_supported": True,
                "test_mode_available": False,
                "test_mode_unavailable_policy": "require_explicit_authorization_for_irreversible",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "ttl": "PT1H",
            },
        }
    }


# --- Manifest ---


@app.get("/anip/manifest")
def get_manifest():
    """Full ANIP manifest — all capability declarations."""
    return _manifest.model_dump()


# --- Profile Handshake ---


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


@app.post("/anip/tokens")
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
    token = request.delegation_token

    # 1. Check capability exists
    if capability_name not in _capability_handlers:
        _log_failure(capability_name, token, request.parameters, "unknown_capability")
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
        token=token,
        minimum_scope=cap_declaration.minimum_scope,
        capability_name=capability_name,
    )
    if delegation_failure is not None:
        _log_failure(capability_name, token, request.parameters, delegation_failure.type)
        return InvokeResponse(success=False, failure=delegation_failure)

    # 4. Invoke the capability
    handler = _capability_handlers[capability_name]
    response = handler(token, request.parameters)

    # 5. Log the invocation
    _log_invocation(capability_name, token, request.parameters, response)

    return response


def _log_invocation(
    capability_name: str,
    token: DelegationToken,
    parameters: dict[str, Any],
    response: InvokeResponse,
) -> None:
    """Log a successful or failed capability invocation."""
    log_invocation(
        capability=capability_name,
        token_id=token.token_id,
        issuer=token.issuer,
        subject=token.subject,
        root_principal=get_root_principal(token),
        parameters=parameters,
        success=response.success,
        result_summary=_summarize_result(response.result) if response.success else None,
        failure_type=response.failure.type if response.failure else None,
        cost_actual=response.cost_actual.model_dump() if response.cost_actual else None,
        delegation_chain=get_chain_token_ids(token),
    )


def _log_failure(
    capability_name: str,
    token: DelegationToken,
    parameters: dict[str, Any],
    failure_type: str,
) -> None:
    """Log a pre-invocation failure (delegation validation, unknown capability)."""
    log_invocation(
        capability=capability_name,
        token_id=token.token_id,
        issuer=token.issuer,
        subject=token.subject,
        root_principal=get_root_principal(token),
        parameters=parameters,
        success=False,
        failure_type=failure_type,
        delegation_chain=get_chain_token_ids(token),
    )


def _summarize_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Create a summary of the result for audit logging (avoid storing large payloads)."""
    if result is None:
        return None
    summary: dict[str, Any] = {}
    if "booking_id" in result:
        summary["booking_id"] = result["booking_id"]
    if "count" in result:
        summary["result_count"] = result["count"]
    if "total_cost" in result:
        summary["total_cost"] = result["total_cost"]
    return summary if summary else {"type": "result_logged"}


# --- Audit / Observability ---


@app.post("/anip/audit")
def get_audit_log(
    token: DelegationToken,
    capability: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100, le=1000),
):
    """Query the audit log.

    Access is restricted by the observability contract:
    only the root principal of the delegation chain can access
    their own audit records. A valid delegation token is required.
    """
    root_principal = get_root_principal(token)

    entries = query_audit_log(
        capability=capability,
        root_principal=root_principal,
        since=since,
        limit=limit,
    )

    return {
        "entries": entries,
        "count": len(entries),
        "root_principal": root_principal,
        "capability_filter": capability,
        "since_filter": since,
    }


# --- Capability Graph ---


@app.get("/anip/graph/{capability_name}")
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
