"""Studio-generated ANIP service scaffold for governed data access."""
# Project: GTM Pipeline Service
# Service: GTM Pipeline Service

import os
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal
from shared.approval_store import approve_request, create_approval_request, list_approval_requests
from .capabilities import generated_capabilities_for_service
from .service_extensions import (
    actor_from_bearer,
    approval_role_required,
    ensure_can_prepare_pipeline_write,
    filter_approval_entries,
    resolve_pipeline_scope,
)

from .data_access_backend_adapter import (
    fetch_stage_bottleneck_summary,
    fetch_sales_team_performance_summary,
    fetch_product_pipeline_summary,
    fetch_pipeline_summary,
    fetch_pipeline_forecast_summary,
    fetch_stalled_opportunities,
    fetch_account_risk_summary,
    preview_followup_task_plan,
    preview_reassignment_plan,
)

APPROVAL_GRANT_POLICY = {
    "allowed_grant_types": ["one_time", "session_bound"],
    "default_grant_type": "one_time",
    "expires_in_seconds": 900,
    "max_uses": 1,
}

QUARTER_LABEL_RE = re.compile(r"^\d{4}-Q[1-4]$")


def _actor_policy(ctx: InvocationContext) -> dict:
    return parse_actor_principal(ctx.root_principal)


def _actor_from_bearer(bearer: str | None) -> dict:
    return actor_from_bearer(bearer)


def _resolve_pipeline_scope(requested_scope: str | None, actor_policy: dict) -> str | None:
    return resolve_pipeline_scope(requested_scope, actor_policy)


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        normalized = value.strip()
        if field == "quarter" and not QUARTER_LABEL_RE.match(normalized):
            raise ANIPError(
                "clarification_required",
                question,
                resolution={"action": "provide_explicit_parameter", "requires": field, "hint": hint},
            )
        return normalized
    raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})


def _require_int(params: dict, field: str, question: str, hint: str) -> int:
    value = params.get(field)
    if value is None or value == '':
        raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})
    return int(value)


def _require_float(params: dict, field: str, question: str, hint: str) -> float:
    value = params.get(field)
    if value is None or value == '':
        raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})
    return float(value)


def _require_bool(params: dict, field: str, question: str, hint: str) -> bool:
    value = params.get(field)
    if value is None or value == '':
        raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {'true', '1', 'yes'}:
        return True
    if lowered in {'false', '0', 'no'}:
        return False
    raise ANIPError("clarification_required", question, resolution={"action": "provide_boolean_parameter", "requires": field, "hint": hint})


