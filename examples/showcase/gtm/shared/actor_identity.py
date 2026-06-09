"""Generic actor identity helpers for the GTM showcase.

This module stays intentionally generic at the contract level:
- bearer -> actor profile
- actor profile -> principal string with claims
- principal string -> parsed actor claims

The GTM services then decide how to apply those claims.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Any


@dataclass(frozen=True)
class ActorProfile:
    actor_id: str
    display_name: str
    email: str
    role: str
    api_key: str
    pipeline_scope: str = "company"
    financial_access: str = "full"
    enrichment_access: str = "full"
    outreach_access: str = "full"
    can_prepare_followup: bool = False
    can_approve_followup: bool = False
    can_use_lookalikes: bool = False
    can_route_leads: bool = False
    can_approve_routing: bool = False
    can_use_objection_variants: bool = True


DEFAULT_ACTORS: dict[str, ActorProfile] = {
    "sales_leader": ActorProfile(
        actor_id="sales_leader",
        display_name="Alex King",
        email="alex.king@example.com",
        role="sales_leader",
        api_key="demo-sales-leader-key",
        pipeline_scope="company",
        financial_access="full",
        enrichment_access="full",
        outreach_access="full",
        can_prepare_followup=True,
        can_approve_followup=True,
        can_use_lookalikes=True,
        can_route_leads=True,
        can_approve_routing=True,
        can_use_objection_variants=True,
    ),
    "account_manager_east": ActorProfile(
        actor_id="account_manager_east",
        display_name="Maya Chen",
        email="maya.chen@example.com",
        role="account_manager",
        api_key="demo-account-manager-east-key",
        pipeline_scope="East",
        financial_access="full",
        enrichment_access="bounded",
        outreach_access="full",
        can_prepare_followup=True,
        can_approve_followup=False,
        can_use_lookalikes=True,
        can_route_leads=False,
        can_approve_routing=False,
        can_use_objection_variants=True,
    ),
    "sales_analyst": ActorProfile(
        actor_id="sales_analyst",
        display_name="Jordan Lee",
        email="jordan.lee@example.com",
        role="sales_analyst",
        api_key="demo-sales-analyst-key",
        pipeline_scope="company",
        financial_access="masked",
        enrichment_access="bounded",
        outreach_access="bounded",
        can_prepare_followup=False,
        can_approve_followup=False,
        can_use_lookalikes=False,
        can_route_leads=False,
        can_approve_routing=False,
        can_use_objection_variants=False,
    ),
    "rev_ops_manager": ActorProfile(
        actor_id="rev_ops_manager",
        display_name="Priya Shah",
        email="priya.shah@example.com",
        role="rev_ops_manager",
        api_key="demo-rev-ops-manager-key",
        pipeline_scope="company",
        financial_access="full",
        enrichment_access="full",
        outreach_access="full",
        can_prepare_followup=True,
        can_approve_followup=False,
        can_use_lookalikes=True,
        can_route_leads=True,
        can_approve_routing=False,
        can_use_objection_variants=True,
    ),
}


def _load_override_profiles() -> dict[str, ActorProfile]:
    raw = (os.getenv("GTM_ACTOR_PROFILES_JSON") or "").strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("GTM_ACTOR_PROFILES_JSON must be a JSON array")
    profiles: dict[str, ActorProfile] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        profile = ActorProfile(
            actor_id=str(item["actor_id"]),
            display_name=str(item.get("display_name") or item["actor_id"]),
            email=str(item.get("email") or f"{item['actor_id']}@example.com"),
            role=str(item.get("role") or "unknown"),
            api_key=str(item["api_key"]),
            pipeline_scope=str(item.get("pipeline_scope") or "company"),
            financial_access=str(item.get("financial_access") or "full"),
            enrichment_access=str(item.get("enrichment_access") or "full"),
            outreach_access=str(item.get("outreach_access") or "full"),
            can_prepare_followup=bool(item.get("can_prepare_followup")),
            can_approve_followup=bool(item.get("can_approve_followup")),
            can_use_lookalikes=bool(item.get("can_use_lookalikes")),
            can_route_leads=bool(item.get("can_route_leads")),
            can_approve_routing=bool(item.get("can_approve_routing")),
            can_use_objection_variants=bool(item.get("can_use_objection_variants", True)),
        )
        profiles[profile.actor_id] = profile
    return profiles


def actor_profiles() -> dict[str, ActorProfile]:
    profiles = dict(DEFAULT_ACTORS)
    profiles.update(_load_override_profiles())
    return profiles


def list_actor_profiles() -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in asdict(profile).items()
            if key != "api_key"
        }
        for profile in actor_profiles().values()
    ]


def get_actor_profile(actor_id: str | None) -> ActorProfile:
    profiles = actor_profiles()
    chosen = (actor_id or "sales_leader").strip()
    if chosen not in profiles:
        raise KeyError(f"Unknown actor profile: {chosen}")
    return profiles[chosen]


def api_key_for_actor(actor_id: str | None) -> str:
    return get_actor_profile(actor_id).api_key


def encode_actor_principal(profile: ActorProfile) -> str:
    return (
        f"human:{profile.email}"
        f"|actor_id={profile.actor_id}"
        f"|display_name={profile.display_name}"
        f"|role={profile.role}"
        f"|pipeline_scope={profile.pipeline_scope}"
        f"|financial_access={profile.financial_access}"
        f"|enrichment_access={profile.enrichment_access}"
        f"|outreach_access={profile.outreach_access}"
        f"|can_prepare_followup={str(profile.can_prepare_followup).lower()}"
        f"|can_approve_followup={str(profile.can_approve_followup).lower()}"
        f"|can_use_lookalikes={str(profile.can_use_lookalikes).lower()}"
        f"|can_route_leads={str(profile.can_route_leads).lower()}"
        f"|can_approve_routing={str(profile.can_approve_routing).lower()}"
        f"|can_use_objection_variants={str(profile.can_use_objection_variants).lower()}"
    )


def authenticate_bearer(bearer: str) -> str | None:
    token = (bearer or "").strip()
    if not token:
        return None
    for profile in actor_profiles().values():
        if token == profile.api_key:
            return encode_actor_principal(profile)
    return None


def parse_actor_principal(principal: str | None) -> dict[str, Any]:
    raw = (principal or "").strip()
    if not raw:
        return {}
    pieces = raw.split("|")
    parsed: dict[str, Any] = {"principal": pieces[0]}
    for piece in pieces[1:]:
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        value = value.strip()
        if value.lower() in {"true", "false"}:
            parsed[key] = value.lower() == "true"
        else:
            parsed[key] = value
    return parsed
