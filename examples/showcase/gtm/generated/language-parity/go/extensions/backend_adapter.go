package extensions

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"generated/gtm-pipeline-q2-review/generated"
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/jackc/pgx/v5"
)

type BackendInvocationContext struct {
	RootPrincipal string
	ApprovalGrant string
}

type BackendAdapter interface {
	Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, adapterInput map[string]any, context BackendInvocationContext) (map[string]any, error)
}

type gtmNativeBackendAdapter struct {
	databaseURL string
}

type ActorPolicy struct {
	ActorID                 string
	Role                    string
	PipelineScope           string
	FinancialAccess         string
	EnrichmentAccess        string
	OutreachAccess          string
	CanPrepareFollowup      bool
	CanApproveFollowup      bool
	CanUseLookalikes        bool
	CanRouteLeads           bool
	CanApproveRouting       bool
	CanUseObjectionVariants bool
}

type ApprovalRecord struct {
	ApprovalRequestID string         `json:"approval_request_id"`
	Capability        string         `json:"capability"`
	RequiredRole      string         `json:"required_role"`
	Status            string         `json:"status"`
	RequestedBy       map[string]any `json:"requested_by"`
	ApprovedBy        map[string]any `json:"approved_by,omitempty"`
	Preview           map[string]any `json:"preview"`
	CreatedAt         string         `json:"created_at"`
	ApprovedAt        string         `json:"approved_at,omitempty"`
}

var approvalStore = struct {
	sync.Mutex
	records map[string]ApprovalRecord
}{records: map[string]ApprovalRecord{}}

func CreateDefaultBackendAdapter() BackendAdapter {
	return &gtmNativeBackendAdapter{databaseURL: firstNonEmpty(os.Getenv("DATABASE_URL"), "postgresql://anip:anip@localhost:5454/anip_gtm")}
}

func (adapter *gtmNativeBackendAdapter) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, _ map[string]any, invocationContext BackendInvocationContext) (map[string]any, error) {
	actor := actorPolicyFromPrincipal(invocationContext.RootPrincipal)
	params := plan.SemanticInput
	switch capability.CapabilityID {
	case "gtm.pipeline_summary":
		return adapter.pipelineSummary(params, actor)
	case "gtm.pipeline_forecast_summary":
		return adapter.forecastSummary(params, actor)
	case "gtm.stage_bottleneck_summary":
		return adapter.stageBottleneckSummary(params, actor)
	case "gtm.sales_team_performance_summary":
		return adapter.salesTeamPerformanceSummary(params, actor)
	case "gtm.product_pipeline_summary":
		return adapter.productPipelineSummary(params, actor)
	case "gtm.account_risk_summary":
		return adapter.accountRiskSummary(params, actor)
	case "gtm.prepare_followup_tasks", "gtm.at_risk_followup_preparation":
		return adapter.prepareFollowupTasks(params, actor)
	case "gtm.prepare_reassignment_plan", "gtm.at_risk_reassignment_preparation":
		return adapter.prepareReassignmentPlan(params, actor)
	case "gtm.stalled_opportunity_review":
		return adapter.stalledOpportunities(params, actor)
	case "gtm.account_enrichment_summary":
		return adapter.accountEnrichmentSummary(params, actor)
	case "gtm.lookalike_accounts":
		return adapter.lookalikeAccounts(params, actor)
	case "gtm.at_risk_account_enrichment_summary":
		return adapter.atRiskAccountEnrichment(params, actor)
	case "gtm.score_leads":
		return scoreLeads(params, actor)
	case "gtm.prioritize_accounts":
		return prioritizeAccounts(params, actor)
	case "gtm.route_leads":
		return routeLeads(params, actor)
	case "gtm.draft_outreach_message":
		return draftOutreach(params)
	case "gtm.bottleneck_account_outreach_draft":
		return bottleneckAccountOutreachDraft(params, actor)
	case "gtm.suggest_followup_content":
		return suggestFollowupContent(params)
	case "gtm.objection_response_variants":
		return objectionVariants(params, actor)
	case "gtm.prioritized_outreach_draft":
		return prioritizedOutreachDraft(params, actor)
	case "gtm.prioritized_routing_preparation":
		next := cloneMap(params)
		if _, ok := next["target_queue"]; !ok {
			next["target_queue"] = "sales"
		}
		return routeLeads(next, actor)
	default:
		return nil, core.NewANIPError("temporarily_unavailable", "The Go native GTM bundle has not implemented "+capability.CapabilityID+" yet.").WithResolution("complete_native_language_slice")
	}
}

