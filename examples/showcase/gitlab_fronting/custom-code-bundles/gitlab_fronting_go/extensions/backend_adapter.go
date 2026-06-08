package extensions

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"

	"{{ANIP_GO_MODULE_PATH}}/generated"
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
	token := strings.TrimSpace(os.Getenv("GITLAB_TOKEN"))
	if token == "" {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "gitlab_error": map[string]any{"error": "missing_gitlab_token"}}), nil
	}
	switch capability.CapabilityID {
	case "gitlab.project.search_context":
		return searchProjectContext(capability, plan, params, token)
	case "gitlab.issue.prepare":
		return prepareOrCreateIssue(capability, plan, params, token, context)
	case "gitlab.mr.comment.prepare":
		return prepareMergeRequestComment(capability, plan, params, token, context)
	case "gitlab.pipeline.trigger.request":
		return preparePipelineTrigger(capability, plan, params, token)
	case "gitlab.release_notes.prepare":
		return prepareReleaseNotes(capability, plan, params, token)
	default:
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_execution_stub"}), nil
	}
}

func searchProjectContext(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (map[string]any, error) {
	project := projectID(params)
	if !projectAllowed(project) {
		return restricted(capability, plan, project), nil
	}
	limit := boundedLimit(params["limit"])
	query := stringParam(params, "query")
	values := url.Values{"search": {query}, "per_page": {strconv.Itoa(limit)}}
	issuesPayload := gitlabRequest("GET", fmt.Sprintf("/projects/%s/issues?%s", url.PathEscape(project), values.Encode()), token, nil)
	mrsPayload := gitlabRequest("GET", fmt.Sprintf("/projects/%s/merge_requests?%s", url.PathEscape(project), values.Encode()), token, nil)
	if issuesPayload.Error != nil {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "gitlab_error": issuesPayload.Error}), nil
	}
	if mrsPayload.Error != nil {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "gitlab_error": mrsPayload.Error}), nil
	}
	items := make([]map[string]any, 0)
	for _, item := range issuesPayload.List {
		if len(items) >= limit {
			break
		}
		items = append(items, map[string]any{"kind": "issue", "iid": item["iid"], "title": item["title"], "state": item["state"], "web_url": item["web_url"]})
	}
	for _, item := range mrsPayload.List {
		if len(items) >= limit {
			break
		}
		items = append(items, map[string]any{"kind": "merge_request", "iid": item["iid"], "title": item["title"], "state": item["state"], "web_url": item["web_url"]})
	}
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "completed",
		"gitlab_query": query,
		"result": map[string]any{"items": items, "count": len(items), "project_id": project},
	}), nil
}

