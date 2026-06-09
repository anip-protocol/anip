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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@FunctionalInterface
public interface BackendAdapter {

    Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context);

    static BackendAdapter defaultAdapter() {
        return new GitLabBackendAdapter();
    }
}

final class GitLabBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newHttpClient();

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        List<String> unresolved = stringList(plan.get("unresolved_required_backend_inputs"));
        if (!unresolved.isEmpty()) {
            return result(capability, plan, "backend_input_incomplete", record("unresolved_required_backend_inputs", unresolved));
        }
        String token = System.getenv().getOrDefault("GITLAB_TOKEN", "").trim();
        if (token.isBlank()) return result(capability, plan, "backend_error", record("gitlab_error", record("error", "missing_gitlab_token")));
        return switch (text(capability.get("capability_id"))) {
            case "gitlab.project.search_context" -> searchProjectContext(capability, plan, params, token);
            case "gitlab.issue.prepare" -> prepareOrCreateIssue(capability, plan, params, token, context);
            case "gitlab.mr.comment.prepare" -> prepareMergeRequestComment(capability, plan, params, token, context);
            case "gitlab.pipeline.trigger.request" -> preparePipelineTrigger(capability, plan, params, token);
            case "gitlab.release_notes.prepare" -> prepareReleaseNotes(capability, plan, params, token);
            default -> result(capability, plan, "backend_execution_stub", record("note", "No GitLab custom handler is registered for this capability."));
        };
    }

    private static Map<String, Object> searchProjectContext(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String project = projectId(params);
        if (!projectAllowed(project)) return restricted(capability, plan, project);
        int limit = boundedLimit(params.get("limit"), 20, 50);
        String query = text(params.get("query"));
        Map<String, Object> issues = gitlab("GET", "/projects/" + urlPath(project) + "/issues?search=" + url(query) + "&per_page=" + limit, token, null);
        Map<String, Object> mrs = gitlab("GET", "/projects/" + urlPath(project) + "/merge_requests?search=" + url(query) + "&per_page=" + limit, token, null);
        if (issues.containsKey("error")) return result(capability, plan, "backend_error", record("gitlab_error", issues));
        if (mrs.containsKey("error")) return result(capability, plan, "backend_error", record("gitlab_error", mrs));
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> item : mapList(issues.get("items"))) {
            if (items.size() >= limit) break;
            items.add(record("kind", "issue", "iid", item.get("iid"), "title", item.get("title"), "state", item.get("state"), "web_url", item.get("web_url")));
        }
        for (Map<String, Object> item : mapList(mrs.get("items"))) {
            if (items.size() >= limit) break;
            items.add(record("kind", "merge_request", "iid", item.get("iid"), "title", item.get("title"), "state", item.get("state"), "web_url", item.get("web_url")));
        }
        return result(capability, plan, "completed", record("gitlab_query", query, "result", record("items", items, "count", items.size(), "project_id", project)));
    }

    private static Map<String, Object> prepareOrCreateIssue(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token, InvocationContext context) {
        ProjectContext project = projectMetadata(capability, plan, params, token);
        if (project.error != null) return project.error;
        Map<String, Object> body = record("title", text(params.get("title")), "description", firstNonBlank(params.get("body"), params.get("description")));
        List<String> labels = stringList(params.get("labels"));
        if (!labels.isEmpty()) body.put("labels", String.join(",", labels));
        Map<String, Object> preview = writePreview(capability, plan, "issues.create", "/projects/" + project.id + "/issues", body, project.payload);
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> created = gitlab("POST", "/projects/" + urlPath(project.id) + "/issues", token, body);
        if (created.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("gitlab_error", created);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("created_issue", record("iid", created.get("iid"), "web_url", created.get("web_url"), "state", created.get("state")));
        preview.put("note", "Created GitLab issue after the ANIP runtime validated and reserved an approval grant.");
        return preview;
    }

    private static Map<String, Object> prepareMergeRequestComment(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token, InvocationContext context) {
        ProjectContext project = projectMetadata(capability, plan, params, token);
        if (project.error != null) return project.error;
        String iid = text(params.get("merge_request_iid"));
        Map<String, Object> mr = gitlab("GET", "/projects/" + urlPath(project.id) + "/merge_requests/" + urlPath(iid), token, null);
        if (mr.containsKey("error")) return result(capability, plan, "backend_error", record("gitlab_error", mr));
        Map<String, Object> body = record("body", ("[" + firstNonBlank(params.get("comment_purpose"), "triage_update") + "] " + text(params.get("context"))).trim());
        Map<String, Object> preview = writePreview(capability, plan, "merge_requests.createNote", "/projects/" + project.id + "/merge_requests/" + iid + "/notes", body, project.payload);
        preview.put("merge_request", record("iid", mr.get("iid"), "title", mr.get("title"), "state", mr.get("state")));
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> posted = gitlab("POST", "/projects/" + urlPath(project.id) + "/merge_requests/" + urlPath(iid) + "/notes", token, body);
        if (posted.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("gitlab_error", posted);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("posted_comment", record("id", posted.get("id")));
        return preview;
    }

    private static Map<String, Object> preparePipelineTrigger(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        ProjectContext project = projectMetadata(capability, plan, params, token);
        if (project.error != null) return project.error;
        Map<String, Object> body = record("ref", text(params.get("ref")), "variables", objectMap(params.get("variables")), "purpose", text(params.get("pipeline_purpose")));
        return writePreview(capability, plan, "pipeline.trigger", "/projects/" + project.id + "/pipeline", body, project.payload);
    }

    private static Map<String, Object> prepareReleaseNotes(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        ProjectContext project = projectMetadata(capability, plan, params, token);
        if (project.error != null) return project.error;
        String range = text(params.get("range"));
        return result(capability, plan, "completed", record(
            "mutation_performed", false,
            "result", record(
                "title", "Release notes for " + firstNonBlank(project.payload.get("path_with_namespace"), project.id) + " " + range,
                "audience", firstNonBlank(params.get("audience"), "internal"),
                "project", projectSummary(project.payload),
                "range", range,
                "sections", List.of(
                    record("title", "Highlights", "items", List.of("Review bounded GitLab context before publishing release notes.")),
                    record("title", "Governance", "items", List.of("This capability drafts content only and does not create a GitLab release."))
                )
            )
        ));
    }

    private static ProjectContext projectMetadata(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String project = projectId(params);
        if (!projectAllowed(project)) return new ProjectContext(project, null, restricted(capability, plan, project));
        Map<String, Object> payload = gitlab("GET", "/projects/" + urlPath(project), token, null);
        if (payload.containsKey("error")) return new ProjectContext(project, null, result(capability, plan, "backend_error", record("gitlab_error", payload)));
        return new ProjectContext(project, payload, null);
    }

    static Map<String, Object> gitlab(String method, String path, String token, Map<String, Object> body) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(apiBase() + path))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("PRIVATE-TOKEN", token)
                .header("User-Agent", "anip-gitlab-fronting-showcase");
            if ("POST".equals(method)) builder.POST(HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body == null ? Map.of() : body)));
            else builder.GET();
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            Map<String, Object> payload = response.body().isBlank() ? new LinkedHashMap<>() : parseGitLabBody(response.body());
            if (response.statusCode() < 200 || response.statusCode() >= 300) return record("error", "gitlab_http_error", "status", response.statusCode(), "detail", payload);
            return payload;
        } catch (Exception exc) {
            return record("error", "gitlab_http_error", "detail", exc.toString());
        }
    }

    private static Map<String, Object> parseGitLabBody(String body) throws Exception {
        String trimmed = body.trim();
        if (trimmed.startsWith("[")) return record("items", MAPPER.readValue(trimmed, new TypeReference<List<Map<String, Object>>>() {}));
        return MAPPER.readValue(trimmed, new TypeReference<>() {});
    }

    private static Map<String, Object> writePreview(Map<String, Object> capability, Map<String, Object> plan, String action, String path, Map<String, Object> body, Map<String, Object> projectPayload) {
        return result(capability, plan, "prepared", record(
            "approval_required", true,
            "mutation_performed", false,
            "gitlab_action", action,
            "gitlab_metadata", projectSummary(projectPayload),
            "gitlab_request", record("method", "POST", "path", path, "body", body),
            "note", "Prepared a GitLab request payload. No GitLab mutation was performed."
        ));
    }

    private static Map<String, Object> projectSummary(Map<String, Object> payload) {
        return record("id", payload.get("id"), "path_with_namespace", payload.get("path_with_namespace"), "default_branch", payload.get("default_branch"), "visibility", payload.get("visibility"), "web_url", payload.get("web_url"));
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

    private static Map<String, Object> restricted(Map<String, Object> capability, Map<String, Object> plan, String project) {
        return result(capability, plan, "restricted", record("project_id", project, "reason", "GitLab project is outside the configured ANIP project policy."));
    }

    private static String projectId(Map<String, Object> params) {
        String explicit = text(params.get("project_id"));
        if (!explicit.isBlank()) return explicit;
        String namespace = text(params.get("namespace")).replaceAll("^/+|/+$", "");
        String project = text(params.get("project")).replaceAll("^/+|/+$", "");
        return !namespace.isBlank() && !project.isBlank() ? namespace + "/" + project : "";
    }

    private static boolean projectAllowed(String project) {
        String key = project.toLowerCase();
        List<String> blocked = csvEnv("ANIP_GITLAB_BLOCKED_PROJECTS");
        List<String> allowed = csvEnv("ANIP_GITLAB_ALLOWED_PROJECTS");
        return !blocked.contains(key) && (allowed.isEmpty() || allowed.contains(key));
    }

    private static boolean mutationEnabled(InvocationContext context) {
        String grant = context == null ? "" : text(context.getApprovalGrant());
        return "true".equals(System.getenv().getOrDefault("ANIP_GITLAB_ALLOW_MUTATION", "")) && !grant.isBlank();
    }

    private static String apiBase() {
        String raw = System.getenv().getOrDefault("GITLAB_API_BASE", "https://gitlab.com/api/v4").trim();
        return raw.endsWith("/") ? raw.substring(0, raw.length() - 1) : raw;
    }

    private static List<String> csvEnv(String name) {
        List<String> result = new ArrayList<>();
        for (String item : System.getenv().getOrDefault(name, "").split(",")) {
            String value = item.trim().toLowerCase();
            if (!value.isBlank() && !result.contains(value)) result.add(value);
        }
        return result;
    }

    private static int boundedLimit(Object value, int defaultValue, int max) {
        try {
            return Math.max(1, Math.min(Integer.parseInt(text(value)), max));
        } catch (Exception ignored) {
            return defaultValue;
        }
    }

    private static List<String> stringList(Object value) {
        List<String> result = new ArrayList<>();
        if (value instanceof List<?> items) {
            for (Object item : items) if (!text(item).isBlank()) result.add(text(item));
        } else if (value instanceof String raw) {
            for (String part : raw.split(",")) if (!part.trim().isBlank()) result.add(part.trim());
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> mapList(Object value) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (value instanceof List<?> items) for (Object item : items) if (item instanceof Map<?, ?> map) result.add((Map<String, Object>) map);
        return result;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> objectMap(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : new LinkedHashMap<>();
    }

    private static String firstNonBlank(Object... values) {
        for (Object value : values) if (!text(value).isBlank()) return text(value);
        return "";
    }

    private static String text(Object value) {
        return value == null ? "" : value.toString().trim();
    }

    private static String url(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private static String urlPath(String value) {
        return url(value).replace("+", "%20");
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }

    private record ProjectContext(String id, Map<String, Object> payload, Map<String, Object> error) {}
}
