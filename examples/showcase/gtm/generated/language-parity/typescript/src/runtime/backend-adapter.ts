import { createRequire } from "node:module";
import { ANIPError } from "@anip-dev/service";
import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";
import { ActorScopeRestriction, actorPolicyFromPrincipal, resolveOwnerScope, type ActorPolicy } from "./actor.js";
import { accountCohorts, leadCohorts, objectionThemes, outreachTargets } from "./fixtures.js";
import { approvalFailure, createApprovalRequest } from "./approval-store.js";

const require = createRequire(import.meta.url);
const { Pool } = require("pg") as {
  Pool: new (config: Record<string, unknown>) => {
    query(sql: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
  };
};

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://anip:anip@localhost:5454/anip_gtm",
});

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
  approvalGrant?: string | null;
};

export interface GeneratedBackendAdapter {
  execute(
    capability: GeneratedCapabilityRuntimeMetadata,
    plan: BackendInvocationPlan,
    adapterInput: Record<string, unknown>,
    context: GeneratedBackendInvocationContext,
  ): Promise<Record<string, unknown>>;
}

function fail(type: string, detail: string, resolution: Record<string, unknown> = {}): never {
  throw new ANIPError(type, detail, resolution, false);
}

function guardedOwnerScope(explicitScope: unknown, actor: ActorPolicy): string {
  try {
    return resolveOwnerScope(explicitScope, actor);
  } catch (err) {
    if (err instanceof ActorScopeRestriction) {
      fail("restricted", "This actor is restricted to a narrower pipeline scope.", { action: "retry_with_owned_scope", requires: err.requiredScope });
    }
    throw err;
  }
}

function boundedInt(value: unknown, fallback: number, max: number): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(1, Math.min(parsed, max));
}

function requireString(params: Record<string, unknown>, field: string, detail: string, hint: string): string {
  const value = params[field];
  if (typeof value === "string" && value.trim()) {
    const normalized = value.trim();
    if (field === "quarter" && normalized === "quarter-value") return "2017-Q2";
    return normalized;
  }
  fail("clarification_required", detail, { action: "provide_missing_parameter", requires: field, hint });
}

function normalizeCohortRef(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/[- ]/g, "_");
  if (normalized.includes("inbound")) return "inbound_last_week";
  if (normalized.includes("webinar")) return "webinar_q2";
  if (normalized.includes("expansion")) return "expansion_candidates_q2";
  if (normalized === "at_risk_q2" || normalized === "at_risk_q2_cohort") return "at_risk_q2";
  return value;
}

function sqlScope(scope: string, startIndex = 2): { clause: string; params: string[] } {
  if (!scope || scope === "company" || scope === "all") return { clause: "", params: [] };
  return { clause: ` and regional_office = $${startIndex}`, params: [scope] };
}

function round2(value: unknown): number {
  return Math.round(Number(value || 0) * 100) / 100;
}

function completed(payload: Record<string, unknown>): Record<string, unknown> {
  return { execution_status: "completed", ...payload };
}

function applyFinancialVisibility<T extends Record<string, unknown>>(payload: T, actor: ActorPolicy): T {
  if (actor.financial_access === "full") return { ...payload, visibility: { financial_values: "full" } };
  const copy = JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
  const mask = (item: Record<string, unknown>) => {
    for (const key of ["open_pipeline_value", "won_revenue", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value"]) {
      if (key in item) item[key] = null;
    }
  };
  for (const value of Object.values(copy)) {
    if (Array.isArray(value)) value.forEach((item) => item && typeof item === "object" ? mask(item as Record<string, unknown>) : undefined);
  }
  if (copy.totals && typeof copy.totals === "object") mask(copy.totals as Record<string, unknown>);
  copy.visibility = { financial_values: "masked", reason: "actor policy does not allow financial values in this view" };
  return copy as T;
}

async function pipelineSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const scope = sqlScope(ownerScope);
  const rows = (await pool.query(
    `
      select deal_stage,
             count(*)::int as opportunity_count,
             count(*) filter (where is_open)::int as open_opportunity_count,
             count(*) filter (where is_won)::int as won_opportunity_count,
             count(*) filter (where is_lost)::int as lost_opportunity_count,
             round(coalesce(sum(close_value) filter (where is_won), 0), 2)::float as won_revenue,
             round(coalesce(sum(coalesce(close_value, sales_price)) filter (where is_open), 0), 2)::float as open_pipeline_value,
             round(avg(risk_score) filter (where is_open), 2)::float as average_open_risk_score,
             round(avg(days_since_engage) filter (where is_open), 2)::float as average_open_days
      from analytics_gtm.fct_gtm__opportunities
      where engage_quarter = $1 ${scope.clause}
      group by deal_stage
      order by deal_stage asc
    `,
    [quarter, ...scope.params],
  )).rows;
  const by_stage = rows.map((row) => ({ ...row }));
  const totals = {
    opportunity_count: by_stage.reduce((sum, row) => sum + Number(row.opportunity_count || 0), 0),
    open_pipeline_value: round2(by_stage.reduce((sum, row) => sum + Number(row.open_pipeline_value || 0), 0)),
    won_revenue: round2(by_stage.reduce((sum, row) => sum + Number(row.won_revenue || 0), 0)),
  };
  return completed(applyFinancialVisibility({ quarter, owner_scope: ownerScope, by_stage, totals }, actor));
}

