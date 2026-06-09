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
	token := strings.TrimSpace(os.Getenv("GITHUB_TOKEN"))
	if token == "" {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "github_error": map[string]any{"error": "missing_github_token"}}), nil
	}
	switch capability.CapabilityID {
	case "github.repo.search_context":
		return searchRepositoryContext(capability, plan, params, token)
	case "github.issue.prepare":
		return prepareOrCreateIssue(capability, plan, params, token, context)
	case "github.pr.comment.prepare":
		return preparePullRequestComment(capability, plan, params, token, context)
	case "github.workflow.dispatch.request":
		return prepareWorkflowDispatch(capability, plan, params, token, context)
	case "github.release_notes.prepare":
		return prepareReleaseNotes(capability, plan, params, token)
	default:
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_execution_stub"}), nil
	}
}

func searchRepositoryContext(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (map[string]any, error) {
	owner, repo := stringParam(params, "owner"), stringParam(params, "repo")
	if !repoAllowed(owner, repo) {
		return restricted(capability, plan, owner, repo), nil
	}
	limit := boundedLimit(params["limit"])
	query := strings.TrimSpace(fmt.Sprintf("repo:%s/%s %s", owner, repo, stringParam(params, "query")))
	payload := githubRequest("GET", "/search/issues?"+url.Values{"q": {query}, "per_page": {strconv.Itoa(limit)}}.Encode(), token, nil)
	if payload["error"] != nil {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "github_error": payload}), nil
	}
	items := make([]map[string]any, 0)
	if rawItems, ok := payload["items"].([]any); ok {
		for _, raw := range rawItems {
			item, ok := raw.(map[string]any)
			if !ok || len(items) >= limit {
				continue
			}
			kind := "issue"
			if item["pull_request"] != nil {
				kind = "pull_request"
			}
			items = append(items, map[string]any{
				"number": item["number"],
				"title": item["title"],
				"state": item["state"],
				"html_url": item["html_url"],
				"kind": kind,
			})
		}
	}
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "completed",
		"github_query": query,
		"result": map[string]any{"items": items, "count": len(items), "total_count": payload["total_count"]},
	}), nil
}

func prepareOrCreateIssue(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string, context BackendInvocationContext) (map[string]any, error) {
	owner, repo, repoPayload, errResult := repoMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	body := map[string]any{"title": stringParam(params, "title"), "body": stringParam(params, "body")}
	if labels := stringList(params["labels"]); len(labels) > 0 {
		body["labels"] = labels
	}
	if assignees := stringList(params["assignees"]); len(assignees) > 0 {
		body["assignees"] = assignees
	}
	preview := writePreview(capability, plan, "issues.create", fmt.Sprintf("/repos/%s/%s/issues", owner, repo), body, repoPayload)
	if !mutationEnabled(context) {
		return preview, nil
	}
	created := githubRequest("POST", fmt.Sprintf("/repos/%s/%s/issues", url.PathEscape(owner), url.PathEscape(repo)), token, body)
	if created["error"] != nil {
		preview["execution_status"] = "backend_error"
		preview["github_error"] = created
		return preview, nil
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["created_issue"] = map[string]any{"number": created["number"], "html_url": created["html_url"], "state": created["state"]}
	preview["note"] = "Created GitHub issue after the ANIP runtime validated and reserved an approval grant."
	return preview, nil
}

func preparePullRequestComment(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string, context BackendInvocationContext) (map[string]any, error) {
	owner, repo, repoPayload, errResult := repoMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	pullNumber := stringParam(params, "pull_number")
	pull := githubRequest("GET", fmt.Sprintf("/repos/%s/%s/pulls/%s", url.PathEscape(owner), url.PathEscape(repo), url.PathEscape(pullNumber)), token, nil)
	if pull["error"] != nil {
		return withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "github_error": pull}), nil
	}
	body := map[string]any{"body": strings.TrimSpace(fmt.Sprintf("[%s] %s", firstNonEmptyText(stringParam(params, "comment_purpose"), "triage_update"), stringParam(params, "context")))}
	preview := writePreview(capability, plan, "issues.createComment", fmt.Sprintf("/repos/%s/%s/issues/%s/comments", owner, repo, pullNumber), body, repoPayload)
	preview["pull_request"] = map[string]any{"number": pull["number"], "title": pull["title"], "state": pull["state"]}
	if !mutationEnabled(context) {
		return preview, nil
	}
	posted := githubRequest("POST", fmt.Sprintf("/repos/%s/%s/issues/%s/comments", url.PathEscape(owner), url.PathEscape(repo), url.PathEscape(pullNumber)), token, body)
	if posted["error"] != nil {
		preview["execution_status"] = "backend_error"
		preview["github_error"] = posted
		return preview, nil
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["posted_comment"] = map[string]any{"id": posted["id"], "html_url": posted["html_url"]}
	return preview, nil
}

