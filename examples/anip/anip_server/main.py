"""ANIP reference server — flight booking service."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel

from .capabilities import book_flight, search_flights
from .data.database import log_invocation, query_audit_log
from .primitives.delegation import (
    acquire_exclusive_lock,
    get_chain_token_ids,
    get_root_principal,
    get_token,
    issue_token,
    register_token,
    release_exclusive_lock,
    resolve_registered_token,
    validate_constraints_narrowing,
    validate_delegation,
    validate_parent_exists,
    validate_scope_narrowing,
)
from .primitives.manifest import build_manifest
from .primitives.models import (
    ANIPFailure,
    DelegationToken,
    InvokeRequest,
    InvokeRequestV2,
    InvokeResponse,
    Resolution,
    TokenPresentation,
    TokenRequest,
)
from .primitives.permissions import discover_permissions

logger = logging.getLogger("anip")

_trust_mode = os.environ.get("ANIP_TRUST_MODE", "signed")


def get_trust_mode() -> str:
    return _trust_mode


def set_trust_mode(mode: str) -> None:
    global _trust_mode
    _trust_mode = mode
    if mode == "declaration":
        logger.warning(
            "ANIP server running in trust-on-declaration mode. "
            "Tokens are NOT cryptographically verified. "
            "Do NOT use this in production."
        )

app = FastAPI(
    title="ANIP Flight Service",
    description="Reference implementation of the Agent-Native Interface Protocol",
    version="0.1.0",
)

# Server key pair — persisted to disk so restarts don't invalidate tokens.
from .primitives.crypto import KeyManager

_key_path = os.environ.get(
    "ANIP_KEY_PATH",
    str(Path(__file__).parent / "data" / "anip-keys.json"),
)
_keys = KeyManager(key_path=_key_path)

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


# --- JWKS ---


@app.get("/.well-known/jwks.json")
def jwks():
    """Public key set for verifying server-issued tokens."""
    return _keys.get_jwks()


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


# --- API Key Authentication ---

# API key → identity mapping
_api_key_identities: dict[str, str] = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}


def _authenticate_caller(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    key = authorization.removeprefix("Bearer ").strip()
    return _api_key_identities.get(key)


def _resolve_jwt_token(token_jwt: str) -> DelegationToken | ANIPFailure:
    """Verify JWT signature and resolve to stored token.

    The JWT claims are the cryptographic authority. After loading the stored
    token, we verify that critical fields (sub, scope, capability, root_principal,
    parent, constraints) match the signed claims. If the store has been mutated,
    the request is rejected.
    """
    try:
        claims = _keys.verify_jwt(token_jwt)
    except Exception as e:
        return ANIPFailure(
            type="invalid_token",
            detail=f"JWT verification failed: {e}",
            resolution=Resolution(action="present_valid_token"),
            retry=False,
        )
    token_id = claims.get("jti")
    if not token_id:
        return ANIPFailure(
            type="invalid_token",
            detail="JWT missing jti claim",
            resolution=Resolution(action="present_valid_token"),
            retry=False,
        )
    stored = get_token(token_id)
    if stored is None:
        return ANIPFailure(
            type="token_not_registered",
            detail=f"token '{token_id}' not found in store",
            resolution=Resolution(action="issue_new_token"),
            retry=True,
        )

    # TRUST BOUNDARY: compare ALL trust-critical signed claims against stored values.
    mismatches = []
    if claims.get("sub") != stored.subject:
        mismatches.append(f"sub: jwt={claims.get('sub')} store={stored.subject}")
    if sorted(claims.get("scope", [])) != sorted(stored.scope):
        mismatches.append(f"scope: jwt={claims.get('scope')} store={stored.scope}")
    if claims.get("capability") != stored.purpose.capability:
        mismatches.append(f"capability: jwt={claims.get('capability')} store={stored.purpose.capability}")
    # root_principal check: only meaningful for child tokens where the chain
    # can be walked. For root tokens (parent=None), the JWT root_principal is
    # the authenticated human identity, while get_root_principal returns the
    # server issuer — these are intentionally different.
    if stored.parent is not None:
        jwt_root = claims.get("root_principal")
        stored_root = get_root_principal(stored)
        if jwt_root is None:
            mismatches.append("root_principal: missing from JWT claims")
        elif jwt_root != stored_root:
            mismatches.append(f"root_principal: jwt={jwt_root} store={stored_root}")
    jwt_parent = claims.get("parent_token_id")
    if jwt_parent != stored.parent:
        mismatches.append(f"parent: jwt={jwt_parent} store={stored.parent}")
    jwt_constraints = claims.get("constraints")
    if jwt_constraints is None:
        mismatches.append("constraints: missing from JWT claims")
    else:
        stored_constraints = stored.constraints.model_dump(mode="json")
        if jwt_constraints != stored_constraints:
            mismatches.append(f"constraints: jwt={jwt_constraints} store={stored_constraints}")
    if mismatches:
        return ANIPFailure(
            type="token_integrity_violation",
            detail=f"Signed JWT claims diverge from stored token: {'; '.join(mismatches)}. "
                   "The stored token may have been tampered with.",
            resolution=Resolution(action="reissue_token"),
            retry=False,
        )

    return stored


# --- Token Issuance ---


@app.post("/anip/tokens")
def issue_or_register_token(request: dict = Body(...), authorization: str | None = Header(None)):
    """Issue a signed delegation token (v0.2) or register an unsigned one (v0.1)."""
    if _trust_mode == "declaration":
        # v0.1 path: accept full DelegationToken
        try:
            token = DelegationToken(**request)
        except Exception as e:
            return {"registered": False, "error": str(e)}
        parent_failure = validate_parent_exists(token)
        if parent_failure is not None:
            return {"registered": False, "error": parent_failure.detail}
        scope_failure = validate_scope_narrowing(token)
        if scope_failure is not None:
            return {"registered": False, "error": scope_failure.detail}
        constraint_failure = validate_constraints_narrowing(token)
        if constraint_failure is not None:
            return {"registered": False, "error": constraint_failure.detail}
        register_token(token)
        return {"registered": True, "token_id": token.token_id}

    # v0.2 path: server-side JWT issuance
    token_request = TokenRequest(**request)

    caller_identity = _authenticate_caller(authorization)
    if caller_identity is None:
        return {"issued": False, "error": "authentication required — provide Authorization: Bearer <key>"}

    parent_token = None
    root_principal = caller_identity

    if token_request.parent_token is not None:
        try:
            parent_claims = _keys.verify_jwt(token_request.parent_token)
        except Exception as e:
            return {"issued": False, "error": f"invalid parent token: {e}"}
        parent_stored = get_token(parent_claims["jti"])
        if parent_stored is None:
            return {"issued": False, "error": "parent token not found in store"}
        if caller_identity != parent_stored.subject:
            return {"issued": False, "error": f"caller '{caller_identity}' is not the parent token's subject ('{parent_stored.subject}') — only the delegatee can sub-delegate"}
        parent_token = parent_stored
        root_principal = parent_claims.get("root_principal", get_root_principal(parent_stored))

    try:
        token, token_id = issue_token(
            request_subject=token_request.subject,
            request_scope=token_request.scope,
            request_capability=token_request.capability,
            issuer_id="anip-flight-service",
            parent_token=parent_token,
            purpose_parameters=token_request.purpose_parameters,
            ttl_hours=token_request.ttl_hours,
        )
    except ValueError as e:
        return {"issued": False, "error": str(e)}

    budget = None
    for s in token_request.scope:
        if ":max_$" in s:
            budget = {"max": float(s.split(":max_$")[1]), "currency": "USD"}
            break

    claims = {
        "jti": token_id,
        "iss": "anip-flight-service",
        "sub": token_request.subject,
        "aud": "anip-flight-service",
        "iat": int(token.expires.timestamp()) - (token_request.ttl_hours * 3600),
        "exp": int(token.expires.timestamp()),
        "scope": token_request.scope,
        "capability": token_request.capability,
        "purpose": token.purpose.model_dump(),
        "root_principal": root_principal,
        "constraints": token.constraints.model_dump(),
    }
    if parent_token is not None:
        claims["parent_token_id"] = parent_token.token_id
    if budget is not None:
        claims["budget"] = budget

    jwt_str = _keys.sign_jwt(claims)

    return {
        "issued": True,
        "token_id": token_id,
        "token": jwt_str,
        "expires": token.expires.isoformat(),
    }


# --- Permission Discovery ---


@app.post("/anip/permissions")
def query_permissions(request: dict = Body(...)):
    """Discover what the agent can do given its delegation chain."""
    if _trust_mode == "declaration" and "token_id" in request:
        token = DelegationToken(**request)
        resolved = resolve_registered_token(token)
        if isinstance(resolved, ANIPFailure):
            raise HTTPException(status_code=401, detail=resolved.detail)
        return discover_permissions(resolved, _manifest.capabilities)
    else:
        token_jwt = request.get("token", "")
        resolved = _resolve_jwt_token(token_jwt)
        if isinstance(resolved, ANIPFailure):
            raise HTTPException(status_code=401, detail=resolved.detail)
        return discover_permissions(resolved, _manifest.capabilities)


# --- Capability Invocation ---


@app.post("/anip/invoke/{capability_name}")
def invoke_capability(capability_name: str, request: dict = Body(...)):
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

    # 2. Resolve token based on trust mode
    if _trust_mode == "declaration" and "delegation_token" in request:
        invoke_req = InvokeRequest(**request)
        token = invoke_req.delegation_token
        resolved = resolve_registered_token(token)
        if isinstance(resolved, ANIPFailure):
            return InvokeResponse(success=False, failure=resolved)
        token = resolved
        parameters = invoke_req.parameters
    else:
        invoke_req_v2 = InvokeRequestV2(**request)
        jwt_resolved = _resolve_jwt_token(invoke_req_v2.token)
        if isinstance(jwt_resolved, ANIPFailure):
            return InvokeResponse(success=False, failure=jwt_resolved)
        token = jwt_resolved
        parameters = invoke_req_v2.parameters

    # 3. Get the capability declaration for scope requirements
    cap_declaration = _manifest.capabilities[capability_name]

    # 4. Validate delegation chain
    delegation_result = validate_delegation(
        token=token,
        minimum_scope=cap_declaration.minimum_scope,
        capability_name=capability_name,
    )
    if isinstance(delegation_result, ANIPFailure):
        _log_failure(capability_name, token, parameters, delegation_result.type)
        return InvokeResponse(success=False, failure=delegation_result)
    token = delegation_result

    # 5. Acquire exclusive lock if needed
    lock_failure = acquire_exclusive_lock(token)
    if lock_failure is not None:
        _log_failure(capability_name, token, parameters, lock_failure.type)
        return InvokeResponse(success=False, failure=lock_failure)
    try:
        # 6. Invoke the capability
        handler = _capability_handlers[capability_name]
        response = handler(token, parameters)

        # 7. Log the invocation
        _log_invocation(capability_name, token, parameters, response)

        return response
    finally:
        release_exclusive_lock(token)


def _calculate_cost_variance(
    capability_name: str,
    response: InvokeResponse,
) -> dict[str, Any] | None:
    """Calculate cost variance between declared and actual cost."""
    if not response.success or response.cost_actual is None:
        return None

    cap = _manifest.capabilities.get(capability_name)
    if cap is None or cap.cost is None or cap.cost.financial is None:
        return None

    declared = cap.cost.financial
    actual_amount = response.cost_actual.financial.get("amount")
    if actual_amount is None:
        return None

    typical = declared.get("typical")
    range_min = declared.get("range_min")
    range_max = declared.get("range_max")

    variance: dict[str, Any] = {
        "actual": actual_amount,
        "currency": declared.get("currency", "USD"),
        "certainty": cap.cost.certainty.value,
    }

    if typical is not None:
        variance["declared_typical"] = typical
        variance["variance_from_typical_pct"] = round(
            ((actual_amount - typical) / typical) * 100, 1
        )

    if range_min is not None and range_max is not None:
        variance["declared_range"] = {"min": range_min, "max": range_max}
        variance["within_declared_range"] = range_min <= actual_amount <= range_max

    return variance


def _log_invocation(
    capability_name: str,
    token: DelegationToken,
    parameters: dict[str, Any],
    response: InvokeResponse,
) -> None:
    """Log a successful or failed capability invocation."""
    cost_variance = _calculate_cost_variance(capability_name, response)
    cost_actual_data = response.cost_actual.model_dump() if response.cost_actual else None
    if cost_actual_data and cost_variance:
        cost_actual_data["variance_tracking"] = cost_variance

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
        cost_actual=cost_actual_data,
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
    request: dict = Body(...),
    capability: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100, le=1000),
):
    """Query the audit log."""
    if _trust_mode == "declaration" and "token_id" in request:
        token = DelegationToken(**request)
        resolved = resolve_registered_token(token)
        if isinstance(resolved, ANIPFailure):
            raise HTTPException(status_code=401, detail=resolved.detail)
        token = resolved
    else:
        token_jwt = request.get("token", "")
        resolved = _resolve_jwt_token(token_jwt)
        if isinstance(resolved, ANIPFailure):
            raise HTTPException(status_code=401, detail=resolved.detail)
        token = resolved

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
