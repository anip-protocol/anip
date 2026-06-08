"""Concrete enrichment adapter for the generated GTM enrichment service."""
from __future__ import annotations

import re

from anip_service import ANIPError

from .enrichment_data import (
    get_account_enrichment_summary,
    get_at_risk_account_enrichment_summary,
    get_lookalike_accounts,
)

VAGUE_ACCOUNT_SCOPE_MARKERS = (
    "our ",
    "we ",
    "should ",
    "next",
    "core accounts",
    "best customer",
    "top account",
    "companies we care",
    "most important",
)


def _bounded_limit(value: object | None, default: int = 5, maximum: int = 10) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _looks_like_vague_account_scope(value: str | None) -> bool:
    normalized = str(value or "").strip().lower()
    return bool(normalized) and any(marker in normalized for marker in VAGUE_ACCOUNT_SCOPE_MARKERS)


def _parse_account_names(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    normalized = re.sub(r"\s+\band\b\s+", ",", str(value or ""), flags=re.IGNORECASE)
    normalized = normalized.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def fetch_account_enrichment_summary(
    account_names: str | list[str] | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    names = _parse_account_names(account_names)
    if not names:
        raise ANIPError("clarification_required", "account scope is missing", resolution={"action": "provide_account_scope", "requires": "account_names"})
    if any(_looks_like_vague_account_scope(name) for name in names):
        raise ANIPError(
            "clarification_required",
            "account scope is ambiguous",
            resolution={
                "action": "provide_account_scope",
                "requires": "account_names",
                "hint": "Provide explicit account names such as Acme Corporation, Codehow, or Condax.",
            },
        )
    accounts = get_account_enrichment_summary(account_names=names, limit=_bounded_limit(limit, len(names)))
    if not accounts:
        raise ANIPError(
            "clarification_required",
            "no supported enrichment accounts matched the request",
            resolution={
                "action": "provide_supported_account_names",
                "requires": "account_names",
                "hint": "Use account names present in the bounded enrichment profile.",
            },
        )
    if (actor_policy or {}).get("enrichment_access") != "full":
        accounts = [
            {**item, "parent_company": None, "revenue_band": None, "employee_band": None}
            for item in accounts
        ]
    return {
        "result": {
            "accounts": accounts,
            "bounded_to_account_count": len(accounts),
            "visibility": {
                "enrichment_access": "full" if (actor_policy or {}).get("enrichment_access") == "full" else "bounded",
            },
        }
    }


def fetch_lookalike_accounts(
    reference_account: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    if not (actor_policy or {}).get("can_use_lookalikes"):
        raise ANIPError("denied", "Lookalike analysis is not available for this actor role.", resolution={"action": "request_authorized_actor", "requires": "role with lookalike access"})
    if not reference_account or not str(reference_account).strip():
        raise ANIPError("clarification_required", "reference account is missing", resolution={"action": "provide_reference_account", "requires": "reference_account"})
    if _looks_like_vague_account_scope(str(reference_account)):
        raise ANIPError(
            "clarification_required",
            "reference account is ambiguous",
            resolution={
                "action": "provide_reference_account",
                "requires": "reference_account",
                "hint": "Provide a specific reference account such as Condax, Acme Corporation, or Codehow.",
            },
        )
    result = get_lookalike_accounts(reference_account=str(reference_account).strip(), limit=_bounded_limit(limit))
    if result is None:
        raise ANIPError("denied", "The requested reference account is not available in the bounded enrichment model.", resolution={"action": "retry_with_supported_account", "requires": "reference_account present in the enrichment profile"})
    if (actor_policy or {}).get("enrichment_access") != "full":
        result = {
            **result,
            "reference_profile": {
                **result["reference_profile"],
                "revenue_band": None,
                "employee_band": None,
            },
            "matches": [
                {**item, "revenue_band": None, "employee_band": None}
                for item in result["matches"]
            ],
            "visibility": {"enrichment_access": "bounded"},
        }
    return {"result": result}


def fetch_at_risk_account_enrichment_summary(
    *,
    quarter: str | None = None,
    ranking_basis: str | None = None,
    owner_scope: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    if not quarter or not str(quarter).strip():
        raise ANIPError("clarification_required", "quarter is missing", resolution={"action": "provide_missing_parameter", "requires": "quarter"})
    if (ranking_basis or "risk_score") != "risk_score":
        raise ANIPError("denied", "At-risk account enrichment only supports ranking_basis=risk_score.", resolution={"action": "retry_with_supported_ranking", "requires": "ranking_basis=risk_score"})
    result = get_at_risk_account_enrichment_summary(
        quarter=str(quarter).strip(),
        ranking_basis="risk_score",
        owner_scope=owner_scope,
        limit=_bounded_limit(limit),
    )
    accounts = result["accounts"]
    if (actor_policy or {}).get("enrichment_access") != "full":
        accounts = [
            {**item, "parent_company": None, "revenue_band": None, "employee_band": None}
            for item in accounts
        ]
    return {
        "result": {
            **result,
            "accounts": accounts,
            "bounded_to_account_count": len(accounts),
            "visibility": {
                "enrichment_access": "full" if (actor_policy or {}).get("enrichment_access") == "full" else "bounded",
            },
        }
    }
