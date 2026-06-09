package extensions

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"

	"{{ANIP_GO_MODULE_PATH}}/generated"
)

type BackendInvocationContext struct {
	RootPrincipal string
}

type BackendAdapter interface {
	Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, adapterInput map[string]any, context BackendInvocationContext) (map[string]any, error)
}

type jiraConfig struct {
	BaseURL string
	Email   string
	Token   string
}

type jiraBackendAdapter struct{}

func CreateDefaultBackendAdapter() BackendAdapter {
	return jiraBackendAdapter{}
}

func (jiraBackendAdapter) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, _ BackendInvocationContext) (map[string]any, error) {
	if len(plan.UnresolvedRequiredBackendInputs) > 0 {
		return map[string]any{
			"execution_status": "backend_input_incomplete",
			"capability_id": capability.CapabilityID,
			"backend_input_contract": plan.BackendInputContract,
			"unresolved_required_backend_inputs": plan.UnresolvedRequiredBackendInputs,
		}, nil
	}
	config := readJiraConfig()
	switch capability.CapabilityID {
	case "jira.backlog.search_context":
		return searchBacklog(capability, plan, params, config), nil
	case "jira.issue.get_context":
		return getIssueContext(capability, plan, params, config), nil
	case "jira.release_notes.prepare":
		return prepareReleaseNotes(capability, plan, params, config), nil
	case "jira.incident_bug.prepare":
		return prepareIssueCreate(capability, plan, params, "Bug"), nil
	case "jira.story.prepare":
		return prepareIssueCreate(capability, plan, params, "Story"), nil
	case "jira.subtask.prepare":
		return prepareSubtask(capability, plan, params, config), nil
	case "jira.customer_escalation.comment.prepare":
		return previewResult(capability, plan, "add_comment", map[string]any{"method": "POST", "path": "/rest/api/3/issue/" + text(params["issue_key"]) + "/comment", "body": map[string]any{"body": adfDoc("["+text(params["comment_purpose"])+"] "+text(params["context"])), "visibility": adapterFirstNonEmpty(text(params["visibility"]), "internal")}}, map[string]any{"issue_key": params["issue_key"], "visibility": adapterFirstNonEmpty(text(params["visibility"]), "internal"), "comment_purpose": params["comment_purpose"]}), nil
	case "jira.workflow_transition.request":
		body := map[string]any{"transition": map[string]any{"id": params["target_status"]}}
		if comment := text(params["comment"]); comment != "" {
			body["update"] = map[string]any{"comment": []any{map[string]any{"add": map[string]any{"body": adfDoc(comment)}}}}
		}
		return previewResult(capability, plan, "transition_issue", map[string]any{"method": "POST", "path": "/rest/api/3/issue/" + text(params["issue_key"]) + "/transitions", "body": body}, map[string]any{"issue_key": params["issue_key"], "target_status": params["target_status"]}), nil
	case "jira.sprint_move.request":
		issues := listValue(params["issue_keys"])
		return previewResult(capability, plan, "move_issues_to_sprint", map[string]any{"method": "POST", "path": "/rest/agile/1.0/sprint/" + text(params["target_sprint"]) + "/issue", "body": map[string]any{"issues": issues}}, map[string]any{"issue_keys": issues, "target_sprint": params["target_sprint"]}), nil
	case "jira.assignee_change.request":
		return previewResult(capability, plan, "assign_issue", map[string]any{"method": "PUT", "path": "/rest/api/3/issue/" + text(params["issue_key"]) + "/assignee", "body": map[string]any{"accountId": params["assignee_ref"]}}, map[string]any{"issue_key": params["issue_key"], "assignee_ref": params["assignee_ref"]}), nil
	case "jira.issue_link.request":
		return previewResult(capability, plan, "link_issues", map[string]any{"method": "POST", "path": "/rest/api/3/issueLink", "body": map[string]any{"type": map[string]any{"name": params["link_type"]}, "inwardIssue": map[string]any{"key": params["source_issue_key"]}, "outwardIssue": map[string]any{"key": params["target_issue_key"]}, "comment": map[string]any{"body": adfDoc(params["reason"])}}}, map[string]any{"requested_link_type": params["link_type"]}), nil
	default:
		return map[string]any{"execution_status": "backend_execution_stub", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "backend_input_contract": plan.BackendInputContract, "note": "No Jira custom handler is registered for this capability."}, nil
	}
}

func readJiraConfig() *jiraConfig {
	baseURL := strings.TrimRight(os.Getenv("JIRA_BASE_URL"), "/")
	email := os.Getenv("JIRA_EMAIL")
	token := os.Getenv("JIRA_API_TOKEN")
	if baseURL == "" || email == "" || token == "" {
		return nil
	}
	return &jiraConfig{BaseURL: baseURL, Email: email, Token: token}
}

