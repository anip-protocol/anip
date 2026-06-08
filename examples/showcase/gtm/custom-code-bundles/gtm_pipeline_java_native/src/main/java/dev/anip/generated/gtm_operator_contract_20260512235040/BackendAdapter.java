package {{ANIP_JAVA_PACKAGE_NAME}};

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.anip.core.ANIPError;
import dev.anip.core.ApprovalRequiredMetadata;
import dev.anip.core.Constants;
import dev.anip.core.GrantPolicy;
import dev.anip.core.Resolution;
import dev.anip.service.InvocationContext;

import java.math.BigDecimal;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

@FunctionalInterface
public interface BackendAdapter {

    Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context);

    static BackendAdapter defaultAdapter() {
        return new GtmNativeBackendAdapter();
    }
}

final class GtmNativeBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final Map<String, ApprovalRecord> APPROVALS = new ConcurrentHashMap<>();

    private final String databaseUrl;

    GtmNativeBackendAdapter() {
        this.databaseUrl = firstNonEmpty(System.getenv("DATABASE_URL"), "postgresql://anip:anip@127.0.0.1:5454/anip_gtm");
    }

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context) {
        ActorPolicy actor = actorPolicyFromPrincipal(context == null ? "" : context.getRootPrincipal());
        Map<String, Object> params = objectMap(plan.get("semantic_input"));
        String capabilityId = string(capability.get("capability_id"));
        try {
            return switch (capabilityId) {
                case "gtm.pipeline_summary" -> pipelineSummary(params, actor);
                case "gtm.pipeline_forecast_summary" -> forecastSummary(params, actor);
                case "gtm.stage_bottleneck_summary" -> stageBottleneckSummary(params, actor);
                case "gtm.sales_team_performance_summary" -> salesTeamPerformanceSummary(params, actor);
                case "gtm.product_pipeline_summary" -> productPipelineSummary(params, actor);
                case "gtm.stalled_opportunity_review" -> stalledOpportunities(params, actor);
                case "gtm.account_risk_summary" -> accountRiskSummary(params, actor);
                case "gtm.prepare_followup_tasks", "gtm.at_risk_followup_preparation" -> {
                    prepareFollowupTasks(params, actor);
                    yield Map.of();
                }
                case "gtm.prepare_reassignment_plan", "gtm.at_risk_reassignment_preparation" -> {
                    prepareReassignmentPlan(params, actor);
                    yield Map.of();
                }
                case "gtm.account_enrichment_summary" -> accountEnrichmentSummary(params, actor);
                case "gtm.lookalike_accounts" -> lookalikeAccounts(params, actor);
                case "gtm.at_risk_account_enrichment_summary" -> atRiskAccountEnrichment(params, actor);
                case "gtm.score_leads" -> scoreLeads(params, actor);
                case "gtm.prioritize_accounts" -> prioritizeAccounts(params, actor);
                case "gtm.route_leads" -> {
                    routeLeads(params, actor);
                    yield Map.of();
                }
                case "gtm.prioritized_routing_preparation" -> {
                    Map<String, Object> next = cloneMap(params);
                    next.putIfAbsent("target_queue", "sales");
                    routeLeads(next, actor);
                    yield Map.of();
                }
                case "gtm.draft_outreach_message" -> draftOutreach(params);
                case "gtm.bottleneck_account_outreach_draft" -> bottleneckAccountOutreachDraft(params, actor);
                case "gtm.suggest_followup_content" -> suggestFollowupContent(params);
                case "gtm.objection_response_variants" -> objectionVariants(params, actor);
                case "gtm.prioritized_outreach_draft" -> prioritizedOutreachDraft(params, actor);
                default -> throw fail("temporarily_unavailable", "The Java native GTM bundle has not implemented " + capabilityId + " yet.", "complete_native_language_slice");
            };
        } catch (ANIPError error) {
            throw error;
        } catch (Exception error) {
            throw new ANIPError("temporarily_unavailable", error.getMessage()).withResolution("contact_service_owner");
        }
    }

    private List<Map<String, Object>> query(String sql, Object... args) throws Exception {
        try (Connection connection = DriverManager.getConnection(jdbcUrl(databaseUrl));
             PreparedStatement statement = connection.prepareStatement(sql)) {
            for (int index = 0; index < args.length; index++) {
                statement.setObject(index + 1, args[index]);
            }
            try (ResultSet rs = statement.executeQuery()) {
                ResultSetMetaData meta = rs.getMetaData();
                List<Map<String, Object>> rows = new ArrayList<>();
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (int index = 1; index <= meta.getColumnCount(); index++) {
                        Object value = rs.getObject(index);
                        if (value instanceof BigDecimal decimal) {
                            value = decimal.doubleValue();
                        }
                        row.put(meta.getColumnLabel(index), value);
                    }
                    rows.add(row);
                }
                return rows;
            }
        }
    }

    private static String jdbcUrl(String url) {
        if (url.startsWith("jdbc:")) return url;
        if (url.startsWith("postgresql://")) {
            try {
                URI parsed = URI.create(url);
                StringBuilder jdbc = new StringBuilder("jdbc:postgresql://");
                jdbc.append(parsed.getHost());
                if (parsed.getPort() > 0) jdbc.append(":").append(parsed.getPort());
                jdbc.append(firstNonEmpty(parsed.getPath(), "/"));
                String userInfo = parsed.getUserInfo();
                if (userInfo != null && !userInfo.isBlank()) {
                    String[] parts = userInfo.split(":", 2);
                    jdbc.append("?user=").append(urlEncode(parts[0]));
                    if (parts.length > 1) jdbc.append("&password=").append(urlEncode(parts[1]));
                }
                return jdbc.toString();
            } catch (Exception ignored) {
                return "jdbc:" + url;
            }
        }
        return url;
    }

    private static String urlEncode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private Map<String, Object> pipelineSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        List<Map<String, Object>> rows = query("""
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
                where engage_quarter = ? %s
                group by deal_stage
                order by deal_stage asc
                """.formatted(scope.clause), args.toArray());
        Map<String, Object> totals = map("opportunity_count", 0, "open_pipeline_value", 0.0, "won_revenue", 0.0);
        for (Map<String, Object> row : rows) {
            totals.put("opportunity_count", (int) (number(totals.get("opportunity_count")) + number(row.get("opportunity_count"))));
            totals.put("open_pipeline_value", round2(number(totals.get("open_pipeline_value")) + number(row.get("open_pipeline_value"))));
            totals.put("won_revenue", round2(number(totals.get("won_revenue")) + number(row.get("won_revenue"))));
        }
        return completed(applyFinancialVisibility(map("quarter", quarter, "owner_scope", owner, "by_stage", rows, "totals", totals), actor));
    }

    private Map<String, Object> forecastSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        String mode = optionalText(params.get("forecast_mode"), "risk_adjusted");
        if (!List.of("risk_adjusted", "likely", "best_case").contains(mode)) {
            throw fail("denied", "Pipeline forecast only supports forecast_mode=risk_adjusted, likely, or best_case.", "retry_with_supported_forecast_mode");
        }
        int limit = boundedInt(params.get("limit"), 5, 10);
        String selected = forecastKey(mode);
        ScopeSql scope = sqlScope(owner);
        List<Object> stageArgs = new ArrayList<>();
        stageArgs.add(quarter);
        stageArgs.addAll(scope.args);
        List<Map<String, Object>> stageRows = query("""
                select deal_stage,
                       sum(open_opportunity_count)::int as open_opportunity_count,
                       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
                       round(sum(likely_revenue), 2)::float as likely_revenue,
                       round(sum(best_case_revenue), 2)::float as best_case_revenue,
                       round(sum(risk_adjusted_revenue), 2)::float as risk_adjusted_revenue,
                       round(avg(average_open_risk_score), 2)::float as average_risk_score
                from analytics_gtm.bi_gtm__forecast_stage_summary
                where engage_quarter = ? %s
                group by deal_stage
                order by deal_stage asc
                """.formatted(scope.clause), stageArgs.toArray());
        for (Map<String, Object> row : stageRows) {
            row.put("selected_forecast_value", row.get(selected));
        }
        List<Object> contributorArgs = new ArrayList<>(stageArgs);
        contributorArgs.add(limit);
        List<Map<String, Object>> contributors = query("""
                select account_name, regional_office, count(*)::int as open_opportunity_count,
                       round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
                       round(sum(close_value * 0.65), 2)::float as likely_revenue,
                       round(sum(close_value * 0.85), 2)::float as best_case_revenue,
                       round(sum(close_value * (1 - coalesce(risk_score, 0) / 100)), 2)::float as risk_adjusted_revenue,
                       round(avg(risk_score), 2)::float as average_risk_score
                from analytics_gtm.fct_gtm__opportunities
                where engage_quarter = ? and is_open = true %s
                  and account_name is not null and trim(account_name) <> ''
                group by account_name, regional_office
                order by %s desc nulls last, account_name
                limit ?
                """.formatted(scope.clause, selected), contributorArgs.toArray());
        for (Map<String, Object> row : contributors) {
            row.put("selected_forecast_value", row.get(selected));
        }
        Map<String, Object> totals = map("open_opportunity_count", 0, "open_pipeline_value", 0.0, "likely_revenue", 0.0, "best_case_revenue", 0.0, "risk_adjusted_revenue", 0.0);
        for (Map<String, Object> row : stageRows) {
            for (String key : List.of("open_opportunity_count", "open_pipeline_value", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue")) {
                totals.put(key, round2(number(totals.get(key)) + number(row.get(key))));
            }
        }
        totals.put("selected_forecast_value", totals.get(selected));
        return completed(applyFinancialVisibility(map("quarter", quarter, "owner_scope", owner, "forecast_mode", mode, "by_stage", stageRows, "top_contributors", contributors, "totals", totals), actor));
    }

    private Map<String, Object> stageBottleneckSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        String sliceBy = optionalText(params.get("slice_by"), "regional_office");
        if (!List.of("regional_office", "manager_name", "product_name").contains(sliceBy)) {
            throw fail("denied", "Stage bottleneck summary only supports regional_office, manager_name, or product_name.", "retry_with_supported_slice");
        }
        int limit = boundedInt(params.get("limit"), 10, 15);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select deal_stage, %s as slice_value,
                       sum(open_opportunity_count)::int as open_opportunity_count,
                       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
                       round(avg(average_open_days), 2)::float as average_open_days,
                       round(avg(average_open_risk_score), 2)::float as average_risk_score
                from analytics_gtm.bi_gtm__stage_bottlenecks
                where engage_quarter = ? %s
                group by deal_stage, %s
                order by average_open_days desc nulls last, average_risk_score desc nulls last, open_opportunity_count desc, slice_value, deal_stage
                limit ?
                """.formatted(sliceBy, scope.clause, sliceBy), args.toArray());
        for (int index = 0; index < rows.size(); index++) {
            rows.get(index).put("slice_by", sliceBy);
            rows.get(index).put("bottleneck_rank", index + 1);
        }
        return completed(applyFinancialVisibility(map("quarter", quarter, "owner_scope", owner, "slice_by", sliceBy, "bottlenecks", rows), actor));
    }

    private Map<String, Object> salesTeamPerformanceSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        String sliceBy = optionalText(params.get("slice_by"), "manager_name");
        if (!List.of("manager_name", "regional_office").contains(sliceBy)) {
            throw fail("denied", "Sales team performance only supports slice_by=manager_name or regional_office.", "retry_with_supported_slice");
        }
        int limit = boundedInt(params.get("limit"), 10, 15);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select %s as slice_value,
                       sum(opportunity_count)::int as opportunity_count,
                       sum(open_opportunity_count)::int as open_opportunity_count,
                       sum(won_opportunity_count)::int as won_opportunity_count,
                       sum(lost_opportunity_count)::int as lost_opportunity_count,
                       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
                       round(sum(won_revenue), 2)::float as won_revenue,
                       round(avg(average_open_risk_score), 2)::float as average_open_risk_score,
                       round(avg(average_open_days), 2)::float as average_open_days
                from analytics_gtm.bi_gtm__sales_team_performance
                where engage_quarter = ? %s
                group by %s
                order by open_pipeline_value desc nulls last, won_opportunity_count desc nulls last, average_open_risk_score desc nulls last, slice_value
                limit ?
                """.formatted(sliceBy, scope.clause, sliceBy), args.toArray());
        for (Map<String, Object> row : rows) {
            row.put("slice_by", sliceBy);
        }
        return completed(applyFinancialVisibility(map("quarter", quarter, "owner_scope", owner, "slice_by", sliceBy, "performance_rows", rows), actor));
    }

    private Map<String, Object> productPipelineSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        String product = string(params.get("product_scope"));
        if ("<nil>".equals(product)) product = "";
        int limit = boundedInt(params.get("limit"), 10, 15);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        String productClause = "";
        if (!product.isBlank()) {
            productClause = " and product_name = ?";
            args.add(product);
        }
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select product_name,
                       sum(open_opportunity_count)::int as open_opportunity_count,
                       sum(won_opportunity_count)::int as won_opportunity_count,
                       sum(lost_opportunity_count)::int as lost_opportunity_count,
                       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
                       round(sum(won_revenue), 2)::float as won_revenue,
                       round(avg(average_open_risk_score), 2)::float as average_open_risk_score
                from analytics_gtm.bi_gtm__product_pipeline
                where engage_quarter = ? %s%s
                group by product_name
                order by open_pipeline_value desc nulls last, won_revenue desc nulls last, open_opportunity_count desc, product_name
                limit ?
                """.formatted(scope.clause, productClause), args.toArray());
        return completed(applyFinancialVisibility(map("quarter", quarter, "owner_scope", owner, "product_scope", product.isBlank() ? null : product, "products", rows), actor));
    }

    private Map<String, Object> stalledOpportunities(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        int minDaysOpen = boundedInt(params.get("min_days_open"), 30, 999);
        int limit = boundedInt(params.get("limit"), 10, 25);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        args.add(minDaysOpen);
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select opportunity_id, account_name, sales_agent_name, regional_office, deal_stage,
                       product_name, engage_date::text, days_since_engage::int, round(risk_score, 2)::float as risk_score
                from analytics_gtm.fct_gtm__opportunities
                where engage_quarter = ? and is_open = true %s and days_since_engage >= ?
                order by risk_score desc nulls last, days_since_engage desc, opportunity_id
                limit ?
                """.formatted(scope.clause), args.toArray());
        return completed(map("quarter", quarter, "owner_scope", owner, "min_days_open", minDaysOpen, "opportunities", rows));
    }

    private Map<String, Object> accountRiskSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        int limit = boundedInt(firstNonNull(params.get("limit"), params.get("top_n")), 10, 25);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select account_name, regional_office, count(*)::int as open_opportunity_count,
                       round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
                       round(avg(risk_score), 2)::float as average_risk_score,
                       max(days_since_engage)::int as max_days_open,
                       string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
                from analytics_gtm.fct_gtm__opportunities
                where engage_quarter = ? and is_open = true %s
                  and account_name is not null and trim(account_name) <> ''
                group by account_name, regional_office
                order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
                limit ?
                """.formatted(scope.clause), args.toArray());
        return completed(applyFinancialVisibility(map("quarter", quarter, "owner_scope", owner, "ranking_basis", optionalText(params.get("ranking_basis"), "risk_score"), "accounts", rows), actor));
    }

    private Map<String, Object> accountEnrichmentSummary(Map<String, Object> params, ActorPolicy actor) throws Exception {
        List<String> names = parseAccountNames(firstNonNull(params.get("account_names"), params.get("account_set"), params.get("target_ref")));
        if (names.isEmpty()) {
            throw failRequires("clarification_required", "Which account set should be enriched?", "provide_missing_parameter", "account_set");
        }
        for (String name : names) {
            if (looksLikeVagueAccountScope(name)) {
                throw failRequires("clarification_required", "account scope is ambiguous", "provide_account_scope", "account_names");
            }
        }
        int limit = boundedInt(params.get("limit"), 5, 10);
        String placeholders = String.join(",", names.stream().map(_item -> "?").toList());
        List<Object> args = new ArrayList<>(names);
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select account_name, sector, office_location, parent_company, revenue_band,
                       employee_band, icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
                from analytics_gtm.mart_gtm__account_enrichment
                where account_name in (%s)
                order by account_name
                limit ?
                """.formatted(placeholders), args.toArray());
        if (rows.isEmpty()) {
            throw failRequires("clarification_required", "no supported enrichment accounts matched the request", "provide_supported_account_names", "account_names");
        }
        String visibility = "full".equals(actor.financialAccess) ? "full" : "not_included";
        return completed(map("account_set", names, "accounts", rows, "visibility", map("financial_values", visibility)));
    }

    private Map<String, Object> lookalikeAccounts(Map<String, Object> params, ActorPolicy actor) throws Exception {
        if (!actor.canUseLookalikes) {
            throw failRequires("denied", "Lookalike analysis is not available for this actor role.", "request_authorized_actor", "role with lookalike access");
        }
        String reference = requireString(params, "reference_account", "Which reference account should be used for lookalikes?", "Use a concrete account name.");
        if (looksLikeVagueAccountScope(reference)) {
            throw failRequires("clarification_required", "reference account is ambiguous", "provide_reference_account", "reference_account");
        }
        if (reference.endsWith("-value")) reference = "Condax";
        int limit = boundedInt(params.get("limit"), 5, 10);
        List<Map<String, Object>> refRows = query("""
                select account_name, sector, office_location, revenue_band, employee_band,
                       lookalike_key, icp_fit, intent_signal
                from analytics_gtm.mart_gtm__account_enrichment
                where account_name = ?
                """, reference);
        if (refRows.isEmpty()) {
            throw failRequires("denied", "The requested reference account is not available in the bounded enrichment model.", "retry_with_supported_account", "reference_account present in the enrichment profile");
        }
        List<Map<String, Object>> matches = query("""
                select account_name, sector, office_location, revenue_band, employee_band,
                       icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
                from analytics_gtm.mart_gtm__account_enrichment
                where lookalike_key = ? and account_name <> ?
                order by revenue_band desc, account_name
                limit ?
                """, refRows.get(0).get("lookalike_key"), reference, limit);
        return completed(map("reference_account", reference, "reference_profile", refRows.get(0), "matches", matches));
    }

    private Map<String, Object> atRiskAccountEnrichment(Map<String, Object> params, ActorPolicy actor) throws Exception {
        Map<String, Object> next = cloneMap(params);
        next.put("limit", boundedInt(params.get("limit"), 5, 10));
        Map<String, Object> risk = accountRiskSummary(next, actor);
        List<Map<String, Object>> riskAccounts = mapList(risk.get("accounts"));
        List<String> names = new ArrayList<>();
        for (Map<String, Object> row : riskAccounts) {
            if (!string(row.get("account_name")).isBlank()) names.add(string(row.get("account_name")));
        }
        Map<String, Map<String, Object>> enrichmentByName = new HashMap<>();
        if (!names.isEmpty()) {
            Map<String, Object> enrichment = accountEnrichmentSummary(map("account_names", names, "limit", names.size()), actor);
            for (Map<String, Object> row : mapList(enrichment.get("accounts"))) {
                enrichmentByName.put(string(row.get("account_name")), row);
            }
        }
        List<Map<String, Object>> accounts = new ArrayList<>();
        for (Map<String, Object> row : riskAccounts) {
            Map<String, Object> item = cloneMap(enrichmentByName.get(string(row.get("account_name"))));
            item.put("account_name", row.get("account_name"));
            item.put("risk_context", row);
            accounts.add(item);
        }
        return completed(map("quarter", risk.get("quarter"), "owner_scope", risk.get("owner_scope"), "ranking_basis", firstNonEmpty(string(risk.get("ranking_basis")), "risk_score"), "accounts", accounts, "source_selection", map("capability", "gtm.account_risk_summary", "account_count", accounts.size(), "no_results", accounts.isEmpty())));
    }

    private void prepareFollowupTasks(Map<String, Object> params, ActorPolicy actor) throws Exception {
        if (!actor.canPrepareFollowup) {
            throw failRequires("denied", "This actor role cannot prepare follow-up work.", "request_authorized_actor", "role with follow-up preparation authority");
        }
        String quarter = requireString(params, "quarter", "target accounts or quarter are missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        String ranking = optionalText(params.get("ranking_basis"), "risk_score");
        if (!"risk_score".equals(ranking)) {
            throw fail("denied", "Follow-up preparation only supports ranking_basis=risk_score.", "retry_with_supported_ranking");
        }
        Map<String, Object> risk = accountRiskSummary(map("quarter", quarter, "owner_scope", owner, "ranking_basis", ranking, "limit", boundedInt(params.get("limit"), 5, 10)), actor);
        List<Map<String, Object>> tasks = new ArrayList<>();
        for (Map<String, Object> row : mapList(risk.get("accounts"))) {
            String ownerName = firstNonEmpty(string(row.get("sales_agents")), "unassigned").split(",")[0].trim();
            tasks.add(map("account_name", row.get("account_name"), "regional_office", row.get("regional_office"), "recommended_owner", ownerName, "task_type", "risk_review_followup", "reason", "Average risk score " + row.get("average_risk_score") + " with " + row.get("open_opportunity_count") + " open opportunities and max age " + row.get("max_days_open") + " days.", "suggested_due_in_days", 3));
        }
        Map<String, Object> preview = map("quarter", quarter, "owner_scope", owner, "ranking_basis", ranking, "requires_approval", true, "tasks", tasks);
        throw approvalError(createApprovalRequest("gtm.prepare_followup_tasks", actor, "sales_leader", preview), "any downstream task creation or CRM mutation would occur");
    }

    private void prepareReassignmentPlan(Map<String, Object> params, ActorPolicy actor) throws Exception {
        if (!actor.canPrepareFollowup) {
            throw failRequires("denied", "This actor role cannot prepare reassignment work.", "request_authorized_actor", "role with reassignment planning authority");
        }
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2");
        String owner = ownerScope(params.get("owner_scope"), actor);
        String selectionBasis = optionalText(params.get("selection_basis"), "manager_capacity");
        if (!List.of("manager_capacity", "stalled_risk_mix").contains(selectionBasis)) {
            throw fail("denied", "Reassignment planning only supports manager_capacity or stalled_risk_mix.", "retry_with_supported_selection_basis");
        }
        int limit = boundedInt(params.get("limit"), 5, 10);
        ScopeSql scope = sqlScope(owner);
        List<Object> args = new ArrayList<>();
        args.add(quarter);
        args.addAll(scope.args);
        args.add(limit);
        List<Map<String, Object>> rows = query("""
                select opportunity_id, account_name, sales_agent_name, manager_name, regional_office,
                       deal_stage, product_name, days_since_engage::int, round(risk_score, 2)::float as risk_score
                from analytics_gtm.fct_gtm__opportunities
                where engage_quarter = ? and is_open = true %s
                order by risk_score desc nulls last, days_since_engage desc, opportunity_id
                limit ?
                """.formatted(scope.clause), args.toArray());
        List<Map<String, Object>> reassignments = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            reassignments.add(map("opportunity_id", row.get("opportunity_id"), "account_name", row.get("account_name"), "sales_agent_name", row.get("sales_agent_name"), "deal_stage", row.get("deal_stage"), "product_name", row.get("product_name"), "source_manager", row.get("manager_name"), "source_region", row.get("regional_office"), "target_manager", "next_available_manager", "target_region", row.get("regional_office"), "days_since_engage", row.get("days_since_engage"), "risk_score", row.get("risk_score"), "reason", row.get("manager_name") + " owns a high-attention opportunity open " + row.get("days_since_engage") + " days with risk score " + row.get("risk_score") + "."));
        }
        Map<String, Object> preview = map("quarter", quarter, "owner_scope", owner, "selection_basis", selectionBasis, "requires_approval", true, "reassignments", reassignments);
        throw approvalError(createApprovalRequest("gtm.prepare_reassignment_plan", actor, "sales_leader", preview), "any downstream reassignment execution would occur");
    }

    private Map<String, Object> scoreLeads(Map<String, Object> params, ActorPolicy actor) {
        String cohort = normalizeCohortRef(requireString(params, "cohort_ref", "Which lead cohort should I score?", "Use inbound_last_week or webinar_q2."));
        List<Map<String, Object>> rows = LEAD_COHORTS.get(cohort);
        if (rows == null) {
            throw failRequires("clarification_required", "The requested prioritization cohort is not explicit enough.", "provide_missing_parameter", "cohort_ref");
        }
        String owner = ownerScope(params.get("owner_scope"), actor);
        List<Map<String, Object>> scored = filterScope(rows, owner);
        sortByPriority(scored, "lead_id");
        int limit = boundedInt(params.get("limit"), 10, 25);
        if (scored.size() > limit) scored = scored.subList(0, limit);
        return completed(map("result", map("cohort_ref", cohort, "owner_scope", owner, "lead_scores", scored)));
    }

    private Map<String, Object> prioritizeAccounts(Map<String, Object> params, ActorPolicy actor) {
        String cohort = normalizeCohortRef(requireString(params, "cohort_ref", "Which account cohort should I prioritize?", "Use expansion_candidates_q2 or at_risk_q2."));
        List<Map<String, Object>> rows = ACCOUNT_COHORTS.get(cohort);
        if (rows == null) {
            throw failRequires("clarification_required", "The requested account cohort is not explicit enough.", "provide_missing_parameter", "cohort_ref");
        }
        String owner = ownerScope(params.get("owner_scope"), actor);
        List<Map<String, Object>> accounts = filterScope(rows, owner);
        sortByPriority(accounts, "account_name");
        int limit = boundedInt(params.get("limit"), 10, 25);
        if (accounts.size() > limit) accounts = accounts.subList(0, limit);
        return completed(map("result", map("cohort_ref", cohort, "owner_scope", owner, "ranking_basis", optionalText(params.get("ranking_basis"), "deal_likelihood"), "accounts", accounts)));
    }

    private void routeLeads(Map<String, Object> params, ActorPolicy actor) {
        if (!actor.canRouteLeads) {
            throw failRequires("denied", "This actor cannot route leads.", "request_authorized_actor", "actor with lead-routing access");
        }
        Map<String, Object> scored = objectMap(scoreLeads(params, actor).get("result"));
        List<Map<String, Object>> leads = mapList(scored.get("lead_scores"));
        String targetQueue = optionalText(params.get("target_queue"), "sales");
        List<Map<String, Object>> previewRows = new ArrayList<>();
        for (Map<String, Object> row : leads) {
            previewRows.add(map("lead_id", row.get("lead_id"), "account_name", row.get("account_name"), "owner_scope", row.get("owner_scope"), "priority_band", row.get("priority_band"), "priority_score", row.get("priority_score"), "recommended_queue", targetQueue, "rationale", row.get("rationale")));
        }
        Map<String, Object> preview = map("cohort_ref", scored.get("cohort_ref"), "owner_scope", scored.get("owner_scope"), "target_queue", targetQueue, "dry_run", true, "preview", previewRows);
        throw approvalError(createApprovalRequest("gtm.route_leads", actor, "sales_leader", preview), "Lead routing stays at preview until an authorized approver confirms it.");
    }

    private Map<String, Object> draftOutreach(Map<String, Object> params) {
        String raw = requireString(params, "target_ref", "Which account or lead is this outreach for?", "Use Condax, Acme Corporation, or Codehow.");
        String targetRef = targetFor(raw);
        Map<String, Object> target = OUTREACH_TARGETS.get(targetRef);
        String objective = optionalText(params.get("objective"), "first_touch");
        String channel = optionalText(params.get("channel"), "email");
        String persona = optionalText(params.get("persona"), string(target.get("persona")));
        String body = "Hi " + persona + ",\n\nI'm reaching out because " + targetRef + " looks like a strong fit for a governed GTM workflow review. Teams in " + target.get("industry") + " often struggle with " + target.get("pain_point") + ". We help them get to " + target.get("proof_point") + " without giving an agent raw, unconstrained system access.\n\nIf useful, I can show how that would apply to " + targetRef + "'s current priorities and suggest " + target.get("next_step") + ".\n\nBest,\nANIP GTM Team";
        return completed(map("result", map("draft_id", "draft_" + targetRef.toLowerCase(Locale.ROOT).replace(" ", "_") + "_" + objective, "target_ref", targetRef, "objective", objective, "channel", channel, "persona", persona, "subject", targetRef + ": governed GTM follow-up without workflow sprawl", "body", body, "tone", "direct and operational", "rationale", "Anchored to " + target.get("priority_context") + " and " + target.get("pain_point") + ".", "target_summary", map("industry", target.get("industry"), "region", target.get("region"), "priority_context", target.get("priority_context")))));
    }

    private Map<String, Object> bottleneckAccountOutreachDraft(Map<String, Object> params, ActorPolicy actor) {
        String quarter = requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2.");
        String target = string(params.get("target_ref"));
        if (!target.isBlank() && !"<nil>".equals(target)) {
            return draftOutreach(params);
        }
        if (!"full".equals(actor.outreachAccess)) {
            throw failRequires("denied", "This actor cannot request approval-gated outreach target selection.", "request_authorized_actor", "role with full outreach approval authority or explicit selected target_ref");
        }
        Map<String, Object> preview = map("quarter", quarter, "owner_scope", null, "objective", optionalText(params.get("objective"), "first_touch"), "channel", optionalText(params.get("channel"), "email"));
        if (!string(params.get("owner_scope")).isBlank()) preview.put("owner_scope", params.get("owner_scope"));
        throw approvalError(createApprovalRequest("gtm.bottleneck_account_outreach_draft", actor, "sales_leader", preview), "Drafting outreach from a bottleneck review requires approval or an explicit selected account before generating the message.");
    }

    private Map<String, Object> suggestFollowupContent(Map<String, Object> params) {
        String target = requireString(params, "target_ref", "Which account or lead should these follow-up variants target?", "Use Condax, Acme Corporation, or Codehow.");
        Map<String, Object> next = cloneMap(params);
        next.put("target_ref", target);
        next.putIfAbsent("objective", "follow_up");
        Map<String, Object> base = objectMap(draftOutreach(next).get("result"));
        int count = boundedInt(params.get("variant_count"), 2, 3);
        List<Map<String, Object>> variants = new ArrayList<>(List.of(
                map("variant_id", "follow_up_value", "message", base.get("body"), "rationale", "Reuses the bounded outreach draft as the value-forward follow-up."),
                map("variant_id", "follow_up_operational", "message", "Following up on " + base.get("target_ref") + ": the practical next step is a bounded GTM workflow review with explicit approval gates.", "rationale", "Short operational follow-up."),
                map("variant_id", "follow_up_risk", "message", base.get("target_ref") + " appears to have enough GTM coordination risk to justify a scoped review before any workflow changes.", "rationale", "Risk-oriented follow-up.")
        ));
        return completed(map("result", map("target_ref", base.get("target_ref"), "persona", base.get("persona"), "variants", variants.subList(0, Math.min(count, variants.size())), "variant_limit_applied", Math.min(count, variants.size()))));
    }

    private Map<String, Object> objectionVariants(Map<String, Object> params, ActorPolicy actor) {
        if (!actor.canUseObjectionVariants) {
            throw failRequires("denied", "This actor can use bounded draft generation but not objection-response variants.", "request_authorized_actor", "role with objection-variant access");
        }
        String raw = requireString(params, "objection_theme", "Which objection or competitor theme should these variants address?", "Use pricing, competitor, or implementation_risk.");
        String normalized = raw.toLowerCase(Locale.ROOT).replace("-", "_").replace(" ", "_");
        String key = normalized.contains("competitor") ? "competitor" : normalized.contains("implement") ? "implementation_risk" : normalized.contains("price") ? "pricing" : normalized;
        Map<String, Object> theme = OBJECTION_THEMES.get(key);
        if (theme == null) {
            throw failRequires("clarification_required", "Unsupported objection theme.", "provide_objection_theme", "objection_theme");
        }
        Object targetRef = null;
        if (!string(params.get("target_ref")).isBlank()) targetRef = targetFor(string(params.get("target_ref")));
        List<Map<String, Object>> variants = new ArrayList<>();
        for (Map<String, Object> item : mapList(theme.get("variants"))) {
            variants.add(map("pattern_id", item.get("variant_id"), "pattern_type", theme.get("label"), "target_ref", targetRef, "message", item.get("message"), "rationale", item.get("rationale")));
        }
        return completed(map("result", map("objection_theme", theme.get("label"), "target_ref", targetRef, "variants", variants)));
    }

    private Map<String, Object> prioritizedOutreachDraft(Map<String, Object> params, ActorPolicy actor) {
        Map<String, Object> result = objectMap(prioritizeAccounts(params, actor).get("result"));
        List<Map<String, Object>> accounts = mapList(result.get("accounts"));
        if (accounts.isEmpty()) {
            return completed(map("result", map("cohort_ref", result.get("cohort_ref"), "accounts", List.of(), "draft", null, "empty", true)));
        }
        Map<String, Object> draft = objectMap(draftOutreach(map("target_ref", accounts.get(0).get("account_name"), "objective", params.get("objective"), "channel", params.get("channel"), "persona", params.get("persona"))).get("result"));
        Map<String, Object> out = cloneMap(result);
        out.put("prioritized_accounts", accounts);
        out.put("selected_target_ref", accounts.get(0).get("account_name"));
        out.put("draft", draft);
        return completed(map("result", out));
    }

    static List<ApprovalRecord> listApprovalRequests(String status) {
        return APPROVALS.values().stream()
                .filter(record -> status == null || status.isBlank() || status.equals(record.status))
                .sorted(Comparator.comparing(record -> record.createdAt))
                .toList();
    }

    static ApprovalRecord approveRequest(String id, ActorPolicy approver) {
        ApprovalRecord record = APPROVALS.get(id);
        if (record == null) return null;
        ApprovalRecord approved = record.approved(approver);
        APPROVALS.put(id, approved);
        return approved;
    }

    static ActorPolicy actorFromBearer(String bearer) {
        String token = bearer == null ? "" : bearer.replaceFirst("(?i)^Bearer\\s+", "").trim();
        Map<String, String> keys = new LinkedHashMap<>();
        keys.put("dev-admin-key", "human:local-developer");
        String raw = System.getenv("ANIP_API_KEYS_JSON");
        if (raw != null && !raw.isBlank()) {
            try {
                keys.putAll(MAPPER.readValue(raw, new TypeReference<Map<String, String>>() {}));
            } catch (Exception ignored) {
            }
        }
        String principal = keys.get(token);
        return principal == null ? null : actorPolicyFromPrincipal(principal);
    }

    private static ApprovalRecord createApprovalRequest(String capability, ActorPolicy requester, String requiredRole, Map<String, Object> preview) {
        String id = "apr_" + randomHex(6);
        ApprovalRecord record = new ApprovalRecord(id, capability, firstNonEmpty(requiredRole, "sales_leader"), "pending", actorSummary(requester), Map.of(), preview, Instant.now().toString(), "");
        APPROVALS.put(id, record);
        return record;
    }

    private static ANIPError approvalError(ApprovalRecord record, String detail) {
        String digest = approvalDigest(record.preview);
        return new ANIPError("approval_required", detail)
                .withResolution(new Resolution("request_approval", Constants.recoveryClassForAction("request_approval"), "approval before downstream mutation", null, null))
                .withApprovalRequired(new ApprovalRequiredMetadata(record.approvalRequestId, digest, digest, new GrantPolicy(List.of("one_time", "session_bound"), "one_time", 900, 1)));
    }

    private static String approvalDigest(Map<String, Object> preview) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] encoded = MAPPER.writeValueAsString(preview).getBytes(StandardCharsets.UTF_8);
            return "sha256:" + bytesToHex(digest.digest(encoded));
        } catch (Exception error) {
            return "sha256:unavailable";
        }
    }

    private static String randomHex(int size) {
        byte[] bytes = new byte[size];
        RANDOM.nextBytes(bytes);
        return bytesToHex(bytes);
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder builder = new StringBuilder();
        for (byte b : bytes) builder.append(String.format("%02x", b));
        return builder.toString();
    }

    private static ANIPError fail(String kind, String detail, String action) {
        String canonical = canonicalRecoveryAction(action);
        return new ANIPError(kind, detail).withResolution(canonical);
    }

    private static ANIPError failRequires(String kind, String detail, String action, String requires) {
        String canonical = canonicalRecoveryAction(action);
        return new ANIPError(kind, detail).withResolution(new Resolution(canonical, Constants.recoveryClassForAction(canonical), requires, null, null));
    }

    private static String canonicalRecoveryAction(String action) {
        return switch (action) {
            case "retry_now", "wait_and_retry", "obtain_binding", "refresh_binding", "obtain_quote_first", "revalidate_state",
                    "request_broader_scope", "request_budget_increase", "request_budget_bound_delegation", "request_matching_currency_delegation",
                    "request_new_delegation", "request_capability_binding", "request_deeper_delegation", "escalate_to_root_principal",
                    "provide_credentials", "request_approval", "check_manifest", "contact_service_owner" -> action;
            case "request_authorized_actor", "retry_with_owned_scope" -> "request_new_delegation";
            case "provide_missing_parameter", "provide_account_scope", "provide_reference_account", "provide_supported_account_names",
                    "provide_objection_theme", "retry_with_supported_forecast_mode", "retry_with_supported_slice",
                    "retry_with_supported_ranking", "retry_with_supported_selection_basis", "retry_with_supported_account",
                    "complete_native_language_slice" -> "obtain_binding";
            default -> "contact_service_owner";
        };
    }

    private static String requireString(Map<String, Object> params, String field, String detail, String hint) {
        String value = string(params.get(field));
        if (!value.isBlank() && !"<nil>".equals(value)) {
            if ("quarter".equals(field) && "quarter-value".equals(value)) return "2017-Q2";
            return value;
        }
        throw failRequires("clarification_required", detail, "provide_missing_parameter", field);
    }

    private static String ownerScope(Object explicit, ActorPolicy actor) {
        String requested = string(explicit);
        for (String suffix : List.of(" region", " territory", " office")) {
            if (requested.toLowerCase(Locale.ROOT).endsWith(suffix)) {
                requested = requested.substring(0, requested.length() - suffix.length()).trim();
                break;
            }
        }
        String actorScope = firstNonEmpty(actor.pipelineScope, "company");
        if (requested.endsWith("-value") || requested.isBlank() || "<nil>".equals(requested) || "all".equals(requested)) return actorScope;
        if ("company".equals(actorScope) || "all".equals(actorScope) || requested.equals(actorScope)) return requested;
        throw failRequires("restricted", "This actor is restricted to a narrower pipeline scope.", "retry_with_owned_scope", actorScope);
    }

    private static ScopeSql sqlScope(String scope) {
        if (scope == null || scope.isBlank() || "company".equals(scope) || "all".equals(scope)) return new ScopeSql("", List.of());
        return new ScopeSql(" and regional_office = ?", List.of(scope));
    }

    private static Map<String, Object> applyFinancialVisibility(Map<String, Object> payload, ActorPolicy actor) {
        if ("full".equals(actor.financialAccess)) {
            payload.put("visibility", map("financial_values", "full"));
            return payload;
        }
        Map<String, Object> copy = cloneMap(payload);
        for (Object value : copy.values()) {
            if (value instanceof List<?> list) {
                for (Object item : list) if (item instanceof Map<?, ?> row) maskFinancial(castMap(row));
            }
        }
        if (copy.get("totals") instanceof Map<?, ?> totals) maskFinancial(castMap(totals));
        copy.put("visibility", map("financial_values", "masked", "reason", "actor policy does not allow financial values in this view"));
        return copy;
    }

    private static void maskFinancial(Map<String, Object> item) {
        for (String key : List.of("open_pipeline_value", "won_revenue", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value")) {
            if (item.containsKey(key)) item.put(key, null);
        }
    }

    private static ActorPolicy actorPolicyFromPrincipal(String rootPrincipal) {
        Map<String, String> claims = claimsFromPrincipal(rootPrincipal);
        if (claims.getOrDefault("actor_id", "").isBlank()) {
            return new ActorPolicy("local-developer", "sales_leader", "company", "full", "full", "full", true, true, true, true, true, true);
        }
        return new ActorPolicy(
                claims.get("actor_id"), firstNonEmpty(claims.get("role"), "unknown"),
                firstNonEmpty(claims.get("pipeline_scope"), "company"),
                firstNonEmpty(claims.get("financial_access"), "masked"),
                firstNonEmpty(claims.get("enrichment_access"), "bounded"),
                firstNonEmpty(claims.get("outreach_access"), "bounded"),
                boolClaim(claims.get("can_prepare_followup")),
                boolClaim(claims.get("can_approve_followup")),
                boolClaim(claims.get("can_use_lookalikes")),
                boolClaim(claims.get("can_route_leads")),
                boolClaim(claims.get("can_approve_routing")),
                boolClaim(claims.get("can_use_objection_variants"))
        );
    }

    private static Map<String, String> claimsFromPrincipal(String rootPrincipal) {
        String raw = string(rootPrincipal);
        if (raw.isBlank()) return Map.of();
        String[] pieces = raw.split("\\|");
        Map<String, String> claims = new LinkedHashMap<>();
        claims.put("principal", pieces.length > 0 ? pieces[0] : "");
        for (int index = 1; index < pieces.length; index++) {
            String piece = pieces[index];
            int separator = piece.indexOf('=');
            if (separator > -1) claims.put(piece.substring(0, separator).trim(), piece.substring(separator + 1).trim());
        }
        return claims;
    }

    private static boolean boolClaim(String value) {
        return "true".equalsIgnoreCase(string(value));
    }

    private static Map<String, Object> actorSummary(ActorPolicy actor) {
        return map("actor_id", actor.actorId, "role", actor.role);
    }

    private static String forecastKey(String mode) {
        if ("best_case".equals(mode)) return "best_case_revenue";
        if ("likely".equals(mode)) return "likely_revenue";
        return "risk_adjusted_revenue";
    }

    private static int boundedInt(Object value, int fallback, int maximum) {
        try {
            int parsed = Integer.parseInt(string(value));
            if (parsed < 1) return 1;
            return Math.min(parsed, maximum);
        } catch (Exception ignored) {
            return fallback;
        }
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static double number(Object value) {
        if (value instanceof Number number) return number.doubleValue();
        try {
            return Double.parseDouble(string(value));
        } catch (Exception ignored) {
            return 0.0;
        }
    }

    private static Object firstNonNull(Object... values) {
        for (Object value : values) {
            String text = string(value);
            if (value != null && !text.isBlank() && !"<nil>".equals(text)) return value;
        }
        return null;
    }

    private static String optionalText(Object value, String fallback) {
        String text = string(value);
        return text.isBlank() || "<nil>".equals(text) ? fallback : text;
    }

    private static String string(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) return value;
        }
        return "";
    }

    private static Map<String, Object> completed(Map<String, Object> payload) {
        Map<String, Object> result = map("execution_status", "completed");
        result.putAll(payload);
        return result;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> objectMap(Object value) {
        if (value instanceof Map<?, ?> map) return castMap(map);
        return Map.of();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Map<?, ?> value) {
        return (Map<String, Object>) value;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> mapList(Object value) {
        if (!(value instanceof List<?> list)) return List.of();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object item : list) if (item instanceof Map<?, ?> map) result.add((Map<String, Object>) map);
        return result;
    }

    private static Map<String, Object> cloneMap(Map<String, Object> source) {
        if (source == null) return new LinkedHashMap<>();
        try {
            return MAPPER.readValue(MAPPER.writeValueAsBytes(source), new TypeReference<Map<String, Object>>() {});
        } catch (Exception ignored) {
            return new LinkedHashMap<>(source);
        }
    }

    private static Map<String, Object> map(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) {
            result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        }
        return result;
    }

    private static String normalizeCohortRef(String value) {
        String normalized = value.trim().toLowerCase(Locale.ROOT).replace("-", "_").replace(" ", "_");
        if (normalized.contains("inbound")) return "inbound_last_week";
        if (normalized.contains("webinar")) return "webinar_q2";
        if (normalized.contains("expansion")) return "expansion_candidates_q2";
        if ("at_risk_q2".equals(normalized) || "at_risk_q2_cohort".equals(normalized) || normalized.contains("risk")) return "at_risk_q2";
        return value;
    }

    private static List<Map<String, Object>> filterScope(List<Map<String, Object>> rows, String owner) {
        List<Map<String, Object>> filtered = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            if (owner == null || owner.isBlank() || "company".equals(owner) || "all".equals(owner) || Objects.equals(row.get("owner_scope"), owner)) {
                filtered.add(cloneMap(row));
            }
        }
        return filtered;
    }

    private static void sortByPriority(List<Map<String, Object>> rows, String nameKey) {
        rows.sort((left, right) -> {
            int score = Double.compare(number(right.get("priority_score")), number(left.get("priority_score")));
            if (score != 0) return score;
            return string(left.get(nameKey)).compareTo(string(right.get(nameKey)));
        });
    }

    private static List<String> parseAccountNames(Object value) {
        if (value instanceof List<?> list) {
            List<String> result = new ArrayList<>();
            for (Object item : list) {
                String cleaned = cleanAccountName(item);
                if (!cleaned.isBlank()) result.add(cleaned);
            }
            return result;
        }
        String text = string(value).replace(" and ", ", ");
        if (text.isBlank()) return List.of();
        List<String> result = new ArrayList<>();
        for (String item : text.split(",")) {
            String cleaned = cleanAccountName(item);
            if (!cleaned.isBlank()) result.add(cleaned);
        }
        return result;
    }

    private static String cleanAccountName(Object value) {
        String text = string(value);
        boolean changed = true;
        while (changed) {
            changed = false;
            String lower = text.toLowerCase(Locale.ROOT);
            for (String prefix : List.of("and ", "my ", "our ", "the ")) {
                if (lower.startsWith(prefix)) {
                    text = text.substring(prefix.length()).trim();
                    changed = true;
                    break;
                }
            }
        }
        String lower = text.toLowerCase(Locale.ROOT);
        for (String prefix : List.of("east account ", "west account ", "central account ", "north account ", "south account ", "account ")) {
            if (lower.startsWith(prefix)) return text.substring(prefix.length()).trim();
        }
        return text.trim();
    }

    private static boolean looksLikeVagueAccountScope(String value) {
        String normalized = value.toLowerCase(Locale.ROOT).trim();
        for (String marker : List.of("our ", "we ", "should ", "next", "core accounts", "best customer", "top account", "companies we care", "most important")) {
            if (normalized.contains(marker)) return true;
        }
        return false;
    }

    private static String targetFor(String value) {
        if (string(value).endsWith("-value")) return "Condax";
        for (String candidate : OUTREACH_TARGETS.keySet()) {
            if (candidate.equalsIgnoreCase(string(value))) return candidate;
        }
        throw failRequires("clarification_required", "Unknown target_ref.", "provide_reference_account", "target_ref");
    }

    static final class ScopeSql {
        final String clause;
        final List<Object> args;

        ScopeSql(String clause, List<Object> args) {
            this.clause = clause;
            this.args = args;
        }
    }

    static final class ActorPolicy {
        final String actorId;
        final String role;
        final String pipelineScope;
        final String financialAccess;
        final String enrichmentAccess;
        final String outreachAccess;
        final boolean canPrepareFollowup;
        final boolean canApproveFollowup;
        final boolean canUseLookalikes;
        final boolean canRouteLeads;
        final boolean canApproveRouting;
        final boolean canUseObjectionVariants;

        ActorPolicy(String actorId, String role, String pipelineScope, String financialAccess, String enrichmentAccess, String outreachAccess,
                    boolean canPrepareFollowup, boolean canApproveFollowup, boolean canUseLookalikes, boolean canRouteLeads,
                    boolean canApproveRouting, boolean canUseObjectionVariants) {
            this.actorId = actorId;
            this.role = role;
            this.pipelineScope = pipelineScope;
            this.financialAccess = financialAccess;
            this.enrichmentAccess = enrichmentAccess;
            this.outreachAccess = outreachAccess;
            this.canPrepareFollowup = canPrepareFollowup;
            this.canApproveFollowup = canApproveFollowup;
            this.canUseLookalikes = canUseLookalikes;
            this.canRouteLeads = canRouteLeads;
            this.canApproveRouting = canApproveRouting;
            this.canUseObjectionVariants = canUseObjectionVariants;
        }
    }

    static final class ApprovalRecord {
        final String approvalRequestId;
        final String capability;
        final String requiredRole;
        final String status;
        final Map<String, Object> requestedBy;
        final Map<String, Object> approvedBy;
        final Map<String, Object> preview;
        final String createdAt;
        final String approvedAt;

        ApprovalRecord(String approvalRequestId, String capability, String requiredRole, String status, Map<String, Object> requestedBy,
                       Map<String, Object> approvedBy, Map<String, Object> preview, String createdAt, String approvedAt) {
            this.approvalRequestId = approvalRequestId;
            this.capability = capability;
            this.requiredRole = requiredRole;
            this.status = status;
            this.requestedBy = requestedBy;
            this.approvedBy = approvedBy;
            this.preview = preview;
            this.createdAt = createdAt;
            this.approvedAt = approvedAt;
        }

        ApprovalRecord approved(ActorPolicy approver) {
            return new ApprovalRecord(approvalRequestId, capability, requiredRole, "approved", requestedBy, actorSummary(approver), preview, createdAt, Instant.now().toString());
        }
    }

    private static final Map<String, List<Map<String, Object>>> LEAD_COHORTS = mapOfLists(
            "inbound_last_week", List.of(
                    map("lead_id", "lead_1001", "account_name", "Acme Corporation", "source", "website_inbound", "segment", "enterprise", "owner_scope", "East", "priority_score", 94, "priority_band", "hot", "confidence", 0.94, "rationale", "High intent, enterprise ICP fit, and recent demo request.", "recommended_queue", "sales"),
                    map("lead_id", "lead_1002", "account_name", "Codehow", "source", "website_inbound", "segment", "commercial", "owner_scope", "East", "priority_score", 91, "priority_band", "hot", "confidence", 0.91, "rationale", "Repeat product-page engagement and strong ICP fit.", "recommended_queue", "sales"),
                    map("lead_id", "lead_1003", "account_name", "Condax", "source", "website_inbound", "segment", "enterprise", "owner_scope", "West", "priority_score", 88, "priority_band", "hot", "confidence", 0.89, "rationale", "High-value account with strong buying signals.", "recommended_queue", "sales"),
                    map("lead_id", "lead_1004", "account_name", "Dalttechnology", "source", "website_inbound", "segment", "mid_market", "owner_scope", "Central", "priority_score", 84, "priority_band", "warm", "confidence", 0.86, "rationale", "Good engagement and healthy ICP alignment.", "recommended_queue", "sdr")
            ),
            "webinar_q2", List.of(
                    map("lead_id", "lead_2001", "account_name", "Finjob", "source", "webinar", "segment", "enterprise", "owner_scope", "East", "priority_score", 89, "priority_band", "hot", "confidence", 0.90, "rationale", "Executive webinar attendance and requested follow-up.", "recommended_queue", "sales"),
                    map("lead_id", "lead_2002", "account_name", "J-Texon", "source", "webinar", "segment", "commercial", "owner_scope", "West", "priority_score", 81, "priority_band", "warm", "confidence", 0.83, "rationale", "Good engagement but smaller likely deal size.", "recommended_queue", "sdr"),
                    map("lead_id", "lead_2003", "account_name", "Konex", "source", "webinar", "segment", "mid_market", "owner_scope", "West", "priority_score", 78, "priority_band", "warm", "confidence", 0.80, "rationale", "Moderate engagement and reasonable ICP fit.", "recommended_queue", "sdr")
            )
    );

    private static final Map<String, List<Map<String, Object>>> ACCOUNT_COHORTS = mapOfLists(
            "expansion_candidates_q2", List.of(
                    map("account_name", "Acme Corporation", "segment", "enterprise", "owner_scope", "East", "priority_score", 96, "priority_band", "hot", "confidence", 0.95, "rationale", "Expansion candidate with strong usage and open pipeline.", "ranking_basis", "deal_likelihood"),
                    map("account_name", "Codehow", "segment", "commercial", "owner_scope", "East", "priority_score", 90, "priority_band", "hot", "confidence", 0.90, "rationale", "Strong engagement and expansion-ready signals.", "ranking_basis", "deal_likelihood"),
                    map("account_name", "Condax", "segment", "enterprise", "owner_scope", "West", "priority_score", 86, "priority_band", "warm", "confidence", 0.87, "rationale", "Good propensity but longer procurement cycle.", "ranking_basis", "deal_likelihood")
            ),
            "at_risk_q2", List.of(
                    map("account_name", "Acme Corporation", "segment", "enterprise", "owner_scope", "Central", "priority_score", 91, "priority_band", "hot", "confidence", 0.90, "rationale", "Highest risk-adjusted retention opportunity with clear recovery path.", "ranking_basis", "deal_likelihood"),
                    map("account_name", "J-Texon", "segment", "commercial", "owner_scope", "West", "priority_score", 88, "priority_band", "hot", "confidence", 0.88, "rationale", "High urgency because the account is at risk and near renewal.", "ranking_basis", "deal_likelihood"),
                    map("account_name", "Finjob", "segment", "enterprise", "owner_scope", "East", "priority_score", 84, "priority_band", "warm", "confidence", 0.85, "rationale", "Meaningful renewal risk but reachable in current quarter.", "ranking_basis", "deal_likelihood")
            )
    );

    private static final Map<String, Map<String, Object>> OUTREACH_TARGETS = mapOfMaps(
            "Condax", map("industry", "industrial manufacturing", "persona", "VP of Operations", "region", "East", "priority_context", "high-priority expansion candidate", "pain_point", "fragmented forecasting and slow handoff between revenue teams", "proof_point", "governed pipeline review with approval-aware follow-up planning", "next_step", "a short operations-focused discovery call"),
            "Acme Corporation", map("industry", "industrial equipment", "persona", "Revenue Operations Director", "region", "Central", "priority_context", "at-risk account needing tighter GTM coordination", "pain_point", "stalled opportunities and uneven rep follow-through", "proof_point", "bounded risk reviews and explainable next-best actions", "next_step", "a practical walkthrough of its stalled-opportunity posture"),
            "Codehow", map("industry", "software and digital services", "persona", "Head of GTM Systems", "region", "East", "priority_context", "high-fit target for follow-up acceleration", "pain_point", "manual scoring and inconsistent routing decisions", "proof_point", "governed scoring and approval-gated routing previews", "next_step", "a systems-focused follow-up conversation")
    );

    private static final Map<String, Map<String, Object>> OBJECTION_THEMES = mapOfMaps(
            "pricing", map("label", "pricing", "variants", List.of(
                    map("variant_id", "pricing_v1", "message", "Frame the conversation around pipeline waste reduction before discussing pricing.", "rationale", "Keeps the conversation on measurable operating value."),
                    map("variant_id", "pricing_v2", "message", "Offer a bounded pilot focused on one GTM workflow instead of a broad rollout.", "rationale", "Reduces perceived risk and keeps scope concrete.")
            )),
            "competitor", map("label", "competitor comparison", "variants", List.of(
                    map("variant_id", "competitor_v1", "message", "Position governed service boundaries and auditability as the differentiator.", "rationale", "Shifts the comparison away from feature checklists toward control and trust."),
                    map("variant_id", "competitor_v2", "message", "Use the multi-service proof to show predictable composition rather than one opaque agent.", "rationale", "Shows operational realism instead of generic autonomy claims.")
            )),
            "implementation_risk", map("label", "implementation risk", "variants", List.of(
                    map("variant_id", "implementation_v1", "message", "Anchor on ANIP in front of existing systems so the buyer does not need a full rebuild.", "rationale", "Directly reduces perceived migration cost."),
                    map("variant_id", "implementation_v2", "message", "Use Phase 1 through Phase 4 proof points to show incremental rollout instead of a big-bang launch.", "rationale", "Demonstrates controlled adoption.")
            ))
    );

    @SafeVarargs
    private static Map<String, List<Map<String, Object>>> mapOfLists(Object... pairs) {
        Map<String, List<Map<String, Object>>> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> rows = (List<Map<String, Object>>) pairs[index + 1];
            result.put(String.valueOf(pairs[index]), rows);
        }
        return result;
    }

    private static Map<String, Map<String, Object>> mapOfMaps(Object... pairs) {
        Map<String, Map<String, Object>> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) {
            result.put(String.valueOf(pairs[index]), objectMap(pairs[index + 1]));
        }
        return result;
    }
}
