"""Bounded GTM pipeline capabilities for the Phase 1 showcase."""
from __future__ import annotations

from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Cost,
    CostCertainty,
    FinancialCost,
    ObservabilityContract,
    ResponseMode,
    SessionInfo,
    SideEffect,
    SideEffectType,
)

import data


def _require_string(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ANIPError(
        "clarification_required",
        question,
        resolution={
            "action": "provide_missing_parameter",
            "requires": field,
            "hint": hint,
        },
    )


def _optional_scope(params: dict) -> str | None:
    value = params.get("owner_scope")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


PIPELINE_SUMMARY_DECL = CapabilityDeclaration(
    name="gtm.pipeline_summary",
    description="Summarize bounded pipeline health for a given quarter and optional region scope.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="quarter", type="string", required=True, description="Quarter label like 2017-Q2"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Regional office or 'company'"),
        CapabilityInput(name="detail_level", type="string", required=False, default="summary", description="summary or stage_breakdown"),
    ],
    output=CapabilityOutput(
        type="pipeline_summary",
        fields=["quarter", "owner_scope", "by_stage", "totals"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.pipeline.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "150ms", "tokens": 500}),
    session=SessionInfo(),
    response_modes=[ResponseMode.UNARY],
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_pipeline_summary(ctx: InvocationContext, params: dict) -> dict:
    quarter = _require_string(
        params,
        "quarter",
        "Which quarter should I summarize?",
        "Use a quarter like 2017-Q2.",
    )
    detail_level = str(params.get("detail_level", "summary")).strip().lower()
    if detail_level == "raw_records":
        raise ANIPError(
            "denied",
            "Raw row-level pipeline exports are out of scope for this capability.",
            resolution={
                "action": "request_bounded_summary",
                "requires": "detail_level=summary or stage_breakdown",
            },
        )

    summary = data.get_pipeline_summary(quarter=quarter, owner_scope=_optional_scope(params))
    if detail_level == "summary":
        summary["by_stage"] = [
            {
                "deal_stage": row["deal_stage"],
                "opportunity_count": row["opportunity_count"],
                "open_pipeline_value": row["open_pipeline_value"],
                "average_open_risk_score": row["average_open_risk_score"],
            }
            for row in summary["by_stage"]
        ]
    return summary


pipeline_summary = Capability(declaration=PIPELINE_SUMMARY_DECL, handler=_handle_pipeline_summary)