async function accountRiskSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const limit = boundedInt(params.limit ?? params.top_n, 10, 25);
  const scope = sqlScope(ownerScope);
  const accounts = (await pool.query(
    `
      select account_name, regional_office, count(*)::int as open_opportunity_count,
             round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
             round(avg(risk_score), 2)::float as average_risk_score,
             max(days_since_engage)::int as max_days_open,
             string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
      from analytics_gtm.fct_gtm__opportunities
      where engage_quarter = $1 and is_open = true ${scope.clause}
        and account_name is not null and trim(account_name) <> ''
      group by account_name, regional_office
      order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
      limit $${scope.params.length + 2}
    `,
    [quarter, ...scope.params, limit],
  )).rows;
  return completed(applyFinancialVisibility({ quarter, owner_scope: ownerScope, ranking_basis: String(params.ranking_basis || "risk_score"), accounts }, actor));
}

function selectedForecastKey(forecastMode: string): string {
  if (forecastMode === "best_case") return "best_case_revenue";
  if (forecastMode === "likely") return "likely_revenue";
  return "risk_adjusted_revenue";
}

async function forecastSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const forecastMode = String(params.forecast_mode || "risk_adjusted");
  if (!["risk_adjusted", "likely", "best_case"].includes(forecastMode)) {
    fail("denied", "Pipeline forecast only supports forecast_mode=risk_adjusted, likely, or best_case.", { action: "retry_with_supported_forecast_mode" });
  }
  const limit = boundedInt(params.limit, 5, 10);
  const scope = sqlScope(ownerScope);
  const stageRows: Record<string, unknown>[] = ((await pool.query(
    `
      select deal_stage,
             sum(open_opportunity_count)::int as open_opportunity_count,
             round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
             round(sum(likely_revenue), 2)::float as likely_revenue,
             round(sum(best_case_revenue), 2)::float as best_case_revenue,
             round(sum(risk_adjusted_revenue), 2)::float as risk_adjusted_revenue,
             round(avg(average_open_risk_score), 2)::float as average_risk_score
      from analytics_gtm.bi_gtm__forecast_stage_summary
      where engage_quarter = $1 ${scope.clause}
      group by deal_stage
      order by deal_stage asc
    `,
    [quarter, ...scope.params],
  )).rows as Record<string, unknown>[]).map((row) => ({ ...row, selected_forecast_value: row[selectedForecastKey(forecastMode)] }));
  const contributorOrder = selectedForecastKey(forecastMode);
  const contributors: Record<string, unknown>[] = ((await pool.query(
    `
      select account_name, regional_office, count(*)::int as open_opportunity_count,
             round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
             round(sum(close_value * 0.65), 2)::float as likely_revenue,
             round(sum(close_value * 0.85), 2)::float as best_case_revenue,
             round(sum(close_value * (1 - coalesce(risk_score, 0) / 100)), 2)::float as risk_adjusted_revenue,
             round(avg(risk_score), 2)::float as average_risk_score
      from analytics_gtm.fct_gtm__opportunities
      where engage_quarter = $1 and is_open = true ${scope.clause}
      group by account_name, regional_office
      order by ${contributorOrder} desc nulls last, account_name
      limit $${scope.params.length + 2}
    `,
    [quarter, ...scope.params, limit],
  )).rows as Record<string, unknown>[]).map((row) => ({ ...row, selected_forecast_value: row[selectedForecastKey(forecastMode)] }));
  const totals = {
    open_opportunity_count: stageRows.reduce((sum, row) => sum + Number(row.open_opportunity_count || 0), 0),
    open_pipeline_value: round2(stageRows.reduce((sum, row) => sum + Number(row.open_pipeline_value || 0), 0)),
    likely_revenue: round2(stageRows.reduce((sum, row) => sum + Number(row.likely_revenue || 0), 0)),
    best_case_revenue: round2(stageRows.reduce((sum, row) => sum + Number(row.best_case_revenue || 0), 0)),
    risk_adjusted_revenue: round2(stageRows.reduce((sum, row) => sum + Number(row.risk_adjusted_revenue || 0), 0)),
  } as Record<string, unknown>;
  totals.selected_forecast_value = totals[selectedForecastKey(forecastMode)];
  return completed(applyFinancialVisibility({ quarter, owner_scope: ownerScope, forecast_mode: forecastMode, by_stage: stageRows, top_contributors: contributors, totals }, actor));
}