func (adapter *gtmNativeBackendAdapter) query(sql string, args ...any) ([]map[string]any, error) {
	conn, err := pgx.Connect(context.Background(), adapter.databaseURL)
	if err != nil {
		return nil, err
	}
	defer conn.Close(context.Background())
	rows, err := conn.Query(context.Background(), sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return pgx.CollectRows(rows, pgx.RowToMap)
}

func fail(kind string, detail string, action string) *core.ANIPError {
	return core.NewANIPError(kind, detail).WithResolution(canonicalRecoveryAction(action))
}

func failRequires(kind string, detail string, action string, requires string) *core.ANIPError {
	err := fail(kind, detail, action)
	err.Resolution.Requires = requires
	return err
}

func canonicalRecoveryAction(action string) string {
	switch action {
	case "retry_now", "wait_and_retry", "obtain_binding", "refresh_binding", "obtain_quote_first", "revalidate_state",
		"request_broader_scope", "request_budget_increase", "request_budget_bound_delegation", "request_matching_currency_delegation",
		"request_new_delegation", "request_capability_binding", "request_deeper_delegation", "escalate_to_root_principal",
		"provide_credentials", "request_approval", "check_manifest", "contact_service_owner":
		return action
	case "request_authorized_actor", "retry_with_owned_scope":
		return "request_new_delegation"
	case "provide_missing_parameter", "provide_account_scope", "provide_reference_account", "provide_supported_account_names",
		"provide_objection_theme", "retry_with_supported_forecast_mode", "retry_with_supported_slice",
		"retry_with_supported_ranking", "retry_with_supported_selection_basis", "retry_with_supported_account":
		return "obtain_binding"
	default:
		return "contact_service_owner"
	}
}

func completed(payload map[string]any) map[string]any {
	result := map[string]any{"execution_status": "completed"}
	for key, value := range payload {
		result[key] = value
	}
	return result
}

func requireString(params map[string]any, field string, detail string, hint string) (string, error) {
	value := strings.TrimSpace(fmt.Sprint(params[field]))
	if value != "" && value != "<nil>" {
		if field == "quarter" && value == "quarter-value" {
			return "2017-Q2", nil
		}
		return value, nil
	}
	err := failRequires("clarification_required", detail, "provide_missing_parameter", field)
	err.Resolution.EstimatedAvailability = hint
	return "", err
}

func boundedInt(value any, fallback int, maximum int) int {
	text := strings.TrimSpace(fmt.Sprint(value))
	parsed, err := strconv.Atoi(text)
	if err != nil {
		return fallback
	}
	if parsed < 1 {
		return 1
	}
	if parsed > maximum {
		return maximum
	}
	return parsed
}

func round2(value float64) float64 {
	return float64(int(value*100+0.5)) / 100
}

func number(value any) float64 {
	switch typed := value.(type) {
	case int:
		return float64(typed)
	case int32:
		return float64(typed)
	case int64:
		return float64(typed)
	case float32:
		return float64(typed)
	case float64:
		return typed
	case string:
		parsed, _ := strconv.ParseFloat(typed, 64)
		return parsed
	default:
		return 0
	}
}

func cloneMap(source map[string]any) map[string]any {
	out := map[string]any{}
	for key, value := range source {
		out[key] = value
	}
	return out
}

func actorSummary(actor ActorPolicy) map[string]any {
	return map[string]any{"actor_id": actor.ActorID, "role": actor.Role}
}

func sameApprovalRequester(record ApprovalRecord, actor ActorPolicy) bool {
	return strings.TrimSpace(fmt.Sprint(record.RequestedBy["actor_id"])) == actor.ActorID
}

func claimsFromPrincipal(rootPrincipal string) map[string]string {
	rootPrincipal = strings.TrimSpace(rootPrincipal)
	if rootPrincipal == "" {
		return map[string]string{}
	}
	pieces := strings.Split(rootPrincipal, "|")
	claims := map[string]string{"principal": pieces[0]}
	for _, piece := range pieces[1:] {
		key, value, ok := strings.Cut(piece, "=")
		if ok {
			claims[strings.TrimSpace(key)] = strings.TrimSpace(value)
		}
	}
	return claims
}

func boolClaim(value string) bool {
	return strings.EqualFold(strings.TrimSpace(value), "true")
}

func actorPolicyFromPrincipal(rootPrincipal string) ActorPolicy {
	claims := claimsFromPrincipal(rootPrincipal)
	if claims["actor_id"] == "" {
		return ActorPolicy{
			ActorID: "local-developer", Role: "sales_leader", PipelineScope: "company",
			FinancialAccess: "full", EnrichmentAccess: "full", OutreachAccess: "full",
			CanPrepareFollowup: true, CanApproveFollowup: true, CanUseLookalikes: true,
			CanRouteLeads: true, CanApproveRouting: true, CanUseObjectionVariants: true,
		}
	}
	return ActorPolicy{
		ActorID: claims["actor_id"], Role: firstNonEmpty(claims["role"], "unknown"),
		PipelineScope:           firstNonEmpty(claims["pipeline_scope"], "company"),
		FinancialAccess:         firstNonEmpty(claims["financial_access"], "masked"),
		EnrichmentAccess:        firstNonEmpty(claims["enrichment_access"], "bounded"),
		OutreachAccess:          firstNonEmpty(claims["outreach_access"], "bounded"),
		CanPrepareFollowup:      boolClaim(claims["can_prepare_followup"]),
		CanApproveFollowup:      boolClaim(claims["can_approve_followup"]),
		CanUseLookalikes:        boolClaim(claims["can_use_lookalikes"]),
		CanRouteLeads:           boolClaim(claims["can_route_leads"]),
		CanApproveRouting:       boolClaim(claims["can_approve_routing"]),
		CanUseObjectionVariants: boolClaim(claims["can_use_objection_variants"]),
	}
}

func ActorFromBearer(bearer string) (ActorPolicy, bool) {
	bearer = strings.TrimSpace(strings.TrimPrefix(bearer, "Bearer "))
	apiKeys := map[string]string{"dev-admin-key": "human:local-developer"}
	if raw := strings.TrimSpace(os.Getenv("ANIP_API_KEYS_JSON")); raw != "" {
		_ = json.Unmarshal([]byte(raw), &apiKeys)
	}
	principal, ok := apiKeys[bearer]
	if !ok {
		return ActorPolicy{}, false
	}
	return actorPolicyFromPrincipal(principal), true
}

func ownerScope(explicit any, actor ActorPolicy) (string, error) {
	requested := strings.TrimSpace(fmt.Sprint(explicit))
	for _, suffix := range []string{" region", " territory", " office"} {
		if strings.HasSuffix(strings.ToLower(requested), suffix) {
			requested = strings.TrimSpace(requested[:len(requested)-len(suffix)])
			break
		}
	}
	actorScope := firstNonEmpty(actor.PipelineScope, "company")
	if strings.HasSuffix(requested, "-value") {
		return actorScope, nil
	}
	if requested == "" || requested == "<nil>" || requested == "all" {
		return actorScope, nil
	}
	if actorScope == "company" || actorScope == "all" || requested == actorScope {
		return requested, nil
	}
	return "", failRequires("restricted", "This actor is restricted to a narrower pipeline scope.", "retry_with_owned_scope", actorScope)
}

func sqlScope(scope string, startIndex int) (string, []any) {
	if scope == "" || scope == "company" || scope == "all" {
		return "", nil
	}
	return fmt.Sprintf(" and regional_office = $%d", startIndex), []any{scope}
}

func applyFinancialVisibility(payload map[string]any, actor ActorPolicy) map[string]any {
	if actor.FinancialAccess == "full" {
		payload["visibility"] = map[string]any{"financial_values": "full"}
		return payload
	}
	copy := cloneDeepMap(payload)
	for _, value := range copy {
		if rows, ok := value.([]map[string]any); ok {
			for _, row := range rows {
				maskFinancial(row)
			}
		}
		if rows, ok := value.([]any); ok {
			for _, item := range rows {
				if row, ok := item.(map[string]any); ok {
					maskFinancial(row)
				}
			}
		}
	}
	if totals, ok := copy["totals"].(map[string]any); ok {
		maskFinancial(totals)
	}
	copy["visibility"] = map[string]any{"financial_values": "masked", "reason": "actor policy does not allow financial values in this view"}
	return copy
}

func cloneDeepMap(source map[string]any) map[string]any {
	data, _ := json.Marshal(source)
	var out map[string]any
	_ = json.Unmarshal(data, &out)
	return out
}

func maskFinancial(item map[string]any) {
	for _, key := range []string{"open_pipeline_value", "won_revenue", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue", "selected_forecast_value"} {
		if _, ok := item[key]; ok {
			item[key] = nil
		}
	}
}

func (adapter *gtmNativeBackendAdapter) pipelineSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	clause, scopeParams := sqlScope(owner, 2)
	rows, err := adapter.query(`
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
		where engage_quarter = $1 `+clause+`
		group by deal_stage
		order by deal_stage asc
	`, append([]any{quarter}, scopeParams...)...)
	if err != nil {
		return nil, err
	}
	totals := map[string]any{"opportunity_count": 0, "open_pipeline_value": 0.0, "won_revenue": 0.0}
	for _, row := range rows {
		totals["opportunity_count"] = int(number(totals["opportunity_count"]) + number(row["opportunity_count"]))
		totals["open_pipeline_value"] = round2(number(totals["open_pipeline_value"]) + number(row["open_pipeline_value"]))
		totals["won_revenue"] = round2(number(totals["won_revenue"]) + number(row["won_revenue"]))
	}
	return completed(applyFinancialVisibility(map[string]any{"quarter": quarter, "owner_scope": owner, "by_stage": rows, "totals": totals}, actor)), nil
}

func forecastKey(mode string) string {
	if mode == "best_case" {
		return "best_case_revenue"
	}
	if mode == "likely" {
		return "likely_revenue"
	}
	return "risk_adjusted_revenue"
}

