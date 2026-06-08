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
        return new GitHubBackendAdapter();
    }
}

final class GitHubBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newHttpClient();

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        List<String> unresolved = stringList(plan.get("unresolved_required_backend_inputs"));
        if (!unresolved.isEmpty()) {
            return result(capability, plan, "backend_input_incomplete", record("unresolved_required_backend_inputs", unresolved));
        }
        String token = System.getenv().getOrDefault("GITHUB_TOKEN", "").trim();
        if (token.isBlank()) return result(capability, plan, "backend_error", record("github_error", record("error", "missing_github_token")));
        return switch (text(capability.get("capability_id"))) {
            case "github.repo.search_context" -> searchRepositoryContext(capability, plan, params, token);
            case "github.issue.prepare" -> prepareOrCreateIssue(capability, plan, params, token, context);
            case "github.pr.comment.prepare" -> preparePullRequestComment(capability, plan, params, token, context);
            case "github.workflow.dispatch.request" -> prepareWorkflowDispatch(capability, plan, params, token, context);
            case "github.release_notes.prepare" -> prepareReleaseNotes(capability, plan, params, token);
            default -> result(capability, plan, "backend_execution_stub", record("note", "No GitHub custom handler is registered for this capability."));
        };
    }

    private static Map<String, Object> searchRepositoryContext(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String owner = text(params.get("owner"));
        String repo = text(params.get("repo"));
        if (!repoAllowed(owner, repo)) return restricted(capability, plan, owner, repo);
        int limit = boundedLimit(params.get("limit"), 20, 50);
        String query = ("repo:" + owner + "/" + repo + " " + text(params.get("query"))).trim();
        Map<String, Object> payload = github("GET", "/search/issues?q=" + url(query) + "&per_page=" + limit, token, null);
        if (payload.containsKey("error")) return result(capability, plan, "backend_error", record("github_error", payload));
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> item : mapList(payload.get("items"))) {
            if (items.size() >= limit) break;
            items.add(record("number", item.get("number"), "title", item.get("title"), "state", item.get("state"), "html_url", item.get("html_url"), "kind", item.get("pull_request") == null ? "issue" : "pull_request"));
        }
        return result(capability, plan, "completed", record("github_query", query, "result", record("items", items, "count", items.size(), "total_count", payload.get("total_count"))));
    }

    private static Map<String, Object> prepareOrCreateIssue(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token, InvocationContext context) {
        RepoContext repo = repoMetadata(capability, plan, params, token);
        if (repo.error != null) return repo.error;
        Map<String, Object> body = record("title", text(params.get("title")), "body", text(params.get("body")));
        List<String> labels = stringList(params.get("labels"));
        List<String> assignees = stringList(params.get("assignees"));
        if (!labels.isEmpty()) body.put("labels", labels);
        if (!assignees.isEmpty()) body.put("assignees", assignees);
        Map<String, Object> preview = writePreview(capability, plan, "issues.create", "/repos/" + repo.owner + "/" + repo.repo + "/issues", body, repo.payload);
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> created = github("POST", "/repos/" + urlPath(repo.owner) + "/" + urlPath(repo.repo) + "/issues", token, body);
        if (created.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("github_error", created);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("created_issue", record("number", created.get("number"), "html_url", created.get("html_url"), "state", created.get("state")));
        preview.put("note", "Created GitHub issue after the ANIP runtime validated and reserved an approval grant.");
        return preview;
    }

    private static Map<String, Object> preparePullRequestComment(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token, InvocationContext context) {
        RepoContext repo = repoMetadata(capability, plan, params, token);
        if (repo.error != null) return repo.error;
        String pullNumber = text(params.get("pull_number"));
        Map<String, Object> pull = github("GET", "/repos/" + urlPath(repo.owner) + "/" + urlPath(repo.repo) + "/pulls/" + urlPath(pullNumber), token, null);
        if (pull.containsKey("error")) return result(capability, plan, "backend_error", record("github_error", pull));
        Map<String, Object> body = record("body", ("[" + firstNonBlank(params.get("comment_purpose"), "triage_update") + "] " + text(params.get("context"))).trim());
        Map<String, Object> preview = writePreview(capability, plan, "issues.createComment", "/repos/" + repo.owner + "/" + repo.repo + "/issues/" + pullNumber + "/comments", body, repo.payload);
        preview.put("pull_request", record("number", pull.get("number"), "title", pull.get("title"), "state", pull.get("state")));
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> posted = github("POST", "/repos/" + urlPath(repo.owner) + "/" + urlPath(repo.repo) + "/issues/" + urlPath(pullNumber) + "/comments", token, body);
        if (posted.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("github_error", posted);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("posted_comment", record("id", posted.get("id"), "html_url", posted.get("html_url")));
        return preview;
    }

    private static Map<String, Object> prepareWorkflowDispatch(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token, InvocationContext context) {
        RepoContext repo = repoMetadata(capability, plan, params, token);
        if (repo.error != null) return repo.error;
        String workflowId = text(params.get("workflow_id"));
        Map<String, Object> body = record("ref", text(params.get("ref")), "inputs", objectMap(params.get("inputs")));
        Map<String, Object> preview = writePreview(capability, plan, "actions.createWorkflowDispatch", "/repos/" + repo.owner + "/" + repo.repo + "/actions/workflows/" + workflowId + "/dispatches", body, repo.payload);
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> dispatched = github("POST", "/repos/" + urlPath(repo.owner) + "/" + urlPath(repo.repo) + "/actions/workflows/" + urlPath(workflowId) + "/dispatches", token, body);
        if (dispatched.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("github_error", dispatched);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("dispatched_workflow", record("workflow_id", workflowId, "ref", body.get("ref")));
        return preview;
    }

    private static Map<String, Object> prepareReleaseNotes(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        RepoContext repo = repoMetadata(capability, plan, params, token);
        if (repo.error != null) return repo.error;
        String range = text(params.get("range"));
        return result(capability, plan, "completed", record(
            "result", record(
                "title", "Release notes for " + repo.owner + "/" + repo.repo + " " + range,
                "audience", firstNonBlank(params.get("audience"), "internal"),
                "repository", repoSummary(repo.payload),
                "range", range,
                "sections", List.of(
                    record("title", "Highlights", "items", List.of("Review bounded GitHub context before publishing release notes.")),
                    record("title", "Governance", "items", List.of("This capability drafts content only and does not create a GitHub release."))
                )
            ),
            "mutation_performed", false
        ));
    }

    private static RepoContext repoMetadata(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String owner = text(params.get("owner"));
        String repo = text(params.get("repo"));
        if (!repoAllowed(owner, repo)) return new RepoContext(owner, repo, null, restricted(capability, plan, owner, repo));
        Map<String, Object> payload = github("GET", "/repos/" + urlPath(owner) + "/" + urlPath(repo), token, null);
        if (payload.containsKey("error")) return new RepoContext(owner, repo, null, result(capability, plan, "backend_error", record("github_error", payload)));
        return new RepoContext(owner, repo, payload, null);
    }

    static Map<String, Object> github(String method, String path, String token, Map<String, Object> body) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create("https://api.github.com" + path))
                .header("Accept", "application/vnd.github+json")
                .header("Authorization", "Bearer " + token)
                .header("Content-Type", "application/json")
                .header("User-Agent", "anip-github-fronting-showcase")
                .header("X-GitHub-Api-Version", "2022-11-28");
            if ("POST".equals(method)) builder.POST(HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body == null ? Map.of() : body)));
            else builder.GET();
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            Map<String, Object> payload = response.body().isBlank() ? new LinkedHashMap<>() : MAPPER.readValue(response.body(), new TypeReference<>() {});
            if (response.statusCode() < 200 || response.statusCode() >= 300) return record("error", "github_http_error", "status", response.statusCode(), "detail", payload);
            return payload;
        } catch (Exception exc) {
            return record("error", "github_http_error", "detail", exc.toString());
        }
    }

    private static Map<String, Object> writePreview(Map<String, Object> capability, Map<String, Object> plan, String action, String path, Map<String, Object> body, Map<String, Object> repoPayload) {
        return result(capability, plan, "prepared", record(
            "approval_required", true,
            "mutation_performed", false,
            "github_action", action,
            "github_metadata", repoSummary(repoPayload),
            "github_request", record("method", "POST", "path", path, "body", body),
            "note", "Prepared a GitHub request payload. No GitHub mutation was performed."
        ));
    }

    private static Map<String, Object> repoSummary(Map<String, Object> payload) {
        Map<String, Object> owner = objectMap(payload.get("owner"));
        return record("owner", owner.get("login"), "repo", payload.get("name"), "default_branch", payload.get("default_branch"), "private", payload.get("private"), "html_url", payload.get("html_url"));
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

    private static Map<String, Object> restricted(Map<String, Object> capability, Map<String, Object> plan, String owner, String repo) {
        return result(capability, plan, "restricted", record("repository", record("owner", owner, "repo", repo), "reason", "GitHub repository is outside the configured ANIP repository policy."));
    }

    private static boolean repoAllowed(String owner, String repo) {
        String key = (owner + "/" + repo).toLowerCase();
        List<String> blocked = csvEnv("ANIP_GITHUB_BLOCKED_REPOS");
        List<String> allowed = csvEnv("ANIP_GITHUB_ALLOWED_REPOS");
        return !blocked.contains(key) && (allowed.isEmpty() || allowed.contains(key));
    }

    private static boolean mutationEnabled(InvocationContext context) {
        String grant = context == null ? "" : text(context.getApprovalGrant());
        return "true".equals(System.getenv().getOrDefault("ANIP_GITHUB_ALLOW_MUTATION", "")) && !grant.isBlank();
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

    private record RepoContext(String owner, String repo, Map<String, Object> payload, Map<String, Object> error) {}
}