STALLED_OPPS_DECL = CapabilityDeclaration(
    name="gtm.stalled_opportunity_review",
    description="Review open opportunities that have been stuck in the pipeline beyond a bounded threshold.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="quarter", type="string", required=True, description="Quarter label like 2017-Q2"),
        CapabilityInput(name="min_days_open", type="integer", required=False, default=30, description="Minimum days open"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Regional office or 'company'"),
        CapabilityInput(name="limit", type="integer", required=False, default=10, description="Maximum opportunity count"),
    ],
    output=CapabilityOutput(
        type="stalled_opportunity_review",
        fields=["quarter", "opportunities"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.pipeline.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "180ms", "tokens": 700}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_stalled_opportunities(ctx: InvocationContext, params: dict) -> dict:
    quarter = _require_string(
        params,
        "quarter",
        "Which quarter should I review for stalled opportunities?",
        "Use a quarter like 2017-Q2.",
    )
    min_days_open = int(params.get("min_days_open", 30))
    limit = min(int(params.get("limit", 10)), 25)
    opportunities = data.get_stalled_opportunities(
        quarter=quarter,
        min_days_open=min_days_open,
        owner_scope=_optional_scope(params),
        limit=limit,
    )
    return {
        "quarter": quarter,
        "min_days_open": min_days_open,
        "opportunities": opportunities,
    }


stalled_opportunity_review = Capability(
    declaration=STALLED_OPPS_DECL,
    handler=_handle_stalled_opportunities,
)


ACCOUNT_RISK_DECL = CapabilityDeclaration(
    name="gtm.account_risk_summary",
    description="Rank the highest-risk open accounts in a bounded quarter and scope.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="quarter", type="string", required=True, description="Quarter label like 2017-Q2"),
        CapabilityInput(name="top_n", type="integer", required=False, default=10, description="How many accounts to rank"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Regional office or 'company'"),
        CapabilityInput(name="ranking_basis", type="string", required=True, description="Use risk_score for Phase 1"),
    ],
    output=CapabilityOutput(
        type="account_risk_summary",
        fields=["quarter", "ranking_basis", "accounts"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.pipeline.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "220ms", "tokens": 850}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_account_risk_summary(ctx: InvocationContext, params: dict) -> dict:
    quarter = _require_string(
        params,
        "quarter",
        "Which quarter should I analyze for account risk?",
        "Use a quarter like 2017-Q2.",
    )
    ranking_basis = _require_string(
        params,
        "ranking_basis",
        "How should I rank the accounts?",
        "For Phase 1, use ranking_basis=risk_score.",
    )
    if ranking_basis != "risk_score":
        raise ANIPError(
            "denied",
            "Phase 1 only supports ranking accounts by risk_score.",
            resolution={
                "action": "retry_with_supported_ranking",
                "requires": "ranking_basis=risk_score",
            },
        )
    top_n = min(int(params.get("top_n", 10)), 20)
    accounts = data.get_account_risk_summary(
        quarter=quarter,
        top_n=top_n,
        owner_scope=_optional_scope(params),
    )
    return {
        "quarter": quarter,
        "ranking_basis": ranking_basis,
        "accounts": accounts,
    }


account_risk_summary = Capability(declaration=ACCOUNT_RISK_DECL, handler=_handle_account_risk_summary)


FOLLOWUP_DECL = CapabilityDeclaration(
    name="gtm.prepare_followup_tasks",
    description="Prepare a bounded follow-up task plan for the highest-risk accounts in scope.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="quarter", type="string", required=True, description="Quarter label like 2017-Q2"),
        CapabilityInput(name="ranking_basis", type="string", required=True, description="Use risk_score for Phase 1"),
        CapabilityInput(name="top_n", type="integer", required=False, default=5, description="How many accounts to include"),
        CapabilityInput(name="owner_scope", type="string", required=False, description="Regional office or 'company'"),
        CapabilityInput(name="approval_reference", type="string", required=False, description="Approval reference for downstream execution"),
    ],
    output=CapabilityOutput(
        type="followup_task_plan",
        fields=["quarter", "tasks", "requires_approval"],
    ),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="PT2H"),
    minimum_scope=["gtm.pipeline.followup"],
    cost=Cost(
        certainty=CostCertainty.ESTIMATED,
        financial=FinancialCost(currency="USD", typical=0, range_min=0, range_max=0),
        compute={"latency_p50": "250ms", "tokens": 1200},
    ),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention="P90D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_prepare_followup_tasks(ctx: InvocationContext, params: dict) -> dict:
    quarter = _require_string(
        params,
        "quarter",
        "Which quarter should I use for follow-up preparation?",
        "Use a quarter like 2017-Q2.",
    )
    ranking_basis = _require_string(
        params,
        "ranking_basis",
        "How should I select accounts for follow-up?",
        "For Phase 1, use ranking_basis=risk_score.",
    )
    if ranking_basis != "risk_score":
        raise ANIPError(
            "denied",
            "Phase 1 follow-up preparation only supports ranking_basis=risk_score.",
            resolution={
                "action": "retry_with_supported_ranking",
                "requires": "ranking_basis=risk_score",
            },
        )

    accounts = data.get_account_risk_summary(
        quarter=quarter,
        top_n=min(int(params.get("top_n", 5)), 10),
        owner_scope=_optional_scope(params),
    )
    tasks = [
        {
            "account_name": row["account_name"],
            "regional_office": row["regional_office"],
            "recommended_owner": row["sales_agents"].split(",")[0] if row["sales_agents"] else "unassigned",
            "task_type": "risk_review_followup",
            "reason": (
                f"Average risk score {row['average_risk_score']} with "
                f"{row['open_opportunity_count']} open opportunities and max age {row['max_days_open']} days."
            ),
            "suggested_due_in_days": 3,
        }
        for row in accounts
    ]

    approval_reference = params.get("approval_reference")
    if not approval_reference:
        raise ANIPError(
            "approval_required",
            "Follow-up task execution requires manager approval before downstream mutation.",
            resolution={
                "action": "request_followup_approval",
                "requires": "approval_reference",
                "grantable_by": "regional_sales_manager",
                "preview": tasks,
            },
        )

    return {
        "quarter": quarter,
        "requires_approval": False,
        "approval_reference": str(approval_reference),
        "tasks": tasks,
    }


prepare_followup_tasks = Capability(declaration=FOLLOWUP_DECL, handler=_handle_prepare_followup_tasks)
