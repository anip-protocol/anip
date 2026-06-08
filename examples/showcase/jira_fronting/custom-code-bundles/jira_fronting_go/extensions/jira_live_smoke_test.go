package extensions

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"testing"

	"{{ANIP_GO_MODULE_PATH}}/generated"
)

func TestJiraLiveBackendAdapter(t *testing.T) {
	config := readJiraConfig()
	if config == nil {
		t.Skip("Jira credentials are not configured")
	}
	projects := jiraLiveGet(t, config, "/rest/api/3/project/search", map[string]string{"maxResults": "1"})["values"].([]any)
	if len(projects) == 0 {
		t.Fatal("expected at least one Jira project")
	}
	projectKey := projects[0].(map[string]any)["key"].(string)
	issues := jiraLiveGet(t, config, "/rest/api/3/search/jql", map[string]string{"jql": "project = " + projectKey + " ORDER BY updated DESC", "maxResults": "2", "fields": "summary,status,issuetype,project"})["issues"].([]any)
	if len(issues) == 0 {
		t.Fatal("expected at least one Jira issue")
	}
	issueKey := issues[0].(map[string]any)["key"].(string)
	secondIssueKey := issueKey
	if len(issues) > 1 {
		secondIssueKey = issues[1].(map[string]any)["key"].(string)
	}
	search := executeForTest(t, "jira.backlog.search_context", map[string]any{"project_key": projectKey, "query": "test", "limit": 5})
	if search["execution_status"] != "completed" {
		t.Fatalf("expected search completed, got %#v", search)
	}
	issue := executeForTest(t, "jira.issue.get_context", map[string]any{"issue_key": issueKey, "include_comments": true})
	if issue["execution_status"] != "completed" {
		t.Fatalf("expected issue completed, got %#v", issue)
	}
	cases := map[string]map[string]any{
		"jira.incident_bug.prepare":                  {"project_key": projectKey, "summary": "ANIP smoke bug", "description": "Preview only", "severity": "sev3", "labels": []any{"anip-smoke"}},
		"jira.story.prepare":                         {"project_key": projectKey, "summary": "ANIP smoke story", "acceptance_criteria": []any{"Given ANIP", "Then no mutation"}, "priority": "medium"},
		"jira.subtask.prepare":                       {"parent_issue_key": issueKey, "summary": "ANIP smoke subtask", "description": "Preview only"},
		"jira.customer_escalation.comment.prepare":   {"issue_key": issueKey, "comment_purpose": "triage_update", "context": "Preview only", "visibility": "internal"},
		"jira.workflow_transition.request":           {"issue_key": issueKey, "target_status": "To Do", "reason": "Preview only", "comment": "Preview only"},
		"jira.sprint_move.request":                   {"issue_keys": []any{issueKey}, "target_sprint": "preview-sprint", "reason": "Preview only"},
		"jira.assignee_change.request":               {"issue_key": issueKey, "assignee_ref": "preview-account-id", "reason": "Preview only"},
		"jira.issue_link.request":                    {"source_issue_key": issueKey, "target_issue_key": secondIssueKey, "link_type": "Relates", "reason": "Preview only"},
	}
	for id, params := range cases {
		result := executeForTest(t, id, params)
		if result["execution_status"] != "prepared" || result["mutation_performed"] != false {
			t.Fatalf("%s expected prepared without mutation, got %#v", id, result)
		}
	}
}

func executeForTest(t *testing.T, capabilityID string, params map[string]any) map[string]any {
	t.Helper()
	capability := capabilityForTest(t, capabilityID)
	plan := generated.BackendInvocationPlan{SemanticInput: params, AdapterInput: params, BackendInputContract: generated.EffectiveBackendInputContract{Mode: "explicit"}}
	result, err := BackendAdapterInstance.Execute(capability, plan, params, BackendInvocationContext{})
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func capabilityForTest(t *testing.T, capabilityID string) generated.GeneratedCapabilityRuntimeMetadata {
	t.Helper()
	for _, capability := range generated.GeneratedCapabilityMetadata {
		if capability.CapabilityID == capabilityID {
			return capability
		}
	}
	t.Fatalf("missing capability %s", capabilityID)
	return generated.GeneratedCapabilityRuntimeMetadata{}
}

func jiraLiveGet(t *testing.T, config *jiraConfig, path string, query map[string]string) map[string]any {
	t.Helper()
	target, _ := url.Parse(config.BaseURL + path)
	values := target.Query()
	for key, value := range query {
		values.Set(key, value)
	}
	target.RawQuery = values.Encode()
	request, _ := http.NewRequest("GET", target.String(), nil)
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Authorization", "Basic "+base64.StdEncoding.EncodeToString([]byte(os.Getenv("JIRA_EMAIL")+":"+os.Getenv("JIRA_API_TOKEN"))))
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var payload map[string]any
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatal(err)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		t.Fatalf("Jira GET %s failed: %#v", path, payload)
	}
	return payload
}
