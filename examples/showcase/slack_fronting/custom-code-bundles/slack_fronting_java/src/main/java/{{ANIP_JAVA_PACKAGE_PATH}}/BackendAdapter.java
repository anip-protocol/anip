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
import java.util.StringJoiner;

@FunctionalInterface
public interface BackendAdapter {

    Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context);

    static BackendAdapter defaultAdapter() {
        return new SlackBackendAdapter();
    }
}

final class SlackBackendAdapter implements BackendAdapter {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newHttpClient();

    @Override
    public Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, InvocationContext context) {
        List<String> unresolved = stringList(plan.get("unresolved_required_backend_inputs"));
        if (!unresolved.isEmpty()) {
            return result(capability, plan, "backend_input_incomplete", record("unresolved_required_backend_inputs", unresolved));
        }
        String token = System.getenv().getOrDefault("SLACK_BOT_TOKEN", "").trim();
        return switch (text(capability.get("capability_id"))) {
            case "slack.channel.read_context" -> token.isBlank() ? result(capability, plan, "backend_not_configured", record("missing_env", "SLACK_BOT_TOKEN")) : readChannel(capability, plan, params, token);
            case "slack.thread.summarize" -> token.isBlank() ? result(capability, plan, "backend_not_configured", record("missing_env", "SLACK_BOT_TOKEN")) : readThread(capability, plan, params, token);
            case "slack.message.prepare", "slack.incident_update.prepare", "slack.announcement.request" -> prepareOrSendMessage(capability, plan, params, token, context);
            default -> result(capability, plan, "backend_execution_stub", record("note", "No Slack custom handler is registered for this capability."));
        };
    }

    private static Map<String, Object> readChannel(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String channelId = text(params.get("channel_id"));
        if (!channelAllowed(channelId)) return restricted(capability, plan, channelId);
        int limit = boundedLimit(params.get("limit"), 20, 50);
        String query = text(params.get("query")).toLowerCase();
        Map<String, Object> payload = slack(token, "conversations.history", record("channel", channelId, "limit", limit));
        if (!Boolean.TRUE.equals(payload.get("ok"))) return backendError(capability, plan, payload);
        List<Map<String, Object>> messages = messageSummaries(payload.get("messages"));
        if (!query.isBlank()) messages.removeIf(message -> !text(message.get("text")).toLowerCase().contains(query));
        if (messages.size() > limit) messages = new ArrayList<>(messages.subList(0, limit));
        return result(capability, plan, "completed", record("result", record("messages", messages, "count", messages.size(), "channel_id", channelId)));
    }

    private static Map<String, Object> readThread(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token) {
        String channelId = text(params.get("channel_id"));
        if (!channelAllowed(channelId)) return restricted(capability, plan, channelId);
        String threadTs = text(params.get("thread_ts"));
        int limit = boundedLimit(params.get("limit"), 50, 100);
        Map<String, Object> payload = slack(token, "conversations.replies", record("channel", channelId, "ts", threadTs, "limit", limit));
        if (!Boolean.TRUE.equals(payload.get("ok"))) return backendError(capability, plan, payload);
        List<Map<String, Object>> messages = messageSummaries(payload.get("messages"));
        return result(capability, plan, "completed", record("result", record("messages", messages, "count", messages.size(), "channel_id", channelId, "thread_ts", threadTs)));
    }

    private static Map<String, Object> prepareOrSendMessage(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> params, String token, InvocationContext context) {
        String channelId = text(params.get("channel_id"));
        if (!channelAllowed(channelId)) return restricted(capability, plan, channelId);
        Map<String, Object> body = record("channel", channelId, "text", messageText(capability, params));
        if (!text(params.get("thread_ts")).isBlank()) body.put("thread_ts", text(params.get("thread_ts")));
        Map<String, Object> preview = result(capability, plan, "prepared", record(
            "approval_required", true,
            "mutation_performed", false,
            "slack_action", "chat.postMessage",
            "post_message_request", record("method", "POST", "path", "/api/chat.postMessage", "body", body),
            "note", "Prepared a Slack message payload. No Slack message was sent."
        ));
        String approvalGrant = context == null ? "" : text(context.getApprovalGrant());
        if (!"true".equals(System.getenv().getOrDefault("ANIP_SLACK_ALLOW_SEND", "")) || approvalGrant.isBlank()) return preview;
        if (token.isBlank()) {
            preview.put("execution_status", "backend_error");
            preview.put("slack_error", record("ok", false, "error", "missing_slack_token"));
            return preview;
        }
        Map<String, Object> posted = slack(token, "chat.postMessage", body);
        if (!Boolean.TRUE.equals(posted.get("ok"))) {
            preview.put("execution_status", "backend_error");
            preview.put("slack_error", posted);
            return preview;
        }
        preview.put("execution_status", "completed");
        preview.put("approval_required", false);
        preview.put("mutation_performed", true);
        preview.put("posted_message", record("channel", posted.get("channel"), "ts", posted.get("ts")));
        preview.put("approval_grant_id", approvalGrant);
        preview.put("note", "Sent Slack message after the ANIP runtime validated and reserved an approval grant.");
        return preview;
    }

    static Map<String, Object> slack(String token, String path, Map<String, Object> body) {
        try {
            StringJoiner form = new StringJoiner("&");
            for (Map.Entry<String, Object> entry : body.entrySet()) form.add(url(entry.getKey()) + "=" + url(text(entry.getValue())));
            HttpRequest request = HttpRequest.newBuilder(URI.create("https://slack.com/api/" + path))
                .header("Accept", "application/json")
                .header("Authorization", "Bearer " + token)
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(form.toString()))
                .build();
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            Map<String, Object> payload = response.body().isBlank() ? new LinkedHashMap<>() : MAPPER.readValue(response.body(), new TypeReference<>() {});
            if (response.statusCode() < 200 || response.statusCode() >= 300) return record("ok", false, "error", "slack_http_error", "status", response.statusCode(), "detail", payload);
            return payload;
        } catch (Exception exc) {
            return record("ok", false, "error", "slack_http_error", "detail", exc.toString());
        }
    }

    private static String messageText(Map<String, Object> capability, Map<String, Object> params) {
        return switch (text(capability.get("capability_id"))) {
            case "slack.incident_update.prepare" -> String.join("\n", nonEmpty(List.of(
                "Incident " + text(params.get("incident_id")) + ": " + text(params.get("status")),
                text(params.get("summary")),
                text(params.get("next_update_time")).isBlank() ? "" : "Next update: " + text(params.get("next_update_time"))
            )));
            case "slack.announcement.request" -> (text(params.get("audience")).isBlank() ? "" : "[" + text(params.get("audience")) + "] ") + text(params.get("announcement"));
            default -> text(params.get("text"));
        };
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> messageSummaries(Object value) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (value instanceof List<?> items) {
            for (Object item : items) {
                if (item instanceof Map<?, ?> message) {
                    Map<String, Object> typed = (Map<String, Object>) message;
                    result.add(record("ts", typed.get("ts"), "user", firstNonBlank(typed.get("user"), typed.get("bot_id")), "text", typed.get("text"), "thread_ts", typed.get("thread_ts")));
                }
            }
        }
        return result;
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

    private static Map<String, Object> restricted(Map<String, Object> capability, Map<String, Object> plan, String channelId) {
        return result(capability, plan, "restricted", record("channel_id", channelId, "reason", "Slack channel is outside the configured ANIP channel policy."));
    }

    private static Map<String, Object> backendError(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> payload) {
        return result(capability, plan, "backend_error", record("slack_error", payload));
    }

    private static boolean channelAllowed(String channelId) {
        List<String> blocked = csvEnv("ANIP_SLACK_BLOCKED_CHANNELS");
        List<String> allowed = csvEnv("ANIP_SLACK_ALLOWED_CHANNELS");
        return !blocked.contains(channelId) && (allowed.isEmpty() || allowed.contains(channelId));
    }

    private static List<String> csvEnv(String name) {
        List<String> result = new ArrayList<>();
        for (String item : System.getenv().getOrDefault(name, "").split(",")) {
            String value = item.trim();
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
        if (value instanceof List<?> items) for (Object item : items) result.add(text(item));
        return result;
    }

    private static List<String> nonEmpty(List<String> values) {
        List<String> result = new ArrayList<>();
        for (String value : values) if (!value.isBlank()) result.add(value);
        return result;
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

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }
}
