package {{ANIP_JAVA_PACKAGE_NAME}};

import dev.anip.core.ANIPError;
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
import static org.junit.jupiter.api.Assertions.assertThrows;

class NotionLiveBackendAdapterTest {
    // Principals the 0.2.0 runtime policy bindings select.
    private static final String REVIEWER = "human:local-dev|actor_id=notion_governance_reviewer";
    private static final String REQUESTER = "human:local-dev|actor_id=governed_notion_requester";
    private static final String NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability.";

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
        CapabilityDef capability = pageCreateCapability();
        Map<String, Object> params = record("parent_id", parentId, "title", "ANIP approved Notion Java page at " + Instant.now(), "content_summary", "Created by explicit ANIP Notion Java generated-handler smoke.");

        // notion_governance_reviewer may create pages: without a grant it gets a preview.
        Map<String, Object> preview = capability.getHandler().apply(context(REVIEWER, null), params);
        assertEquals("prepared", preview.get("execution_status"));
        assertEquals(false, preview.get("mutation_performed"));

        // governed_notion_requester's binding requires approval: no grant, no adapter call.
        ANIPError approval = assertThrows(ANIPError.class, () -> capability.getHandler().apply(context(REQUESTER, null), params));
        assertEquals("approval_required", approval.getErrorType());

        if ("true".equals(System.getenv("ANIP_NOTION_ALLOW_MUTATION"))) {
            // The runtime sets the approval grant only after validating it.
            Map<String, Object> created = capability.getHandler().apply(context(REQUESTER, "grant_live_java_notion_smoke"), params);
            assertEquals("completed", created.get("execution_status"));
            assertEquals(true, created.get("mutation_performed"));
            assertNotNull(((Map<?, ?>) created.get("created_page")).get("id"));
        }
    }

    // The generated policy refuses a principal no binding selects before the
    // backend adapter runs, so this needs no Notion credentials.
    @Test
    void generatedHandlerRefusesUnboundActors() {
        CapabilityDef capability = pageCreateCapability();
        Map<String, Object> params = record("parent_id", "11111111-1111-4111-8111-111111111111", "title", "Refused", "content_summary", "Never reaches Notion.");
        for (String principal : List.of("human:local-dev", "human:local-dev|actor_id=notion_fronting_consumer")) {
            ANIPError error = assertThrows(ANIPError.class, () -> capability.getHandler().apply(context(principal, "grant_live_java_notion_smoke"), params), principal);
            assertEquals("denied", error.getErrorType(), principal);
            assertEquals(NO_BINDING_DETAIL, error.getDetail(), principal);
        }
    }

    private static CapabilityDef pageCreateCapability() {
        return GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
            .filter(item -> "notion.page.create.prepare".equals(item.getDeclaration().getName()))
            .findFirst()
            .orElseThrow();
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

    private static InvocationContext context(String principal, String grantId) {
        return new InvocationContext(null, principal, "agent:notion-live-smoke", "inv-test", null, null, null, null, grantId, List.of("notion.page.create.prepare"), List.of(), ignored -> true);
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }
}

