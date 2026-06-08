"""Studio-generated backend adapter scaffold for the GTM enrichment showcase."""
# Backend type: curated_sql
# Target: Governed SQL access over dbt-modeled account enrichment views
# Backend template: generated-backend-template:sql

from anip_service import ANIPError

from data import (
    get_account_enrichment_summary,
    get_at_risk_account_enrichment_summary,
    get_lookalike_accounts,
)


def fetch_account_enrichment_summary(
    account_names: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 2 GTM mapping for bounded account enrichment."""
    names = [item.strip() for item in str(account_names or '').split(',') if item.strip()]
    if not names:
        raise ANIPError("clarification_required", "account scope is missing", resolution={"action": "provide_account_scope", "requires": "account_names"})
    accounts = get_account_enrichment_summary(account_names=names, limit=min(int(limit or len(names)), 10))
    if (actor_policy or {}).get("enrichment_access") != "full":
        accounts = [
            {
                **item,
                "parent_company": None,
                "revenue_band": None,
                "employee_band": None,
            }
            for item in accounts
        ]
    return {
        'accounts': accounts,
        'bounded_to_account_count': len(accounts),
        'visibility': {
            'enrichment_access': 'full' if (actor_policy or {}).get("enrichment_access") == "full" else 'bounded',
        },
    }


def fetch_at_risk_account_enrichment_summary(
    quarter: str | None = None,
    ranking_basis: str | None = None,
    owner_scope: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Select bounded at-risk accounts and return their enrichment context."""
    if not quarter or not str(quarter).strip():
        raise ANIPError(
            "clarification_required",
            "quarter is missing",
            resolution={"action": "provide_missing_parameter", "requires": "quarter"},
        )
    if (ranking_basis or "risk_score") != "risk_score":
        raise ANIPError(
            "denied",
            "At-risk account enrichment only supports ranking_basis=risk_score.",
            resolution={"action": "retry_with_supported_ranking", "requires": "ranking_basis=risk_score"},
        )
    result = get_at_risk_account_enrichment_summary(
        quarter=str(quarter).strip(),
        ranking_basis="risk_score",
        owner_scope=owner_scope,
        limit=min(int(limit or 5), 10),
    )
    accounts = result["accounts"]
    if (actor_policy or {}).get("enrichment_access") != "full":
        accounts = [
            {
                **item,
                "parent_company": None,
                "revenue_band": None,
                "employee_band": None,
            }
            for item in accounts
        ]
    return {
        **result,
        "accounts": accounts,
        "bounded_to_account_count": len(accounts),
        "visibility": {
            "enrichment_access": "full" if (actor_policy or {}).get("enrichment_access") == "full" else "bounded",
        },
    }


def fetch_lookalike_accounts(
    reference_account: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 2 GTM mapping for explainable lookalike analysis."""
    if not (actor_policy or {}).get("can_use_lookalikes"):
        raise ANIPError("denied", "Lookalike analysis is not available for this actor role.", resolution={"action": "request_authorized_actor", "requires": "role with lookalike access"})
    if not reference_account or not str(reference_account).strip():
        raise ANIPError("clarification_required", "reference account is missing", resolution={"action": "provide_reference_account", "requires": "reference_account"})
    result = get_lookalike_accounts(reference_account=str(reference_account).strip(), limit=min(int(limit or 5), 10))
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
                {
                    **item,
                    "revenue_band": None,
                    "employee_band": None,
                }
                for item in result["matches"]
            ],
            "visibility": {"enrichment_access": "bounded"},
        }
    return result