func jiraJSON(config *jiraConfig, method, path string, query map[string]string, body map[string]any) map[string]any {
	if config == nil {
		return map[string]any{"error": "jira_not_configured"}
	}
	target, _ := url.Parse(config.BaseURL + path)
	values := target.Query()
	for key, value := range query {
		values.Set(key, value)
	}
	target.RawQuery = values.Encode()
	var requestBody *strings.Reader
	if body != nil {
		encoded, _ := json.Marshal(body)
		requestBody = strings.NewReader(string(encoded))
	} else {
		requestBody = strings.NewReader("")
	}
	request, _ := http.NewRequest(method, target.String(), requestBody)
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Authorization", "Basic "+base64.StdEncoding.EncodeToString([]byte(config.Email+":"+config.Token)))
	if body != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return map[string]any{"error": "jira_http_error", "detail": err.Error()}
	}
	defer response.Body.Close()
	var payload map[string]any
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		payload = map[string]any{}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return map[string]any{"error": "jira_http_error", "status": response.StatusCode, "detail": payload}
	}
	return payload
}

func searchBacklog(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, config *jiraConfig) map[string]any {
	projectKey := text(params["project_key"])
	queryText := text(params["query"])
	jql := issueQueryJQL(projectKey, queryText)
	if issueType := text(params["issue_type"]); issueType != "" {
		jql += ` AND issuetype = "` + safeJQLValue(issueType) + `"`
	}
	if status := text(params["status"]); status != "" {
		jql += ` AND status = "` + safeJQLValue(status) + `"`
	}
	if config == nil {
		return map[string]any{"execution_status": "backend_not_configured", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "jql_preview": jql}
	}
	payload := searchIssues(config, jql, boundedLimit(params["limit"], 25, 50), "summary,status,issuetype,project,assignee,priority")
	if payload["error"] != nil {
		return backendError(capability, plan, payload)
	}
	issues := summarizeIssues(payload["issues"])
	return map[string]any{"execution_status": "completed", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "jql": jql, "result": map[string]any{"issues": issues, "count": len(issues), "is_last": payload["isLast"]}}
}

func getIssueContext(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, config *jiraConfig) map[string]any {
	issueKey := text(params["issue_key"])
	if config == nil {
		return map[string]any{"execution_status": "backend_not_configured", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "path_preview": "/rest/api/3/issue/" + issueKey}
	}
	payload := jiraJSON(config, "GET", "/rest/api/3/issue/"+url.PathEscape(issueKey), map[string]string{"fields": "summary,status,issuetype,project,assignee,priority,description"}, nil)
	if payload["error"] != nil {
		return backendError(capability, plan, payload)
	}
	result := issueSummary(payload)
	return map[string]any{"execution_status": "completed", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "result": result}
}

func prepareReleaseNotes(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, config *jiraConfig) map[string]any {
	projectKey := text(params["project_key"])
	releaseRef := text(params["release_ref"])
	audience := adapterFirstNonEmpty(text(params["audience"]), "internal")
	var jql string
	if strings.EqualFold(releaseRef, "unversioned") {
		jql = `project = "` + safeJQLValue(projectKey) + `" AND fixVersion is EMPTY`
	} else {
		jql = `project = "` + safeJQLValue(projectKey) + `" AND fixVersion = "` + safeJQLValue(releaseRef) + `"`
	}
	if issueQuery := text(params["issue_query"]); issueQuery != "" {
		jql += ` AND text ~ "` + safeJQLValue(issueQuery) + `"`
	}
	jql += " ORDER BY priority DESC, updated DESC"
	issues := []map[string]any{}
	if config != nil {
		payload := searchIssues(config, jql, boundedLimit(params["limit"], 20, 50), "summary,status,issuetype,project")
		if payload["error"] != nil {
			return backendError(capability, plan, payload)
		}
		issues = summarizeIssues(payload["issues"])
	}
	return map[string]any{"execution_status": "prepared", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "jql": jql, "result": map[string]any{"audience": audience, "issue_count": len(issues), "issues": issues, "draft": releaseNoteDraft(audience, releaseRef, issues)}, "note": "Prepared release notes only. No Jira mutation or publication was performed."}
}

func prepareIssueCreate(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, issueTypeName string) map[string]any {
	fields := map[string]any{"project": map[string]any{"key": params["project_key"]}, "issuetype": map[string]any{"name": issueTypeName}, "summary": text(params["summary"])}
	if capability.CapabilityID == "jira.incident_bug.prepare" {
		fields["description"] = adfDoc(params["description"])
		fields["priority"] = map[string]any{"name": priorityForSeverity(params["severity"])}
	} else {
		fields["description"] = adfDoc("Acceptance criteria:\n" + text(params["acceptance_criteria"]))
		if priority := text(params["priority"]); priority != "" {
			fields["priority"] = map[string]any{"name": strings.Title(priority)}
		}
	}
	if labels := labels(params["labels"]); len(labels) > 0 {
		fields["labels"] = labels
	}
	return previewResult(capability, plan, "create_issue", map[string]any{"method": "POST", "path": "/rest/api/3/issue", "body": map[string]any{"fields": fields}}, map[string]any{"project_key": params["project_key"], "requested_issue_type": issueTypeName})
}

