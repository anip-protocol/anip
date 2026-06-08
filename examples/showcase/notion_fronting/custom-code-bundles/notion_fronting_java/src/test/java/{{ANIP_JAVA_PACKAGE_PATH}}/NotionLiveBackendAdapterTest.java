package {{ANIP_JAVA_PACKAGE_NAME}};

import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class NotionLiveBackendAdapterTest {
    @Test
    @EnabledIfEnvironmentVariable(named = "NOTION_TOKEN", matches = ".+")
    void executesLiveReadsAndPreparedPreviewsWithoutMutation() {
        String workspaceScope = requiredEnv("NOTION_WORKSPACE_SCOPE");
        String parentId = requiredEnv("NOTION_PARENT_PAGE_ID");
        String databaseId = requiredEnv("NOTION_DATABASE_ID");
        BackendAdapter adapter = BackendAdapter.defaultAdapter();
        Map<String, Object> searchParams = record("workspace_scope", workspaceScope, "query", "ANIP", "limit", 5);
        Map<String, Object> search = adapter.execute(capability("notion.workspace.search_context"), plan(searchParams), searchParams, null);
        assertEquals("completed", search.get("execution_status"), () -> "Search failed: " + search);

        Map<String, Object> queryParams = record("database_id", databaseId, "limit", 5);
        Map<String, Object> query = adapter.execute(capability("notion.database.query_context"), plan(queryParams), queryParams, null);
        assertEquals("completed", query.get("execution_status"), () -> "Query failed: " + query);

        Map<String, Object> createParams = record("parent_id", parentId, "title", "ANIP Notion Java preview", "content_summary", "Preview only");
        Map<String, Object> create = adapter.execute(capability("notion.page.create.prepare"), plan(createParams), createParams, null);
        assertEquals("prepared", create.get("execution_status"));
        assertEquals(false, create.get("mutation_performed"));
    }

    @Test
    @EnabledIfEnvironmentVariable(named = "NOTION_TOKEN", matches = ".+")
    void generatedHandlerStopsWithoutApprovalAndCreatesWithGrant() {
        String parentId = requiredEnv("NOTION_PARENT_PAGE_ID");
        CapabilityDef capability = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
            .filter(item -> "notion.page.create.prepare".equals(item.getDeclaration().getName()))
            .findFirst()
            .orElseThrow();
        Map<String, Object> params = record("parent_id", parentId, "title", "ANIP approved Notion Java page at " + Instant.now(), "content_summary", "Created by explicit ANIP Notion Java generated-handler smoke.");

        Map<String, Object> preview = capability.getHandler().apply(approvalContext(null), withApprovalRequest(params));
        assertEquals("prepared", preview.get("execution_status"));
        assertEquals(false, preview.get("mutation_performed"));

        if ("true".equals(System.getenv("ANIP_NOTION_ALLOW_MUTATION"))) {
            Map<String, Object> created = capability.getHandler().apply(approvalContext("grant_live_java_notion_smoke"), params);
            assertEquals("completed", created.get("execution_status"));
            assertEquals(true, created.get("mutation_performed"));
            assertNotNull(((Map<?, ?>) created.get("created_page")).get("id"));
        }
    }

    private static String requiredEnv(String name) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? "" : value;
    }

    private static Map<String, Object> capability(String id) {
        return GeneratedRuntimeTarget.capabilities().stream().filter(item -> id.equals(item.get("capability_id"))).findFirst().orElseThrow();
    }

    private static Map<String, Object> plan(Map<String, Object> params) {
        return record("selected_binding", null, "semantic_input", params, "adapter_input", params, "backend_input_contract", record("mode", "explicit", "required", List.of(), "optional", List.of()), "unresolved_required_backend_inputs", List.of());
    }

    private static InvocationContext approvalContext(String grantId) {
        return new InvocationContext(null, "human:local-dev|actor_id=notion_fronting_consumer", "agent:notion-live-smoke", "inv-test", null, null, null, null, grantId, List.of("notion.page.create.prepare"), List.of(), ignored -> true);
    }

    private static Map<String, Object> withApprovalRequest(Map<String, Object> source) {
        Map<String, Object> result = new LinkedHashMap<>(source);
        result.put("request_execution_approval", true);
        return result;
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }
}

