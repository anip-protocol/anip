package {{ANIP_JAVA_PACKAGE_NAME}};

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.anip.service.InvocationContext;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;

@FunctionalInterface
public interface BackendAdapter {

    Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context);

    static BackendAdapter defaultAdapter() {
        return new JiraBackendAdapter();
    }
}

final class JiraBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newHttpClient();

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        List<String> unresolved = stringList(plan.get("unresolved_required_backend_inputs"));
        if (!unresolved.isEmpty()) {
            return result(capability, plan, "backend_input_incomplete", Map.of("unresolved_required_backend_inputs", unresolved));
        }
        String id = text(capability.get("capability_id"));
        JiraConfig config = JiraConfig.read();
        return switch (id) {
            case "jira.backlog.search_context" -> searchBacklog(capability, plan, params, config);
            case "jira.issue.get_context" -> getIssueContext(capability, plan, params, config);
            case "jira.release_notes.prepare" -> prepareReleaseNotes(capability, plan, params, config);
            case "jira.incident_bug.prepare" -> prepareIssueCreate(capability, plan, params, "Bug");
            case "jira.story.prepare" -> prepareIssueCreate(capability, plan, params, "Story");
            case "jira.subtask.prepare" -> prepareSubtask(capability, plan, params, config);
            case "jira.customer_escalation.comment.prepare" -> preview(capability, plan, "add_comment", Map.of("method", "POST", "path", "/rest/api/3/issue/" + text(params.get("issue_key")) + "/comment", "body", Map.of("body", adf("[" + text(params.get("comment_purpose")) + "] " + text(params.get("context"))), "visibility", firstNonEmpty(text(params.get("visibility")), "internal"))), Map.of("issue_key", params.get("issue_key"), "visibility", firstNonEmpty(text(params.get("visibility")), "internal"), "comment_purpose", params.get("comment_purpose")));
            case "jira.workflow_transition.request" -> preview(capability, plan, "transition_issue", Map.of("method", "POST", "path", "/rest/api/3/issue/" + text(params.get("issue_key")) + "/transitions", "body", Map.of("transition", Map.of("id", params.get("target_status")))), Map.of("issue_key", params.get("issue_key"), "target_status", params.get("target_status")));
            case "jira.sprint_move.request" -> preview(capability, plan, "move_issues_to_sprint", Map.of("method", "POST", "path", "/rest/agile/1.0/sprint/" + text(params.get("target_sprint")) + "/issue", "body", Map.of("issues", listValue(params.get("issue_keys")))), Map.of("issue_keys", listValue(params.get("issue_keys")), "target_sprint", params.get("target_sprint")));
            case "jira.assignee_change.request" -> preview(capability, plan, "assign_issue", Map.of("method", "PUT", "path", "/rest/api/3/issue/" + text(params.get("issue_key")) + "/assignee", "body", Map.of("accountId", params.get("assignee_ref"))), Map.of("issue_key", params.get("issue_key"), "assignee_ref", params.get("assignee_ref")));
            case "jira.issue_link.request" -> preview(capability, plan, "link_issues", Map.of("method", "POST", "path", "/rest/api/3/issueLink", "body", Map.of("type", Map.of("name", params.get("link_type")), "inwardIssue", Map.of("key", params.get("source_issue_key")), "outwardIssue", Map.of("key", params.get("target_issue_key")), "comment", Map.of("body", adf(params.get("reason"))))), Map.of("requested_link_type", params.get("link_type")));
            default -> result(capability, plan, "backend_execution_stub", Map.of("note", "No Jira custom handler is registered for this capability."));
        };
    }

    private static Map<String, Object> searchBacklog(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, JiraConfig config) {
        String jql = issueQuery(text(params.get("project_key")), text(params.get("query")));
        if (!text(params.get("issue_type")).isEmpty()) jql += " AND issuetype = \"" + safeJql(params.get("issue_type")) + "\"";
        if (!text(params.get("status")).isEmpty()) jql += " AND status = \"" + safeJql(params.get("status")) + "\"";
        if (config == null) return result(capability, plan, "backend_not_configured", Map.of("jql_preview", jql));
        Map<String, Object> payload = searchIssues(config, jql, boundedLimit(params.get("limit"), 25, 50), "summary,status,issuetype,project,assignee,priority");
        if (payload.containsKey("error")) return backendError(capability, plan, payload);
        List<Map<String, Object>> issues = issueSummaries(payload.get("issues"));
        return result(capability, plan, "completed", Map.of("jql", jql, "result", Map.of("issues", issues, "count", issues.size(), "is_last", payload.get("isLast"))));
    }

    private static Map<String, Object> getIssueContext(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, JiraConfig config) {
        String issueKey = text(params.get("issue_key"));
        if (config == null) return result(capability, plan, "backend_not_configured", Map.of("path_preview", "/rest/api/3/issue/" + issueKey));
        Map<String, Object> payload = jira(config, "GET", "/rest/api/3/issue/" + url(issueKey), Map.of("fields", "summary,status,issuetype,project,assignee,priority,description"), null);
        if (payload.containsKey("error")) return backendError(capability, plan, payload);
        return result(capability, plan, "completed", Map.of("result", issueSummary(payload)));
    }

    private static Map<String, Object> prepareReleaseNotes(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, JiraConfig config) {
        String releaseRef = text(params.get("release_ref"));
        String audience = firstNonEmpty(text(params.get("audience")), "internal");
        String jql = "project = \"" + safeJql(params.get("project_key")) + "\" AND " + (releaseRef.equalsIgnoreCase("unversioned") ? "fixVersion is EMPTY" : "fixVersion = \"" + safeJql(releaseRef) + "\"");
        if (!text(params.get("issue_query")).isEmpty()) jql += " AND text ~ \"" + safeJql(params.get("issue_query")) + "\"";
        jql += " ORDER BY priority DESC, updated DESC";
        List<Map<String, Object>> issues = new ArrayList<>();
        if (config != null) {
            Map<String, Object> payload = searchIssues(config, jql, boundedLimit(params.get("limit"), 20, 50), "summary,status,issuetype,project");
            if (payload.containsKey("error")) return backendError(capability, plan, payload);
            issues = issueSummaries(payload.get("issues"));
        }
        return result(capability, plan, "prepared", Map.of("jql", jql, "result", Map.of("audience", audience, "issue_count", issues.size(), "issues", issues, "draft", releaseDraft(audience, releaseRef, issues)), "note", "Prepared release notes only. No Jira mutation or publication was performed."));
    }

    private static Map<String, Object> prepareIssueCreate(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String issueType) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("project", Map.of("key", params.get("project_key")));
        fields.put("issuetype", Map.of("name", issueType));
        fields.put("summary", text(params.get("summary")));
        if (text(capability.get("capability_id")).equals("jira.incident_bug.prepare")) {
            fields.put("description", adf(params.get("description")));
            fields.put("priority", Map.of("name", priorityForSeverity(params.get("severity"))));
        } else {
            fields.put("description", adf("Acceptance criteria:\n" + text(params.get("acceptance_criteria"))));
            if (!text(params.get("priority")).isEmpty()) fields.put("priority", Map.of("name", capitalize(text(params.get("priority")))));
        }
        List<String> labels = labels(params.get("labels"));
        if (!labels.isEmpty()) fields.put("labels", labels);
        return preview(capability, plan, "create_issue", Map.of("method", "POST", "path", "/rest/api/3/issue", "body", Map.of("fields", fields)), Map.of("project_key", params.get("project_key"), "requested_issue_type", issueType));
    }

    private static Map<String, Object> prepareSubtask(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, JiraConfig config) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("parent", Map.of("key", params.get("parent_issue_key")));
        fields.put("issuetype", Map.of("name", "Sub-task"));
        fields.put("summary", text(params.get("summary")));
        fields.put("description", adf(params.get("description")));
        if (config != null) {
            Map<String, Object> parent = jira(config, "GET", "/rest/api/3/issue/" + url(text(params.get("parent_issue_key"))), Map.of("fields", "project"), null);
            String projectKey = nested(parent, "fields", "project", "key");
            if (!projectKey.isEmpty()) fields.put("project", Map.of("key", projectKey));
            if (!text(parent.get("id")).isEmpty()) fields.put("parent", Map.of("id", parent.get("id")));
        }
        return preview(capability, plan, "create_subtask", Map.of("method", "POST", "path", "/rest/api/3/issue", "body", Map.of("fields", fields)), Map.of("parent_issue_key", params.get("parent_issue_key")));
    }

    private static Map<String, Object> preview(Map<String, Object> capability, Map<String, Object> plan, String action, Map<String, Object> request, Map<String, Object> metadata) {
        Map<String, Object> extra = new LinkedHashMap<>();
        extra.put("approval_required", text(capability.get("operation_type")).equals("approval_gated") || text(capability.get("execution_posture")).equals("prepare_only"));
        extra.put("mutation_performed", false);
        extra.put("jira_action", action);
        extra.put("jira_request_preview", request);
        extra.put("jira_metadata", metadata);
        extra.put("note", "Prepared a governed Jira request preview. No Jira mutation was performed.");
        return result(capability, plan, "prepared", extra);
    }

    private static Map<String, Object> result(Map<String, Object> capability, Map<String, Object> plan, String status, Map<String, Object> extra) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("execution_status", status);
        result.put("capability_id", capability.get("capability_id"));
        result.put("selected_backend", plan.get("selected_binding"));
        result.put("semantic_input", plan.get("semantic_input"));
        result.put("backend_input_contract", plan.get("backend_input_contract"));
        result.putAll(extra);
        return result;
    }

    private static Map<String, Object> backendError(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> payload) {
        return result(capability, plan, "backend_error", Map.of("jira_error", payload));
    }

    private static Map<String, Object> searchIssues(JiraConfig config, String jql, int limit, String fields) {
        return jira(config, "GET", "/rest/api/3/search/jql", Map.of("jql", jql, "maxResults", Integer.toString(limit), "fields", fields), null);
    }

    static Map<String, Object> jira(JiraConfig config, String method, String path, Map<String, String> query, Map<String, Object> body) {
        try {
            StringJoiner joiner = new StringJoiner("&");
            for (Map.Entry<String, String> entry : query.entrySet()) joiner.add(url(entry.getKey()) + "=" + url(entry.getValue()));
            URI uri = URI.create(config.baseUrl + path + (query.isEmpty() ? "" : "?" + joiner));
            HttpRequest.Builder builder = HttpRequest.newBuilder(uri).header("Accept", "application/json").header("Authorization", "Basic " + Base64.getEncoder().encodeToString((config.email + ":" + config.token).getBytes(StandardCharsets.UTF_8)));
            if (body == null) builder.method(method, HttpRequest.BodyPublishers.noBody());
            else builder.method(method, HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body))).header("Content-Type", "application/json");
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            Map<String, Object> payload = response.body().isBlank() ? new LinkedHashMap<>() : MAPPER.readValue(response.body(), new TypeReference<>() {});
            if (response.statusCode() < 200 || response.statusCode() >= 300) return Map.of("error", "jira_http_error", "status", response.statusCode(), "detail", payload);
            return payload;
        } catch (Exception exc) {
            return Map.of("error", "jira_http_error", "detail", exc.toString());
        }
    }

    private static String issueQuery(String projectKey, String query) {
        String jql = "project = \"" + safeJql(projectKey) + "\"";
        if (!query.isBlank()) jql += " AND text ~ \"" + safeJql(query) + "\"";
        return jql + " ORDER BY updated DESC";
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> issueSummaries(Object value) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (value instanceof List<?> items) for (Object item : items) if (item instanceof Map<?, ?> issue) result.add(issueSummary((Map<String, Object>) issue));
        return result;
    }

    private static Map<String, Object> issueSummary(Map<String, Object> issue) {
        return Map.of("key", issue.get("key"), "summary", nested(issue, "fields", "summary"), "status", nested(issue, "fields", "status", "name"), "issue_type", nested(issue, "fields", "issuetype", "name"), "project_key", nested(issue, "fields", "project", "key"), "assignee", nested(issue, "fields", "assignee", "displayName"), "priority", nested(issue, "fields", "priority", "name"));
    }

    private static Map<String, Object> adf(Object value) {
        return Map.of("type", "doc", "version", 1, "content", List.of(Map.of("type", "paragraph", "content", List.of(Map.of("type", "text", "text", text(value))))));
    }

    private static String releaseDraft(String audience, String releaseRef, List<Map<String, Object>> issues) {
        String heading = "Release " + releaseRef + " notes for " + audience;
        if (issues.isEmpty()) return heading + "\n\nNo matching Jira issues were returned for the bounded query.";
        List<String> lines = new ArrayList<>(List.of(heading, ""));
        for (Map<String, Object> issue : issues) lines.add("- " + issue.get("key") + ": " + issue.get("summary") + " (" + issue.get("status") + ")");
        return String.join("\n", lines);
    }

    private static int boundedLimit(Object value, int defaultValue, int max) {
        try {
            return Math.max(1, Math.min(Integer.parseInt(text(value)), max));
        } catch (Exception ignored) {
            return defaultValue;
        }
    }

    private static String safeJql(Object value) {
        return text(value).replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static List<String> listValue(Object value) {
        List<String> result = new ArrayList<>();
        if (value instanceof List<?> items) {
            for (Object item : items) addUnique(result, text(item));
        } else if (!text(value).isEmpty()) {
            for (String item : text(value).split(",")) addUnique(result, item.trim());
        }
        return result;
    }

    private static List<String> labels(Object value) {
        List<String> result = new ArrayList<>();
        for (String item : listValue(value)) {
            String label = item.toLowerCase().replaceAll("[^a-z0-9_.-]+", "-").replaceAll("^-+|-+$", "");
            if (!label.isEmpty()) result.add(label);
        }
        return result;
    }

    private static void addUnique(List<String> values, String value) {
        if (!value.isBlank() && !values.contains(value)) values.add(value);
    }

    private static String priorityForSeverity(Object value) {
        return switch (text(value).toLowerCase()) {
            case "sev1", "sev2" -> "High";
            case "sev4" -> "Low";
            default -> "Medium";
        };
    }

    private static String text(Object value) {
        return value == null ? "" : value.toString().trim();
    }

    @SuppressWarnings("unchecked")
    private static String nested(Map<String, Object> value, String... path) {
        Object current = value;
        for (String key : path) {
            if (!(current instanceof Map<?, ?> record)) return "";
            current = ((Map<String, Object>) record).get(key);
        }
        return text(current);
    }

    private static List<String> stringList(Object value) {
        List<String> result = new ArrayList<>();
        if (value instanceof List<?> items) for (Object item : items) result.add(text(item));
        return result;
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) if (!value.isBlank()) return value;
        return "";
    }

    private static String capitalize(String value) {
        return value.isBlank() ? value : value.substring(0, 1).toUpperCase() + value.substring(1);
    }

    private static String url(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    record JiraConfig(String baseUrl, String email, String token) {
        static JiraConfig read() {
            String baseUrl = System.getenv().getOrDefault("JIRA_BASE_URL", "").replaceAll("/+$", "");
            String email = System.getenv().getOrDefault("JIRA_EMAIL", "");
            String token = System.getenv().getOrDefault("JIRA_API_TOKEN", "");
            if (baseUrl.isBlank() || email.isBlank() || token.isBlank()) return null;
            return new JiraConfig(baseUrl, email, token);
        }
    }
}
