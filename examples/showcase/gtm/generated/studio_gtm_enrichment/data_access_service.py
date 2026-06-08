"""Studio-generated ANIP service scaffold for governed data access."""
# Project: GTM Account Enrichment Data Access
# Service: GTM Enrichment Service

import os

from fastapi import FastAPI

from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal

from data_access_backend_adapter import (
    fetch_account_enrichment_summary,
    fetch_at_risk_account_enrichment_summary,
    fetch_lookalike_accounts,
)


def _actor_policy(ctx: InvocationContext) -> dict:
    return parse_actor_principal(ctx.root_principal)


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
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


GTM_ACCOUNT_ENRICHMENT_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.account_enrichment_summary',
    description='Return bounded firmographic context and fit signals for selected accounts.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='account_names', type='string', required=True, description='Comma-separated account names'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum accounts to summarize'),
    ],
    output=CapabilityOutput(
        type='gtm_account_enrichment_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.enrichment.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '250ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_account_enrichment_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return bounded firmographic context and fit signals for selected accounts."""
# - return only bounded fields from the modeled enrichment view
    actor_policy = _actor_policy(ctx)
    account_names = _require_str(
        params,
        'account_names',
        'account scope is missing',
        'Comma-separated account names',
    )
    limit = params.get('limit')
    return fetch_account_enrichment_summary(account_names=account_names, limit=limit, actor_policy=actor_policy)

gtm_account_enrichment_summary = Capability(declaration=GTM_ACCOUNT_ENRICHMENT_SUMMARY_DECL, handler=_handle_gtm_account_enrichment_summary)

GTM_AT_RISK_ACCOUNT_ENRICHMENT_SUMMARY_DECL = CapabilityDeclaration(
    name='gtm.at_risk_account_enrichment_summary',
    description='Return bounded enrichment context for the top at-risk open accounts in a quarter and optional owner scope. If the risk selection is empty, return success with an empty account list.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='quarter', type='string', required=True, description='Quarter label like 2017-Q2'),
        CapabilityInput(name='owner_scope', type='string', required=False, description='Regional office or company'),
        CapabilityInput(name='ranking_basis', type='string', required=False, default='risk_score', allowed_values=['risk_score'], description='Risk ranking basis'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum accounts to summarize'),
    ],
    output=CapabilityOutput(
        type='gtm_at_risk_account_enrichment_summary_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.pipeline.read', 'gtm.enrichment.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '350ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_at_risk_account_enrichment_summary(ctx: InvocationContext, params: dict) -> dict:
    """Return bounded enrichment context for selected at-risk accounts."""
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(
        params,
        'quarter',
        'quarter is missing',
        'Quarter label like 2017-Q2',
    )
    owner_scope = params.get('owner_scope')
    ranking_basis = params.get('ranking_basis') or 'risk_score'
    limit = params.get('limit')
    return fetch_at_risk_account_enrichment_summary(
        quarter=quarter,
        owner_scope=owner_scope,
        ranking_basis=ranking_basis,
        limit=limit,
        actor_policy=actor_policy,
    )

gtm_at_risk_account_enrichment_summary = Capability(declaration=GTM_AT_RISK_ACCOUNT_ENRICHMENT_SUMMARY_DECL, handler=_handle_gtm_at_risk_account_enrichment_summary)

GTM_LOOKALIKE_ACCOUNTS_DECL = CapabilityDeclaration(
    name='gtm.lookalike_accounts',
    description='Return bounded lookalike accounts using explainable similarity logic.',
    contract_version="1.0",
    inputs=[
        CapabilityInput(name='reference_account', type='string', required=True, description='Reference account name'),
        CapabilityInput(name='limit', type='integer', required=False, description='Maximum lookalike accounts to return'),
    ],
    output=CapabilityOutput(
        type='gtm_lookalike_accounts_result',
        fields=['result'],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window='not_applicable'),
    minimum_scope=['gtm.enrichment.read'],
    cost=Cost(certainty=CostCertainty.FIXED, compute={'latency_p50': '250ms'}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True,
        retention='P90D',
        fields_logged=['capability', 'parameters'],
        audit_accessible_by=['delegation.root_principal'],
    ),
)

def _handle_gtm_lookalike_accounts(ctx: InvocationContext, params: dict) -> dict:
    """Return bounded lookalike accounts using explainable similarity logic."""
# - similarity must remain explainable from modeled account attributes
    actor_policy = _actor_policy(ctx)
    reference_account = _require_str(
        params,
        'reference_account',
        'reference account is missing',
        'Reference account name',
    )
    limit = params.get('limit')
    return fetch_lookalike_accounts(reference_account=reference_account, limit=limit, actor_policy=actor_policy)

gtm_lookalike_accounts = Capability(declaration=GTM_LOOKALIKE_ACCOUNTS_DECL, handler=_handle_gtm_lookalike_accounts)

service = ANIPService(
    service_id='anip-gtm-enrichment-showcase',
    capabilities=[
    gtm_at_risk_account_enrichment_summary,
    gtm_account_enrichment_summary,
    gtm_lookalike_accounts,
    ],
    storage=os.getenv('ANIP_STORAGE', ':memory:'),
    trust=os.getenv('ANIP_TRUST_LEVEL', 'unsigned'),
    key_path=os.getenv('ANIP_KEY_PATH', './anip-keys'),
    authenticate=authenticate_bearer,
)

app = FastAPI(title='Studio Generated Governed Data Access Service')
mount_anip(app, service, health_endpoint=True)

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '9200')))
