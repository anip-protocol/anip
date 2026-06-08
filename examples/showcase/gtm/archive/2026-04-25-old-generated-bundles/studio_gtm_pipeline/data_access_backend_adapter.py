"""Studio-generated backend adapter scaffold for the GTM pipeline showcase."""
# Backend type: cube_rest
# Target: Cube semantic query surface
# Backend template: generated-backend-template:semantic-query

from anip_service import ANIPError

try:
    from backend_extensions import preprocess_backend_params
except ImportError:
    def preprocess_backend_params(operation: str, params: dict) -> dict:
        return dict(params or {})

from data import (
    get_account_risk_summary,
    get_pipeline_forecast_summary,
    get_pipeline_summary,
    get_product_pipeline_summary,
    get_reassignment_plan_preview,
    get_sales_team_performance_summary,
    get_stage_bottleneck_summary,
    get_stalled_opportunities,
)


def fetch_pipeline_summary(
    quarter: str | None = None,
    owner_scope: str | None = None,
    detail_level: str | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 1 GTM mapping over the modeled pipeline dataset."""
    if detail_level == 'raw_records':
        raise ANIPError("denied", "Raw row-level pipeline exports are out of scope for this capability.", resolution={"action": "request_bounded_summary", "requires": "detail_level=summary or stage_breakdown"})
    summary = get_pipeline_summary(quarter=quarter or '2017-Q2', owner_scope=owner_scope)
    if detail_level == 'summary':
        summary['by_stage'] = [
            {
                'deal_stage': row['deal_stage'],
                'opportunity_count': row['opportunity_count'],
                'open_pipeline_value': row['open_pipeline_value'],
                'average_open_risk_score': row['average_open_risk_score'],
            }
            for row in summary['by_stage']
        ]
    if (actor_policy or {}).get("financial_access") != "full":
        for row in summary["by_stage"]:
            row["open_pipeline_value"] = None
            row["won_revenue"] = None
        summary["totals"]["open_pipeline_value"] = None
        summary["totals"]["won_revenue"] = None
        summary["visibility"] = {
            "financial_values": "masked",
            "reason": "actor policy does not allow financial values in this view",
        }
    return summary


def fetch_pipeline_forecast_summary(
    quarter: str | None = None,
    owner_scope: str | None = None,
    forecast_mode: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 6 GTM mapping for bounded forecast review."""
    if forecast_mode and forecast_mode not in {"risk_adjusted", "likely", "best_case"}:
        raise ANIPError(
            "denied",
            "Pipeline forecast only supports forecast_mode=risk_adjusted, likely, or best_case.",
            resolution={
                "action": "retry_with_supported_forecast_mode",
                "requires": "forecast_mode=risk_adjusted, likely, or best_case",
            },
        )
    summary = get_pipeline_forecast_summary(
        quarter=quarter or "2017-Q2",
        owner_scope=owner_scope,
        forecast_mode=forecast_mode or "risk_adjusted",
        limit=min(int(limit or 5), 10),
    )
    if (actor_policy or {}).get("financial_access") != "full":
        for row in summary["by_stage"]:
            row["open_pipeline_value"] = None
            row["likely_revenue"] = None
            row["best_case_revenue"] = None
            row["risk_adjusted_revenue"] = None
            row["selected_forecast_value"] = None
        for row in summary["top_contributors"]:
            row["open_pipeline_value"] = None
            row["likely_revenue"] = None
            row["best_case_revenue"] = None
            row["risk_adjusted_revenue"] = None
            row["selected_forecast_value"] = None
        summary["totals"]["open_pipeline_value"] = None
        summary["totals"]["likely_revenue"] = None
        summary["totals"]["best_case_revenue"] = None
        summary["totals"]["risk_adjusted_revenue"] = None
        summary["totals"]["selected_forecast_value"] = None
        summary["visibility"] = {
            "financial_values": "masked",
            "reason": "actor policy does not allow financial forecast values in this view",
        }
    else:
        summary["visibility"] = {"financial_values": "full"}
    return summary


def fetch_stage_bottleneck_summary(
    quarter: str | None = None,
    owner_scope: str | None = None,
    slice_by: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 6 GTM mapping for bounded stage bottleneck review."""
    if slice_by and slice_by not in {"regional_office", "manager_name", "product_name"}:
        raise ANIPError(
            "denied",
            "Stage bottleneck summary only supports slice_by=regional_office, manager_name, or product_name.",
            resolution={
                "action": "retry_with_supported_slice",
                "requires": "slice_by=regional_office, manager_name, or product_name",
            },
        )
    summary = get_stage_bottleneck_summary(
        quarter=quarter or "2017-Q2",
        owner_scope=owner_scope,
        slice_by=slice_by or "regional_office",
        limit=min(int(limit or 10), 15),
    )
    if (actor_policy or {}).get("financial_access") != "full":
        for row in summary["bottlenecks"]:
            row["open_pipeline_value"] = None
        summary["visibility"] = {
            "financial_values": "masked",
            "reason": "actor policy does not allow financial values in this bottleneck view",
        }
    else:
        summary["visibility"] = {"financial_values": "full"}
    return summary


def fetch_sales_team_performance_summary(
    quarter: str | None = None,
    owner_scope: str | None = None,
    slice_by: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 6 GTM mapping for bounded sales team performance review."""
    if slice_by and slice_by not in {"manager_name", "regional_office"}:
        raise ANIPError(
            "denied",
            "Sales team performance only supports slice_by=manager_name or regional_office.",
            resolution={
                "action": "retry_with_supported_slice",
                "requires": "slice_by=manager_name or regional_office",
            },
        )
    summary = get_sales_team_performance_summary(
        quarter=quarter or "2017-Q2",
        owner_scope=owner_scope,
        slice_by=slice_by or "manager_name",
        limit=min(int(limit or 10), 15),
    )
    if (actor_policy or {}).get("financial_access") != "full":
        for row in summary["performance_rows"]:
            row["open_pipeline_value"] = None
            row["won_revenue"] = None
        summary["visibility"] = {
            "financial_values": "masked",
            "reason": "actor policy does not allow financial values in this team performance view",
        }
    else:
        summary["visibility"] = {"financial_values": "full"}
    return summary


def fetch_product_pipeline_summary(
    quarter: str | None = None,
    owner_scope: str | None = None,
    product_scope: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 6 GTM mapping for bounded product pipeline review."""
    normalized = preprocess_backend_params(
        "fetch_product_pipeline_summary",
        {
            "quarter": quarter,
            "owner_scope": owner_scope,
            "product_scope": product_scope,
            "limit": limit,
            "actor_policy": actor_policy,
        },
    )
    quarter = normalized.get("quarter")
    owner_scope = normalized.get("owner_scope")
    product_scope = normalized.get("product_scope")
    limit = normalized.get("limit")
    actor_policy = normalized.get("actor_policy")
    summary = get_product_pipeline_summary(
        quarter=quarter or "2017-Q2",
        owner_scope=owner_scope,
        product_scope=str(product_scope).strip() if product_scope else None,
        limit=min(int(limit or 10), 15),
    )
    if (actor_policy or {}).get("financial_access") != "full":
        for row in summary["products"]:
            row["open_pipeline_value"] = None
            row["won_revenue"] = None
        summary["visibility"] = {
            "financial_values": "masked",
            "reason": "actor policy does not allow financial values in this product pipeline view",
        }
    else:
        summary["visibility"] = {"financial_values": "full"}
    return summary


def preview_reassignment_plan(
    quarter: str | None = None,
    owner_scope: str | None = None,
    selection_basis: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 6 GTM mapping for approval-gated reassignment planning."""
    if selection_basis and selection_basis not in {"manager_capacity", "stalled_risk_mix"}:
        raise ANIPError(
            "denied",
            "Reassignment planning only supports selection_basis=manager_capacity or stalled_risk_mix.",
            resolution={
                "action": "retry_with_supported_selection_basis",
                "requires": "selection_basis=manager_capacity or stalled_risk_mix",
            },
        )
    preview = get_reassignment_plan_preview(
        quarter=quarter or "2017-Q2",
        owner_scope=owner_scope,
        selection_basis=selection_basis or "manager_capacity",
        limit=min(int(limit or 5), 10),
    )
    preview["visibility"] = {"financial_values": "not_used_in_preview"}
    return preview


def fetch_stalled_opportunities(
    quarter: str | None = None,
    min_days_open: int | None = None,
    owner_scope: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 1 GTM mapping for stalled opportunity review."""
    opportunities = get_stalled_opportunities(
        quarter=quarter or '2017-Q2',
        min_days_open=int(min_days_open or 30),
        owner_scope=owner_scope,
        limit=min(int(limit or 10), 25),
    )
    return {
        'quarter': quarter or '2017-Q2',
        'owner_scope': owner_scope or 'company',
        'opportunities': opportunities,
    }


def fetch_account_risk_summary(
    quarter: str | None = None,
    ranking_basis: str | None = None,
    owner_scope: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 1 GTM mapping for account-risk ranking."""
    if ranking_basis and ranking_basis != 'risk_score':
        raise ANIPError("denied", "Phase 1 account risk ranking only supports ranking_basis=risk_score.", resolution={"action": "retry_with_supported_ranking", "requires": "ranking_basis=risk_score"})
    accounts = get_account_risk_summary(
        quarter=quarter or '2017-Q2',
        top_n=min(int(limit or 10), 10),
        owner_scope=owner_scope,
    )
    return {
        'quarter': quarter or '2017-Q2',
        'owner_scope': owner_scope or 'company',
        'ranking_basis': ranking_basis or 'risk_score',
        'accounts': [
            {
                **row,
                "open_pipeline_value": row.get("open_pipeline_value")
                if (actor_policy or {}).get("financial_access") == "full"
                else None,
            }
            for row in accounts
        ],
        'visibility': {
            'financial_values': 'full' if (actor_policy or {}).get("financial_access") == "full" else 'masked',
        },
    }


def preview_followup_task_plan(
    quarter: str | None = None,
    ranking_basis: str | None = None,
    owner_scope: str | None = None,
    limit: int | None = None,
    actor_policy: dict | None = None,
) -> dict:
    """Concrete Phase 1 GTM follow-up preview used before approval."""
    ranking_basis = ranking_basis or 'risk_score'
    if ranking_basis != 'risk_score':
        raise ANIPError("denied", "Phase 1 follow-up preparation only supports ranking_basis=risk_score.", resolution={"action": "retry_with_supported_ranking", "requires": "ranking_basis=risk_score"})
    accounts = get_account_risk_summary(
        quarter=quarter or '2017-Q2',
        top_n=min(int(limit or 5), 10),
        owner_scope=owner_scope,
    )
    tasks = [
        {
            'account_name': row['account_name'],
            'regional_office': row['regional_office'],
            'recommended_owner': row['sales_agents'].split(',')[0] if row['sales_agents'] else 'unassigned',
            'task_type': 'risk_review_followup',
            'reason': f"Average risk score {row['average_risk_score']} with {row['open_opportunity_count']} open opportunities and max age {row['max_days_open']} days.",
            'suggested_due_in_days': 3,
        }
        for row in accounts
    ]
    return {
        'quarter': quarter or '2017-Q2',
        'owner_scope': owner_scope or 'company',
        'ranking_basis': ranking_basis,
        'requires_approval': True,
        'tasks': tasks,
    }
