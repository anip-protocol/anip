"""Non-generated service extension hooks for the GTM pipeline service.

This file is intended to survive scaffold regeneration.
"""

from __future__ import annotations

from fastapi import HTTPException

from anip_service import ANIPError
from shared.actor_identity import authenticate_bearer, parse_actor_principal


def actor_from_bearer(bearer: str | None) -> dict:
    principal = authenticate_bearer(bearer or "")
    if not principal:
        raise HTTPException(status_code=401, detail="Valid actor bearer required")
    return parse_actor_principal(principal)


def resolve_pipeline_scope(requested_scope: str | None, actor_policy: dict) -> str | None:
    actor_scope = str(actor_policy.get("pipeline_scope") or "company")
    normalized_requested = str(requested_scope).strip() if requested_scope else None
    if actor_scope in {"company", "all"}:
        return normalized_requested
    if not normalized_requested or normalized_requested in {"company", "all"}:
        return actor_scope
    if normalized_requested != actor_scope:
        raise ANIPError(
            "restricted",
            "This actor is restricted to a narrower pipeline scope.",
            resolution={"action": "retry_with_owned_scope", "requires": actor_scope},
        )
    return normalized_requested


def filter_approval_entries(entries: list[dict], actor_policy: dict) -> list[dict]:
    if actor_policy.get("can_approve_followup"):
        return entries
    actor_id = actor_policy.get("actor_id")
    return [item for item in entries if item.get("requested_by", {}).get("actor_id") == actor_id]


def ensure_can_prepare_pipeline_write(actor_policy: dict, *, action_label: str, authority_label: str) -> None:
    if actor_policy.get("can_prepare_followup"):
        return
    raise ANIPError(
        "denied",
        f"This actor role cannot prepare {action_label}.",
        resolution={"action": "request_authorized_actor", "requires": authority_label},
    )


def approval_role_required(actor_policy: dict, default_role: str = "sales_leader") -> str:
    if actor_policy.get("can_approve_followup"):
        return str(actor_policy.get("role") or default_role)
    return default_role