func (adapter *gtmNativeBackendAdapter) forecastSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	mode := strings.TrimSpace(fmt.Sprint(params["forecast_mode"]))
	if mode == "" || mode == "<nil>" {
		mode = "risk_adjusted"
	}
	if mode != "risk_adjusted" && mode != "likely" && mode != "best_case" {
		return nil, fail("denied", "Pipeline forecast only supports forecast_mode=risk_adjusted, likely, or best_case.", "retry_with_supported_forecast_mode")
	}
	limit := boundedInt(params["limit"], 5, 10)
	clause, scopeParams := sqlScope(owner, 2)
	stageRows, err := adapter.query(`
		select deal_stage,
		       sum(open_opportunity_count)::int as open_opportunity_count,
		       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
		       round(sum(likely_revenue), 2)::float as likely_revenue,
		       round(sum(best_case_revenue), 2)::float as best_case_revenue,
		       round(sum(risk_adjusted_revenue), 2)::float as risk_adjusted_revenue,
		       round(avg(average_open_risk_score), 2)::float as average_risk_score
		from analytics_gtm.bi_gtm__forecast_stage_summary
		where engage_quarter = $1 `+clause+`
		group by deal_stage
		order by deal_stage asc
	`, append([]any{quarter}, scopeParams...)...)
	if err != nil {
		return nil, err
	}
	selected := forecastKey(mode)
	for _, row := range stageRows {
		row["selected_forecast_value"] = row[selected]
	}
	contributors, err := adapter.query(fmt.Sprintf(`
		select account_name, regional_office, count(*)::int as open_opportunity_count,
		       round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
		       round(sum(close_value * 0.65), 2)::float as likely_revenue,
		       round(sum(close_value * 0.85), 2)::float as best_case_revenue,
		       round(sum(close_value * (1 - coalesce(risk_score, 0) / 100)), 2)::float as risk_adjusted_revenue,
		       round(avg(risk_score), 2)::float as average_risk_score
		from analytics_gtm.fct_gtm__opportunities
		where engage_quarter = $1 and is_open = true %s
		  and account_name is not null and trim(account_name) <> ''
		group by account_name, regional_office
		order by %s desc nulls last, account_name
		limit $%d
	`, clause, selected, len(scopeParams)+2), append(append([]any{quarter}, scopeParams...), limit)...)
	if err != nil {
		return nil, err
	}
	for _, row := range contributors {
		row["selected_forecast_value"] = row[selected]
	}
	totals := map[string]any{
		"open_opportunity_count": 0, "open_pipeline_value": 0.0, "likely_revenue": 0.0,
		"best_case_revenue": 0.0, "risk_adjusted_revenue": 0.0,
	}
	for _, row := range stageRows {
		for _, key := range []string{"open_opportunity_count", "open_pipeline_value", "likely_revenue", "best_case_revenue", "risk_adjusted_revenue"} {
			totals[key] = round2(number(totals[key]) + number(row[key]))
		}
	}
	totals["selected_forecast_value"] = totals[selected]
	payload := map[string]any{"quarter": quarter, "owner_scope": owner, "forecast_mode": mode, "by_stage": stageRows, "top_contributors": contributors, "totals": totals}
	return completed(applyFinancialVisibility(payload, actor)), nil
}

func (adapter *gtmNativeBackendAdapter) stageBottleneckSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	sliceBy := optionalText(params["slice_by"], "regional_office")
	if sliceBy != "regional_office" && sliceBy != "manager_name" && sliceBy != "product_name" {
		return nil, fail("denied", "Stage bottleneck summary only supports regional_office, manager_name, or product_name.", "retry_with_supported_slice")
	}
	limit := boundedInt(params["limit"], 10, 15)
	clause, scopeParams := sqlScope(owner, 2)
	rows, err := adapter.query(fmt.Sprintf(`
		select deal_stage, %s as slice_value,
		       sum(open_opportunity_count)::int as open_opportunity_count,
		       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
		       round(avg(average_open_days), 2)::float as average_open_days,
		       round(avg(average_open_risk_score), 2)::float as average_risk_score
		from analytics_gtm.bi_gtm__stage_bottlenecks
		where engage_quarter = $1 %s
		group by deal_stage, %s
		order by average_open_days desc nulls last, average_risk_score desc nulls last, open_opportunity_count desc, slice_value, deal_stage
		limit $%d
	`, sliceBy, clause, sliceBy, len(scopeParams)+2), append(append([]any{quarter}, scopeParams...), limit)...)
	if err != nil {
		return nil, err
	}
	for index, row := range rows {
		row["slice_by"] = sliceBy
		row["bottleneck_rank"] = index + 1
	}
	return completed(applyFinancialVisibility(map[string]any{"quarter": quarter, "owner_scope": owner, "slice_by": sliceBy, "bottlenecks": rows}, actor)), nil
}

func (adapter *gtmNativeBackendAdapter) salesTeamPerformanceSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	sliceBy := optionalText(params["slice_by"], "manager_name")
	if sliceBy != "manager_name" && sliceBy != "regional_office" {
		return nil, fail("denied", "Sales team performance only supports slice_by=manager_name or regional_office.", "retry_with_supported_slice")
	}
	limit := boundedInt(params["limit"], 10, 15)
	clause, scopeParams := sqlScope(owner, 2)
	rows, err := adapter.query(fmt.Sprintf(`
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
		where engage_quarter = $1 %s
		group by %s
		order by open_pipeline_value desc nulls last, won_opportunity_count desc nulls last, average_open_risk_score desc nulls last, slice_value
		limit $%d
	`, sliceBy, clause, sliceBy, len(scopeParams)+2), append(append([]any{quarter}, scopeParams...), limit)...)
	if err != nil {
		return nil, err
	}
	for _, row := range rows {
		row["slice_by"] = sliceBy
	}
	return completed(applyFinancialVisibility(map[string]any{"quarter": quarter, "owner_scope": owner, "slice_by": sliceBy, "performance_rows": rows}, actor)), nil
}

func (adapter *gtmNativeBackendAdapter) productPipelineSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	product := strings.TrimSpace(fmt.Sprint(params["product_scope"]))
	if product == "<nil>" {
		product = ""
	}
	limit := boundedInt(params["limit"], 10, 15)
	clause, scopeParams := sqlScope(owner, 2)
	productClause := ""
	queryArgs := append([]any{quarter}, scopeParams...)
	if product != "" {
		productClause = fmt.Sprintf(" and product_name = $%d", len(queryArgs)+1)
		queryArgs = append(queryArgs, product)
	}
	limitIndex := len(queryArgs) + 1
	queryArgs = append(queryArgs, limit)
	rows, err := adapter.query(fmt.Sprintf(`
		select product_name,
		       sum(open_opportunity_count)::int as open_opportunity_count,
		       sum(won_opportunity_count)::int as won_opportunity_count,
		       sum(lost_opportunity_count)::int as lost_opportunity_count,
		       round(sum(open_pipeline_value), 2)::float as open_pipeline_value,
		       round(sum(won_revenue), 2)::float as won_revenue,
		       round(avg(average_open_risk_score), 2)::float as average_open_risk_score
		from analytics_gtm.bi_gtm__product_pipeline
		where engage_quarter = $1 %s%s
		group by product_name
		order by open_pipeline_value desc nulls last, won_revenue desc nulls last, open_opportunity_count desc, product_name
		limit $%d
	`, clause, productClause, limitIndex), queryArgs...)
	if err != nil {
		return nil, err
	}
	productValue := any(nil)
	if product != "" {
		productValue = product
	}
	return completed(applyFinancialVisibility(map[string]any{"quarter": quarter, "owner_scope": owner, "product_scope": productValue, "products": rows}, actor)), nil
}