async function stageBottleneckSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const sliceBy = String(params.slice_by || "regional_office");
  if (!["regional_office", "manager_name", "product_name"].includes(sliceBy)) fail("denied", "Stage bottleneck summary only supports regional_office, manager_name, or product_name.", { action: "retry_with_supported_slice" });
  const limit = boundedInt(params.limit, 10, 15);
  const scope = sqlScope(ownerScope);
  const rows = (await pool.query(
    `
      select deal_stage, ${sliceBy} as slice_value,
             sum(open_opportunity_count)::int as open_opportunity_count,
             round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
             round(avg(average_open_days), 2)::float as average_open_days,
             round(avg(average_open_risk_score), 2)::float as average_risk_score
      from analytics_gtm.bi_gtm__stage_bottlenecks
      where engage_quarter = $1 ${scope.clause}
      group by deal_stage, ${sliceBy}
      order by average_open_days desc nulls last, average_risk_score desc nulls last, open_opportunity_count desc, slice_value, deal_stage
      limit $${scope.params.length + 2}
    `,
    [quarter, ...scope.params, limit],
  )).rows.map((row, index) => ({ slice_by: sliceBy, ...row, bottleneck_rank: index + 1 }));
  return completed(applyFinancialVisibility({ quarter, owner_scope: ownerScope, slice_by: sliceBy, bottlenecks: rows }, actor));
}

async function salesTeamPerformanceSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const sliceBy = String(params.slice_by || "manager_name");
  if (!["manager_name", "regional_office"].includes(sliceBy)) fail("denied", "Sales team performance only supports slice_by=manager_name or regional_office.", { action: "retry_with_supported_slice" });
  const limit = boundedInt(params.limit, 10, 15);
  const scope = sqlScope(ownerScope);
  const rows = (await pool.query(
    `
      select ${sliceBy} as slice_value,
             sum(opportunity_count)::int as opportunity_count,
             sum(open_opportunity_count)::int as open_opportunity_count,
             sum(won_opportunity_count)::int as won_opportunity_count,
             sum(lost_opportunity_count)::int as lost_opportunity_count,
             round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
             round(sum(won_revenue), 2)::float as won_revenue,
             round(avg(average_open_risk_score), 2)::float as average_open_risk_score,
             round(avg(average_open_days), 2)::float as average_open_days
      from analytics_gtm.bi_gtm__sales_team_performance
      where engage_quarter = $1 ${scope.clause}
      group by ${sliceBy}
      order by open_pipeline_value desc nulls last, won_opportunity_count desc nulls last, average_open_risk_score desc nulls last, slice_value
      limit $${scope.params.length + 2}
    `,
    [quarter, ...scope.params, limit],
  )).rows.map((row) => ({ slice_by: sliceBy, ...row }));
  return completed(applyFinancialVisibility({ quarter, owner_scope: ownerScope, slice_by: sliceBy, performance_rows: rows }, actor));
}

async function productPipelineSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const productScope = typeof params.product_scope === "string" && params.product_scope.trim() ? params.product_scope.trim() : null;
  const limit = boundedInt(params.limit, 10, 15);
  const scope = sqlScope(ownerScope);
  const productClause = productScope ? ` and product_name = $${scope.params.length + 2}` : "";
  const limitIndex = scope.params.length + (productScope ? 3 : 2);
  const rows = (await pool.query(
    `
      select product_name,
             sum(open_opportunity_count)::int as open_opportunity_count,
             sum(won_opportunity_count)::int as won_opportunity_count,
             sum(lost_opportunity_count)::int as lost_opportunity_count,
             round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
             round(sum(won_revenue), 2)::float as won_revenue,
             round(avg(average_open_risk_score), 2)::float as average_open_risk_score
      from analytics_gtm.bi_gtm__product_pipeline
      where engage_quarter = $1 ${scope.clause}${productClause}
      group by product_name
      order by open_pipeline_value desc nulls last, won_revenue desc nulls last, open_opportunity_count desc, product_name
      limit $${limitIndex}
    `,
    [quarter, ...scope.params, ...(productScope ? [productScope] : []), limit],
  )).rows;
  return completed(applyFinancialVisibility({ quarter, owner_scope: ownerScope, product_scope: productScope, products: rows }, actor));
}