func prepareOrCreateIssue(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string, context BackendInvocationContext) (map[string]any, error) {
	project, projectPayload, errResult := projectMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	body := map[string]any{"title": stringParam(params, "title"), "description": firstNonEmptyText(stringParam(params, "body"), stringParam(params, "description"))}
	if labels := stringList(params["labels"]); len(labels) > 0 {
		body["labels"] = strings.Join(labels, ",")
	}
	preview := writePreview(capability, plan, "issues.create", fmt.Sprintf("/projects/%s/issues", project), body, projectPayload)
	if !mutationEnabled(context) {
		return preview, nil
	}
	created := gitlabRequest("POST", fmt.Sprintf("/projects/%s/issues", url.PathEscape(project)), token, body)
	if created.Error != nil {
		preview["execution_status"] = "backend_error"
		preview["gitlab_error"] = created.Error
		return preview, nil
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["created_issue"] = map[string]any{"iid": created.Object["iid"], "web_url": created.Object["web_url"], "state": created.Object["state"]}
	preview["note"] = "Created GitLab issue after the ANIP runtime validated and reserved an approval grant."
	return preview, nil
}

func prepareMergeRequestComment(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string, context BackendInvocationContext) (map[string]any, error) {
	project, projectPayload, errResult := projectMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	iid := stringParam(params, "merge_request_iid")
	mr := gitlabRequest("GET", fmt.Sprintf("/projects/%s/merge_requests/%s", url.PathEscape(project), url.PathEscape(iid)), token, nil)
	if mr.Error != nil {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "gitlab_error": mr.Error}), nil
	}
	body := map[string]any{"body": strings.TrimSpace(fmt.Sprintf("[%s] %s", firstNonEmptyText(stringParam(params, "comment_purpose"), "triage_update"), stringParam(params, "context")))}
	preview := writePreview(capability, plan, "merge_requests.createNote", fmt.Sprintf("/projects/%s/merge_requests/%s/notes", project, iid), body, projectPayload)
	preview["merge_request"] = map[string]any{"iid": mr.Object["iid"], "title": mr.Object["title"], "state": mr.Object["state"]}
	if !mutationEnabled(context) {
		return preview, nil
	}
	posted := gitlabRequest("POST", fmt.Sprintf("/projects/%s/merge_requests/%s/notes", url.PathEscape(project), url.PathEscape(iid)), token, body)
	if posted.Error != nil {
		preview["execution_status"] = "backend_error"
		preview["gitlab_error"] = posted.Error
		return preview, nil
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["posted_comment"] = map[string]any{"id": posted.Object["id"]}
	return preview, nil
}

func preparePipelineTrigger(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (map[string]any, error) {
	project, projectPayload, errResult := projectMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	body := map[string]any{"ref": stringParam(params, "ref"), "variables": objectParam(params["variables"]), "purpose": stringParam(params, "pipeline_purpose")}
	return writePreview(capability, plan, "pipeline.trigger", fmt.Sprintf("/projects/%s/pipeline", project), body, projectPayload), nil
}

func prepareReleaseNotes(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (map[string]any, error) {
	project, projectPayload, errResult := projectMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	releaseRange := stringParam(params, "range")
	projectName := firstNonEmptyText(stringValue(projectPayload["path_with_namespace"]), project)
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "completed",
		"mutation_performed": false,
		"result": map[string]any{
			"title": fmt.Sprintf("Release notes for %s %s", projectName, releaseRange),
			"audience": firstNonEmptyText(stringParam(params, "audience"), "internal"),
			"project": projectSummary(projectPayload),
			"range": releaseRange,
			"sections": []map[string]any{
				{"title": "Highlights", "items": []string{"Review bounded GitLab context before publishing release notes."}},
				{"title": "Governance", "items": []string{"This capability drafts content only and does not create a GitLab release."}},
			},
		},
	}), nil
}

func projectMetadata(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (string, map[string]any, map[string]any) {
	project := projectID(params)
	if !projectAllowed(project) {
		return project, nil, restricted(capability, plan, project)
	}
	payload := gitlabRequest("GET", fmt.Sprintf("/projects/%s", url.PathEscape(project)), token, nil)
	if payload.Error != nil {
		return project, nil, withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "gitlab_error": payload.Error})
	}
	return project, payload.Object, nil
}

type gitlabPayload struct {
	Object map[string]any
	List []map[string]any
	Error map[string]any
}

func gitlabRequest(method string, path string, token string, body map[string]any) gitlabPayload {
	var reader io.Reader
	if body != nil {
		content, _ := json.Marshal(body)
		reader = bytes.NewReader(content)
	}
	request, err := http.NewRequest(method, apiBase()+path, reader)
	if err != nil {
		return gitlabPayload{Error: map[string]any{"error": "gitlab_request_error", "detail": err.Error()}}
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("PRIVATE-TOKEN", token)
	request.Header.Set("User-Agent", "anip-gitlab-fronting-showcase")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return gitlabPayload{Error: map[string]any{"error": "gitlab_request_error", "detail": err.Error()}}
	}
	defer response.Body.Close()
	raw, _ := io.ReadAll(response.Body)
	payload := gitlabPayload{Object: map[string]any{}, List: []map[string]any{}}
	if len(raw) > 0 && raw[0] == '[' {
		_ = json.Unmarshal(raw, &payload.List)
	} else if len(raw) > 0 {
		_ = json.Unmarshal(raw, &payload.Object)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return gitlabPayload{Error: map[string]any{"error": "gitlab_http_error", "status": response.StatusCode, "detail": firstPayload(payload)}}
	}
	return payload
}

