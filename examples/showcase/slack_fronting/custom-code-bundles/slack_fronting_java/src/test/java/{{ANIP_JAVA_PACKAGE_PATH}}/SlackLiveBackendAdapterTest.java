package {{ANIP_JAVA_PACKAGE_NAME}};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

import dev.anip.core.ANIPError;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SlackLiveBackendAdapterTest {

    @Test
    @EnabledIfEnvironmentVariable(named = "SLACK_BOT_TOKEN", matches = ".+")
    void executesLiveReadsAndPreparedPreviewsWithoutMutation() {
        String token = System.getenv("SLACK_BOT_TOKEN");
        String channelId = System.getenv("SLACK_CHANNEL_ID");
        assertTrue(channelId != null && !channelId.isBlank(), "SLACK_CHANNEL_ID is required");
        Map<String, Object> history = SlackBackendAdapter.slack(token, "conversations.history", record("channel", channelId, "limit", 1));
        assertEquals(true, history.get("ok"));
        String threadTs = "";
        List<?> messages = (List<?>) history.get("messages");
        if (!messages.isEmpty()) {
            Map<?, ?> message = (Map<?, ?>) messages.get(0);
            threadTs = text(message.get("thread_ts")).isBlank() ? text(message.get("ts")) : text(message.get("thread_ts"));
        }

        BackendAdapter adapter = BackendAdapter.defaultAdapter();
        assertEquals("completed", adapter.execute(capability("slack.channel.read_context"), plan(record("channel_id", channelId, "limit", 5)), record("channel_id", channelId, "limit", 5), null).get("execution_status"));
        if (!threadTs.isBlank()) {
            assertEquals("completed", adapter.execute(capability("slack.thread.summarize"), plan(record("channel_id", channelId, "thread_ts", threadTs, "limit", 10)), record("channel_id", channelId, "thread_ts", threadTs, "limit", 10), null).get("execution_status"));
        }

        Map<String, Map<String, Object>> previews = recordOfRecords(
            "slack.message.prepare", record("channel_id", channelId, "text", "ANIP Slack Java smoke preview"),
            "slack.incident_update.prepare", record("channel_id", channelId, "incident_id", "INC-123", "status", "monitoring", "summary", "Preview only", "next_update_time", "in 30 minutes"),
            "slack.announcement.request", record("channel_id", channelId, "announcement", "Preview governed announcement only", "audience", "internal")
        );
        for (Map.Entry<String, Map<String, Object>> entry : previews.entrySet()) {
            Map<String, Object> result = adapter.execute(capability(entry.getKey()), plan(entry.getValue()), new LinkedHashMap<>(entry.getValue()), null);
            assertEquals("prepared", result.get("execution_status"));
            assertEquals(false, result.get("mutation_performed"));
        }
        if ("true".equals(System.getenv("ANIP_SLACK_ALLOW_SEND"))) {
            Map<String, Object> params = record("channel_id", channelId, "text", "ANIP approved Slack Java post");
            Map<String, Object> sent = adapter.execute(capability("slack.message.prepare"), plan(params), params, approvalContext("grant_live_java_smoke"));
            assertEquals("completed", sent.get("execution_status"));
            assertEquals(true, sent.get("mutation_performed"));
            assertTrue(!text(((Map<?, ?>) sent.get("posted_message")).get("ts")).isBlank());
        }
    }

    @Test
    @EnabledIfEnvironmentVariable(named = "SLACK_BOT_TOKEN", matches = ".+")
    void generatedHandlerStopsWithoutApprovalAndSendsWithGrant() {
        String channelId = System.getenv("SLACK_CHANNEL_ID");
        assertTrue(channelId != null && !channelId.isBlank(), "SLACK_CHANNEL_ID is required");
        CapabilityDef capability = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
                .filter(item -> "slack.announcement.request".equals(item.getDeclaration().getName()))
                .findFirst()
                .orElseThrow();
        Map<String, Object> params = record("channel_id", channelId, "announcement", "ANIP approved Slack Java generated handler post", "audience", "test");

        try {
            capability.getHandler().apply(approvalContext(null), params);
            throw new AssertionError("Expected approval_required without grant");
        } catch (ANIPError error) {
            assertEquals("approval_required", error.getErrorType());
        }

        if ("true".equals(System.getenv("ANIP_SLACK_ALLOW_SEND"))) {
            Map<String, Object> sent = capability.getHandler().apply(approvalContext("grant_live_java_handler_smoke"), params);
            assertEquals("completed", sent.get("execution_status"));
            assertEquals(true, sent.get("mutation_performed"));
            assertTrue(!text(((Map<?, ?>) sent.get("posted_message")).get("ts")).isBlank());
        }
    }

    private static Map<String, Object> capability(String id) {
        return GeneratedRuntimeTarget.capabilities().stream().filter(item -> id.equals(item.get("capability_id"))).findFirst().orElseThrow();
    }

    private static Map<String, Object> plan(Map<String, Object> params) {
        return record("selected_binding", null, "semantic_input", params, "adapter_input", params, "backend_input_contract", record("mode", "explicit", "required", List.of(), "optional", List.of()), "unresolved_required_backend_inputs", List.of());
    }

    private static InvocationContext approvalContext(String grantId) {
        return new InvocationContext(null, "human:local-dev|actor_id=slack_requester", "agent:slack-live-smoke", "inv-test", null, null, null, null, grantId, List.of("slack.message.prepare", "slack.announcement.request"), List.of(), ignored -> true);
    }

    private static String text(Object value) {
        return value == null ? "" : value.toString().trim();
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }

    private static Map<String, Map<String, Object>> recordOfRecords(Object... pairs) {
        Map<String, Map<String, Object>> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), (Map<String, Object>) pairs[index + 1]);
        return result;
    }
}
