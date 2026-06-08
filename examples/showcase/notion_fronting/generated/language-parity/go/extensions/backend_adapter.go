package extensions

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/anip-protocol/anip/examples/showcase/notion_fronting/generated/language-parity/go/generated"
)

type BackendInvocationContext struct {
	RootPrincipal string
	ApprovalGrant string
}

type BackendAdapter interface {
	Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, adapterInput map[string]any, context BackendInvocationContext) (map[string]any, error)
}

type notionBackendAdapter struct{}

func CreateDefaultBackendAdapter() BackendAdapter {
	return notionBackendAdapter{}
}

func (notionBackendAdapter) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) (map[string]any, error) {
	if len(plan.UnresolvedRequiredBackendInputs) > 0 {
		return result(capability, plan, "backend_input_incomplete", map[string]any{"unresolved_required_backend_inputs": plan.UnresolvedRequiredBackendInputs}), nil
	}
	if notionToken() == "" {
		return result(capability, plan, "backend_error", map[string]any{"notion_error": map[string]any{"error": "missing_notion_token"}}), nil
	}
	switch capability.CapabilityID {
	case "notion.workspace.search_context":
		return searchWorkspace(capability, plan, params), nil
	case "notion.database.query_context":
		return queryDatabase(capability, plan, params), nil
	case "notion.page.create.prepare":
		return prepareOrCreatePage(capability, plan, params, context), nil
	case "notion.page.update.prepare":
		return preparePageUpdate(capability, plan, params), nil
	case "notion.comment.prepare":
		return prepareOrPostComment(capability, plan, params, context), nil
	default:
		return result(capability, plan, "backend_execution_stub", map[string]any{"note": "No Notion custom handler is registered for this capability."}), nil
	}
}

func searchWorkspace(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any) map[string]any {
	scope := text(params["workspace_scope"])
	if !scopeAllowed(scope) {
		return restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.")
	}
	limit := boundedLimit(params["limit"], 20, 50)
	response := notionRequest("POST", "/search", map[string]any{"query": text(params["query"]), "page_size": limit})
	if response["error"] != nil {
		return result(capability, plan, "backend_error", map[string]any{"notion_error": response})
	}
	items := summarizeResults(response, limit)
	return result(capability, plan, "completed", map[string]any{"notion_query": params["query"], "result": map[string]any{"workspace_scope": scope, "items": items, "count": len(items)}})
}

func queryDatabase(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any) map[string]any {
	databaseID := text(params["database_id"])
	if !idAllowed(databaseID, "ANIP_NOTION_ALLOWED_DATABASES") {
		return restricted(capability, plan, "Database is outside the configured ANIP policy.")
	}
	limit := boundedLimit(params["limit"], 20, 50)
	dataSourceID := configuredDataSourceID()
	if dataSourceID != "" && !idAllowed(dataSourceID, "ANIP_NOTION_ALLOWED_DATA_SOURCES") {
		return restricted(capability, plan, "Data source is outside the configured ANIP policy.")
	}
	if dataSourceID == "" {
		database := notionRequest("GET", "/databases/"+databaseID, nil)
		if database["error"] != nil {
			return result(capability, plan, "backend_error", map[string]any{"notion_error": database})
		}
		if dataSources, ok := database["data_sources"].([]any); ok && len(dataSources) > 0 {
			if first, ok := dataSources[0].(map[string]any); ok {
				dataSourceID = text(first["id"])
			}
		}
	}
	response := map[string]any{}
	if dataSourceID != "" {
		response = notionRequest("POST", "/data_sources/"+dataSourceID+"/query", map[string]any{"page_size": limit})
	} else {
		response = notionRequest("POST", "/databases/"+databaseID+"/query", map[string]any{"page_size": limit})
	}
	if response["error"] != nil {
		return result(capability, plan, "backend_error", map[string]any{"notion_error": response})
	}
	items := summarizeResults(response, limit)
	return result(capability, plan, "completed", map[string]any{"result": map[string]any{"database_id": databaseID, "data_source_id": dataSourceID, "items": items, "count": len(items)}})
}

