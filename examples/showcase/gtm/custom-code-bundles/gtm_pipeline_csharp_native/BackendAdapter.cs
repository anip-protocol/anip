using Anip.Core;
using Anip.Service;
using Npgsql;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}};

public delegate Dictionary<string, object?> BackendAdapterHandler(
    Dictionary<string, object?> capability,
    Dictionary<string, object?> plan,
    Dictionary<string, object?> adapterInput,
    InvocationContext context);

public static class BackendAdapter
{
    public static BackendAdapterHandler Default => new GtmNativeBackendAdapter().Execute;
}

internal sealed class GtmNativeBackendAdapter
{
    private readonly string _databaseUrl = Environment.GetEnvironmentVariable("DATABASE_URL") ?? "postgresql://anip:anip@127.0.0.1:5454/anip_gtm";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private static readonly Dictionary<string, ApprovalRecord> Approvals = new();
    private static readonly object ApprovalLock = new();

    public Dictionary<string, object?> Execute(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> plan,
        Dictionary<string, object?> _adapterInput,
        InvocationContext context)
    {
        var actor = ActorPolicy.FromPrincipal(context.RootPrincipal);
        var parameters = Map(plan.GetValueOrDefault("semantic_input"));
        var capabilityId = Text(capability.GetValueOrDefault("capability_id"));
        try
        {
            return capabilityId switch
            {
                "gtm.pipeline_summary" => PipelineSummary(parameters, actor),
                "gtm.pipeline_forecast_summary" => ForecastSummary(parameters, actor),
                "gtm.stage_bottleneck_summary" => StageBottleneckSummary(parameters, actor),
                "gtm.sales_team_performance_summary" => SalesTeamPerformanceSummary(parameters, actor),
                "gtm.product_pipeline_summary" => ProductPipelineSummary(parameters, actor),
                "gtm.stalled_opportunity_review" => StalledOpportunities(parameters, actor),
                "gtm.account_risk_summary" => AccountRiskSummary(parameters, actor),
                "gtm.prepare_followup_tasks" or "gtm.at_risk_followup_preparation" => ThrowApproval(PrepareFollowupTasks(parameters, actor)),
                "gtm.prepare_reassignment_plan" or "gtm.at_risk_reassignment_preparation" => ThrowApproval(PrepareReassignmentPlan(parameters, actor)),
                "gtm.account_enrichment_summary" => AccountEnrichmentSummary(parameters, actor),
                "gtm.lookalike_accounts" => LookalikeAccounts(parameters, actor),
                "gtm.at_risk_account_enrichment_summary" => AtRiskAccountEnrichment(parameters, actor),
                "gtm.score_leads" => ScoreLeads(parameters, actor),
                "gtm.prioritize_accounts" => PrioritizeAccounts(parameters, actor),
                "gtm.route_leads" => ThrowApproval(RouteLeads(parameters, actor)),
                "gtm.prioritized_routing_preparation" => ThrowApproval(RouteLeads(WithDefault(parameters, "target_queue", "sales"), actor)),
                "gtm.draft_outreach_message" => DraftOutreach(parameters),
                "gtm.bottleneck_account_outreach_draft" => BottleneckAccountOutreachDraft(parameters, actor),
                "gtm.suggest_followup_content" => SuggestFollowupContent(parameters),
                "gtm.objection_response_variants" => ObjectionVariants(parameters, actor),
                "gtm.prioritized_outreach_draft" => PrioritizedOutreachDraft(parameters, actor),
                _ => throw Fail("temporarily_unavailable", $"The C# native GTM bundle has not implemented {capabilityId} yet.", "complete_native_language_slice"),
            };
        }
        catch (AnipError)
        {
            throw;
        }
        catch (Exception error)
        {
            throw new AnipError("temporarily_unavailable", error.Message).WithResolution("contact_service_owner");
        }
    }