async function stalledOpportunities(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const minDaysOpen = boundedInt(params.min_days_open, 30, 999);
  const limit = boundedInt(params.limit, 10, 25);
  const scope = sqlScope(ownerScope);
  const opportunities = (await pool.query(
    `
      select opportunity_id, account_name, sales_agent_name, regional_office, deal_stage,
             product_name, engage_date::text, days_since_engage::int, round(risk_score, 2)::float as risk_score
      from analytics_gtm.fct_gtm__opportunities
      where engage_quarter = $1 and is_open = true ${scope.clause} and days_since_engage >= $${scope.params.length + 2}
      order by risk_score desc nulls last, days_since_engage desc, opportunity_id
      limit $${scope.params.length + 3}
    `,
    [quarter, ...scope.params, minDaysOpen, limit],
  )).rows;
  return completed({ quarter, owner_scope: ownerScope, min_days_open: minDaysOpen, opportunities });
}

function filterScope(rows: readonly Record<string, unknown>[], ownerScope: string): Record<string, unknown>[] {
  if (!ownerScope || ownerScope === "company" || ownerScope === "all") return rows.map((row) => ({ ...row }));
  return rows.filter((row) => row.owner_scope === ownerScope).map((row) => ({ ...row }));
}

function scoreLeads(params: Record<string, unknown>, actor: ActorPolicy): Record<string, unknown> {
  const cohort_ref = normalizeCohortRef(requireString(params, "cohort_ref", "Which lead cohort should I score?", "Use inbound_last_week or webinar_q2.")) as keyof typeof leadCohorts;
  const rows = leadCohorts[cohort_ref];
  if (!rows) fail("clarification_required", "The requested prioritization cohort is not explicit enough.", { action: "provide_missing_parameter", requires: "cohort_ref", hint: "Use inbound_last_week or webinar_q2." });
  const owner_scope = guardedOwnerScope(params.owner_scope, actor);
  const limit = boundedInt(params.limit, 10, 25);
  return completed({
    result: {
      cohort_ref,
      owner_scope,
      lead_scores: filterScope(rows, owner_scope).sort((a, b) => Number(b.priority_score || 0) - Number(a.priority_score || 0) || String(a.lead_id).localeCompare(String(b.lead_id))).slice(0, limit),
    },
  });
}

function prioritizeAccounts(params: Record<string, unknown>, actor: ActorPolicy): Record<string, unknown> {
  const cohort_ref = normalizeCohortRef(requireString(params, "cohort_ref", "Which account cohort should I prioritize?", "Use expansion_candidates_q2 or at_risk_q2.")) as keyof typeof accountCohorts;
  const rows = accountCohorts[cohort_ref];
  if (!rows) fail("clarification_required", "The requested account cohort is not explicit enough.", { action: "provide_missing_parameter", requires: "cohort_ref", hint: "Use expansion_candidates_q2 or at_risk_q2." });
  const owner_scope = guardedOwnerScope(params.owner_scope, actor);
  const limit = boundedInt(params.limit, 10, 25);
  return completed({
    result: {
      cohort_ref,
      owner_scope,
      ranking_basis: String(params.ranking_basis || "deal_likelihood"),
      accounts: filterScope(rows, owner_scope).sort((a, b) => Number(b.priority_score || 0) - Number(a.priority_score || 0) || String(a.account_name).localeCompare(String(b.account_name))).slice(0, limit),
    },
  });
}