func prepareOrCreatePage(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) map[string]any {
	parentID := text(params["parent_id"])
	if !idAllowed(parentID, "ANIP_NOTION_ALLOWED_PARENTS") {
		return restricted(capability, plan, "Parent page/database is outside the configured ANIP policy.")
	}
	body := map[string]any{
		"parent":     map[string]any{"page_id": parentID},
		"properties": map[string]any{"title": map[string]any{"title": richText(text(params["title"]))}},
		"children":   []any{map[string]any{"object": "block", "type": "paragraph", "paragraph": map[string]any{"rich_text": richText(text(params["content_summary"]))}}},
	}
	preview := writePreview(capability, plan, "pages.create", body, map[string]any{"parent_id": parentID})
	if os.Getenv("ANIP_NOTION_ALLOW_MUTATION") != "true" || strings.TrimSpace(context.ApprovalGrant) == "" {
		return preview
	}
	created := notionRequest("POST", "/pages", body)
	if created["error"] != nil {
		preview["execution_status"] = "backend_error"
		preview["notion_error"] = created
		return preview
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["created_page"] = summarizeObject(created)
	return preview
}

func preparePageUpdate(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any) map[string]any {
	pageID := text(params["page_id"])
	if !idAllowed(pageID, "ANIP_NOTION_ALLOWED_PAGES") {
		return restricted(capability, plan, "Page is outside the configured ANIP policy.")
	}
	return writePreview(capability, plan, "pages.update.preview", map[string]any{"archived": false, "change_summary": text(params["change_summary"]), "content_patch": text(params["content_patch"])}, map[string]any{"page_id": pageID})
}

func prepareOrPostComment(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) map[string]any {
	pageID := text(params["page_id"])
	if !idAllowed(pageID, "ANIP_NOTION_ALLOWED_PAGES") {
		return restricted(capability, plan, "Page is outside the configured ANIP policy.")
	}
	body := map[string]any{"parent": map[string]any{"page_id": pageID}, "rich_text": richText(strings.TrimSpace("["+text(params["comment_purpose"])+"] "+text(params["context"])))}
	preview := writePreview(capability, plan, "comments.create", body, map[string]any{"page_id": pageID})
	if os.Getenv("ANIP_NOTION_ALLOW_MUTATION") != "true" || strings.TrimSpace(context.ApprovalGrant) == "" {
		return preview
	}
	created := notionRequest("POST", "/comments", body)
	if created["error"] != nil {
		preview["execution_status"] = "backend_error"
		preview["notion_error"] = created
		return preview
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["created_comment"] = created
	return preview
}

func notionRequest(method, path string, body map[string]any) map[string]any {
	var reader *bytes.Reader
	if body == nil {
		reader = bytes.NewReader(nil)
	} else {
		payload, _ := json.Marshal(body)
		reader = bytes.NewReader(payload)
	}
	request, _ := http.NewRequest(method, apiBase()+path, reader)
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Authorization", "Bearer "+notionToken())
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Notion-Version", notionVersion())
	request.Header.Set("User-Agent", "anip-notion-fronting-showcase")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return map[string]any{"error": "notion_connection_error", "detail": err.Error()}
	}
	defer response.Body.Close()
	var decoded map[string]any
	if err := json.NewDecoder(response.Body).Decode(&decoded); err != nil {
		return map[string]any{"error": "notion_decode_error", "detail": err.Error()}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return map[string]any{"error": "notion_http_error", "status": response.StatusCode, "detail": decoded}
	}
	return decoded
}

func writePreview(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, action string, body map[string]any, metadata map[string]any) map[string]any {
	return result(capability, plan, "prepared", map[string]any{
		"approval_required":  true,
		"mutation_performed": false,
		"notion_action":      action,
		"notion_metadata":    metadata,
		"notion_request":     map[string]any{"operation": action, "body": body},
		"note":               "Prepared a Notion API payload. No Notion mutation was performed.",
	})
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

func summarizeResults(response map[string]any, limit int) []map[string]any {
	results, _ := response["results"].([]any)
	items := []map[string]any{}
	for _, value := range results {
		item, ok := value.(map[string]any)
		if !ok {
			continue
		}
		items = append(items, summarizeObject(item))
		if len(items) >= limit {
			break
		}
	}
	return items
}

func summarizeObject(item map[string]any) map[string]any {
	title := text(item["url"])
	if item["object"] == "page" {
		if found := titleFromPage(item); found != "" {
			title = found
		}
	}
	if title == "" {
		title = text(item["id"])
	}
	return map[string]any{"id": item["id"], "object": item["object"], "title": title, "url": item["url"], "created_time": item["created_time"], "last_edited_time": item["last_edited_time"]}
}

func titleFromPage(page map[string]any) string {
	properties, _ := page["properties"].(map[string]any)
	for _, property := range properties {
		value, _ := property.(map[string]any)
		if value["type"] != "title" {
			continue
		}
		parts, _ := value["title"].([]any)
		chunks := []string{}
		for _, part := range parts {
			partMap, _ := part.(map[string]any)
			chunks = append(chunks, text(partMap["plain_text"]))
		}
		return strings.TrimSpace(strings.Join(chunks, ""))
	}
	return ""
}

func richText(value string) []any {
	return []any{map[string]any{"type": "text", "text": map[string]any{"content": truncate(value, 1900)}}}
}

func truncate(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	return value[:limit]
}

func scopeAllowed(scope string) bool {
	key := strings.ToLower(strings.TrimSpace(scope))
	blocked := csvEnv("ANIP_NOTION_BLOCKED_WORKSPACES")
	allowed := csvEnv("ANIP_NOTION_ALLOWED_WORKSPACES")
	if blocked[key] {
		return false
	}
	return len(allowed) == 0 || allowed[key]
}

func idAllowed(value, envName string) bool {
	allowed := csvEnv(envName)
	return len(allowed) == 0 || allowed[strings.ToLower(strings.TrimSpace(value))]
}

func csvEnv(name string) map[string]bool {
	result := map[string]bool{}
	for _, part := range strings.Split(os.Getenv(name), ",") {
		if value := strings.ToLower(strings.TrimSpace(part)); value != "" {
			result[value] = true
		}
	}
	return result
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

func text(value any) string {
	if value == nil {
		return ""
	}
	if typed, ok := value.(string); ok {
		return strings.TrimSpace(typed)
	}
	payload, _ := json.Marshal(value)
	return strings.Trim(strings.TrimSpace(string(payload)), "\"")
}

func notionToken() string {
	return strings.TrimSpace(os.Getenv("NOTION_TOKEN"))
}

func apiBase() string {
	if value := strings.TrimSpace(os.Getenv("NOTION_API_BASE")); value != "" {
		return strings.TrimRight(value, "/")
	}
	return "https://api.notion.com/v1"
}

func notionVersion() string {
	if value := strings.TrimSpace(os.Getenv("NOTION_VERSION")); value != "" {
		return value
	}
	return "2026-03-11"
}

func configuredDataSourceID() string {
	if value := strings.TrimSpace(os.Getenv("NOTION_DATA_SOURCE_ID")); value != "" {
		return value
	}
	return strings.TrimSpace(os.Getenv("ANIP_NOTION_DATA_SOURCE_ID"))
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()
