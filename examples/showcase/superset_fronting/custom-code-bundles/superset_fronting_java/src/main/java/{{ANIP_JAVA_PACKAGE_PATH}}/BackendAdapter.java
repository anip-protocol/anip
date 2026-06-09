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
        return new SupersetBackendAdapter();
    }
}

final class SupersetBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newHttpClient();

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        List<String> unresolved = stringList(plan.getOrDefault("unresolved_required_backend_inputs", List.of()));
        if (!unresolved.isEmpty()) return result(capability, plan, "backend_input_incomplete", record("unresolved_required_backend_inputs", unresolved));
        String token = accessToken();
        if (token.isBlank()) return result(capability, plan, "backend_error", record("superset_error", record("error", "missing_superset_credentials")));
        return switch (text(capability.get("capability_id"))) {
            case "superset.analytics.discover_context" -> discoverContext(capability, plan, params, token);
            case "superset.analytics.answer_question" -> answerQuestion(capability, plan, params);
            case "superset.chart.preview.create" -> chartPreview(capability, plan, params);
            case "superset.chart.publish.request" -> chartPublishRequest(capability, plan, params, context);
            case "superset.dashboard.draft.prepare" -> dashboardDraft(capability, plan, params);
            case "superset.dataset.draft.prepare" -> datasetDraft(capability, plan, params, context);
            default -> result(capability, plan, "backend_execution_stub", record("note", "No Superset custom handler is registered for this capability."));
        };
    }

    private static Map<String, Object> discoverContext(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String workspaceScope = text(params.get("workspace_scope"));
        if (!scopeAllowed(workspaceScope)) return restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.");
        String query = text(params.get("query")).toLowerCase();
        int limit = boundedLimit(params.get("limit"), 20, 50);
        String assetType = text(params.get("asset_type"));
        List<String[]> endpoints = List.of(new String[]{"dataset", "/api/v1/dataset/"}, new String[]{"chart", "/api/v1/chart/"}, new String[]{"dashboard", "/api/v1/dashboard/"});
        List<Map<String, Object>> items = new ArrayList<>();
        for (String[] endpoint : endpoints) {
            String kind = endpoint[0];
            if (!assetType.isBlank() && !assetType.equals(kind)) continue;
            Map<String, Object> payload = requestJson("GET", endpoint[1] + "?page_size=" + limit, token, null);
            if (payload.containsKey("error")) return result(capability, plan, "backend_error", record("superset_error", payload));
            for (Map<String, Object> item : listResult(payload)) {
                String title = firstNonBlank(item.get("table_name"), item.get("slice_name"), item.get("dashboard_title"), item.get("name"), item.get("id"));
                if (!query.isBlank() && !title.toLowerCase().contains(query)) continue;
                items.add(record("asset_type", kind, "id", item.get("id"), "title", title, "url", item.get("url")));
                if (items.size() >= limit) break;
            }
            if (items.size() >= limit) break;
        }
        return result(capability, plan, "completed", record("result", record("workspace_scope", workspaceScope, "items", items, "count", items.size())));
    }

    private static Map<String, Object> answerQuestion(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params) {
        String datasetRef = text(params.get("dataset_ref"));
        if (!datasetAllowed(datasetRef)) return restricted(capability, plan, "Dataset is outside the configured ANIP policy.");
        return result(capability, plan, "completed", record("mutation_performed", false, "result", record("question", params.get("question"), "dataset_ref", datasetRef, "metric", params.get("metric"), "dimension", params.get("dimension"), "time_window", params.get("time_window"), "answer", "Governed analytics answer placeholder. The service owns SQL generation and execution policy.", "raw_sql_disclosed", false)));
    }

    private static Map<String, Object> chartPreview(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params) {
        String datasetRef = text(params.get("dataset_ref"));
        if (!datasetAllowed(datasetRef)) return restricted(capability, plan, "Dataset is outside the configured ANIP policy.");
        Map<String, Object> body = record("dataset_ref", datasetRef, "metric", params.get("metric"), "dimension", params.get("dimension"), "visualization_type", params.get("visualization_type"), "title", firstNonBlank(params.get("title"), text(params.get("metric")) + " by " + firstNonBlank(params.get("dimension"), "time")), "save_chart", false);
        return writePreview(capability, plan, "chart.preview", body, record("dataset_ref", datasetRef));
    }

    private static Map<String, Object> chartPublishRequest(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        Map<String, Object> preview = writePreview(capability, plan, "chart.publish", record("chart_preview_ref", params.get("chart_preview_ref"), "dashboard_scope", params.get("dashboard_scope"), "reason", params.get("reason"), "title", params.get("title")), record("dashboard_scope", params.get("dashboard_scope")));
        if ("true".equals(System.getenv("ANIP_SUPERSET_ALLOW_MUTATION")) && context != null && !text(context.getApprovalGrant()).isBlank()) {
            preview.put("execution_status", "completed");
            preview.put("approval_required", false);
            preview.put("mutation_performed", false);
            preview.put("note", "Approved publish request recorded. Concrete chart save is intentionally left to deployment-specific Superset adapter code.");
        }
        return preview;
    }

    private static Map<String, Object> dashboardDraft(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params) {
        return writePreview(capability, plan, "dashboard.draft", record("dashboard_scope", params.get("dashboard_scope"), "objective", params.get("objective"), "chart_refs", params.get("chart_refs"), "layout_hint", params.get("layout_hint"), "audience", params.get("audience")), record("dashboard_scope", params.get("dashboard_scope")));
    }

    private static Map<String, Object> datasetDraft(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        Map<String, Object> preview = writePreview(capability, plan, "dataset.draft", record("database_ref", params.get("database_ref"), "dataset_purpose", params.get("dataset_purpose"), "query_intent", params.get("query_intent"), "source_tables", params.get("source_tables"), "metrics", params.get("metrics"), "raw_sql_accepted", false), record("database_ref", params.get("database_ref")));
        if ("true".equals(System.getenv("ANIP_SUPERSET_ALLOW_MUTATION")) && context != null && !text(context.getApprovalGrant()).isBlank()) {
            preview.put("execution_status", "completed");
            preview.put("approval_required", false);
            preview.put("mutation_performed", false);
            preview.put("note", "Approved dataset draft recorded. Raw SQL generation remains deployment-owned.");
        }
        return preview;
    }

    private static Map<String, Object> writePreview(Map<String, Object> capability, Map<String, Object> plan, String action, Map<String, Object> body, Map<String, Object> metadata) {
        return result(capability, plan, "prepared", record("approval_required", true, "mutation_performed", false, "superset_action", action, "superset_metadata", metadata, "superset_request", record("operation", action, "body", body), "note", "Prepared a governed Superset analytics request. No Superset mutation was performed."));
    }

    private static String accessToken() {
        String direct = text(System.getenv("SUPERSET_ACCESS_TOKEN"));
        if (!direct.isBlank()) return direct;
        String username = text(System.getenv("SUPERSET_USERNAME"));
        String password = text(System.getenv("SUPERSET_PASSWORD"));
        if (username.isBlank() || password.isBlank()) return "";
        Map<String, Object> payload = requestJson("POST", "/api/v1/security/login", "", record("username", username, "password", password, "provider", firstNonBlank(System.getenv("SUPERSET_AUTH_PROVIDER"), "db"), "refresh", true));
        return text(payload.get("access_token"));
    }

    private static Map<String, Object> requestJson(String method, String path, String token, Map<String, Object> body) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(firstNonBlank(System.getenv("SUPERSET_BASE_URL"), "http://127.0.0.1:18088").replaceAll("/$", "") + path))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .header("User-Agent", "anip-superset-fronting-showcase");
            if (!token.isBlank()) builder.header("Authorization", "Bearer " + token);
            HttpRequest request = builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body))).build();
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> payload = response.body().isBlank() ? new LinkedHashMap<>() : MAPPER.readValue(response.body(), new TypeReference<>() {});
            if (response.statusCode() < 200 || response.statusCode() >= 300) return record("error", "superset_http_error", "status", response.statusCode(), "detail", payload);
            return payload;
        } catch (Exception exc) {
            return record("error", "superset_connection_error", "detail", exc.toString());
        }
    }

    private static Map<String, Object> result(Map<String, Object> capability, Map<String, Object> plan, String status, Map<String, Object> extra) {
        Map<String, Object> result = record("execution_status", status, "capability_id", capability.get("capability_id"), "selected_backend", plan.get("selected_binding"), "semantic_input", plan.get("semantic_input"), "backend_input_contract", plan.get("backend_input_contract"));
        result.putAll(extra);
        return result;
    }

    private static Map<String, Object> restricted(Map<String, Object> capability, Map<String, Object> plan, String reason) {
        return result(capability, plan, "restricted", record("reason", reason));
    }

    private static boolean scopeAllowed(String scope) {
        String key = scope.toLowerCase().trim();
        List<String> blocked = csvEnv("ANIP_SUPERSET_BLOCKED_WORKSPACES");
        List<String> allowed = csvEnv("ANIP_SUPERSET_ALLOWED_WORKSPACES");
        return !blocked.contains(key) && (allowed.isEmpty() || allowed.contains(key));
    }

    private static boolean datasetAllowed(String datasetRef) {
        List<String> allowed = csvEnv("ANIP_SUPERSET_ALLOWED_DATASETS");
        return allowed.isEmpty() || allowed.contains(datasetRef.toLowerCase().trim());
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> listResult(Map<String, Object> payload) {
        if (!(payload.get("result") instanceof Map<?, ?> raw)) return List.of();
        Object data = raw.get("data");
        if (data instanceof List<?> list) return (List<Map<String, Object>>) (List<?>) list;
        return List.of();
    }

    private static int boundedLimit(Object value, int defaultValue, int maximum) {
        try {
            int parsed = Integer.parseInt(text(value));
            return Math.max(1, Math.min(parsed, maximum));
        } catch (Exception ignored) {
            return defaultValue;
        }
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }

    private static String firstNonBlank(Object... values) {
        for (Object value : values) {
            String text = text(value);
            if (!text.isBlank()) return text;
        }
        return "";
    }

    private static String text(Object value) {
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static List<String> stringList(Object value) {
        if (value instanceof List<?> list) return list.stream().map(SupersetBackendAdapter::text).filter(item -> !item.isBlank()).distinct().toList();
        if (value instanceof String text && !text.isBlank()) return List.of(text.split(",")).stream().map(String::trim).filter(item -> !item.isBlank()).distinct().toList();
        return List.of();
    }

    private static List<String> csvEnv(String name) {
        return stringList(System.getenv(name)).stream().map(String::toLowerCase).toList();
    }
}