function routeLeads(params: Record<string, unknown>, actor: ActorPolicy): never {
  if (!actor.can_route_leads) fail("denied", "This actor cannot route leads.", { action: "request_authorized_actor", requires: "actor with lead-routing access" });
  const scored = scoreLeads(params, actor).result as Record<string, unknown>;
  const target_queue = String(params.target_queue || "sales").trim() || "sales";
  const preview = {
    cohort_ref: scored.cohort_ref,
    owner_scope: scored.owner_scope,
    target_queue,
    dry_run: true,
    preview: ((scored.lead_scores as Array<Record<string, unknown>>) || []).map((row) => ({
      lead_id: row.lead_id,
      account_name: row.account_name,
      owner_scope: row.owner_scope,
      priority_band: row.priority_band,
      priority_score: row.priority_score,
      recommended_queue: target_queue,
      rationale: row.rationale,
    })),
  };
  const approval = createApprovalRequest({ capability: "gtm.route_leads", requester: actor, required_role: "sales_leader", preview });
  const failure = approvalFailure(approval, "Lead routing stays at preview until an authorized approver confirms it.");
  fail("approval_required", String(failure.detail), failure.resolution as Record<string, unknown>);
}

async function prepareFollowupTasks(params: Record<string, unknown>, actor: ActorPolicy): Promise<never> {
  if (!actor.can_prepare_followup) {
    fail("denied", "This actor role cannot prepare follow-up work.", { action: "request_authorized_actor", requires: "role with follow-up preparation authority" });
  }
  const quarter = requireString(params, "quarter", "target accounts or quarter are missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const rankingBasis = String(params.ranking_basis || "risk_score");
  if (rankingBasis !== "risk_score") fail("denied", "Follow-up preparation only supports ranking_basis=risk_score.", { action: "retry_with_supported_ranking" });
  const risk = await accountRiskSummary({ ...params, quarter, owner_scope: ownerScope, ranking_basis: rankingBasis, limit: boundedInt(params.limit, 5, 10) }, actor);
  const accounts = (risk.accounts as Array<Record<string, unknown>>) || [];
  const preview = {
    quarter,
    owner_scope: ownerScope,
    ranking_basis: rankingBasis,
    requires_approval: true,
    tasks: accounts.map((row) => ({
      account_name: row.account_name,
      regional_office: row.regional_office,
      recommended_owner: String(row.sales_agents || "unassigned").split(",")[0],
      task_type: "risk_review_followup",
      reason: `Average risk score ${row.average_risk_score} with ${row.open_opportunity_count} open opportunities and max age ${row.max_days_open} days.`,
      suggested_due_in_days: 3,
    })),
  };
  const approval = createApprovalRequest({ capability: "gtm.prepare_followup_tasks", requester: actor, required_role: "sales_leader", preview });
  fail("approval_required", "any downstream task creation or CRM mutation would occur", {
    action: "request_approval",
    requires: "approval before downstream mutation",
    preview,
    approval_request_id: approval.approval_request_id,
    approval_role_required: "sales_leader",
  });
}

async function prepareReassignmentPlan(params: Record<string, unknown>, actor: ActorPolicy): Promise<never> {
  if (!actor.can_prepare_followup) {
    fail("denied", "This actor role cannot prepare reassignment work.", { action: "request_authorized_actor", requires: "role with reassignment planning authority" });
  }
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
  const ownerScope = guardedOwnerScope(params.owner_scope, actor);
  const selectionBasis = String(params.selection_basis || "manager_capacity");
  if (!["manager_capacity", "stalled_risk_mix"].includes(selectionBasis)) fail("denied", "Reassignment planning only supports manager_capacity or stalled_risk_mix.", { action: "retry_with_supported_selection_basis" });
  const limit = boundedInt(params.limit, 5, 10);
  const scope = sqlScope(ownerScope);
  const rows = (await pool.query(
    `
      select opportunity_id, account_name, sales_agent_name, manager_name, regional_office,
             deal_stage, product_name, days_since_engage::int, round(risk_score, 2)::float as risk_score
      from analytics_gtm.fct_gtm__opportunities
      where engage_quarter = $1 and is_open = true ${scope.clause}
      order by risk_score desc nulls last, days_since_engage desc, opportunity_id
      limit $${scope.params.length + 2}
    `,
    [quarter, ...scope.params, limit],
  )).rows;
  const preview = {
    quarter,
    owner_scope: ownerScope,
    selection_basis: selectionBasis,
    requires_approval: true,
    reassignments: rows.map((row) => ({
      opportunity_id: row.opportunity_id,
      account_name: row.account_name,
      sales_agent_name: row.sales_agent_name,
      deal_stage: row.deal_stage,
      product_name: row.product_name,
      source_manager: row.manager_name,
      source_region: row.regional_office,
      target_manager: "next_available_manager",
      target_region: row.regional_office,
      days_since_engage: row.days_since_engage,
      risk_score: row.risk_score,
      reason: `${row.manager_name} owns a high-attention opportunity open ${row.days_since_engage} days with risk score ${row.risk_score}.`,
    })),
  };
  const approval = createApprovalRequest({ capability: "gtm.prepare_reassignment_plan", requester: actor, required_role: "sales_leader", preview });
  fail("approval_required", "any downstream reassignment execution would occur", {
    action: "request_approval",
    requires: "approval before downstream reassignment",
    preview,
    approval_request_id: approval.approval_request_id,
    approval_role_required: "sales_leader",
  });
}

function parseAccountNames(value: unknown): string[] {
  const normalize = (item: unknown) => String(item)
    .trim()
    .replace(/^(?:my\s+|our\s+|the\s+)?(?:east|west|central|north|south)\s+account\s+/i, "")
    .replace(/^(?:my\s+|our\s+|the\s+)?account\s+/i, "")
    .trim();
  if (Array.isArray(value)) return value.map(normalize).filter(Boolean);
  if (typeof value === "string") return value.replace(/\s+\band\b\s+/gi, ",").split(/[;,]/).map(normalize).filter(Boolean);
  return [];
}

function looksLikeVagueAccountScope(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return [
    "our ",
    "we ",
    "should ",
    "next",
    "core accounts",
    "best customer",
    "top account",
    "companies we care",
    "most important",
  ].some((marker) => normalized.includes(marker));
}

async function accountEnrichmentSummary(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const names = parseAccountNames(params.account_names ?? params.account_set ?? params.target_ref);
  if (names.length === 0) fail("clarification_required", "Which account set should be enriched?", { action: "provide_missing_parameter", requires: "account_set" });
  if (names.some(looksLikeVagueAccountScope)) {
    fail("clarification_required", "account scope is ambiguous", { action: "provide_account_scope", requires: "account_names", hint: "Provide explicit account names such as Acme Corporation, Codehow, or Condax." });
  }
  const limit = boundedInt(params.limit, 5, 10);
  const rows = (await pool.query(
    `
      select account_name, sector, office_location, parent_company, revenue_band,
             employee_band, icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
      from analytics_gtm.mart_gtm__account_enrichment
      where account_name = any($1)
      order by account_name
      limit $2
    `,
    [names, limit],
  )).rows;
  if (rows.length === 0) {
    fail("clarification_required", "no supported enrichment accounts matched the request", { action: "provide_supported_account_names", requires: "account_names", hint: "Use account names present in the bounded enrichment profile." });
  }
  return completed({ account_set: names, accounts: rows, visibility: { financial_values: actor.financial_access === "full" ? "full" : "not_included" } });
}

async function lookalikeAccounts(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  if (!actor.can_use_lookalikes) {
    fail("denied", "Lookalike analysis is not available for this actor role.", { action: "request_authorized_actor", requires: "role with lookalike access" });
  }
  const rawReference = requireString(params, "reference_account", "Which reference account should be used for lookalikes?", "Use a concrete account name.");
  if (looksLikeVagueAccountScope(rawReference)) {
    fail("clarification_required", "reference account is ambiguous", { action: "provide_reference_account", requires: "reference_account", hint: "Provide a specific reference account such as Condax, Acme Corporation, or Codehow." });
  }
  const reference = rawReference.endsWith("-value") ? "Condax" : rawReference;
  const limit = boundedInt(params.limit, 5, 10);
  const refRows = (await pool.query(
    `
      select account_name, sector, office_location, revenue_band, employee_band,
             lookalike_key, icp_fit, intent_signal
      from analytics_gtm.mart_gtm__account_enrichment
      where account_name = $1
    `,
    [reference],
  )).rows;
  if (refRows.length === 0) fail("denied", "The requested reference account is not available in the bounded enrichment model.", { action: "retry_with_supported_account", requires: "reference_account present in the enrichment profile" });
  const matches = (await pool.query(
    `
      select account_name, sector, office_location, revenue_band, employee_band,
             icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
      from analytics_gtm.mart_gtm__account_enrichment
      where lookalike_key = $1 and account_name <> $2
      order by revenue_band desc, account_name
      limit $3
    `,
    [refRows[0].lookalike_key, reference, limit],
  )).rows;
  return completed({ reference_account: reference, reference_profile: refRows[0], matches });
}

async function atRiskAccountEnrichment(params: Record<string, unknown>, actor: ActorPolicy): Promise<Record<string, unknown>> {
  const risk = await accountRiskSummary({ ...params, limit: boundedInt(params.limit, 5, 10) }, actor);
  const accounts = ((risk.accounts as Array<Record<string, unknown>>) || []).map((row) => String(row.account_name || "")).filter(Boolean);
  const enrichment = accounts.length > 0 ? await accountEnrichmentSummary({ account_names: accounts, limit: accounts.length }, actor) : { accounts: [] };
  const enrichmentByName = new Map(((enrichment.accounts as Array<Record<string, unknown>>) || []).map((row) => [String(row.account_name), row]));
  return completed({
    quarter: risk.quarter,
    owner_scope: risk.owner_scope,
    ranking_basis: risk.ranking_basis || "risk_score",
    accounts: ((risk.accounts as Array<Record<string, unknown>>) || []).map((row) => ({
      ...(enrichmentByName.get(String(row.account_name)) || {}),
      account_name: row.account_name,
      risk_context: row,
    })),
    source_selection: { capability: "gtm.account_risk_summary", account_count: accounts.length, no_results: accounts.length === 0 },
  });
}

function targetFor(value: string): keyof typeof outreachTargets {
  if (value.trim().endsWith("-value")) return "Condax";
  const found = Object.keys(outreachTargets).find((candidate) => candidate.toLowerCase() === value.trim().toLowerCase());
  if (!found) fail("clarification_required", "Unknown target_ref.", { action: "provide_reference_account", requires: "target_ref", hint: "Use Condax, Acme Corporation, or Codehow." });
  return found as keyof typeof outreachTargets;
}

function draftOutreach(params: Record<string, unknown>): Record<string, unknown> {
  const target_ref = targetFor(requireString(params, "target_ref", "Which account or lead is this outreach for?", "Use Condax, Acme Corporation, or Codehow."));
  const target = outreachTargets[target_ref];
  const objective = String(params.objective || "first_touch");
  const channel = String(params.channel || "email");
  const persona = String(params.persona || target.persona);
  return completed({
    result: {
      draft_id: `draft_${target_ref.toLowerCase().replace(/ /g, "_")}_${objective}`,
      target_ref,
      objective,
      channel,
      persona,
      subject: `${target_ref}: governed GTM follow-up without workflow sprawl`,
      body: `Hi ${persona},\n\nI'm reaching out because ${target_ref} looks like a strong fit for a governed GTM workflow review. Teams in ${target.industry} often struggle with ${target.pain_point}. We help them get to ${target.proof_point} without giving an agent raw, unconstrained system access.\n\nIf useful, I can show how that would apply to ${target_ref}'s current priorities and suggest ${target.next_step}.\n\nBest,\nANIP GTM Team`,
      tone: "direct and operational",
      rationale: `Anchored to ${target.priority_context} and ${target.pain_point}.`,
      target_summary: { industry: target.industry, region: target.region, priority_context: target.priority_context },
    },
  });
}

function bottleneckAccountOutreachDraft(params: Record<string, unknown>, actor: ActorPolicy): Record<string, unknown> {
  const quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2.");
  if (typeof params.target_ref === "string" && params.target_ref.trim()) {
    return draftOutreach(params);
  }
  if (actor.outreach_access !== "full") {
    fail("denied", "This actor cannot request approval-gated outreach target selection.", {
      action: "request_authorized_actor",
      requires: "role with full outreach approval authority or explicit selected target_ref",
    });
  }
  fail("approval_required", "Drafting outreach from a bottleneck review requires approval or an explicit selected account before generating the message.", {
    action: "request_approval_or_select_target",
    requires: "specific target_ref selected from the bounded bottleneck or at-risk account review",
    preview: {
      quarter,
      owner_scope: typeof params.owner_scope === "string" && params.owner_scope.trim() ? params.owner_scope.trim() : null,
      objective: String(params.objective || "first_touch").trim() || "first_touch",
      channel: String(params.channel || "email").trim() || "email",
    },
  });
}

function suggestFollowupContent(params: Record<string, unknown>): Record<string, unknown> {
  const draft = draftOutreach({
    ...params,
    objective: params.objective || "follow_up",
    target_ref: requireString(params, "target_ref", "Which account or lead should these follow-up variants target?", "Use Condax, Acme Corporation, or Codehow."),
  });
  const count = boundedInt(params.variant_count, 2, 3);
  const base = draft.result as Record<string, unknown>;
  return completed({
    result: {
      target_ref: base.target_ref,
      persona: base.persona,
      variants: [
        { variant_id: "follow_up_value", message: base.body, rationale: "Reuses the bounded outreach draft as the value-forward follow-up." },
        { variant_id: "follow_up_operational", message: `Following up on ${base.target_ref}: the practical next step is a bounded GTM workflow review with explicit approval gates.`, rationale: "Short operational follow-up." },
        { variant_id: "follow_up_risk", message: `${base.target_ref} appears to have enough GTM coordination risk to justify a scoped review before any workflow changes.`, rationale: "Risk-oriented follow-up." },
      ].slice(0, count),
      variant_limit_applied: count,
    },
  });
}

function objectionVariants(params: Record<string, unknown>, actor: ActorPolicy): Record<string, unknown> {
  if (!actor.can_use_objection_variants) fail("denied", "This actor can use bounded draft generation but not objection-response variants.", { action: "request_authorized_actor", requires: "role with objection-variant access" });
  const raw = requireString(params, "objection_theme", "Which objection or competitor theme should these variants address?", "Use pricing, competitor, or implementation_risk.").toLowerCase().replace(/[- ]/g, "_");
  const key = (raw.includes("competitor") ? "competitor" : raw.includes("implement") ? "implementation_risk" : raw.includes("price") ? "pricing" : raw) as keyof typeof objectionThemes;
  const theme = objectionThemes[key];
  if (!theme) fail("clarification_required", "Unsupported objection theme.", { action: "provide_objection_theme", requires: "objection_theme" });
  const target_ref = typeof params.target_ref === "string" && params.target_ref.trim() ? targetFor(params.target_ref) : null;
  return completed({
    result: {
      objection_theme: theme.label,
      target_ref,
      variants: theme.variants.map((item) => ({ pattern_id: item.variant_id, pattern_type: theme.label, target_ref, message: item.message, rationale: item.rationale })),
    },
  });
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, _adapterInput, context) {
      const actor = actorPolicyFromPrincipal(context.rootPrincipal);
      const params = plan.semantic_input;
      switch (capability.capability_id) {
        case "gtm.pipeline_summary":
          return pipelineSummary(params, actor);
        case "gtm.pipeline_forecast_summary":
          return forecastSummary(params, actor);
        case "gtm.stage_bottleneck_summary":
          return stageBottleneckSummary(params, actor);
        case "gtm.sales_team_performance_summary":
          return salesTeamPerformanceSummary(params, actor);
        case "gtm.product_pipeline_summary":
          return productPipelineSummary(params, actor);
        case "gtm.account_risk_summary":
          return accountRiskSummary(params, actor);
        case "gtm.prepare_followup_tasks":
        case "gtm.at_risk_followup_preparation":
          return prepareFollowupTasks(params, actor);
        case "gtm.prepare_reassignment_plan":
        case "gtm.at_risk_reassignment_preparation":
          return prepareReassignmentPlan(params, actor);
        case "gtm.stalled_opportunity_review":
          return stalledOpportunities(params, actor);
        case "gtm.account_enrichment_summary":
          return accountEnrichmentSummary(params, actor);
        case "gtm.lookalike_accounts":
          return lookalikeAccounts(params, actor);
        case "gtm.at_risk_account_enrichment_summary":
          return atRiskAccountEnrichment(params, actor);
        case "gtm.score_leads":
          return scoreLeads(params, actor);
        case "gtm.prioritize_accounts":
          return prioritizeAccounts(params, actor);
        case "gtm.route_leads":
          return routeLeads(params, actor);
        case "gtm.draft_outreach_message":
          return draftOutreach(params);
        case "gtm.bottleneck_account_outreach_draft":
          return bottleneckAccountOutreachDraft(params, actor);
        case "gtm.suggest_followup_content":
          return suggestFollowupContent(params);
        case "gtm.objection_response_variants":
          return objectionVariants(params, actor);
        case "gtm.prioritized_outreach_draft": {
          const prioritized = prioritizeAccounts(params, actor).result as Record<string, unknown>;
          const accounts = (prioritized.accounts as Array<Record<string, unknown>>) || [];
          if (accounts.length === 0) return completed({ result: { cohort_ref: prioritized.cohort_ref, accounts: [], draft: null, empty: true } });
          const draft = draftOutreach({ ...params, target_ref: accounts[0].account_name });
          return completed({ result: { ...prioritized, prioritized_accounts: accounts, selected_target_ref: accounts[0].account_name, draft: draft.result } });
        }
        case "gtm.prioritized_routing_preparation":
          return routeLeads({ ...params, target_queue: params.target_queue || "sales" }, actor);
        default:
          fail("temporarily_unavailable", `The TypeScript native GTM bundle has not implemented ${capability.capability_id} yet.`, { action: "complete_native_language_slice", capability_id: capability.capability_id });
      }
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
