"""REST adapter for the live GTM prioritization backend."""
from __future__ import annotations

import os
from typing import Any

import httpx

from anip_service import ANIPError


BACKEND_BASE_URL = os.getenv(
    "GTM_PRIORITIZATION_BACKEND_URL",
    "http://gtm-prioritization-backend:9400",
).rstrip("/")
BACKEND_AUTH_TOKEN = os.getenv("GTM_PRIORITIZATION_BACKEND_TOKEN", "demo-prioritization-backend-token")


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"{BACKEND_BASE_URL}{path}",
        json=payload,
        headers={"Authorization": f"Bearer {BACKEND_AUTH_TOKEN}"},
        timeout=20.0,
    )
    if response.status_code == 404:
        raise ANIPError(
            "clarification_required",
            "The requested prioritization cohort is not explicit enough.",
            resolution={
                "action": "provide_missing_parameter",
                "requires": "cohort_ref",
                "hint": "Use a supported cohort like inbound_last_week, webinar_q2, expansion_candidates_q2, or at_risk_q2.",
            },
        )
    if response.is_error:
        raise ANIPError(
            "temporarily_unavailable",
            "The prioritization backend is currently unavailable.",
            resolution={"action": "retry_later"},
        )
    return response.json()


def score_leads(*, cohort_ref: str, limit: int | None = None, owner_scope: str | None = None) -> dict[str, Any]:
    return _post(
        "/v1/prioritization/score",
        {
            "cohort_ref": cohort_ref,
            "limit": limit,
            "owner_scope": owner_scope,
        },
    )


def prioritize_accounts(
    *,
    cohort_ref: str,
    ranking_basis: str | None = None,
    limit: int | None = None,
    owner_scope: str | None = None,
) -> dict[str, Any]:
    return _post(
        "/v1/prioritization/accounts",
        {
            "cohort_ref": cohort_ref,
            "ranking_basis": ranking_basis,
            "limit": limit,
            "owner_scope": owner_scope,
        },
    )


def preview_route_leads(*, cohort_ref: str, target_queue: str, owner_scope: str | None = None) -> dict[str, Any]:
    return _post(
        "/v1/prioritization/route",
        {
            "cohort_ref": cohort_ref,
            "target_queue": target_queue,
            "owner_scope": owner_scope,
            "dry_run": True,
        },
    )