    private Dictionary<string, object?> PipelineSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var scope = ScopeClause(owner, 1);
        var rows = Query($"""
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
            where engage_quarter = @p0 {scope.Sql}
            group by deal_stage
            order by deal_stage asc
            """, Args(quarter, scope.Args));
        var totals = new Dictionary<string, object?>
        {
            ["opportunity_count"] = rows.Sum(row => Number(row.GetValueOrDefault("opportunity_count"))),
            ["open_pipeline_value"] = Round2(rows.Sum(row => Number(row.GetValueOrDefault("open_pipeline_value")))),
            ["won_revenue"] = Round2(rows.Sum(row => Number(row.GetValueOrDefault("won_revenue")))),
        };
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "by_stage", rows, "totals", totals), actor));
    }

    private Dictionary<string, object?> ForecastSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var mode = TextOr(p.GetValueOrDefault("forecast_mode"), "risk_adjusted");
        if (!new[] { "risk_adjusted", "likely", "best_case" }.Contains(mode))
        {
            throw Fail("denied", "Pipeline forecast only supports forecast_mode=risk_adjusted, likely, or best_case.", "retry_with_supported_forecast_mode");
        }
        var limit = BoundedInt(p.GetValueOrDefault("limit"), 5, 10);
        var selected = ForecastKey(mode);
        var scope = ScopeClause(owner, 1);
        var stageRows = Query($"""
            select deal_stage,
                   sum(open_opportunity_count)::int as open_opportunity_count,
                   round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
                   round(sum(likely_revenue), 2)::float as likely_revenue,
                   round(sum(best_case_revenue), 2)::float as best_case_revenue,
                   round(sum(risk_adjusted_revenue), 2)::float as risk_adjusted_revenue,
                   round(avg(average_open_risk_score), 2)::float as average_risk_score
            from analytics_gtm.bi_gtm__forecast_stage_summary
            where engage_quarter = @p0 {scope.Sql}
            group by deal_stage
            order by deal_stage asc
            """, Args(quarter, scope.Args));
        foreach (var row in stageRows) row["selected_forecast_value"] = row.GetValueOrDefault(selected);
        var contributors = Query($"""
            select account_name, regional_office, count(*)::int as open_opportunity_count,
                   round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
                   round(sum(close_value * 0.65), 2)::float as likely_revenue,
                   round(sum(close_value * 0.85), 2)::float as best_case_revenue,
                   round(sum(close_value * (1 - coalesce(risk_score, 0) / 100)), 2)::float as risk_adjusted_revenue,
                   round(avg(risk_score), 2)::float as average_risk_score
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = @p0 and is_open = true {scope.Sql}
              and account_name is not null and trim(account_name) <> ''
            group by account_name, regional_office
            order by {selected} desc nulls last, account_name
            limit @p{scope.Args.Count + 1}
            """, Args(quarter, scope.Args, limit));
        foreach (var row in contributors) row["selected_forecast_value"] = row.GetValueOrDefault(selected);
        var totals = new Dictionary<string, object?>
        {
            ["open_opportunity_count"] = stageRows.Sum(row => Number(row.GetValueOrDefault("open_opportunity_count"))),
            ["open_pipeline_value"] = Round2(stageRows.Sum(row => Number(row.GetValueOrDefault("open_pipeline_value")))),
            ["likely_revenue"] = Round2(stageRows.Sum(row => Number(row.GetValueOrDefault("likely_revenue")))),
            ["best_case_revenue"] = Round2(stageRows.Sum(row => Number(row.GetValueOrDefault("best_case_revenue")))),
            ["risk_adjusted_revenue"] = Round2(stageRows.Sum(row => Number(row.GetValueOrDefault("risk_adjusted_revenue")))),
        };
        totals["selected_forecast_value"] = totals[selected];
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "forecast_mode", mode, "by_stage", stageRows, "top_contributors", contributors, "totals", totals), actor));
    }

    private Dictionary<string, object?> StageBottleneckSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var sliceBy = TextOr(p.GetValueOrDefault("slice_by"), "regional_office");
        if (!new[] { "regional_office", "manager_name", "product_name" }.Contains(sliceBy))
        {
            throw Fail("denied", "Stage bottleneck summary only supports regional_office, manager_name, or product_name.", "retry_with_supported_slice");
        }
        var scope = ScopeClause(owner, 1);
        var rows = Query($"""
            select deal_stage, {sliceBy} as slice_value,
                   count(*)::int as open_opportunity_count,
                   round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
                   round(avg(risk_score), 2)::float as average_risk_score,
                   max(days_since_engage)::int as max_days_open
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = @p0 and is_open = true {scope.Sql}
            group by deal_stage, {sliceBy}
            order by average_risk_score desc nulls last, open_pipeline_value desc nulls last
            limit @p{scope.Args.Count + 1}
            """, Args(quarter, scope.Args, BoundedInt(p.GetValueOrDefault("limit"), 10, 15)));
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "slice_by", sliceBy, "bottlenecks", rows), actor));
    }

    private Dictionary<string, object?> SalesTeamPerformanceSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var scope = ScopeClause(owner, 1);
        var rows = Query($"""
            select manager_name, sales_agent_name, regional_office,
                   count(*)::int as opportunity_count,
                   count(*) filter (where is_won)::int as won_count,
                   round(coalesce(sum(close_value) filter (where is_won), 0), 2)::float as won_revenue,
                   round(avg(risk_score) filter (where is_open), 2)::float as average_open_risk_score
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = @p0 {scope.Sql}
            group by manager_name, sales_agent_name, regional_office
            order by won_revenue desc nulls last, opportunity_count desc, sales_agent_name
            limit @p{scope.Args.Count + 1}
            """, Args(quarter, scope.Args, BoundedInt(p.GetValueOrDefault("limit"), 10, 20)));
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "team_members", rows), actor));
    }

    private Dictionary<string, object?> ProductPipelineSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var scope = ScopeClause(owner, 1);
        var rows = Query($"""
            select product_name,
                   count(*)::int as opportunity_count,
                   count(*) filter (where is_open)::int as open_opportunity_count,
                   round(coalesce(sum(coalesce(close_value, sales_price)) filter (where is_open), 0), 2)::float as open_pipeline_value,
                   round(coalesce(sum(close_value) filter (where is_won), 0), 2)::float as won_revenue,
                   round(avg(risk_score) filter (where is_open), 2)::float as average_open_risk_score
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = @p0 {scope.Sql}
            group by product_name
            order by open_pipeline_value desc nulls last, product_name
            limit @p{scope.Args.Count + 1}
            """, Args(quarter, scope.Args, BoundedInt(p.GetValueOrDefault("limit"), 10, 20)));
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "products", rows), actor));
    }

    private Dictionary<string, object?> StalledOpportunities(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var minDays = BoundedInt(p.GetValueOrDefault("min_days_open"), 30, 365);
        var scope = ScopeClause(owner, 2);
        var rows = Query($"""
            select opportunity_id, account_name, sales_agent_name, manager_name, regional_office,
                   deal_stage, product_name, days_since_engage::int, round(risk_score, 2)::float as risk_score,
                   round(close_value, 2)::float as open_pipeline_value
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = @p0 and is_open = true {scope.Sql} and days_since_engage >= @p1
            order by risk_score desc nulls last, days_since_engage desc, opportunity_id
            limit @p{scope.Args.Count + 2}
            """, Args(quarter, new List<object?> { minDays }.Concat(scope.Args).ToList(), BoundedInt(p.GetValueOrDefault("limit"), 10, 25)));
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "min_days_open", minDays, "opportunities", rows), actor));
    }

    private Dictionary<string, object?> AccountRiskSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var quarter = Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var scope = ScopeClause(owner, 1);
        var rows = Query($"""
            select account_name, regional_office, count(*)::int as open_opportunity_count,
                   round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
                   round(avg(risk_score), 2)::float as average_risk_score,
                   max(days_since_engage)::int as max_days_open,
                   string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
            from analytics_gtm.fct_gtm__opportunities
            where engage_quarter = @p0 and is_open = true {scope.Sql}
              and account_name is not null and trim(account_name) <> ''
            group by account_name, regional_office
            order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
            limit @p{scope.Args.Count + 1}
            """, Args(quarter, scope.Args, BoundedInt(p.GetValueOrDefault("limit") ?? p.GetValueOrDefault("top_n"), 10, 25)));
        return Completed(ApplyFinancialVisibility(Dict("quarter", quarter, "owner_scope", owner, "ranking_basis", TextOr(p.GetValueOrDefault("ranking_basis"), "risk_score"), "accounts", rows), actor));
    }

    private Dictionary<string, object?> AccountEnrichmentSummary(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var names = ParseNames(p.GetValueOrDefault("account_names") ?? p.GetValueOrDefault("account_set") ?? p.GetValueOrDefault("target_ref"));
        if (names.Count == 0 || names.Any(LooksVagueAccountScope))
        {
            throw FailRequires("clarification_required", "Which bounded account set should be enriched?", "provide_account_scope", "account_names");
        }
        var placeholders = string.Join(", ", names.Select((_, index) => $"@p{index}"));
        var rows = Query($"""
            select account_name, sector, office_location, parent_company, revenue_band,
                   employee_band, icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
            from analytics_gtm.mart_gtm__account_enrichment
            where account_name in ({placeholders})
            order by account_name
            limit @p{names.Count}
            """, names.Cast<object?>().Concat(new object?[] { BoundedInt(p.GetValueOrDefault("limit"), 5, 10) }).ToList());
        if (rows.Count == 0) throw FailRequires("clarification_required", "no supported enrichment accounts matched the request", "provide_supported_account_names", "account_names");
        return Completed(Dict("account_set", names, "accounts", rows, "visibility", Dict("financial_values", actor.FinancialAccess == "full" ? "full" : "not_included")));
    }

    private Dictionary<string, object?> LookalikeAccounts(Dictionary<string, object?> p, ActorPolicy actor)
    {
        if (!actor.CanUseLookalikes) throw FailRequires("denied", "Lookalike analysis is not available for this actor role.", "request_authorized_actor", "role with lookalike access");
        var reference = Require(p, "reference_account", "Which reference account should be used for lookalikes?", "Use a concrete account name.");
        if (LooksVagueAccountScope(reference)) throw FailRequires("clarification_required", "reference account is ambiguous", "provide_reference_account", "reference_account");
        if (reference.EndsWith("-value", StringComparison.OrdinalIgnoreCase)) reference = "Condax";
        var refRows = Query("""
            select account_name, sector, office_location, revenue_band, employee_band,
                   lookalike_key, icp_fit, intent_signal
            from analytics_gtm.mart_gtm__account_enrichment
            where account_name = @p0
            """, [reference]);
        if (refRows.Count == 0) throw FailRequires("denied", "The requested reference account is not available in the bounded enrichment model.", "retry_with_supported_account", "reference_account");
        var matches = Query("""
            select account_name, sector, office_location, revenue_band, employee_band,
                   icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
            from analytics_gtm.mart_gtm__account_enrichment
            where lookalike_key = @p0 and account_name <> @p1
            order by revenue_band desc, account_name
            limit @p2
            """, [refRows[0]["lookalike_key"], reference, BoundedInt(p.GetValueOrDefault("limit"), 5, 10)]);
        return Completed(Dict("reference_account", reference, "reference_profile", refRows[0], "matches", matches));
    }

    private Dictionary<string, object?> AtRiskAccountEnrichment(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var risk = AccountRiskSummary(WithDefault(p, "limit", BoundedInt(p.GetValueOrDefault("limit"), 5, 10)), actor);
        var accounts = Rows(risk.GetValueOrDefault("accounts")).Select(row => Dict("account_name", row.GetValueOrDefault("account_name"), "risk_context", row)).ToList();
        return Completed(Dict("quarter", risk.GetValueOrDefault("quarter"), "owner_scope", risk.GetValueOrDefault("owner_scope"), "ranking_basis", risk.GetValueOrDefault("ranking_basis"), "accounts", accounts, "source_selection", Dict("capability", "gtm.account_risk_summary", "account_count", accounts.Count)));
    }

    private ApprovalRecord PrepareFollowupTasks(Dictionary<string, object?> p, ActorPolicy actor)
    {
        if (!actor.CanPrepareFollowup) throw FailRequires("denied", "This actor role cannot prepare follow-up work.", "request_authorized_actor", "role with follow-up preparation authority");
        var risk = AccountRiskSummary(WithDefault(p, "limit", BoundedInt(p.GetValueOrDefault("limit"), 5, 10)), actor);
        var tasks = Rows(risk.GetValueOrDefault("accounts")).Select(row => Dict(
            "account_name", row.GetValueOrDefault("account_name"),
            "regional_office", row.GetValueOrDefault("regional_office"),
            "recommended_owner", First(Text(row.GetValueOrDefault("sales_agents")).Split(',')).Trim(),
            "task_type", "risk_review_followup",
            "reason", $"Average risk score {row.GetValueOrDefault("average_risk_score")} with {row.GetValueOrDefault("open_opportunity_count")} open opportunities.",
            "suggested_due_in_days", 3)).ToList();
        return CreateApproval("gtm.prepare_followup_tasks", actor, "sales_leader", Dict("quarter", risk.GetValueOrDefault("quarter"), "owner_scope", risk.GetValueOrDefault("owner_scope"), "requires_approval", true, "tasks", tasks));
    }

    private ApprovalRecord PrepareReassignmentPlan(Dictionary<string, object?> p, ActorPolicy actor)
    {
        if (!actor.CanPrepareFollowup) throw FailRequires("denied", "This actor role cannot prepare reassignment work.", "request_authorized_actor", "role with reassignment planning authority");
        var rows = Rows(StalledOpportunities(WithDefault(p, "limit", BoundedInt(p.GetValueOrDefault("limit"), 5, 10)), actor).GetValueOrDefault("opportunities"));
        var reassignments = rows.Select(row => Dict("opportunity_id", row.GetValueOrDefault("opportunity_id"), "account_name", row.GetValueOrDefault("account_name"), "target_manager", "next_available_manager", "reason", "High-attention stalled opportunity preview.")).ToList();
        return CreateApproval("gtm.prepare_reassignment_plan", actor, "sales_leader", Dict("quarter", TextOr(p.GetValueOrDefault("quarter"), "2017-Q2"), "requires_approval", true, "reassignments", reassignments));
    }

    private Dictionary<string, object?> ScoreLeads(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var cohort = NormalizeCohort(Require(p, "cohort_ref", "Which lead cohort should I score?", "Use inbound_last_week or webinar_q2."));
        if (!LeadCohorts.TryGetValue(cohort, out var rows)) throw FailRequires("clarification_required", "The requested prioritization cohort is not explicit enough.", "provide_missing_parameter", "cohort_ref");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var scored = FilterScope(rows, owner).OrderByDescending(row => Number(row["priority_score"])).ThenBy(row => Text(row["lead_id"])).Take(BoundedInt(p.GetValueOrDefault("limit"), 10, 25)).ToList();
        return Completed(Dict("result", Dict("cohort_ref", cohort, "owner_scope", owner, "lead_scores", scored)));
    }

    private Dictionary<string, object?> PrioritizeAccounts(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var cohort = NormalizeCohort(Require(p, "cohort_ref", "Which account cohort should I prioritize?", "Use expansion_candidates_q2 or at_risk_q2."));
        if (!AccountCohorts.TryGetValue(cohort, out var rows)) throw FailRequires("clarification_required", "The requested account cohort is not explicit enough.", "provide_missing_parameter", "cohort_ref");
        var owner = OwnerScope(p.GetValueOrDefault("owner_scope"), actor);
        var ranked = FilterScope(rows, owner).OrderByDescending(row => Number(row["priority_score"])).ThenBy(row => Text(row["account_name"])).Take(BoundedInt(p.GetValueOrDefault("limit"), 10, 25)).ToList();
        return Completed(Dict("result", Dict("cohort_ref", cohort, "owner_scope", owner, "ranking_basis", TextOr(p.GetValueOrDefault("ranking_basis"), "deal_likelihood"), "accounts", ranked)));
    }

    private ApprovalRecord RouteLeads(Dictionary<string, object?> p, ActorPolicy actor)
    {
        if (!actor.CanRouteLeads) throw FailRequires("denied", "This actor cannot route leads.", "request_authorized_actor", "actor with lead-routing access");
        var scored = Map(ScoreLeads(p, actor).GetValueOrDefault("result"));
        var targetQueue = TextOr(p.GetValueOrDefault("target_queue"), "sales");
        var preview = Rows(scored.GetValueOrDefault("lead_scores")).Select(row => Dict("lead_id", row["lead_id"], "account_name", row["account_name"], "recommended_queue", targetQueue, "priority_band", row["priority_band"], "priority_score", row["priority_score"])).ToList();
        return CreateApproval("gtm.route_leads", actor, "sales_leader", Dict("cohort_ref", scored["cohort_ref"], "owner_scope", scored["owner_scope"], "target_queue", targetQueue, "dry_run", true, "preview", preview));
    }

    private Dictionary<string, object?> DraftOutreach(Dictionary<string, object?> p)
    {
        var targetRef = TargetFor(Require(p, "target_ref", "Which account or lead is this outreach for?", "Use Condax, Acme Corporation, or Codehow."));
        var target = OutreachTargets[targetRef];
        var objective = TextOr(p.GetValueOrDefault("objective"), "first_touch");
        var channel = TextOr(p.GetValueOrDefault("channel"), "email");
        var persona = TextOr(p.GetValueOrDefault("persona"), Text(target["persona"]));
        var body = $"Hi {persona},\n\nI'm reaching out because {targetRef} looks like a strong fit for a governed GTM workflow review. Teams in {target["industry"]} often struggle with {target["pain_point"]}. We help them get to {target["proof_point"]} without giving an agent raw, unconstrained system access.\n\nIf useful, I can show how that would apply to {targetRef}'s current priorities and suggest {target["next_step"]}.\n\nBest,\nANIP GTM Team";
        return Completed(Dict("result", Dict("draft_id", $"draft_{targetRef.ToLowerInvariant().Replace(" ", "_")}_{objective}", "target_ref", targetRef, "objective", objective, "channel", channel, "persona", persona, "subject", $"{targetRef}: governed GTM follow-up without workflow sprawl", "body", body, "tone", "direct and operational", "rationale", $"Anchored to {target["priority_context"]} and {target["pain_point"]}.", "target_summary", Dict("industry", target["industry"], "region", target["region"], "priority_context", target["priority_context"]))));
    }

    private Dictionary<string, object?> BottleneckAccountOutreachDraft(Dictionary<string, object?> p, ActorPolicy actor)
    {
        Require(p, "quarter", "quarter is missing", "Quarter label like 2017-Q2.");
        var target = Text(p.GetValueOrDefault("target_ref"));
        if (!string.IsNullOrWhiteSpace(target)) return DraftOutreach(p);
        if (actor.OutreachAccess != "full") throw FailRequires("denied", "This actor cannot request approval-gated outreach target selection.", "request_authorized_actor", "role with full outreach approval authority or explicit selected target_ref");
        var preview = Dict("quarter", p.GetValueOrDefault("quarter"), "owner_scope", p.GetValueOrDefault("owner_scope"), "objective", TextOr(p.GetValueOrDefault("objective"), "first_touch"), "channel", TextOr(p.GetValueOrDefault("channel"), "email"));
        throw ApprovalError(CreateApproval("gtm.bottleneck_account_outreach_draft", actor, "sales_leader", preview), "Drafting outreach from a bottleneck review requires approval or an explicit selected account before generating the message.");
    }

    private Dictionary<string, object?> SuggestFollowupContent(Dictionary<string, object?> p)
    {
        var target = Require(p, "target_ref", "Which account or lead should these follow-up variants target?", "Use Condax, Acme Corporation, or Codehow.");
        var baseDraft = Map(DraftOutreach(WithDefault(p, "target_ref", target)).GetValueOrDefault("result"));
        var variants = new List<Dictionary<string, object?>>
        {
            Dict("variant_id", "follow_up_value", "message", baseDraft["body"], "rationale", "Value-forward follow-up."),
            Dict("variant_id", "follow_up_operational", "message", $"Following up on {baseDraft["target_ref"]}: the practical next step is a bounded GTM workflow review with explicit approval gates.", "rationale", "Short operational follow-up."),
            Dict("variant_id", "follow_up_risk", "message", $"{baseDraft["target_ref"]} appears to have enough GTM coordination risk to justify a scoped review before workflow changes.", "rationale", "Risk-oriented follow-up."),
        };
        return Completed(Dict("result", Dict("target_ref", baseDraft["target_ref"], "persona", baseDraft["persona"], "variants", variants.Take(BoundedInt(p.GetValueOrDefault("variant_count"), 2, 3)).ToList())));
    }

    private Dictionary<string, object?> ObjectionVariants(Dictionary<string, object?> p, ActorPolicy actor)
    {
        if (!actor.CanUseObjectionVariants) throw FailRequires("denied", "This actor can use bounded draft generation but not objection-response variants.", "request_authorized_actor", "role with objection-variant access");
        var raw = Require(p, "objection_theme", "Which objection or competitor theme should these variants address?", "Use pricing, competitor, or implementation_risk.").ToLowerInvariant();
        var theme = raw.Contains("competitor") ? "competitor" : raw.Contains("implement") ? "implementation_risk" : raw.Contains("price") ? "pricing" : raw.Replace("-", "_").Replace(" ", "_");
        if (!Objections.TryGetValue(theme, out var variants)) throw FailRequires("clarification_required", "Unsupported objection theme.", "provide_objection_theme", "objection_theme");
        return Completed(Dict("result", Dict("objection_theme", theme, "target_ref", string.IsNullOrWhiteSpace(Text(p.GetValueOrDefault("target_ref"))) ? null : TargetFor(Text(p["target_ref"])), "variants", variants)));
    }

    private Dictionary<string, object?> PrioritizedOutreachDraft(Dictionary<string, object?> p, ActorPolicy actor)
    {
        var ranked = Map(PrioritizeAccounts(p, actor).GetValueOrDefault("result"));
        var accounts = Rows(ranked.GetValueOrDefault("accounts"));
        if (accounts.Count == 0) return Completed(Dict("result", Dict("accounts", accounts, "draft", null, "empty", true)));
        var draft = Map(DraftOutreach(Dict("target_ref", accounts[0]["account_name"], "objective", p.GetValueOrDefault("objective"), "channel", p.GetValueOrDefault("channel"), "persona", p.GetValueOrDefault("persona"))).GetValueOrDefault("result"));
        ranked["prioritized_accounts"] = accounts;
        ranked["selected_target_ref"] = accounts[0]["account_name"];
        ranked["draft"] = draft;
        return Completed(Dict("result", ranked));
    }

    internal static List<ApprovalRecord> ListApprovals(string? status)
    {
        lock (ApprovalLock)
        {
            return Approvals.Values
                .Where(record => string.IsNullOrWhiteSpace(status) || record.Status == status)
                .OrderBy(record => record.CreatedAt)
                .ToList();
        }
    }

    internal static ApprovalRecord? Approve(string id, ActorPolicy approver)
    {
        lock (ApprovalLock)
        {
            if (!Approvals.TryGetValue(id, out var record)) return null;
            var approved = record with { Status = "approved", ApprovedBy = ActorSummary(approver), ApprovedAt = DateTimeOffset.UtcNow.ToString("O") };
            Approvals[id] = approved;
            return approved;
        }
    }

    internal static ActorPolicy ActorFromBearer(string? bearer)
    {
        var token = (bearer ?? "").Replace("Bearer ", "", StringComparison.OrdinalIgnoreCase).Trim();
        var raw = Environment.GetEnvironmentVariable("ANIP_API_KEYS_JSON");
        if (!string.IsNullOrWhiteSpace(raw))
        {
            try
            {
                var keys = JsonSerializer.Deserialize<Dictionary<string, string>>(raw, JsonOptions) ?? [];
                if (keys.TryGetValue(token, out var principal)) return ActorPolicy.FromPrincipal(principal);
            }
            catch { }
        }
        return ActorPolicy.FromPrincipal(null);
    }

    private ApprovalRecord CreateApproval(string capability, ActorPolicy actor, string requiredRole, Dictionary<string, object?> preview)
    {
        var record = new ApprovalRecord("apr_" + RandomHex(6), capability, requiredRole, "pending", ActorSummary(actor), new(), preview, DateTimeOffset.UtcNow.ToString("O"), null);
        lock (ApprovalLock) Approvals[record.ApprovalRequestId] = record;
        return record;
    }

    private static Dictionary<string, object?> ThrowApproval(ApprovalRecord record)
    {
        throw ApprovalError(record, "Approval is required before downstream mutation.");
    }

    private static AnipError ApprovalError(ApprovalRecord record, string detail)
    {
        var digest = Digest(record.Preview);
        return new AnipError("approval_required", detail, new Resolution
        {
            Action = "request_approval",
            RecoveryClass = Constants.RecoveryClassForAction("request_approval"),
            Requires = "approval before downstream mutation",
        }).WithApprovalRequired(new ApprovalRequiredMetadata
        {
            ApprovalRequestId = record.ApprovalRequestId,
            PreviewDigest = digest,
            RequestedParametersDigest = digest,
            GrantPolicy = new GrantPolicy { AllowedGrantTypes = ["one_time", "session_bound"], DefaultGrantType = "one_time", ExpiresInSeconds = 900, MaxUses = 1 },
        });
    }

    private List<Dictionary<string, object?>> Query(string sql, List<object?> args)
    {
        using var connection = new NpgsqlConnection(NormalizeDbUrl(_databaseUrl));
        connection.Open();
        using var command = new NpgsqlCommand(sql, connection);
        for (var index = 0; index < args.Count; index++) command.Parameters.AddWithValue($"p{index}", args[index] ?? DBNull.Value);
        using var reader = command.ExecuteReader();
        var rows = new List<Dictionary<string, object?>>();
        while (reader.Read())
        {
            var row = new Dictionary<string, object?>();
            for (var index = 0; index < reader.FieldCount; index++) row[reader.GetName(index)] = reader.IsDBNull(index) ? null : reader.GetValue(index);
            rows.Add(row);
        }
        return rows;
    }

    private static string NormalizeDbUrl(string value)
    {
        if (value.StartsWith("Host=", StringComparison.OrdinalIgnoreCase)) return value;
        var uri = new Uri(value);
        var userInfo = uri.UserInfo.Split(':', 2);
        return $"Host={uri.Host};Port={(uri.Port > 0 ? uri.Port : 5432)};Database={uri.AbsolutePath.TrimStart('/')};Username={Uri.UnescapeDataString(userInfo.ElementAtOrDefault(0) ?? "")};Password={Uri.UnescapeDataString(userInfo.ElementAtOrDefault(1) ?? "")}";
    }

    private sealed record ScopeClauseResult(string Sql, List<object?> Args);

    private static ScopeClauseResult ScopeClause(string scope, int parameterIndex)
    {
        if (string.IsNullOrWhiteSpace(scope) || scope is "company" or "all") return new ScopeClauseResult("", []);
        return new ScopeClauseResult($" and regional_office = @p{parameterIndex}", [scope]);
    }

    private static List<object?> Args(object? first, List<object?> middle, object? last) => [first, .. middle, last];
    private static List<object?> Args(object? first, List<object?> rest) => [first, .. rest];

    private static string OwnerScope(object? explicitScope, ActorPolicy actor)
    {
        var requested = Text(explicitScope);
        if (string.IsNullOrWhiteSpace(requested) || requested == "<nil>") return actor.PipelineScope;
        if (actor.PipelineScope is not ("company" or "all") && !requested.Equals(actor.PipelineScope, StringComparison.OrdinalIgnoreCase))
        {
            throw FailRequires("restricted", "This actor is restricted to a narrower pipeline scope.", "retry_with_owned_scope", actor.PipelineScope);
        }
        return requested;
    }

    private static Dictionary<string, object?> ApplyFinancialVisibility(Dictionary<string, object?> payload, ActorPolicy actor)
    {
        if (actor.FinancialAccess == "full") return WithDefault(payload, "visibility", Dict("financial_values", "full"));
        var copy = JsonSerializer.Deserialize<Dictionary<string, object?>>(JsonSerializer.Serialize(payload, JsonOptions), JsonOptions) ?? [];
        void Mask(Dictionary<string, object?> row)
        {
            foreach (var key in new[] { "open_pipeline_value", "won_revenue", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value" })
            {
                if (row.ContainsKey(key)) row[key] = null;
            }
        }
        foreach (var value in copy.Values)
        {
            if (value is JsonElement { ValueKind: JsonValueKind.Array } array)
            {
                foreach (var item in array.EnumerateArray())
                {
                    var row = Map(item);
                    Mask(row);
                }
            }
            foreach (var row in Rows(value)) Mask(row);
        }
        if (copy.TryGetValue("totals", out var totals)) Mask(Map(totals));
        copy["visibility"] = Dict("financial_values", "masked", "reason", "actor policy does not allow financial values in this view");
        return copy;
    }

    private static string Require(Dictionary<string, object?> p, string field, string detail, string hint)
    {
        var value = Text(p.GetValueOrDefault(field));
        if (!string.IsNullOrWhiteSpace(value) && value != "<nil>") return field == "quarter" && value == "quarter-value" ? "2017-Q2" : value;
        var error = FailRequires("clarification_required", detail, "provide_missing_parameter", field);
        error.Resolution!.EstimatedAvailability = hint;
        throw error;
    }

    private static string NormalizeCohort(string value)
    {
        var normalized = value.Trim().ToLowerInvariant().Replace("-", "_").Replace(" ", "_");
        if (normalized.Contains("inbound")) return "inbound_last_week";
        if (normalized.Contains("webinar")) return "webinar_q2";
        if (normalized.Contains("expansion")) return "expansion_candidates_q2";
        if (normalized.Contains("risk")) return "at_risk_q2";
        return normalized;
    }

    private static string TargetFor(string raw)
    {
        foreach (var key in OutreachTargets.Keys)
        {
            if (raw.Contains(key, StringComparison.OrdinalIgnoreCase)) return key;
        }
        throw FailRequires("clarification_required", "Unknown target_ref.", "provide_reference_account", "target_ref");
    }

    private static List<string> ParseNames(object? value)
    {
        if (value is IEnumerable<object?> items) return items.Select(Text).Where(text => !string.IsNullOrWhiteSpace(text)).ToList();
        if (value is JsonElement { ValueKind: JsonValueKind.Array } array) return array.EnumerateArray().Select(item => Text(item)).Where(text => !string.IsNullOrWhiteSpace(text)).ToList();
        var normalized = Regex.Replace(Text(value), @"\s+\band\b\s+", ",", RegexOptions.IgnoreCase);
        return normalized.Split(new[] { ',', ';' }, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Where(text => !string.IsNullOrWhiteSpace(text)).ToList();
    }

    private static bool LooksVagueAccountScope(string value)
    {
        var normalized = value.ToLowerInvariant();
        return normalized.Contains("top") || normalized.Contains("risk") || normalized.Contains("accounts") || normalized.Contains("selected");
    }

    private static List<Dictionary<string, object?>> FilterScope(List<Dictionary<string, object?>> rows, string scope)
    {
        if (scope is "" or "company" or "all") return rows.Select(Clone).ToList();
        return rows.Where(row => Text(row.GetValueOrDefault("owner_scope")).Equals(scope, StringComparison.OrdinalIgnoreCase)).Select(Clone).ToList();
    }

    private static Dictionary<string, object?> Completed(Dictionary<string, object?> payload) => WithDefault(payload, "execution_status", "completed");
    private static Dictionary<string, object?> WithDefault(Dictionary<string, object?> source, string key, object? value) { var copy = Clone(source); copy.TryAdd(key, value); return copy; }
    private static Dictionary<string, object?> Clone(Dictionary<string, object?> source) => new(source);
    private static Dictionary<string, object?> Dict(params object?[] values) { var result = new Dictionary<string, object?>(); for (var i = 0; i + 1 < values.Length; i += 2) result[Text(values[i])] = values[i + 1]; return result; }
    private static string Text(object? value) => value switch { null => "", JsonElement e when e.ValueKind == JsonValueKind.String => e.GetString() ?? "", JsonElement e => e.ToString(), _ => value.ToString() ?? "" };
    private static string TextOr(object? value, string fallback) => string.IsNullOrWhiteSpace(Text(value)) || Text(value) == "<nil>" ? fallback : Text(value);
    private static double Number(object? value) => double.TryParse(Text(value), out var parsed) ? parsed : 0;
    private static double Round2(double value) => Math.Round(value, 2, MidpointRounding.AwayFromZero);
    private static int BoundedInt(object? value, int fallback, int max) => Math.Max(1, Math.Min(max, int.TryParse(Text(value), out var parsed) ? parsed : fallback));
    private static string ForecastKey(string mode) => mode == "best_case" ? "best_case_revenue" : mode == "likely" ? "likely_revenue" : "risk_adjusted_revenue";
    private static string First(IEnumerable<string> values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "unassigned";

    private static Dictionary<string, object?> Map(object? value)
    {
        if (value is Dictionary<string, object?> dict) return dict;
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Object) return JsonSerializer.Deserialize<Dictionary<string, object?>>(element.GetRawText(), JsonOptions) ?? [];
        return [];
    }

    private static List<Dictionary<string, object?>> Rows(object? value)
    {
        if (value is List<Dictionary<string, object?>> rows) return rows;
        if (value is IEnumerable<Dictionary<string, object?>> enumerable) return enumerable.ToList();
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Array) return element.EnumerateArray().Select(item => Map(item)).ToList();
        return [];
    }

    private static AnipError Fail(string kind, string detail, string action) => new(kind, detail, new Resolution { Action = CanonicalAction(action), RecoveryClass = Constants.RecoveryClassForAction(CanonicalAction(action)) });

    private static AnipError FailRequires(string kind, string detail, string action, string requires)
    {
        var canonical = CanonicalAction(action);
        return new AnipError(kind, detail, new Resolution { Action = canonical, RecoveryClass = Constants.RecoveryClassForAction(canonical), Requires = requires });
    }

    private static string CanonicalAction(string action) => action switch
    {
        "request_authorized_actor" or "retry_with_owned_scope" => "request_new_delegation",
        "provide_missing_parameter" or "provide_account_scope" or "provide_reference_account" or "provide_supported_account_names" or "provide_objection_theme" or "retry_with_supported_forecast_mode" or "retry_with_supported_slice" or "retry_with_supported_ranking" or "retry_with_supported_selection_basis" or "retry_with_supported_account" or "complete_native_language_slice" => "obtain_binding",
        _ => action,
    };

    private static string Digest(object payload)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(payload, JsonOptions)));
        return "sha256:" + Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static string RandomHex(int bytes)
    {
        Span<byte> buffer = stackalloc byte[bytes];
        RandomNumberGenerator.Fill(buffer);
        return Convert.ToHexString(buffer).ToLowerInvariant();
    }

    private static Dictionary<string, object?> ActorSummary(ActorPolicy actor) => Dict("actor_id", actor.ActorId, "role", actor.Role, "pipeline_scope", actor.PipelineScope);

    private static readonly Dictionary<string, List<Dictionary<string, object?>>> LeadCohorts = new()
    {
        ["inbound_last_week"] =
        [
            Dict("lead_id", "lead-001", "account_name", "Condax", "owner_scope", "East", "priority_score", 94, "priority_band", "high", "rationale", "High fit and urgent buying signal."),
            Dict("lead_id", "lead-002", "account_name", "Codehow", "owner_scope", "East", "priority_score", 89, "priority_band", "high", "rationale", "Strong GTM systems fit."),
            Dict("lead_id", "lead-003", "account_name", "Acme Corporation", "owner_scope", "West", "priority_score", 82, "priority_band", "medium", "rationale", "Expansion interest and active pipeline."),
        ],
        ["webinar_q2"] =
        [
            Dict("lead_id", "lead-101", "account_name", "Groovestreet", "owner_scope", "Central", "priority_score", 86, "priority_band", "high", "rationale", "Engaged webinar attendee."),
            Dict("lead_id", "lead-102", "account_name", "Betasoloin", "owner_scope", "West", "priority_score", 79, "priority_band", "medium", "rationale", "Relevant pain profile."),
        ],
    };

    private static readonly Dictionary<string, List<Dictionary<string, object?>>> AccountCohorts = new()
    {
        ["expansion_candidates_q2"] =
        [
            Dict("account_name", "Condax", "owner_scope", "East", "priority_score", 94, "priority_band", "high", "rationale", "Expansion candidate with high GTM fit."),
            Dict("account_name", "Codehow", "owner_scope", "East", "priority_score", 90, "priority_band", "high", "rationale", "Strong system integration need."),
            Dict("account_name", "Acme Corporation", "owner_scope", "West", "priority_score", 84, "priority_band", "medium", "rationale", "Expansion motion visible."),
        ],
        ["at_risk_q2"] =
        [
            Dict("account_name", "Condax", "owner_scope", "East", "priority_score", 95, "priority_band", "high", "rationale", "High risk and high value."),
            Dict("account_name", "Acme Corporation", "owner_scope", "West", "priority_score", 88, "priority_band", "high", "rationale", "Aging high-value opportunity."),
            Dict("account_name", "Codehow", "owner_scope", "East", "priority_score", 82, "priority_band", "medium", "rationale", "Needs follow-up."),
        ],
    };

    private static readonly Dictionary<string, Dictionary<string, object?>> OutreachTargets = new()
    {
        ["Condax"] = Dict("industry", "industrial manufacturing", "persona", "VP of Operations", "region", "East", "priority_context", "high-priority expansion candidate", "pain_point", "fragmented forecasting and slow handoff between revenue teams", "proof_point", "governed pipeline review with approval-aware follow-up planning", "next_step", "a short operations-focused discovery call"),
        ["Acme Corporation"] = Dict("industry", "enterprise services", "persona", "Revenue Operations Lead", "region", "West", "priority_context", "stalled high-value opportunity", "pain_point", "manual handoffs and unreviewed routing", "proof_point", "bounded agent execution with explicit approval records", "next_step", "a focused revenue operations review"),
        ["Codehow"] = Dict("industry", "software and digital services", "persona", "Head of GTM Systems", "region", "East", "priority_context", "high-fit target for follow-up acceleration", "pain_point", "manual scoring and inconsistent routing decisions", "proof_point", "governed scoring and approval-gated routing previews", "next_step", "a systems-focused follow-up conversation"),
    };

    private static readonly Dictionary<string, List<Dictionary<string, object?>>> Objections = new()
    {
        ["pricing"] = [Dict("variant_id", "pricing_value", "message", "Anchor on avoided workflow sprawl and governed execution evidence.", "rationale", "Value framing.")],
        ["competitor"] = [Dict("variant_id", "competitor_control", "message", "Differentiate on service-side governance rather than prompt-only tool use.", "rationale", "Control-plane framing.")],
        ["implementation_risk"] = [Dict("variant_id", "implementation_safe", "message", "Start with preview-only capabilities and approval gates before writes.", "rationale", "Implementation-risk reduction.")],
    };
}