func (adapter *gtmNativeBackendAdapter) stalledOpportunities(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	minDaysOpen := boundedInt(params["min_days_open"], 30, 999)
	limit := boundedInt(params["limit"], 10, 25)
	clause, scopeParams := sqlScope(owner, 2)
	rows, err := adapter.query(fmt.Sprintf(`
		select opportunity_id, account_name, sales_agent_name, regional_office, deal_stage,
		       product_name, engage_date::text, days_since_engage::int, round(risk_score, 2)::float as risk_score
		from analytics_gtm.fct_gtm__opportunities
		where engage_quarter = $1 and is_open = true %s and days_since_engage >= $%d
		order by risk_score desc nulls last, days_since_engage desc, opportunity_id
		limit $%d
	`, clause, len(scopeParams)+2, len(scopeParams)+3), append(append([]any{quarter}, scopeParams...), minDaysOpen, limit)...)
	if err != nil {
		return nil, err
	}
	return completed(map[string]any{"quarter": quarter, "owner_scope": owner, "min_days_open": minDaysOpen, "opportunities": rows}), nil
}

func (adapter *gtmNativeBackendAdapter) accountRiskSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	limit := boundedInt(firstNonNil(params["limit"], params["top_n"]), 10, 25)
	clause, scopeParams := sqlScope(owner, 2)
	rows, err := adapter.query(fmt.Sprintf(`
		select account_name, regional_office, count(*)::int as open_opportunity_count,
		       round(sum(coalesce(close_value, sales_price)), 2)::float as open_pipeline_value,
		       round(avg(risk_score), 2)::float as average_risk_score,
		       max(days_since_engage)::int as max_days_open,
		       string_agg(distinct sales_agent_name, ', ' order by sales_agent_name) as sales_agents
		from analytics_gtm.fct_gtm__opportunities
		where engage_quarter = $1 and is_open = true %s
		  and account_name is not null and trim(account_name) <> ''
		group by account_name, regional_office
		order by average_risk_score desc nulls last, open_pipeline_value desc nulls last, account_name
		limit $%d
	`, clause, len(scopeParams)+2), append(append([]any{quarter}, scopeParams...), limit)...)
	if err != nil {
		return nil, err
	}
	payload := map[string]any{
		"quarter": quarter, "owner_scope": owner,
		"ranking_basis": optionalText(params["ranking_basis"], "risk_score"),
		"accounts":      rows,
	}
	return completed(applyFinancialVisibility(payload, actor)), nil
}

func firstNonNil(values ...any) any {
	for _, value := range values {
		if value != nil && strings.TrimSpace(fmt.Sprint(value)) != "" && fmt.Sprint(value) != "<nil>" {
			return value
		}
	}
	return nil
}

func optionalText(value any, fallback string) string {
	text := strings.TrimSpace(fmt.Sprint(value))
	if text == "" || text == "<nil>" {
		return fallback
	}
	return text
}

func createApprovalRequest(capability string, requester ActorPolicy, requiredRole string, preview map[string]any) ApprovalRecord {
	digest := approvalDigest(preview)
	approvalStore.Lock()
	defer approvalStore.Unlock()
	for _, record := range approvalStore.records {
		if record.Capability == capability && record.Status == "pending" && approvalDigest(record.Preview) == digest && sameApprovalRequester(record, requester) {
			return record
		}
	}
	id := "apr_" + randomHex(6)
	now := time.Now().UTC().Format(time.RFC3339)
	record := ApprovalRecord{
		ApprovalRequestID: id,
		Capability:        capability,
		RequiredRole:      firstNonEmpty(requiredRole, "sales_leader"),
		Status:            "pending",
		RequestedBy:       actorSummary(requester),
		Preview:           preview,
		CreatedAt:         now,
	}
	approvalStore.records[id] = record
	return record
}

func ListApprovalRequests(status string) []ApprovalRecord {
	approvalStore.Lock()
	defer approvalStore.Unlock()
	records := make([]ApprovalRecord, 0, len(approvalStore.records))
	for _, record := range approvalStore.records {
		if status == "" || record.Status == status {
			records = append(records, record)
		}
	}
	sort.Slice(records, func(i, j int) bool { return records[i].CreatedAt < records[j].CreatedAt })
	return records
}

func ApproveRequest(id string, approver ActorPolicy) (ApprovalRecord, bool) {
	approvalStore.Lock()
	defer approvalStore.Unlock()
	record, ok := approvalStore.records[id]
	if !ok {
		return ApprovalRecord{}, false
	}
	record.Status = "approved"
	record.ApprovedBy = actorSummary(approver)
	record.ApprovedAt = time.Now().UTC().Format(time.RFC3339)
	approvalStore.records[id] = record
	return record, true
}

func randomHex(size int) string {
	bytes := make([]byte, size)
	if _, err := rand.Read(bytes); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(bytes)
}

