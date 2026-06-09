package {{ANIP_JAVA_PACKAGE_NAME}};

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.anip.service.InvocationContext;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@FunctionalInterface
public interface BackendAdapter {
    Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context);

    static BackendAdapter defaultAdapter() {
        return new NotionBackendAdapter();
    }
}

final class NotionBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newHttpClient();

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        List<String> unresolved = stringList(plan.get("unresolved_required_backend_inputs"));
        if (!unresolved.isEmpty()) return result(capability, plan, "backend_input_incomplete", record("unresolved_required_backend_inputs", unresolved));
        if (token().isBlank()) return result(capability, plan, "backend_error", record("notion_error", record("error", "missing_notion_token")));
        return switch (text(capability.get("capability_id"))) {
            case "notion.workspace.search_context" -> searchWorkspace(capability, plan, params);
            case "notion.database.query_context" -> queryDatabase(capability, plan, params);
            case "notion.page.create.prepare" -> prepareOrCreatePage(capability, plan, params, context);
            case "notion.page.update.prepare" -> preparePageUpdate(capability, plan, params);
            case "notion.comment.prepare" -> prepareOrPostComment(capability, plan, params, context);
            default -> result(capability, plan, "backend_execution_stub", record("note", "No Notion custom handler is registered for this capability."));
        };
    }

    private static Map<String, Object> searchWorkspace(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params) {
        String scope = text(params.get("workspace_scope"));
        if (!scopeAllowed(scope)) return restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.");
        int limit = boundedLimit(params.get("limit"), 20, 50);
        Map<String, Object> response = notion("POST", "/search", record("query", text(params.get("query")), "page_size", limit));
        if (response.containsKey("error")) return result(capability, plan, "backend_error", record("notion_error", response));
        List<Map<String, Object>> items = summarizeResults(response, limit);
        return result(capability, plan, "completed", record("notion_query", params.get("query"), "result", record("workspace_scope", scope, "items", items, "count", items.size())));
    }

    private static Map<String, Object> queryDatabase(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params) {
        String databaseId = text(params.get("database_id"));
        if (!idAllowed(databaseId, "ANIP_NOTION_ALLOWED_DATABASES")) return restricted(capability, plan, "Database is outside the configured ANIP policy.");
        int limit = boundedLimit(params.get("limit"), 20, 50);
        String dataSourceId = configuredDataSourceId();
        if (!dataSourceId.isBlank() && !idAllowed(dataSourceId, "ANIP_NOTION_ALLOWED_DATA_SOURCES")) return restricted(capability, plan, "Data source is outside the configured ANIP policy.");
        if (dataSourceId.isBlank()) {
            Map<String, Object> database = notion("GET", "/databases/" + databaseId, null);
            if (database.containsKey("error")) return result(capability, plan, "backend_error", record("notion_error", database));
            List<Map<String, Object>> dataSources = mapList(database.get("data_sources"));
            if (!dataSources.isEmpty()) dataSourceId = text(dataSources.get(0).get("id"));
        }
        Map<String, Object> response = dataSourceId.isBlank()
            ? notion("POST", "/databases/" + databaseId + "/query", record("page_size", limit))
            : notion("POST", "/data_sources/" + dataSourceId + "/query", record("page_size", limit));
        if (response.containsKey("error")) return result(capability, plan, "backend_error", record("notion_error", response));
        List<Map<String, Object>> items = summarizeResults(response, limit);
        return result(capability, plan, "completed", record("result", record("database_id", databaseId, "data_source_id", dataSourceId, "items", items, "count", items.size())));
    }

    private static Map<String, Object> prepareOrCreatePage(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        String parentId = text(params.get("parent_id"));
        if (!idAllowed(parentId, "ANIP_NOTION_ALLOWED_PARENTS")) return restricted(capability, plan, "Parent page/database is outside the configured ANIP policy.");
        Map<String, Object> body = record(
            "parent", record("page_id", parentId),
            "properties", record("title", record("title", richText(text(params.get("title"))))),
            "children", List.of(record("object", "block", "type", "paragraph", "paragraph", record("rich_text", richText(text(params.get("content_summary"))))))
        );
        Map<String, Object> preview = writePreview(capability, plan, "pages.create", body, record("parent_id", parentId));
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> created = notion("POST", "/pages", body);
        if (created.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("notion_error", created);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("created_page", summarizeObject(created));
        return preview;
    }

    private static Map<String, Object> preparePageUpdate(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params) {
        String pageId = text(params.get("page_id"));
        if (!idAllowed(pageId, "ANIP_NOTION_ALLOWED_PAGES")) return restricted(capability, plan, "Page is outside the configured ANIP policy.");
        return writePreview(capability, plan, "pages.update.preview", record("archived", false, "change_summary", text(params.get("change_summary")), "content_patch", text(params.get("content_patch"))), record("page_id", pageId));
    }

    private static Map<String, Object> prepareOrPostComment(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        String pageId = text(params.get("page_id"));
        if (!idAllowed(pageId, "ANIP_NOTION_ALLOWED_PAGES")) return restricted(capability, plan, "Page is outside the configured ANIP policy.");
        Map<String, Object> body = record("parent", record("page_id", pageId), "rich_text", richText(("[" + text(params.get("comment_purpose")) + "] " + text(params.get("context"))).trim()));
        Map<String, Object> preview = writePreview(capability, plan, "comments.create", body, record("page_id", pageId));
        if (!mutationEnabled(context)) return preview;
        Map<String, Object> created = notion("POST", "/comments", body);
        if (created.containsKey("error")) {
            preview.put("execution_status", "backend_error");
            preview.put("notion_error", created);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("created_comment", created);
        return preview;
    }

    private static Map<String, Object> notion(String method, String path, Map<String, Object> body) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(apiBase() + path))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + token())
                .header("Notion-Version", notionVersion())
                .header("User-Agent", "anip-notion-fronting-showcase")
                .method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body)))
                .build();
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> payload = response.body().isBlank() ? new LinkedHashMap<>() : MAPPER.readValue(response.body(), new TypeReference<>() {});
            if (response.statusCode() < 200 || response.statusCode() >= 300) return record("error", "notion_http_error", "status", response.statusCode(), "detail", payload);
            return payload;
        } catch (Exception exc) {
            return record("error", "notion_connection_error", "detail", exc.toString());
        }
    }

    private static Map<String, Object> writePreview(Map<String, Object> capability, Map<String, Object> plan, String action, Map<String, Object> body, Map<String, Object> metadata) {
        return result(capability, plan, "prepared", record("approval_required", true, "mutation_performed", false, "notion_action", action, "notion_metadata", metadata, "notion_request", record("operation", action, "body", body), "note", "Prepared a Notion API payload. No Notion mutation was performed."));
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

    private static Map<String, Object> restricted(Map<String, Object> capability, Map<String, Object> plan, String reason) {
        return result(capability, plan, "restricted", record("reason", reason));
    }

    private static List<Map<String, Object>> summarizeResults(Map<String, Object> response, int limit) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> item : mapList(path(response, "results"))) {
            items.add(summarizeObject(item));
            if (items.size() >= limit) break;
        }
        return items;
    }

    private static Map<String, Object> summarizeObject(Map<String, Object> item) {
        String title = "page".equals(text(item.get("object"))) ? titleFromPage(item) : text(item.get("url"));
        if (title.isBlank()) title = text(item.get("id"));
        return record("id", item.get("id"), "object", item.get("object"), "title", title, "url", item.get("url"), "created_time", item.get("created_time"), "last_edited_time", item.get("last_edited_time"));
    }

    private static String titleFromPage(Map<String, Object> page) {
        Object properties = page.get("properties");
        if (!(properties instanceof Map<?, ?> map)) return "";
        for (Object value : map.values()) {
            if (!(value instanceof Map<?, ?> property) || !"title".equals(text(property.get("type")))) continue;
            return mapList(property.get("title")).stream().map(part -> text(part.get("plain_text"))).reduce("", String::concat).trim();
        }
        return "";
    }

    private static List<Map<String, Object>> richText(String value) {
        return List.of(record("type", "text", "text", record("content", value.length() > 1900 ? value.substring(0, 1900) : value)));
    }

    private static boolean scopeAllowed(String scope) {
        String key = scope.toLowerCase();
        List<String> blocked = csvEnv("ANIP_NOTION_BLOCKED_WORKSPACES");
        List<String> allowed = csvEnv("ANIP_NOTION_ALLOWED_WORKSPACES");
        return !blocked.contains(key) && (allowed.isEmpty() || allowed.contains(key));
    }

    private static boolean idAllowed(String value, String envName) {
        List<String> allowed = csvEnv(envName);
        return allowed.isEmpty() || allowed.contains(value.toLowerCase());
    }

    private static boolean mutationEnabled(InvocationContext context) {
        String grant = context == null ? "" : text(context.getApprovalGrant());
        return "true".equals(System.getenv("ANIP_NOTION_ALLOW_MUTATION")) && !grant.isBlank();
    }

    private static String token() {
        return System.getenv().getOrDefault("NOTION_TOKEN", "").trim();
    }

    private static String apiBase() {
        return System.getenv().getOrDefault("NOTION_API_BASE", "https://api.notion.com/v1").trim().replaceAll("/+$", "");
    }

    private static String notionVersion() {
        return System.getenv().getOrDefault("NOTION_VERSION", "2026-03-11").trim();
    }

    private static String configuredDataSourceId() {
        String value = System.getenv().getOrDefault("NOTION_DATA_SOURCE_ID", "").trim();
        return value.isBlank() ? System.getenv().getOrDefault("ANIP_NOTION_DATA_SOURCE_ID", "").trim() : value;
    }

    private static Object path(Object source, String... keys) {
        Object current = source;
        for (String key : keys) {
            if (!(current instanceof Map<?, ?> map)) return null;
            current = map.get(key);
        }
        return current;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> mapList(Object value) {
        if (value instanceof List<?> list) return (List<Map<String, Object>>) (List<?>) list;
        return List.of();
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }

    private static int boundedLimit(Object value, int defaultValue, int maximum) {
        try {
            int parsed = Integer.parseInt(text(value));
            return Math.max(1, Math.min(parsed, maximum));
        } catch (Exception ignored) {
            return defaultValue;
        }
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static List<String> stringList(Object value) {
        if (value instanceof List<?> list) return list.stream().map(NotionBackendAdapter::text).filter(item -> !item.isBlank()).distinct().toList();
        if (value instanceof String text && !text.isBlank()) return List.of(text.split(",")).stream().map(String::trim).filter(item -> !item.isBlank()).distinct().toList();
        return List.of();
    }

    private static List<String> csvEnv(String name) {
        return stringList(System.getenv(name)).stream().map(String::toLowerCase).toList();
    }
}