internal sealed record ActorPolicy(
    string ActorId,
    string Role,
    string PipelineScope,
    string FinancialAccess,
    string OutreachAccess,
    bool CanPrepareFollowup,
    bool CanUseLookalikes,
    bool CanRouteLeads,
    bool CanUseObjectionVariants)
{
    public static ActorPolicy FromPrincipal(string? principal)
    {
        var claims = new Dictionary<string, string>();
        foreach (var piece in (principal ?? "").Split('|').Skip(1))
        {
            var separator = piece.IndexOf('=');
            if (separator > 0) claims[piece[..separator]] = piece[(separator + 1)..];
        }
        var actorId = claims.GetValueOrDefault("actor_id", "sales_leader");
        return new ActorPolicy(
            actorId,
            claims.GetValueOrDefault("role", actorId == "sales_analyst" ? "sales_analyst" : "sales_leader"),
            claims.GetValueOrDefault("pipeline_scope", actorId == "account_manager_east" ? "East" : "company"),
            claims.GetValueOrDefault("financial_access", actorId == "sales_analyst" ? "masked" : "full"),
            claims.GetValueOrDefault("outreach_access", actorId == "sales_analyst" ? "bounded" : "full"),
            Bool(claims.GetValueOrDefault("can_prepare_followup"), actorId is "sales_leader" or "rev_ops_manager" or "account_manager_east"),
            Bool(claims.GetValueOrDefault("can_use_lookalikes"), actorId != "sales_analyst"),
            Bool(claims.GetValueOrDefault("can_route_leads"), actorId is "sales_leader" or "rev_ops_manager"),
            Bool(claims.GetValueOrDefault("can_use_objection_variants"), actorId != "sales_analyst"));
    }

    private static bool Bool(string? value, bool fallback) => bool.TryParse(value, out var parsed) ? parsed : fallback;
}

internal sealed record ApprovalRecord(
    string ApprovalRequestId,
    string Capability,
    string RequiredRole,
    string Status,
    Dictionary<string, object?> RequestedBy,
    Dictionary<string, object?> ApprovedBy,
    Dictionary<string, object?> Preview,
    string CreatedAt,
    string? ApprovedAt);