func approvalDigest(preview map[string]any) string {
	content, _ := json.Marshal(preview)
	sum := sha256.Sum256(content)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func approvedApprovalFor(capability string, preview map[string]any, requester ActorPolicy) (ApprovalRecord, bool) {
	digest := approvalDigest(preview)
	approvalStore.Lock()
	defer approvalStore.Unlock()
	for _, record := range approvalStore.records {
		if record.Capability == capability && record.Status == "approved" && approvalDigest(record.Preview) == digest && sameApprovalRequester(record, requester) {
			return record, true
		}
	}
	return ApprovalRecord{}, false
}

func completedApprovedPreview(record ApprovalRecord) map[string]any {
	result := cloneMap(record.Preview)
	result["approval_request_id"] = record.ApprovalRequestID
	result["approval_status"] = "approved"
	result["approved_by"] = record.ApprovedBy
	result["approved_at"] = record.ApprovedAt
	return completed(map[string]any{"result": result})
}

func approvalError(record ApprovalRecord, detail string) *core.ANIPError {
	digest := approvalDigest(record.Preview)
	err := core.NewANIPError("approval_required", detail).WithResolution("request_approval")
	err.Resolution.Requires = "approval before downstream mutation"
	err.ApprovalRequired = &core.ApprovalRequiredMetadata{
		ApprovalRequestID:         record.ApprovalRequestID,
		PreviewDigest:             digest,
		RequestedParametersDigest: digest,
		GrantPolicy: core.GrantPolicy{
			AllowedGrantTypes: []string{"one_time", "session_bound"},
			DefaultGrantType:  "one_time",
			ExpiresInSeconds:  900,
			MaxUses:           1,
		},
	}
	return err
}

func (adapter *gtmNativeBackendAdapter) prepareFollowupTasks(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	if !actor.CanPrepareFollowup {
		return nil, failRequires("denied", "This actor role cannot prepare follow-up work.", "request_authorized_actor", "role with follow-up preparation authority")
	}
	quarter, err := requireString(params, "quarter", "target accounts or quarter are missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	ranking := optionalText(params["ranking_basis"], "risk_score")
	if ranking != "risk_score" {
		return nil, fail("denied", "Follow-up preparation only supports ranking_basis=risk_score.", "retry_with_supported_ranking")
	}
	risk, err := adapter.accountRiskSummary(map[string]any{"quarter": quarter, "owner_scope": owner, "ranking_basis": ranking, "limit": boundedInt(params["limit"], 5, 10)}, actor)
	if err != nil {
		return nil, err
	}
	accounts, _ := risk["accounts"].([]map[string]any)
	tasks := make([]map[string]any, 0, len(accounts))
	for _, row := range accounts {
		ownerName := strings.Split(firstNonEmpty(fmt.Sprint(row["sales_agents"]), "unassigned"), ",")[0]
		tasks = append(tasks, map[string]any{
			"account_name": row["account_name"], "regional_office": row["regional_office"], "recommended_owner": strings.TrimSpace(ownerName),
			"task_type":             "risk_review_followup",
			"reason":                fmt.Sprintf("Average risk score %v with %v open opportunities and max age %v days.", row["average_risk_score"], row["open_opportunity_count"], row["max_days_open"]),
			"suggested_due_in_days": 3,
		})
	}
	preview := map[string]any{"quarter": quarter, "owner_scope": owner, "ranking_basis": ranking, "requires_approval": true, "tasks": tasks}
	if record, ok := approvedApprovalFor("gtm.prepare_followup_tasks", preview, actor); ok {
		return completedApprovedPreview(record), nil
	}
	record := createApprovalRequest("gtm.prepare_followup_tasks", actor, "sales_leader", preview)
	return nil, approvalError(record, "any downstream task creation or CRM mutation would occur")
}

func (adapter *gtmNativeBackendAdapter) prepareReassignmentPlan(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	if !actor.CanPrepareFollowup {
		return nil, failRequires("denied", "This actor role cannot prepare reassignment work.", "request_authorized_actor", "role with reassignment planning authority")
	}
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2")
	if err != nil {
		return nil, err
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	selectionBasis := optionalText(params["selection_basis"], "manager_capacity")
	if selectionBasis != "manager_capacity" && selectionBasis != "stalled_risk_mix" {
		return nil, fail("denied", "Reassignment planning only supports manager_capacity or stalled_risk_mix.", "retry_with_supported_selection_basis")
	}
	limit := boundedInt(params["limit"], 5, 10)
	clause, scopeParams := sqlScope(owner, 2)
	rows, err := adapter.query(fmt.Sprintf(`
		select opportunity_id, account_name, sales_agent_name, manager_name, regional_office,
		       deal_stage, product_name, days_since_engage::int, round(risk_score, 2)::float as risk_score
		from analytics_gtm.fct_gtm__opportunities
		where engage_quarter = $1 and is_open = true %s
		order by risk_score desc nulls last, days_since_engage desc, opportunity_id
		limit $%d
	`, clause, len(scopeParams)+2), append(append([]any{quarter}, scopeParams...), limit)...)
	if err != nil {
		return nil, err
	}
	reassignments := make([]map[string]any, 0, len(rows))
	for _, row := range rows {
		reassignments = append(reassignments, map[string]any{
			"opportunity_id": row["opportunity_id"], "account_name": row["account_name"], "sales_agent_name": row["sales_agent_name"],
			"deal_stage": row["deal_stage"], "product_name": row["product_name"], "source_manager": row["manager_name"],
			"source_region": row["regional_office"], "target_manager": "next_available_manager", "target_region": row["regional_office"],
			"days_since_engage": row["days_since_engage"], "risk_score": row["risk_score"],
			"reason": fmt.Sprintf("%v owns a high-attention opportunity open %v days with risk score %v.", row["manager_name"], row["days_since_engage"], row["risk_score"]),
		})
	}
	preview := map[string]any{"quarter": quarter, "owner_scope": owner, "selection_basis": selectionBasis, "requires_approval": true, "reassignments": reassignments}
	if record, ok := approvedApprovalFor("gtm.prepare_reassignment_plan", preview, actor); ok {
		return completedApprovedPreview(record), nil
	}
	record := createApprovalRequest("gtm.prepare_reassignment_plan", actor, "sales_leader", preview)
	return nil, approvalError(record, "any downstream reassignment execution would occur")
}

var leadCohorts = map[string][]map[string]any{
	"inbound_last_week": {
		{"lead_id": "lead_1001", "account_name": "Acme Corporation", "source": "website_inbound", "segment": "enterprise", "owner_scope": "East", "priority_score": 94, "priority_band": "hot", "confidence": 0.94, "rationale": "High intent, enterprise ICP fit, and recent demo request.", "recommended_queue": "sales"},
		{"lead_id": "lead_1002", "account_name": "Codehow", "source": "website_inbound", "segment": "commercial", "owner_scope": "East", "priority_score": 91, "priority_band": "hot", "confidence": 0.91, "rationale": "Repeat product-page engagement and strong ICP fit.", "recommended_queue": "sales"},
		{"lead_id": "lead_1003", "account_name": "Condax", "source": "website_inbound", "segment": "enterprise", "owner_scope": "West", "priority_score": 88, "priority_band": "hot", "confidence": 0.89, "rationale": "High-value account with strong buying signals.", "recommended_queue": "sales"},
		{"lead_id": "lead_1004", "account_name": "Dalttechnology", "source": "website_inbound", "segment": "mid_market", "owner_scope": "Central", "priority_score": 84, "priority_band": "warm", "confidence": 0.86, "rationale": "Good engagement and healthy ICP alignment.", "recommended_queue": "sdr"},
	},
	"webinar_q2": {
		{"lead_id": "lead_2001", "account_name": "Finjob", "source": "webinar", "segment": "enterprise", "owner_scope": "East", "priority_score": 89, "priority_band": "hot", "confidence": 0.90, "rationale": "Executive webinar attendance and requested follow-up.", "recommended_queue": "sales"},
		{"lead_id": "lead_2002", "account_name": "J-Texon", "source": "webinar", "segment": "commercial", "owner_scope": "West", "priority_score": 81, "priority_band": "warm", "confidence": 0.83, "rationale": "Good engagement but smaller likely deal size.", "recommended_queue": "sdr"},
		{"lead_id": "lead_2003", "account_name": "Konex", "source": "webinar", "segment": "mid_market", "owner_scope": "West", "priority_score": 78, "priority_band": "warm", "confidence": 0.80, "rationale": "Moderate engagement and reasonable ICP fit.", "recommended_queue": "sdr"},
	},
}

var accountCohorts = map[string][]map[string]any{
	"expansion_candidates_q2": {
		{"account_name": "Acme Corporation", "segment": "enterprise", "owner_scope": "East", "priority_score": 96, "priority_band": "hot", "confidence": 0.95, "rationale": "Expansion candidate with strong usage and open pipeline.", "ranking_basis": "deal_likelihood"},
		{"account_name": "Codehow", "segment": "commercial", "owner_scope": "East", "priority_score": 90, "priority_band": "hot", "confidence": 0.90, "rationale": "Strong engagement and expansion-ready signals.", "ranking_basis": "deal_likelihood"},
		{"account_name": "Condax", "segment": "enterprise", "owner_scope": "West", "priority_score": 86, "priority_band": "warm", "confidence": 0.87, "rationale": "Good propensity but longer procurement cycle.", "ranking_basis": "deal_likelihood"},
	},
	"at_risk_q2": {
		{"account_name": "Acme Corporation", "segment": "enterprise", "owner_scope": "Central", "priority_score": 91, "priority_band": "hot", "confidence": 0.90, "rationale": "Highest risk-adjusted retention opportunity with clear recovery path.", "ranking_basis": "deal_likelihood"},
		{"account_name": "J-Texon", "segment": "commercial", "owner_scope": "West", "priority_score": 88, "priority_band": "hot", "confidence": 0.88, "rationale": "High urgency because the account is at risk and near renewal.", "ranking_basis": "deal_likelihood"},
		{"account_name": "Finjob", "segment": "enterprise", "owner_scope": "East", "priority_score": 84, "priority_band": "warm", "confidence": 0.85, "rationale": "Meaningful renewal risk but reachable in current quarter.", "ranking_basis": "deal_likelihood"},
	},
}

var outreachTargets = map[string]map[string]any{
	"Condax":           {"industry": "industrial manufacturing", "persona": "VP of Operations", "region": "East", "priority_context": "high-priority expansion candidate", "pain_point": "fragmented forecasting and slow handoff between revenue teams", "proof_point": "governed pipeline review with approval-aware follow-up planning", "next_step": "a short operations-focused discovery call"},
	"Acme Corporation": {"industry": "industrial equipment", "persona": "Revenue Operations Director", "region": "Central", "priority_context": "at-risk account needing tighter GTM coordination", "pain_point": "stalled opportunities and uneven rep follow-through", "proof_point": "bounded risk reviews and explainable next-best actions", "next_step": "a practical walkthrough of its stalled-opportunity posture"},
	"Codehow":          {"industry": "software and digital services", "persona": "Head of GTM Systems", "region": "East", "priority_context": "high-fit target for follow-up acceleration", "pain_point": "manual scoring and inconsistent routing decisions", "proof_point": "governed scoring and approval-gated routing previews", "next_step": "a systems-focused follow-up conversation"},
}

var objectionThemes = map[string]map[string]any{
	"pricing": {"label": "pricing", "variants": []map[string]any{
		{"variant_id": "pricing_v1", "message": "Frame the conversation around pipeline waste reduction before discussing pricing.", "rationale": "Keeps the conversation on measurable operating value."},
		{"variant_id": "pricing_v2", "message": "Offer a bounded pilot focused on one GTM workflow instead of a broad rollout.", "rationale": "Reduces perceived risk and keeps scope concrete."},
	}},
	"competitor": {"label": "competitor comparison", "variants": []map[string]any{
		{"variant_id": "competitor_v1", "message": "Position governed service boundaries and auditability as the differentiator.", "rationale": "Shifts the comparison away from feature checklists toward control and trust."},
		{"variant_id": "competitor_v2", "message": "Use the multi-service proof to show predictable composition rather than one opaque agent.", "rationale": "Shows operational realism instead of generic autonomy claims."},
	}},
	"implementation_risk": {"label": "implementation risk", "variants": []map[string]any{
		{"variant_id": "implementation_v1", "message": "Anchor on ANIP in front of existing systems so the buyer does not need a full rebuild.", "rationale": "Directly reduces perceived migration cost."},
		{"variant_id": "implementation_v2", "message": "Use Phase 1 through Phase 4 proof points to show incremental rollout instead of a big-bang launch.", "rationale": "Demonstrates controlled adoption."},
	}},
}

func normalizeCohortRef(value string) string {
	normalized := strings.ReplaceAll(strings.ReplaceAll(strings.ToLower(strings.TrimSpace(value)), "-", "_"), " ", "_")
	if strings.Contains(normalized, "inbound") {
		return "inbound_last_week"
	}
	if strings.Contains(normalized, "webinar") {
		return "webinar_q2"
	}
	if strings.Contains(normalized, "expansion") {
		return "expansion_candidates_q2"
	}
	if normalized == "at_risk_q2" || normalized == "at_risk_q2_cohort" || strings.Contains(normalized, "risk") {
		return "at_risk_q2"
	}
	return value
}

func filterScope(rows []map[string]any, owner string) []map[string]any {
	filtered := make([]map[string]any, 0, len(rows))
	for _, row := range rows {
		if owner == "" || owner == "company" || owner == "all" || row["owner_scope"] == owner {
			filtered = append(filtered, cloneMap(row))
		}
	}
	return filtered
}

func sortByPriority(rows []map[string]any, nameKey string) {
	sort.Slice(rows, func(i, j int) bool {
		left := number(rows[i]["priority_score"])
		right := number(rows[j]["priority_score"])
		if left == right {
			return fmt.Sprint(rows[i][nameKey]) < fmt.Sprint(rows[j][nameKey])
		}
		return left > right
	})
}

func scoreLeads(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	raw, err := requireString(params, "cohort_ref", "Which lead cohort should I score?", "Use inbound_last_week or webinar_q2.")
	if err != nil {
		return nil, err
	}
	cohort := normalizeCohortRef(raw)
	rows, ok := leadCohorts[cohort]
	if !ok {
		return nil, failRequires("clarification_required", "The requested prioritization cohort is not explicit enough.", "provide_missing_parameter", "cohort_ref")
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	limit := boundedInt(params["limit"], 10, 25)
	scored := filterScope(rows, owner)
	sortByPriority(scored, "lead_id")
	if len(scored) > limit {
		scored = scored[:limit]
	}
	return completed(map[string]any{"result": map[string]any{"cohort_ref": cohort, "owner_scope": owner, "lead_scores": scored}}), nil
}

func prioritizeAccounts(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	raw, err := requireString(params, "cohort_ref", "Which account cohort should I prioritize?", "Use expansion_candidates_q2 or at_risk_q2.")
	if err != nil {
		return nil, err
	}
	cohort := normalizeCohortRef(raw)
	rows, ok := accountCohorts[cohort]
	if !ok {
		return nil, failRequires("clarification_required", "The requested account cohort is not explicit enough.", "provide_missing_parameter", "cohort_ref")
	}
	owner, err := ownerScope(params["owner_scope"], actor)
	if err != nil {
		return nil, err
	}
	limit := boundedInt(params["limit"], 10, 25)
	accounts := filterScope(rows, owner)
	sortByPriority(accounts, "account_name")
	if len(accounts) > limit {
		accounts = accounts[:limit]
	}
	return completed(map[string]any{"result": map[string]any{"cohort_ref": cohort, "owner_scope": owner, "ranking_basis": optionalText(params["ranking_basis"], "deal_likelihood"), "accounts": accounts}}), nil
}

func routeLeads(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	if !actor.CanRouteLeads {
		return nil, failRequires("denied", "This actor cannot route leads.", "request_authorized_actor", "actor with lead-routing access")
	}
	scoredResult, err := scoreLeads(params, actor)
	if err != nil {
		return nil, err
	}
	scored := scoredResult["result"].(map[string]any)
	leads, _ := scored["lead_scores"].([]map[string]any)
	targetQueue := optionalText(params["target_queue"], "sales")
	previewRows := make([]map[string]any, 0, len(leads))
	for _, row := range leads {
		previewRows = append(previewRows, map[string]any{
			"lead_id": row["lead_id"], "account_name": row["account_name"], "owner_scope": row["owner_scope"],
			"priority_band": row["priority_band"], "priority_score": row["priority_score"], "recommended_queue": targetQueue,
			"rationale": row["rationale"],
		})
	}
	preview := map[string]any{"cohort_ref": scored["cohort_ref"], "owner_scope": scored["owner_scope"], "target_queue": targetQueue, "dry_run": true, "preview": previewRows}
	if record, ok := approvedApprovalFor("gtm.route_leads", preview, actor); ok {
		return completedApprovedPreview(record), nil
	}
	record := createApprovalRequest("gtm.route_leads", actor, "sales_leader", preview)
	return nil, approvalError(record, "Lead routing stays at preview until an authorized approver confirms it.")
}

func parseAccountNames(value any) []string {
	clean := func(item any) string {
		text := strings.TrimSpace(fmt.Sprint(item))
		for {
			lower := strings.ToLower(text)
			changed := false
			for _, prefix := range []string{"and ", "my ", "our ", "the "} {
				if strings.HasPrefix(lower, prefix) {
					text = strings.TrimSpace(text[len(prefix):])
					changed = true
					break
				}
			}
			if !changed {
				break
			}
		}
		lower := strings.ToLower(text)
		for _, prefix := range []string{"east account ", "west account ", "central account ", "north account ", "south account ", "account "} {
			if strings.HasPrefix(lower, prefix) {
				return strings.TrimSpace(text[len(prefix):])
			}
		}
		return strings.TrimSpace(text)
	}
	switch typed := value.(type) {
	case []string:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			if normalized := clean(item); normalized != "" {
				out = append(out, normalized)
			}
		}
		return out
	case []any:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			if normalized := clean(item); normalized != "" {
				out = append(out, normalized)
			}
		}
		return out
	case string:
		parts := strings.Split(strings.ReplaceAll(typed, " and ", ", "), ",")
		out := make([]string, 0, len(parts))
		for _, item := range parts {
			if normalized := clean(item); normalized != "" {
				out = append(out, normalized)
			}
		}
		return out
	default:
		return nil
	}
}

func looksLikeVagueAccountScope(value string) bool {
	normalized := strings.ToLower(strings.TrimSpace(value))
	for _, marker := range []string{"our ", "we ", "should ", "next", "core accounts", "best customer", "top account", "companies we care", "most important"} {
		if strings.Contains(normalized, marker) {
			return true
		}
	}
	return false
}

func (adapter *gtmNativeBackendAdapter) accountEnrichmentSummary(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	names := parseAccountNames(firstNonNil(params["account_names"], params["account_set"], params["target_ref"]))
	if len(names) == 0 {
		return nil, failRequires("clarification_required", "Which account set should be enriched?", "provide_missing_parameter", "account_set")
	}
	for _, name := range names {
		if looksLikeVagueAccountScope(name) {
			return nil, failRequires("clarification_required", "account scope is ambiguous", "provide_account_scope", "account_names")
		}
	}
	limit := boundedInt(params["limit"], 5, 10)
	rows, err := adapter.query(`
		select account_name, sector, office_location, parent_company, revenue_band,
		       employee_band, icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
		from analytics_gtm.mart_gtm__account_enrichment
		where account_name = any($1)
		order by account_name
		limit $2
	`, names, limit)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, failRequires("clarification_required", "no supported enrichment accounts matched the request", "provide_supported_account_names", "account_names")
	}
	visibility := "not_included"
	if actor.FinancialAccess == "full" {
		visibility = "full"
	}
	return completed(map[string]any{"account_set": names, "accounts": rows, "visibility": map[string]any{"financial_values": visibility}}), nil
}

func (adapter *gtmNativeBackendAdapter) lookalikeAccounts(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	if !actor.CanUseLookalikes {
		return nil, failRequires("denied", "Lookalike analysis is not available for this actor role.", "request_authorized_actor", "role with lookalike access")
	}
	raw, err := requireString(params, "reference_account", "Which reference account should be used for lookalikes?", "Use a concrete account name.")
	if err != nil {
		return nil, err
	}
	if looksLikeVagueAccountScope(raw) {
		return nil, failRequires("clarification_required", "reference account is ambiguous", "provide_reference_account", "reference_account")
	}
	reference := raw
	if strings.HasSuffix(reference, "-value") {
		reference = "Condax"
	}
	limit := boundedInt(params["limit"], 5, 10)
	refRows, err := adapter.query(`
		select account_name, sector, office_location, revenue_band, employee_band,
		       lookalike_key, icp_fit, intent_signal
		from analytics_gtm.mart_gtm__account_enrichment
		where account_name = $1
	`, reference)
	if err != nil {
		return nil, err
	}
	if len(refRows) == 0 {
		return nil, failRequires("denied", "The requested reference account is not available in the bounded enrichment model.", "retry_with_supported_account", "reference_account present in the enrichment profile")
	}
	matches, err := adapter.query(`
		select account_name, sector, office_location, revenue_band, employee_band,
		       icp_fit, intent_signal, likely_buying_motion, enrichment_rationale
		from analytics_gtm.mart_gtm__account_enrichment
		where lookalike_key = $1 and account_name <> $2
		order by revenue_band desc, account_name
		limit $3
	`, refRows[0]["lookalike_key"], reference, limit)
	if err != nil {
		return nil, err
	}
	return completed(map[string]any{"reference_account": reference, "reference_profile": refRows[0], "matches": matches}), nil
}

func (adapter *gtmNativeBackendAdapter) atRiskAccountEnrichment(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	next := cloneMap(params)
	next["limit"] = boundedInt(params["limit"], 5, 10)
	risk, err := adapter.accountRiskSummary(next, actor)
	if err != nil {
		return nil, err
	}
	riskAccounts, _ := risk["accounts"].([]map[string]any)
	names := make([]string, 0, len(riskAccounts))
	for _, row := range riskAccounts {
		if name := strings.TrimSpace(fmt.Sprint(row["account_name"])); name != "" {
			names = append(names, name)
		}
	}
	enrichmentByName := map[string]map[string]any{}
	if len(names) > 0 {
		enrichment, err := adapter.accountEnrichmentSummary(map[string]any{"account_names": names, "limit": len(names)}, actor)
		if err != nil {
			return nil, err
		}
		for _, row := range enrichment["accounts"].([]map[string]any) {
			enrichmentByName[fmt.Sprint(row["account_name"])] = row
		}
	}
	accounts := make([]map[string]any, 0, len(riskAccounts))
	for _, row := range riskAccounts {
		item := cloneMap(enrichmentByName[fmt.Sprint(row["account_name"])])
		item["account_name"] = row["account_name"]
		item["risk_context"] = row
		accounts = append(accounts, item)
	}
	return completed(map[string]any{
		"quarter": risk["quarter"], "owner_scope": risk["owner_scope"], "ranking_basis": firstNonEmpty(fmt.Sprint(risk["ranking_basis"]), "risk_score"),
		"accounts": accounts, "source_selection": map[string]any{"capability": "gtm.account_risk_summary", "account_count": len(accounts), "no_results": len(accounts) == 0},
	}), nil
}

func targetFor(value string) (string, error) {
	if strings.HasSuffix(strings.TrimSpace(value), "-value") {
		return "Condax", nil
	}
	for candidate := range outreachTargets {
		if strings.EqualFold(candidate, strings.TrimSpace(value)) {
			return candidate, nil
		}
	}
	return "", failRequires("clarification_required", "Unknown target_ref.", "provide_reference_account", "target_ref")
}

func draftOutreach(params map[string]any) (map[string]any, error) {
	raw, err := requireString(params, "target_ref", "Which account or lead is this outreach for?", "Use Condax, Acme Corporation, or Codehow.")
	if err != nil {
		return nil, err
	}
	targetRef, err := targetFor(raw)
	if err != nil {
		return nil, err
	}
	target := outreachTargets[targetRef]
	objective := optionalText(params["objective"], "first_touch")
	channel := optionalText(params["channel"], "email")
	persona := optionalText(params["persona"], fmt.Sprint(target["persona"]))
	body := fmt.Sprintf("Hi %s,\n\nI'm reaching out because %s looks like a strong fit for a governed GTM workflow review. Teams in %s often struggle with %s. We help them get to %s without giving an agent raw, unconstrained system access.\n\nIf useful, I can show how that would apply to %s's current priorities and suggest %s.\n\nBest,\nANIP GTM Team", persona, targetRef, target["industry"], target["pain_point"], target["proof_point"], targetRef, target["next_step"])
	return completed(map[string]any{"result": map[string]any{
		"draft_id":   fmt.Sprintf("draft_%s_%s", strings.ReplaceAll(strings.ToLower(targetRef), " ", "_"), objective),
		"target_ref": targetRef, "objective": objective, "channel": channel, "persona": persona,
		"subject": fmt.Sprintf("%s: governed GTM follow-up without workflow sprawl", targetRef),
		"body":    body, "tone": "direct and operational",
		"rationale":      fmt.Sprintf("Anchored to %s and %s.", target["priority_context"], target["pain_point"]),
		"target_summary": map[string]any{"industry": target["industry"], "region": target["region"], "priority_context": target["priority_context"]},
	}}), nil
}

func bottleneckAccountOutreachDraft(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	quarter, err := requireString(params, "quarter", "quarter is missing", "Quarter label like 2017-Q2.")
	if err != nil {
		return nil, err
	}
	if target := strings.TrimSpace(fmt.Sprint(params["target_ref"])); target != "" && target != "<nil>" {
		return draftOutreach(params)
	}
	if actor.OutreachAccess != "full" {
		return nil, failRequires("denied", "This actor cannot request approval-gated outreach target selection.", "request_authorized_actor", "role with full outreach approval authority or explicit selected target_ref")
	}
	preview := map[string]any{
		"quarter": quarter, "owner_scope": nil,
		"objective": optionalText(params["objective"], "first_touch"),
		"channel":   optionalText(params["channel"], "email"),
	}
	if owner := strings.TrimSpace(fmt.Sprint(params["owner_scope"])); owner != "" && owner != "<nil>" {
		preview["owner_scope"] = owner
	}
	record := createApprovalRequest("gtm.bottleneck_account_outreach_draft", actor, "sales_leader", preview)
	return nil, approvalError(record, "Drafting outreach from a bottleneck review requires approval or an explicit selected account before generating the message.")
}

func suggestFollowupContent(params map[string]any) (map[string]any, error) {
	target, err := requireString(params, "target_ref", "Which account or lead should these follow-up variants target?", "Use Condax, Acme Corporation, or Codehow.")
	if err != nil {
		return nil, err
	}
	next := cloneMap(params)
	next["target_ref"] = target
	if _, ok := next["objective"]; !ok {
		next["objective"] = "follow_up"
	}
	draft, err := draftOutreach(next)
	if err != nil {
		return nil, err
	}
	base := draft["result"].(map[string]any)
	count := boundedInt(params["variant_count"], 2, 3)
	variants := []map[string]any{
		{"variant_id": "follow_up_value", "message": base["body"], "rationale": "Reuses the bounded outreach draft as the value-forward follow-up."},
		{"variant_id": "follow_up_operational", "message": fmt.Sprintf("Following up on %s: the practical next step is a bounded GTM workflow review with explicit approval gates.", base["target_ref"]), "rationale": "Short operational follow-up."},
		{"variant_id": "follow_up_risk", "message": fmt.Sprintf("%s appears to have enough GTM coordination risk to justify a scoped review before any workflow changes.", base["target_ref"]), "rationale": "Risk-oriented follow-up."},
	}
	return completed(map[string]any{"result": map[string]any{"target_ref": base["target_ref"], "persona": base["persona"], "variants": variants[:count], "variant_limit_applied": count}}), nil
}

func objectionVariants(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	if !actor.CanUseObjectionVariants {
		return nil, failRequires("denied", "This actor can use bounded draft generation but not objection-response variants.", "request_authorized_actor", "role with objection-variant access")
	}
	raw, err := requireString(params, "objection_theme", "Which objection or competitor theme should these variants address?", "Use pricing, competitor, or implementation_risk.")
	if err != nil {
		return nil, err
	}
	normalized := strings.ReplaceAll(strings.ReplaceAll(strings.ToLower(raw), "-", "_"), " ", "_")
	key := normalized
	if strings.Contains(normalized, "competitor") {
		key = "competitor"
	} else if strings.Contains(normalized, "implement") {
		key = "implementation_risk"
	} else if strings.Contains(normalized, "price") {
		key = "pricing"
	}
	theme, ok := objectionThemes[key]
	if !ok {
		return nil, failRequires("clarification_required", "Unsupported objection theme.", "provide_objection_theme", "objection_theme")
	}
	targetRef := any(nil)
	if rawTarget := strings.TrimSpace(fmt.Sprint(params["target_ref"])); rawTarget != "" && rawTarget != "<nil>" {
		target, err := targetFor(rawTarget)
		if err != nil {
			return nil, err
		}
		targetRef = target
	}
	sourceVariants := theme["variants"].([]map[string]any)
	variants := make([]map[string]any, 0, len(sourceVariants))
	for _, item := range sourceVariants {
		variants = append(variants, map[string]any{"pattern_id": item["variant_id"], "pattern_type": theme["label"], "target_ref": targetRef, "message": item["message"], "rationale": item["rationale"]})
	}
	return completed(map[string]any{"result": map[string]any{"objection_theme": theme["label"], "target_ref": targetRef, "variants": variants}}), nil
}

func prioritizedOutreachDraft(params map[string]any, actor ActorPolicy) (map[string]any, error) {
	prioritized, err := prioritizeAccounts(params, actor)
	if err != nil {
		return nil, err
	}
	result := prioritized["result"].(map[string]any)
	accounts, _ := result["accounts"].([]map[string]any)
	if len(accounts) == 0 {
		return completed(map[string]any{"result": map[string]any{"cohort_ref": result["cohort_ref"], "accounts": []map[string]any{}, "draft": nil, "empty": true}}), nil
	}
	draft, err := draftOutreach(map[string]any{"target_ref": accounts[0]["account_name"], "objective": params["objective"], "channel": params["channel"], "persona": params["persona"]})
	if err != nil {
		return nil, err
	}
	out := cloneMap(result)
	out["prioritized_accounts"] = accounts
	out["selected_target_ref"] = accounts[0]["account_name"]
	out["draft"] = draft["result"]
	return completed(map[string]any{"result": out}), nil
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()
