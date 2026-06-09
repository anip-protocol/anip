package {{ANIP_JAVA_PACKAGE_NAME}};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

class JiraLiveBackendAdapterTest {

    @Test
    @EnabledIfEnvironmentVariable(named = "JIRA_API_TOKEN", matches = ".+")
    void executesLiveReadsAndPreparedPreviewsWithoutMutation() {
        JiraBackendAdapter.JiraConfig config = JiraBackendAdapter.JiraConfig.read();
        Map<String, Object> projects = JiraBackendAdapter.jira(config, "GET", "/rest/api/3/project/search", Map.of("maxResults", "1"), null);
        String projectKey = text(((Map<?, ?>) ((List<?>) projects.get("values")).get(0)).get("key"));
        Map<String, Object> search = JiraBackendAdapter.jira(config, "GET", "/rest/api/3/search/jql", Map.of("jql", "project = " + projectKey + " ORDER BY updated DESC", "maxResults", "2", "fields", "summary,status,issuetype,project"), null);
        List<?> issues = (List<?>) search.get("issues");
        assertFalse(issues.isEmpty());
        String issueKey = text(((Map<?, ?>) issues.get(0)).get("key"));
        String secondIssueKey = issues.size() > 1 ? text(((Map<?, ?>) issues.get(1)).get("key")) : issueKey;

        BackendAdapter adapter = BackendAdapter.defaultAdapter();
        assertEquals("completed", adapter.execute(capability("jira.backlog.search_context"), plan(Map.of("project_key", projectKey, "query", "test", "limit", 5)), new LinkedHashMap<>(Map.of("project_key", projectKey, "query", "test", "limit", 5)), null).get("execution_status"));
        assertEquals("completed", adapter.execute(capability("jira.issue.get_context"), plan(Map.of("issue_key", issueKey, "include_comments", true)), new LinkedHashMap<>(Map.of("issue_key", issueKey, "include_comments", true)), null).get("execution_status"));

        Map<String, Map<String, Object>> previews = Map.of(
            "jira.incident_bug.prepare", Map.of("project_key", projectKey, "summary", "ANIP smoke bug", "description", "Preview only", "severity", "sev3", "labels", List.of("anip-smoke")),
            "jira.story.prepare", Map.of("project_key", projectKey, "summary", "ANIP smoke story", "acceptance_criteria", List.of("Given ANIP", "Then no mutation"), "priority", "medium"),
            "jira.subtask.prepare", Map.of("parent_issue_key", issueKey, "summary", "ANIP smoke subtask", "description", "Preview only"),
            "jira.customer_escalation.comment.prepare", Map.of("issue_key", issueKey, "comment_purpose", "triage_update", "context", "Preview only", "visibility", "internal"),
            "jira.workflow_transition.request", Map.of("issue_key", issueKey, "target_status", "To Do", "reason", "Preview only", "comment", "Preview only"),
            "jira.sprint_move.request", Map.of("issue_keys", List.of(issueKey), "target_sprint", "preview-sprint", "reason", "Preview only"),
            "jira.assignee_change.request", Map.of("issue_key", issueKey, "assignee_ref", "preview-account-id", "reason", "Preview only"),
            "jira.issue_link.request", Map.of("source_issue_key", issueKey, "target_issue_key", secondIssueKey, "link_type", "Relates", "reason", "Preview only")
        );
        for (Map.Entry<String, Map<String, Object>> entry : previews.entrySet()) {
            Map<String, Object> result = adapter.execute(capability(entry.getKey()), plan(entry.getValue()), new LinkedHashMap<>(entry.getValue()), null);
            assertEquals("prepared", result.get("execution_status"));
            assertEquals(false, result.get("mutation_performed"));
        }
    }

    private static Map<String, Object> capability(String id) {
        return GeneratedRuntimeTarget.capabilities().stream().filter(item -> id.equals(item.get("capability_id"))).findFirst().orElseThrow();
    }

    private static Map<String, Object> plan(Map<String, Object> params) {
        Map<String, Object> plan = new LinkedHashMap<>();
        plan.put("selected_binding", null);
        plan.put("semantic_input", params);
        plan.put("adapter_input", params);
        plan.put("backend_input_contract", Map.of("mode", "explicit", "required", List.of(), "optional", List.of()));
        plan.put("unresolved_required_backend_inputs", List.of());
        return plan;
    }

    private static String text(Object value) {
        return value == null ? "" : value.toString().trim();
    }
}
