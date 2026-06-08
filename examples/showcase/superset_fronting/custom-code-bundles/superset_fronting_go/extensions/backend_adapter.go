package extensions

import (
	"bytes"
	"encoding/json"
	"fmt"
	"{{ANIP_GO_MODULE_PATH}}/generated"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
)

type BackendInvocationContext struct {
	RootPrincipal string
	ApprovalGrant string
}

type BackendAdapter interface {
	Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, adapterInput map[string]any, context BackendInvocationContext) (map[string]any, error)
}

type defaultBackendAdapter struct{}

func CreateDefaultBackendAdapter() BackendAdapter {
	return defaultBackendAdapter{}
}

func (defaultBackendAdapter) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) (map[string]any, error) {
	if len(plan.UnresolvedRequiredBackendInputs) > 0 {
		return map[string]any{
			"execution_status": "backend_input_incomplete",
			"capability_id": capability.CapabilityID,
			"backend_input_contract": plan.BackendInputContract,
			"unresolved_required_backend_inputs": plan.UnresolvedRequiredBackendInputs,
			"note": "Generated host is runnable, but backend-only inputs still require extension completion.",
		}, nil
	}
	token := accessToken()
	if token == "" {
		return result(capability, plan, "backend_error", map[string]any{"superset_error": map[string]any{"error": "missing_superset_credentials"}}), nil
	}
	switch capability.CapabilityID {
	case "superset.analytics.discover_context":
		return discoverContext(capability, plan, params, token), nil
	case "superset.analytics.answer_question":
		return answerQuestion(capability, plan, params), nil
	case "superset.chart.preview.create":
		return chartPreview(capability, plan, params), nil
	case "superset.chart.publish.request":
		return chartPublishRequest(capability, plan, params, context), nil
	case "superset.dashboard.draft.prepare":
		return dashboardDraft(capability, plan, params), nil
	case "superset.dataset.draft.prepare":
		return datasetDraft(capability, plan, params, context), nil
	default:
		return result(capability, plan, "backend_execution_stub", map[string]any{"note": "No Superset custom handler is registered for this capability."}), nil
	}
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()

func discoverContext(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) map[string]any {
	workspaceScope := text(params["workspace_scope"])
	if !scopeAllowed(workspaceScope) {
		return restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.")
	}
	query := strings.ToLower(text(params["query"]))
	limit := boundedLimit(params["limit"], 20, 50)
	assetType := text(params["asset_type"])
	endpoints := [][2]string{{"dataset", "/api/v1/dataset/"}, {"chart", "/api/v1/chart/"}, {"dashboard", "/api/v1/dashboard/"}}
	items := []map[string]any{}
	for _, endpoint := range endpoints {
		kind := endpoint[0]
		if assetType != "" && assetType != kind {
			continue
		}
		payload := requestJSON("GET", endpoint[1]+"?page_size="+strconv.Itoa(limit), token, nil)
		if payload["error"] != nil {
			return result(capability, plan, "backend_error", map[string]any{"superset_error": payload})
		}
		for _, item := range listResult(payload) {
			title := firstNonBlankAdapter(text(item["table_name"]), text(item["slice_name"]), text(item["dashboard_title"]), text(item["name"]), text(item["id"]))
			if query != "" && !strings.Contains(strings.ToLower(title), query) {
				continue
			}
			items = append(items, map[string]any{"asset_type": kind, "id": item["id"], "title": title, "url": item["url"]})
			if len(items) >= limit {
				break
			}
		}
		if len(items) >= limit {
			break
		}
	}
	return result(capability, plan, "completed", map[string]any{"result": map[string]any{"workspace_scope": workspaceScope, "items": items, "count": len(items)}})
}

func answerQuestion(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any) map[string]any {
	datasetRef := text(params["dataset_ref"])
	if !datasetAllowed(datasetRef) {
		return restricted(capability, plan, "Dataset is outside the configured ANIP policy.")
	}
	return result(capability, plan, "completed", map[string]any{"mutation_performed": false, "result": map[string]any{"question": params["question"], "dataset_ref": datasetRef, "metric": params["metric"], "dimension": params["dimension"], "time_window": params["time_window"], "answer": "Governed analytics answer placeholder. The service owns SQL generation and execution policy.", "raw_sql_disclosed": false}})
}

func chartPreview(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any) map[string]any {
	datasetRef := text(params["dataset_ref"])
	if !datasetAllowed(datasetRef) {
		return restricted(capability, plan, "Dataset is outside the configured ANIP policy.")
	}
	body := map[string]any{"dataset_ref": datasetRef, "metric": params["metric"], "dimension": params["dimension"], "visualization_type": params["visualization_type"], "title": firstNonBlankAdapter(text(params["title"]), fmt.Sprintf("%s by %s", text(params["metric"]), firstNonBlankAdapter(text(params["dimension"]), "time"))), "save_chart": false}
	return writePreview(capability, plan, "chart.preview", body, map[string]any{"dataset_ref": datasetRef})
}

func chartPublishRequest(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) map[string]any {
	preview := writePreview(capability, plan, "chart.publish", map[string]any{"chart_preview_ref": params["chart_preview_ref"], "dashboard_scope": params["dashboard_scope"], "reason": params["reason"], "title": params["title"]}, map[string]any{"dashboard_scope": params["dashboard_scope"]})
	if os.Getenv("ANIP_SUPERSET_ALLOW_MUTATION") == "true" && strings.TrimSpace(context.ApprovalGrant) != "" {
		preview["execution_status"] = "completed"
		preview["approval_required"] = false
		preview["mutation_performed"] = false
		preview["note"] = "Approved publish request recorded. Concrete chart save is intentionally left to deployment-specific Superset adapter code."
	}
	return preview
}

func dashboardDraft(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any) map[string]any {
	return writePreview(capability, plan, "dashboard.draft", map[string]any{"dashboard_scope": params["dashboard_scope"], "objective": params["objective"], "chart_refs": params["chart_refs"], "layout_hint": params["layout_hint"], "audience": params["audience"]}, map[string]any{"dashboard_scope": params["dashboard_scope"]})
}

func datasetDraft(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) map[string]any {
	preview := writePreview(capability, plan, "dataset.draft", map[string]any{"database_ref": params["database_ref"], "dataset_purpose": params["dataset_purpose"], "query_intent": params["query_intent"], "source_tables": params["source_tables"], "metrics": params["metrics"], "raw_sql_accepted": false}, map[string]any{"database_ref": params["database_ref"]})
	if os.Getenv("ANIP_SUPERSET_ALLOW_MUTATION") == "true" && strings.TrimSpace(context.ApprovalGrant) != "" {
		preview["execution_status"] = "completed"
		preview["approval_required"] = false
		preview["mutation_performed"] = false
		preview["note"] = "Approved dataset draft recorded. Raw SQL generation remains deployment-owned."
	}
	return preview
}

func writePreview(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, action string, body map[string]any, supersetMetadata map[string]any) map[string]any {
	return result(capability, plan, "prepared", map[string]any{"approval_required": true, "mutation_performed": false, "superset_action": action, "superset_metadata": supersetMetadata, "superset_request": map[string]any{"operation": action, "body": body}, "note": "Prepared a governed Superset analytics request. No Superset mutation was performed."})
}

func result(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, status string, extra map[string]any) map[string]any {
	payload := map[string]any{"execution_status": status, "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "backend_input_contract": plan.BackendInputContract}
	for key, value := range extra {
		payload[key] = value
	}
	return payload
}

func restricted(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, reason string) map[string]any {
	return result(capability, plan, "restricted", map[string]any{"reason": reason})
}

func accessToken() string {
	if token := strings.TrimSpace(os.Getenv("SUPERSET_ACCESS_TOKEN")); token != "" {
		return token
	}
	username := strings.TrimSpace(os.Getenv("SUPERSET_USERNAME"))
	password := strings.TrimSpace(os.Getenv("SUPERSET_PASSWORD"))
	if username == "" || password == "" {
		return ""
	}
	payload := requestJSON("POST", "/api/v1/security/login", "", map[string]any{"username": username, "password": password, "provider": firstNonBlankAdapter(os.Getenv("SUPERSET_AUTH_PROVIDER"), "db"), "refresh": true})
	return text(payload["access_token"])
}

func requestJSON(method, path, token string, body map[string]any) map[string]any {
	var reader io.Reader
	if body != nil {
		content, _ := json.Marshal(body)
		reader = bytes.NewReader(content)
	}
	request, err := http.NewRequest(method, strings.TrimRight(firstNonBlankAdapter(os.Getenv("SUPERSET_BASE_URL"), "http://127.0.0.1:18088"), "/")+path, reader)
	if err != nil {
		return map[string]any{"error": "superset_connection_error", "detail": err.Error()}
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("User-Agent", "anip-superset-fronting-showcase")
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return map[string]any{"error": "superset_connection_error", "detail": err.Error()}
	}
	defer response.Body.Close()
	var payload map[string]any
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil && err != io.EOF {
		return map[string]any{"error": "superset_decode_error", "detail": err.Error()}
	}
	if payload == nil {
		payload = map[string]any{}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return map[string]any{"error": "superset_http_error", "status": response.StatusCode, "detail": payload}
	}
	return payload
}

func listResult(payload map[string]any) []map[string]any {
	raw, ok := payload["result"].(map[string]any)
	if !ok {
		return []map[string]any{}
	}
	items, ok := raw["data"].([]any)
	if !ok {
		return []map[string]any{}
	}
	result := []map[string]any{}
	for _, item := range items {
		if object, ok := item.(map[string]any); ok {
			result = append(result, object)
		}
	}
	return result
}

func scopeAllowed(scope string) bool {
	key := strings.ToLower(strings.TrimSpace(scope))
	blocked := csvEnv("ANIP_SUPERSET_BLOCKED_WORKSPACES")
	allowed := csvEnv("ANIP_SUPERSET_ALLOWED_WORKSPACES")
	return !contains(blocked, key) && (len(allowed) == 0 || contains(allowed, key))
}

func datasetAllowed(datasetRef string) bool {
	allowed := csvEnv("ANIP_SUPERSET_ALLOWED_DATASETS")
	return len(allowed) == 0 || contains(allowed, strings.ToLower(strings.TrimSpace(datasetRef)))
}

func boundedLimit(value any, defaultValue, maximum int) int {
	limit, err := strconv.Atoi(text(value))
	if err != nil {
		limit = defaultValue
	}
	if limit < 1 {
		return 1
	}
	if limit > maximum {
		return maximum
	}
	return limit
}

func csvEnv(name string) []string {
	result := []string{}
	for _, item := range strings.Split(os.Getenv(name), ",") {
		value := strings.ToLower(strings.TrimSpace(item))
		if value != "" && !contains(result, value) {
			result = append(result, value)
		}
	}
	return result
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func firstNonBlankAdapter(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}