GTM_PIPELINE_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.pipeline_summary',
    description='Return a bounded pipeline health summary for a quarter and optional scope.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='detail_level', type='string', required=False, default='summary', allowed_values=['summary', 'stage_breakdown'], description='summary or stage_breakdown'),
    ],
    output=CapabilityOutput(
        type='gtm_pipeline_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '250ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_pipeline_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return a bounded pipeline health summary for a quarter and optional scope."""
# - read from dbt-modeled pipeline views
# - use Cube measures for bounded aggregations
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    actor_policy = _actor_policy(ctx)
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    detail_level = params.get('detail_level')
    return fetch_pipeline_summary(quarter=quarter, owner_scope=owner_scope, detail_level=detail_level, actor_policy=actor_policy)

gtm_pipeline_summary = Capability(declaration=GTM_PIPELINE_SUMMARY_DECL, handler=_handle_gtm_pipeline_summary)

GTM_PIPELINE_FORECAST_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.pipeline_forecast_summary',
    description='Return a bounded forecast summary for open pipeline with likely, best-case, and risk-adjusted views.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='forecast_mode', type='string', required=False, default='risk_adjusted', allowed_values=['risk_adjusted', 'likely', 'best_case'], description='risk_adjusted, likely, or best_case'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum contributing accounts to return'),
    ],
    output=CapabilityOutput(
        type='gtm_pipeline_forecast_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '300ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_pipeline_forecast_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return a bounded forecast summary for open pipeline with likely, best-case, and risk-adjusted views."""
# - read aggregate forecast slices through Cube over dbt-modeled GTM opportunities
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    forecast_mode = params.get('forecast_mode')
    limit = params.get('limit')
    return fetch_pipeline_forecast_summary(
        quarter=quarter,
        owner_scope=owner_scope,
        forecast_mode=forecast_mode,
        limit=limit,
        actor_policy=actor_policy,
    )

gtm_pipeline_forecast_summary = Capability(declaration=GTM_PIPELINE_FORECAST_SUMMARY_DECL, handler=_handle_gtm_pipeline_forecast_summary)

GTM_STAGE_BOTTLENECK_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.stage_bottleneck_summary',
    description='Return a bounded stage bottleneck summary for open pipeline by an allowed slice.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='slice_by', type='string', required=False, default='regional_office', allowed_values=['regional_office', 'manager_name', 'product_name'], description='regional_office, manager_name, or product_name'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum bottleneck rows to return'),
    ],
    output=CapabilityOutput(
        type='gtm_stage_bottleneck_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '300ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_stage_bottleneck_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return a bounded stage bottleneck summary for open pipeline by an allowed slice."""
# - read aggregate stage-accumulation slices through Cube over dbt-modeled GTM opportunities
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    slice_by = params.get('slice_by')
    limit = params.get('limit')
    return fetch_stage_bottleneck_summary(
        quarter=quarter,
        owner_scope=owner_scope,
        slice_by=slice_by,
        limit=limit,
        actor_policy=actor_policy,
    )

gtm_stage_bottleneck_summary = Capability(declaration=GTM_STAGE_BOTTLENECK_SUMMARY_DECL, handler=_handle_gtm_stage_bottleneck_summary)

GTM_SALES_TEAM_PERFORMANCE_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.sales_team_performance_summary',
    description='Return a bounded sales team performance summary for a quarter and optional scope.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='slice_by', type='string', required=False, default='manager_name', allowed_values=['manager_name', 'regional_office'], description='manager_name or regional_office'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum team rows to return'),
    ],
    output=CapabilityOutput(
        type='gtm_sales_team_performance_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '300ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_sales_team_performance_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return a bounded sales team performance summary for a quarter and optional scope."""
# - read aggregate team slices through Cube over dbt-modeled GTM pipeline views
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    slice_by = params.get('slice_by')
    limit = params.get('limit')
    return fetch_sales_team_performance_summary(
        quarter=quarter,
        owner_scope=owner_scope,
        slice_by=slice_by,
        limit=limit,
        actor_policy=actor_policy,
    )

gtm_sales_team_performance_summary = Capability(declaration=GTM_SALES_TEAM_PERFORMANCE_SUMMARY_DECL, handler=_handle_gtm_sales_team_performance_summary)

GTM_PRODUCT_PIPELINE_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.product_pipeline_summary',
    description='Return a bounded product pipeline summary for a quarter and optional scope.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='product_scope', type='string', required=False, semantic_type='entity_reference', entity_reference=True, catalog_ref='gtm.product_catalog', description='Specific product to focus on'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum product rows to return'),
    ],
    output=CapabilityOutput(
        type='gtm_product_pipeline_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '300ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_product_pipeline_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return a bounded product pipeline summary for a quarter and optional scope."""
# - read aggregate product slices through Cube over dbt-modeled GTM opportunities
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    product_scope = params.get('product_scope')
    limit = params.get('limit')
    return fetch_product_pipeline_summary(
        quarter=quarter,
        owner_scope=owner_scope,
        product_scope=product_scope,
        limit=limit,
        actor_policy=actor_policy,
    )

gtm_product_pipeline_summary = Capability(declaration=GTM_PRODUCT_PIPELINE_SUMMARY_DECL, handler=_handle_gtm_product_pipeline_summary)

GTM_PREPARE_REASSIGNMENT_PLAN_DECL = CapabilityDeclaration(
    name='gtm.prepare_reassignment_plan',
    description='Prepare a reassignment preview for overloaded pipeline coverage without executing downstream mutations.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='selection_basis', type='string', required=False, default='manager_capacity', allowed_values=['manager_capacity', 'stalled_risk_mix'], description='manager_capacity or stalled_risk_mix'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum reassignment candidates to include'),
    ],
    output=CapabilityOutput(
        type='gtm_prepare_reassignment_plan_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.reassign'],
    grant_policy=APPROVAL_GRANT_POLICY,
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '300ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_prepare_reassignment_plan(ctx: InvocationContext, params: dict) -> dict:
    """Prepare a reassignment preview for overloaded pipeline coverage without executing downstream mutations."""
# - return approval_required with a bounded reassignment preview instead of mutating assignments
    actor_policy = _actor_policy(ctx)
    ensure_can_prepare_pipeline_write(
        actor_policy,
        action_label="reassignment work",
        authority_label="role with reassignment planning authority",
    )
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    selection_basis = params.get('selection_basis')
    limit = params.get('limit')
    preview = preview_reassignment_plan(
        quarter=quarter,
        owner_scope=owner_scope,
        selection_basis=selection_basis,
        limit=limit,
        actor_policy=actor_policy,
    )
    approval_request = create_approval_request(
        capability='gtm.prepare_reassignment_plan',
        requester=actor_policy,
        required_role='sales_leader',
        preview=preview,
    )
    raise ANIPError(
        "approval_required",
        'any downstream reassignment execution would occur',
        resolution={
            "action": "request_approval",
            "requires": "approval before downstream reassignment",
            "preview": preview,
            "approval_request_id": approval_request["approval_request_id"],
            "approval_role_required": approval_role_required(actor_policy),
        },
    )

gtm_prepare_reassignment_plan = Capability(
    declaration=GTM_PREPARE_REASSIGNMENT_PLAN_DECL,
    handler=_handle_gtm_prepare_reassignment_plan,
)

GTM_STALLED_OPPORTUNITY_REVIEW_DECL = CapabilityDeclaration(
    name='gtm.stalled_opportunity_review',
    description='Return stalled open opportunities with bounded evidence and explainable stall reasoning.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='min_days_open', type='integer', required=False, description='Minimum days open'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum opportunities to return'),
    ],
    output=CapabilityOutput(
        type='gtm_stalled_opportunity_review_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '250ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_stalled_opportunity_review(ctx: InvocationContext, params: dict) -> dict:
    """Return stalled open opportunities with bounded evidence and explainable stall reasoning."""
# - derive stall duration from modeled opportunity dates
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'stalled-days threshold is missing when the request is ambiguous',
        'Quarter label like 2017-Q2',
    )
    min_days_open = params.get('min_days_open')
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    limit = params.get('limit')
    return fetch_stalled_opportunities(quarter=quarter, min_days_open=min_days_open, owner_scope=owner_scope, limit=limit, actor_policy=actor_policy)

gtm_stalled_opportunity_review = Capability(declaration=GTM_STALLED_OPPORTUNITY_REVIEW_DECL, handler=_handle_gtm_stalled_opportunity_review)

GTM_ACCOUNT_RISK_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.account_risk_summary',
    description='Rank at-risk accounts with explicit evidence for why they need attention.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='ranking_basis', type='string', required=True, default='risk_score', allowed_values=['risk_score'], description='Risk ranking basis'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum accounts to return'),
    ],
    output=CapabilityOutput(
        type='gtm_account_risk_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '250ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_account_risk_summary(ctx: InvocationContext, params: dict) -> dict:
    """Rank at-risk accounts with explicit evidence for why they need attention."""
# - risk ranking must stay explainable in the response payload
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    ranking_basis = params.get('ranking_basis') or 'risk_score'
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    limit = params.get('limit')
    return fetch_account_risk_summary(quarter=quarter, ranking_basis=ranking_basis, owner_scope=owner_scope, limit=limit, actor_policy=actor_policy)

gtm_account_risk_summary = Capability(declaration=GTM_ACCOUNT_RISK_SUMMARY_DECL, handler=_handle_gtm_account_risk_summary)

GTM_PREPARE_FOLLOWUP_TASKS_DECL = CapabilityDeclaration(
    name='gtm.prepare_followup_tasks',
    description='Prepare follow-up tasks for high-risk accounts without executing downstream mutations.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, semantic_type='time_scope', description='Quarter label like 2017-Q2'),
        CapabilityInput(name='ranking_basis', type='string', required=True, default='risk_score', allowed_values=['risk_score'], description='Risk ranking basis'),
        CapabilityInput(name='owner_scope', type='string', required=False, semantic_type='scope_reference', description='Regional office or company'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum accounts to include'),
    ],
    output=CapabilityOutput(
        type='gtm_prepare_followup_tasks_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.followup'],
    grant_policy=APPROVAL_GRANT_POLICY,
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '250ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_prepare_followup_tasks(ctx: InvocationContext, params: dict) -> dict:
    """Prepare follow-up tasks for high-risk accounts without executing downstream mutations."""
# - return approval_required with a preview payload instead of mutating downstream systems
    actor_policy = _actor_policy(ctx)
    ensure_can_prepare_pipeline_write(
        actor_policy,
        action_label="follow-up work",
        authority_label="role with follow-up preparation authority",
    )
    quarter = _require_str(
        params,
        'quarter',
        'target accounts or quarter are missing',
        'Quarter label like 2017-Q2',
    )
    ranking_basis = params.get('ranking_basis') or 'risk_score'
    owner_scope = _resolve_pipeline_scope(params.get('owner_scope'), actor_policy)
    limit = params.get('limit')
    preview = preview_followup_task_plan(quarter=quarter, ranking_basis=ranking_basis, owner_scope=owner_scope, limit=limit, actor_policy=actor_policy)
    approval_request = create_approval_request(
        capability='gtm.prepare_followup_tasks',
        requester=actor_policy,
        required_role='sales_leader',
        preview=preview,
    )
    raise ANIPError(
        "approval_required",
        'any downstream task creation or CRM mutation would occur',
        resolution={
            "action": "request_approval",
            "requires": "approval before downstream mutation",
            "preview": preview,
            "approval_request_id": approval_request["approval_request_id"],
            "approval_role_required": approval_role_required(actor_policy),
        },
    )

gtm_prepare_followup_tasks = Capability(declaration=GTM_PREPARE_FOLLOWUP_TASKS_DECL, handler=_handle_gtm_prepare_followup_tasks)

custom_capabilities = [
    gtm_pipeline_summary,
    gtm_pipeline_forecast_summary,
    gtm_stage_bottleneck_summary,
    gtm_sales_team_performance_summary,
    gtm_product_pipeline_summary,
    gtm_prepare_reassignment_plan,
    gtm_stalled_opportunity_review,
    gtm_account_risk_summary,
    gtm_prepare_followup_tasks,
]

custom_capability_names = {capability.declaration.name for capability in custom_capabilities}
custom_capability_registry = {capability.declaration.name: capability for capability in custom_capabilities}
combined_capabilities = [
    *custom_capabilities,
    *[
        capability
        for capability in generated_capabilities_for_service('gtm-pipeline-service', capability_registry=custom_capability_registry)
        if capability.declaration.name not in custom_capability_names
    ],
]

service = ANIPService(
    service_id=os.getenv('ANIP_SERVICE_ID', 'gtm-pipeline-service'),
    capabilities=combined_capabilities,
    storage=os.getenv('ANIP_STORAGE', ':memory:'),
    trust=os.getenv('ANIP_TRUST_LEVEL', 'unsigned'),
    key_path=os.getenv('ANIP_KEY_PATH', './anip-keys'),
    authenticate=authenticate_bearer,
)

app = FastAPI(title='Studio Generated Governed Data Access Service')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ANIP-Signature"],
)
mount_anip(app, service, health_endpoint=True)


def create_service() -> ANIPService:
    return service


def create_app() -> FastAPI:
    return app


@app.get("/gtm/approvals")
async def list_approvals(request: Request, status: str | None = None):
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.startswith("Bearer ") else None
    actor_policy = _actor_from_bearer(bearer)
    entries = list_approval_requests(status=status)
    return {"entries": filter_approval_entries(entries, actor_policy)}


@app.post("/gtm/approvals/{approval_request_id}/approve")
async def approve(approval_request_id: str, request: Request):
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.startswith("Bearer ") else None
    actor_policy = _actor_from_bearer(bearer)
    if not actor_policy.get("can_approve_followup"):
        raise HTTPException(status_code=403, detail="This actor cannot approve follow-up work")
    record = approve_request(approval_request_id, actor_policy)
    if not record:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return {"approval": record}

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '9200')))