func prepareSubtask(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, config *jiraConfig) map[string]any {
	parentIssueKey := text(params["parent_issue_key"])
	fields := map[string]any{"parent": map[string]any{"key": parentIssueKey}, "issuetype": map[string]any{"name": "Sub-task"}, "summary": text(params["summary"]), "description": adfDoc(params["description"])}
	if config != nil {
		parent := jiraJSON(config, "GET", "/rest/api/3/issue/"+url.PathEscape(parentIssueKey), map[string]string{"fields": "project"}, nil)
		if parent["error"] == nil {
			if projectKey := nestedString(parent, "fields", "project", "key"); projectKey != "" {
				fields["project"] = map[string]any{"key": projectKey}
			}
			if id := text(parent["id"]); id != "" {
				fields["parent"] = map[string]any{"id": id}
			}
		}
	}
	return previewResult(capability, plan, "create_subtask", map[string]any{"method": "POST", "path": "/rest/api/3/issue", "body": map[string]any{"fields": fields}}, map[string]any{"parent_issue_key": parentIssueKey})
}

func previewResult(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, action string, request map[string]any, metadata map[string]any) map[string]any {
	return map[string]any{"execution_status": "prepared", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "approval_required": capability.OperationType == "approval_gated" || capability.ExecutionPosture == "prepare_only", "mutation_performed": false, "jira_action": action, "jira_request_preview": request, "jira_metadata": metadata, "note": "Prepared a governed Jira request preview. No Jira mutation was performed."}
}

func backendError(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, payload map[string]any) map[string]any {
	return map[string]any{"execution_status": "backend_error", "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "jira_error": payload}
}

func searchIssues(config *jiraConfig, jql string, limit int, fields string) map[string]any {
	return jiraJSON(config, "GET", "/rest/api/3/search/jql", map[string]string{"jql": jql, "maxResults": strconv.Itoa(limit), "fields": fields}, nil)
}

func issueQueryJQL(projectKey, queryText string) string {
	jql := `project = "` + safeJQLValue(projectKey) + `"`
	if queryText != "" {
		jql += ` AND text ~ "` + safeJQLValue(queryText) + `"`
	}
	return jql + " ORDER BY updated DESC"
}

func issueSummary(issue map[string]any) map[string]any {
	return map[string]any{"key": issue["key"], "summary": nestedString(issue, "fields", "summary"), "status": nestedString(issue, "fields", "status", "name"), "issue_type": nestedString(issue, "fields", "issuetype", "name"), "project_key": nestedString(issue, "fields", "project", "key"), "assignee": nestedString(issue, "fields", "assignee", "displayName"), "priority": nestedString(issue, "fields", "priority", "name")}
}

func summarizeIssues(value any) []map[string]any {
	items, _ := value.([]any)
	result := make([]map[string]any, 0, len(items))
	for _, item := range items {
		if issue, ok := item.(map[string]any); ok {
			result = append(result, issueSummary(issue))
		}
	}
	return result
}

func adfDoc(value any) map[string]any {
	return map[string]any{"type": "doc", "version": 1, "content": []any{map[string]any{"type": "paragraph", "content": []any{map[string]any{"type": "text", "text": text(value)}}}}}
}

func releaseNoteDraft(audience, releaseRef string, issues []map[string]any) string {
	heading := fmt.Sprintf("Release %s notes for %s", releaseRef, audience)
	if len(issues) == 0 {
		return heading + "\n\nNo matching Jira issues were returned for the bounded query."
	}
	lines := []string{heading, ""}
	for _, issue := range issues {
		lines = append(lines, fmt.Sprintf("- %s: %s (%s)", issue["key"], issue["summary"], issue["status"]))
	}
	return strings.Join(lines, "\n")
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

func safeJQLValue(value any) string {
	return strings.ReplaceAll(strings.ReplaceAll(text(value), `\`, `\\`), `"`, `\"`)
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func listValue(value any) []string {
	var raw []any
	switch typed := value.(type) {
	case []any:
		raw = typed
	case []string:
		for _, item := range typed {
			raw = append(raw, item)
		}
	case string:
		for _, item := range strings.Split(typed, ",") {
			raw = append(raw, item)
		}
	}
	result := []string{}
	for _, item := range raw {
		if candidate := text(item); candidate != "" && !contains(result, candidate) {
			result = append(result, candidate)
		}
	}
	return result
}

func labels(value any) []string {
	allowed := regexp.MustCompile(`[^a-z0-9_.-]+`)
	result := []string{}
	for _, item := range listValue(value) {
		label := strings.Trim(allowed.ReplaceAllString(strings.ToLower(item), "-"), "-")
		if label != "" {
			result = append(result, label)
		}
	}
	return result
}

func priorityForSeverity(value any) string {
	switch strings.ToLower(text(value)) {
	case "sev1", "sev2":
		return "High"
	case "sev4":
		return "Low"
	default:
		return "Medium"
	}
}

func nestedString(value map[string]any, path ...string) string {
	var current any = value
	for _, key := range path {
		record, ok := current.(map[string]any)
		if !ok {
			return ""
		}
		current = record[key]
	}
	return text(current)
}

func adapterFirstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func contains(values []string, candidate string) bool {
	for _, value := range values {
		if value == candidate {
			return true
		}
	}
	return false
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()