func prepareWorkflowDispatch(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string, context BackendInvocationContext) (map[string]any, error) {
	owner, repo, repoPayload, errResult := repoMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	workflowID := stringParam(params, "workflow_id")
	body := map[string]any{"ref": stringParam(params, "ref"), "inputs": objectParam(params["inputs"])}
	preview := writePreview(capability, plan, "actions.createWorkflowDispatch", fmt.Sprintf("/repos/%s/%s/actions/workflows/%s/dispatches", owner, repo, workflowID), body, repoPayload)
	if !mutationEnabled(context) {
		return preview, nil
	}
	dispatched := githubRequest("POST", fmt.Sprintf("/repos/%s/%s/actions/workflows/%s/dispatches", url.PathEscape(owner), url.PathEscape(repo), url.PathEscape(workflowID)), token, body)
	if dispatched["error"] != nil {
		preview["execution_status"] = "backend_error"
		preview["github_error"] = dispatched
		return preview, nil
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["dispatched_workflow"] = map[string]any{"workflow_id": workflowID, "ref": body["ref"]}
	return preview, nil
}

func prepareReleaseNotes(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (map[string]any, error) {
	owner, repo, repoPayload, errResult := repoMetadata(capability, plan, params, token)
	if errResult != nil {
		return errResult, nil
	}
	releaseRange := stringParam(params, "range")
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "completed",
		"result": map[string]any{
			"title": fmt.Sprintf("Release notes for %s/%s %s", owner, repo, releaseRange),
			"audience": firstNonEmptyText(stringParam(params, "audience"), "internal"),
			"repository": repoSummary(repoPayload),
			"range": releaseRange,
			"sections": []map[string]any{
				{"title": "Highlights", "items": []string{"Review bounded GitHub context before publishing release notes."}},
				{"title": "Governance", "items": []string{"This capability drafts content only and does not create a GitHub release."}},
			},
		},
		"mutation_performed": false,
	}), nil
}

func repoMetadata(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) (string, string, map[string]any, map[string]any) {
	owner, repo := stringParam(params, "owner"), stringParam(params, "repo")
	if !repoAllowed(owner, repo) {
		return owner, repo, nil, restricted(capability, plan, owner, repo)
	}
	payload := githubRequest("GET", fmt.Sprintf("/repos/%s/%s", url.PathEscape(owner), url.PathEscape(repo)), token, nil)
	if payload["error"] != nil {
		return owner, repo, nil, withMetadata(capability, plan, map[string]any{"execution_status": "backend_error", "github_error": payload})
	}
	return owner, repo, payload, nil
}

func githubRequest(method string, path string, token string, body map[string]any) map[string]any {
	var reader io.Reader
	if body != nil {
		content, _ := json.Marshal(body)
		reader = bytes.NewReader(content)
	}
	request, err := http.NewRequest(method, "https://api.github.com"+path, reader)
	if err != nil {
		return map[string]any{"error": "github_request_error", "detail": err.Error()}
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("User-Agent", "anip-github-fronting-showcase")
	request.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return map[string]any{"error": "github_request_error", "detail": err.Error()}
	}
	defer response.Body.Close()
	raw, _ := io.ReadAll(response.Body)
	payload := map[string]any{}
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &payload)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return map[string]any{"error": "github_http_error", "status": response.StatusCode, "detail": payload}
	}
	return payload
}

func withMetadata(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, result map[string]any) map[string]any {
	result["capability_id"] = capability.CapabilityID
	result["selected_backend"] = plan.SelectedBinding
	result["semantic_input"] = plan.SemanticInput
	return result
}

func restricted(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, owner string, repo string) map[string]any {
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "restricted",
		"repository": map[string]any{"owner": owner, "repo": repo},
		"reason": "GitHub repository is outside the configured ANIP repository policy.",
	})
}

func writePreview(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, action string, path string, body map[string]any, repoPayload map[string]any) map[string]any {
	return withMetadata(capability, plan, map[string]any{
		"execution_status": "prepared",
		"approval_required": true,
		"mutation_performed": false,
		"github_action": action,
		"github_metadata": repoSummary(repoPayload),
		"github_request": map[string]any{"method": "POST", "path": path, "body": body},
		"note": "Prepared a GitHub request payload. No GitHub mutation was performed.",
	})
}

func repoSummary(payload map[string]any) map[string]any {
	owner := ""
	if rawOwner, ok := payload["owner"].(map[string]any); ok {
		owner = stringValue(rawOwner["login"])
	}
	return map[string]any{"owner": owner, "repo": payload["name"], "default_branch": payload["default_branch"], "private": payload["private"], "html_url": payload["html_url"]}
}

func repoAllowed(owner string, repo string) bool {
	key := strings.ToLower(owner + "/" + repo)
	blocked := csvSet("ANIP_GITHUB_BLOCKED_REPOS")
	allowed := csvSet("ANIP_GITHUB_ALLOWED_REPOS")
	if blocked[key] {
		return false
	}
	return len(allowed) == 0 || allowed[key]
}

func mutationEnabled(context BackendInvocationContext) bool {
	return os.Getenv("ANIP_GITHUB_ALLOW_MUTATION") == "true" && strings.TrimSpace(context.ApprovalGrant) != ""
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
