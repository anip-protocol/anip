package {{ANIP_JAVA_PACKAGE_NAME}};

import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SupersetLiveBackendAdapterTest {
    @Test
    @EnabledIfEnvironmentVariable(named = "SUPERSET_BASE_URL", matches = ".+")
    void executesLiveDiscoveryAndPreparedPreviewsWithoutMutation() {
        String workspaceScope = firstNonBlank(System.getenv("SUPERSET_WORKSPACE_SCOPE"), "local");
        Map<String, Object> discovery = invoke("superset.analytics.discover_context", record("workspace_scope", workspaceScope, "query", "birth", "limit", 5));
        assertEquals("completed", discovery.get("execution_status"), () -> "Discovery failed: " + discovery);
        assertTrue(((Number) ((Map<?, ?>) discovery.get("result")).get("count")).intValue() >= 0);

        Map<String, Object> chart = invoke("superset.chart.preview.create", record("dataset_ref", "1", "metric", "count", "visualization_type", "bar", "title", "ANIP Java preview chart"));
        assertEquals("prepared", chart.get("execution_status"));
        assertEquals(false, chart.get("mutation_performed"));
        assertEquals(false, ((Map<?, ?>) ((Map<?, ?>) chart.get("superset_request")).get("body")).get("save_chart"));

        Map<String, Object> dataset = invoke("superset.dataset.draft.prepare", record("database_ref", "1", "dataset_purpose", "ANIP smoke", "query_intent", "Count records by category"));
        assertEquals("prepared", dataset.get("execution_status"));
        assertEquals(false, dataset.get("mutation_performed"));
    }

    private static Map<String, Object> invoke(String capabilityId, Map<String, Object> params) {
        CapabilityDef capability = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
            .filter(item -> capabilityId.equals(item.getDeclaration().getName()))
            .findFirst()
            .orElseThrow();
        return capability.getHandler().apply(new InvocationContext(null, "human:local-dev|actor_id=superset_fronting_consumer", "agent:superset-live-smoke", "inv-test", null, null, null, null, null, List.of(capabilityId), List.of(), ignored -> true), params);
    }

    private static Map<String, Object> record(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < pairs.length; index += 2) result.put(String.valueOf(pairs[index]), pairs[index + 1]);
        return result;
    }

    private static String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) return value;
        }
        return "";
    }
}
