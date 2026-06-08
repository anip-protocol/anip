"""Actor claim helpers for the self-contained GTM Python native bundle."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
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
        can_prepare_followup=True,
        can_approve_followup=True,
        can_use_lookalikes=True,
        can_route_leads=True,
        can_approve_routing=True,
    ),
    "account_manager_east": ActorProfile(
        actor_id="account_manager_east",
        display_name="Maya Chen",
        email="maya.chen@example.com",
        role="account_manager",
        api_key="demo-account-manager-east-key",
        pipeline_scope="East",
        enrichment_access="bounded",
        can_prepare_followup=True,
        can_use_lookalikes=True,
    ),
    "sales_analyst": ActorProfile(
        actor_id="sales_analyst",
        display_name="Jordan Lee",
        email="jordan.lee@example.com",
        role="sales_analyst",
        api_key="demo-sales-analyst-key",
        financial_access="masked",
        enrichment_access="bounded",
        outreach_access="bounded",
        can_use_objection_variants=False,
    ),
    "rev_ops_manager": ActorProfile(
        actor_id="rev_ops_manager",
        display_name="Priya Shah",
        email="priya.shah@example.com",
        role="rev_ops_manager",
        api_key="demo-rev-ops-manager-key",
        can_prepare_followup=True,
        can_use_lookalikes=True,
        can_route_leads=True,
    ),
}


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


def parse_actor_principal(root_principal: str | None) -> dict[str, Any]:
    raw = (root_principal or "").strip()
    pieces = raw.split("|") if raw else []
    claims: dict[str, Any] = {"principal": pieces[0] if pieces else ""}
    for piece in pieces[1:]:
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        claims[key.strip()] = value.strip()
    for key in (
        "can_prepare_followup",
        "can_approve_followup",
        "can_use_lookalikes",
        "can_route_leads",
        "can_approve_routing",
        "can_use_objection_variants",
    ):
        claims[key] = str(claims.get(key) or "").lower() == "true"
    claims.setdefault("actor_id", "unknown")
    claims.setdefault("role", "unknown")
    claims.setdefault("pipeline_scope", "company")
    claims.setdefault("financial_access", "masked")
    claims.setdefault("enrichment_access", "bounded")
    claims.setdefault("outreach_access", "bounded")
    return claims


def actor_profiles() -> dict[str, ActorProfile]:
    raw = (os.getenv("GTM_ACTOR_PROFILES_JSON") or "").strip()
    if not raw:
        return dict(DEFAULT_ACTORS)
    profiles = dict(DEFAULT_ACTORS)
    for item in json.loads(raw):
        if isinstance(item, dict):
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


def api_key_map() -> dict[str, str]:
    raw = (os.getenv("ANIP_API_KEYS_JSON") or "").strip()
    if raw:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items()}
    keys = {"dev-admin-key": "human:local-developer"}
    keys.update({profile.api_key: encode_actor_principal(profile) for profile in actor_profiles().values()})
    return keys


def authenticate_bearer(bearer: str) -> str | None:
    return api_key_map().get(bearer)


def list_actor_profiles() -> list[dict[str, Any]]:
    return [{key: value for key, value in asdict(profile).items() if key != "api_key"} for profile in actor_profiles().values()]
