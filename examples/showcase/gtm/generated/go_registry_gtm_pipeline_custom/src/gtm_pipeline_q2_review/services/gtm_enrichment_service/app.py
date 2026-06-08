"""Benchmark-grade GTM enrichment ANIP service."""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, Cost, CostCertainty, ObservabilityContract, SessionInfo, SideEffect, SideEffectType
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from shared.actor_identity import authenticate_bearer, parse_actor_principal

from ...enrichment_backend_adapter import fetch_account_enrichment_summary, fetch_at_risk_account_enrichment_summary, fetch_lookalike_accounts
from ...service_extensions import resolve_pipeline_scope


SERVICE_ID = "gtm-enrichment-service"


def _actor_policy(ctx: InvocationContext) -> dict:
    return parse_actor_principal(ctx.root_principal)


def _require_str(params: dict, field: str, question: str, hint: str) -> str:
    value = params.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ANIPError("clarification_required", question, resolution={"action": "provide_missing_parameter", "requires": field, "hint": hint})


GTM_ACCOUNT_ENRICHMENT_SUMMARY_DECL = CapabilityDeclaration(
    name="gtm.account_enrichment_summary",
    description="Return bounded firmographic context and fit signals for selected accounts; raw records, full exports, underlying notes, and debug payloads are not supported.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="account_names", type="string", required=True, semantic_type="entity_reference", entity_reference=True, catalog_ref="gtm.account_catalog", description="Comma-separated account names"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum accounts to summarize"),
    ],
    output=CapabilityOutput(type="gtm_account_enrichment_summary_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.enrichment.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


def _handle_gtm_account_enrichment_summary(ctx: InvocationContext, params: dict) -> dict:
    account_names = _require_str(params, "account_names", "account scope is missing", "Use comma-separated account names.")
    return fetch_account_enrichment_summary(account_names=account_names, limit=params.get("limit"), actor_policy=_actor_policy(ctx))


GTM_LOOKALIKE_ACCOUNTS_DECL = CapabilityDeclaration(
    name="gtm.lookalike_accounts",
    description="Return bounded lookalike accounts using explainable similarity logic; raw payloads and underlying model data are not supported.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="reference_account", type="string", required=True, semantic_type="entity_reference", entity_reference=True, catalog_ref="gtm.account_catalog", description="Reference account name"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum lookalike accounts to return"),
    ],
    output=CapabilityOutput(type="gtm_lookalike_accounts_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.enrichment.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "250ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


def _handle_gtm_lookalike_accounts(ctx: InvocationContext, params: dict) -> dict:
    reference_account = _require_str(params, "reference_account", "reference account is missing", "Use Condax, Acme Corporation, or Codehow.")
    return fetch_lookalike_accounts(reference_account=reference_account, limit=params.get("limit"), actor_policy=_actor_policy(ctx))


GTM_AT_RISK_ACCOUNT_ENRICHMENT_SUMMARY_DECL = CapabilityDeclaration(
    name="gtm.at_risk_account_enrichment_summary",
    description="Rank at-risk accounts and return bounded enrichment context for the selected accounts.",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="quarter", type="string", required=True, semantic_type="time_scope", description="Quarter label like 2017-Q2"),
        CapabilityInput(name="ranking_basis", type="string", required=False, default="risk_score", allowed_values=["risk_score"], description="Risk ranking basis"),
        CapabilityInput(name="owner_scope", type="string", required=False, semantic_type="scope_reference", description="Regional office or company"),
        CapabilityInput(name="limit", type="integer", required=False, description="Maximum accounts to enrich"),
    ],
    output=CapabilityOutput(type="gtm_at_risk_account_enrichment_summary_result", fields=["result"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["gtm.pipeline.read", "gtm.enrichment.read"],
    cost=Cost(certainty=CostCertainty.FIXED, compute={"latency_p50": "350ms"}),
    session=SessionInfo(),
    observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=["capability", "parameters"], audit_accessible_by=["delegation.root_principal"]),
)


def _handle_gtm_at_risk_account_enrichment_summary(ctx: InvocationContext, params: dict) -> dict:
    actor_policy = _actor_policy(ctx)
    quarter = _require_str(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2.")
    ranking_basis = str(params.get("ranking_basis") or "risk_score").strip() or "risk_score"
    return fetch_at_risk_account_enrichment_summary(
        quarter=quarter,
        ranking_basis=ranking_basis,
        owner_scope=resolve_pipeline_scope(str(params.get("owner_scope") or "").strip() or None, actor_policy),
        limit=params.get("limit"),
        actor_policy=actor_policy,
    )

gtm_account_enrichment_summary = Capability(declaration=GTM_ACCOUNT_ENRICHMENT_SUMMARY_DECL, handler=_handle_gtm_account_enrichment_summary)
gtm_lookalike_accounts = Capability(declaration=GTM_LOOKALIKE_ACCOUNTS_DECL, handler=_handle_gtm_lookalike_accounts)
gtm_at_risk_account_enrichment_summary = Capability(declaration=GTM_AT_RISK_ACCOUNT_ENRICHMENT_SUMMARY_DECL, handler=_handle_gtm_at_risk_account_enrichment_summary)


def create_service() -> ANIPService:
    return ANIPService(
        service_id=os.getenv("ANIP_SERVICE_ID", SERVICE_ID),
        capabilities=[gtm_account_enrichment_summary, gtm_lookalike_accounts, gtm_at_risk_account_enrichment_summary],
        storage=os.getenv("ANIP_STORAGE", ":memory:"),
        trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
        key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
        authenticate=authenticate_bearer,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="GTM Enrichment Service")
    mount_anip(app, create_service(), health_endpoint=True)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "4100")))