func apiBase() string {
	return strings.TrimRight(firstNonEmptyText(os.Getenv("GITLAB_API_BASE"), "https://gitlab.com/api/v4"), "/")
}

func firstPayload(payload gitlabPayload) any {
	if len(payload.List) > 0 {
		return payload.List
	}
	return payload.Object
}

func withMetadata(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, result map[string]any) map[string]any {
	result["capability_id"] = capability.CapabilityID
	result["selected_backend"] = plan.SelectedBinding
	result["semantic_input"] = plan.SemanticInput
	return result
}

func restricted(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, project string) map[string]any {
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "restricted",
		"project_id": project,
		"reason": "GitLab project is outside the configured ANIP project policy.",
	})
}

func writePreview(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, action string, path string, body map[string]any, projectPayload map[string]any) map[string]any {
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "prepared",
		"approval_required": true,
		"mutation_performed": false,
		"gitlab_action": action,
		"gitlab_metadata": projectSummary(projectPayload),
		"gitlab_request": map[string]any{"method": "POST", "path": path, "body": body},
		"note": "Prepared a GitLab request payload. No GitLab mutation was performed.",
	})
}

func projectSummary(payload map[string]any) map[string]any {
	return map[string]any{"id": payload["id"], "path_with_namespace": payload["path_with_namespace"], "default_branch": payload["default_branch"], "visibility": payload["visibility"], "web_url": payload["web_url"]}
}

func projectID(params map[string]any) string {
	if explicit := stringParam(params, "project_id"); explicit != "" {
		return explicit
	}
	namespace := strings.Trim(stringParam(params, "namespace"), "/")
	project := strings.Trim(stringParam(params, "project"), "/")
	if namespace != "" && project != "" {
		return namespace + "/" + project
	}
	return ""
}

func projectAllowed(project string) bool {
	key := strings.ToLower(project)
	blocked := csvSet("ANIP_GITLAB_BLOCKED_PROJECTS")
	allowed := csvSet("ANIP_GITLAB_ALLOWED_PROJECTS")
	if blocked[key] {
		return false
	}
	return len(allowed) == 0 || allowed[key]
}

func mutationEnabled(context BackendInvocationContext) bool {
	return os.Getenv("ANIP_GITLAB_ALLOW_MUTATION") == "true" && strings.TrimSpace(context.ApprovalGrant) != ""
}

func csvSet(name string) map[string]bool {
	result := map[string]bool{}
	for _, item := range strings.Split(os.Getenv(name), ",") {
		if value := strings.ToLower(strings.TrimSpace(item)); value != "" {
			result[value] = true
		}
	}
	return result
}

func boundedLimit(value any) int {
	limit, err := strconv.Atoi(stringValue(value))
	if err != nil {
		limit = 20
	}
	if limit < 1 {
		return 1
	}
	if limit > 50 {
		return 50
	}
	return limit
}

func stringList(value any) []string {
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
	seen := map[string]bool{}
	result := []string{}
	for _, item := range raw {
		text := strings.TrimSpace(stringValue(item))
		if text != "" && !seen[text] {
			seen[text] = true
			result = append(result, text)
		}
	}
	return result
}

func objectParam(value any) map[string]any {
	if typed, ok := value.(map[string]any); ok {
		return typed
	}
	return map[string]any{}
}

func stringParam(params map[string]any, name string) string {
	return strings.TrimSpace(stringValue(params[name]))
}

func stringValue(value any) string {
	if value == nil {
		return ""
	}
	return fmt.Sprint(value)
}

func firstNonEmptyText(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()
