package {{ANIP_JAVA_PACKAGE_NAME}};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GitHubLiveBackendAdapterTest {

    @Test
    @EnabledIfEnvironmentVariable(named = "GITHUB_TOKEN", matches = ".+")
    void executesLiveReadsAndPreparedPreviewsWithoutMutation() {
        String owner = System.getenv("GITHUB_OWNER");
        String repo = System.getenv("GITHUB_REPO");
        assertTrue(owner != null && !owner.isBlank(), "GITHUB_OWNER is required");
        assertTrue(repo != null && !repo.isBlank(), "GITHUB_REPO is required");

        BackendAdapter adapter = BackendAdapter.defaultAdapter();
        assertEquals("completed", adapter.execute(capability("github.repo.search_context"), plan(record("owner", owner, "repo", repo, "query", "is:issue", "limit", 5)), record("owner", owner, "repo", repo, "query", "is:issue", "limit", 5), null).get("execution_status"));
        Map<String, Object> issue = adapter.execute(capability("github.issue.prepare"), plan(record("owner", owner, "repo", repo, "title", "ANIP GitHub Java preview", "body", "Preview only")), record("owner", owner, "repo", repo, "title", "ANIP GitHub Java preview", "body", "Preview only"), null);
        assertEquals("prepared", issue.get("execution_status"));
        assertEquals(false, issue.get("mutation_performed"));
        assertEquals("completed", adapter.execute(capability("github.release_notes.prepare"), plan(record("owner", owner, "repo", repo, "range", "HEAD", "audience", "internal")), record("owner", owner, "repo", repo, "range", "HEAD", "audience", "internal"), null).get("execution_status"));
    }

    @Test
    @EnabledIfEnvironmentVariable(named = "GITHUB_TOKEN", matches = ".+")
    void generatedHandlerStopsWithoutApprovalAndCreatesWithGrant() {
        String owner = System.getenv("GITHUB_OWNER");
        String repo = System.getenv("GITHUB_REPO");
        assertTrue(owner != null && !owner.isBlank(), "GITHUB_OWNER is required");
        assertTrue(repo != null && !repo.isBlank(), "GITHUB_REPO is required");
        CapabilityDef capability = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
                .filter(item -> "github.issue.prepare".equals(item.getDeclaration().getName()))
                .findFirst()
                .orElseThrow();
        Map<String, Object> params = record("owner", owner, "repo", repo, "title", "ANIP approved GitHub Java issue at " + Instant.now(), "body", "Created by explicit ANIP GitHub Java generated-handler smoke.");

        Map<String, Object> preview = capability.getHandler().apply(approvalContext(null), withApprovalRequest(params));
        assertEquals("prepared", preview.get("execution_status"));
        assertEquals(false, preview.get("mutation_performed"));

        if ("true".equals(System.getenv("ANIP_GITHUB_ALLOW_MUTATION"))) {
            Map<String, Object> created = capability.getHandler().apply(approvalContext("grant_live_java_github_smoke"), params);
            assertEquals("completed", created.get("execution_status"));
            assertEquals(true, created.get("mutation_performed"));
            assertTrue(((Map<?, ?>) created.get("created_issue")).get("number") != null);
        }
    }

    private static Map<String, Object> capability(String id) {
        return GeneratedRuntimeTarget.capabilities().stream().filter(item -> id.equals(item.get("capability_id"))).findFirst().orElseThrow();
    }

    private static Map<String, Object> plan(Map<String, Object> params) {
        return record("selected_binding", null, "semantic_input", params, "adapter_input", params, "backend_input_contract", record("mode", "explicit", "required", List.of(), "optional", List.of()), "unresolved_required_backend_inputs", List.of());
    }

    private static InvocationContext approvalContext(String grantId) {
        return new InvocationContext(null, "human:local-dev|actor_id=github_fronting_consumer", "agent:github-live-smoke", "inv-test", null, null, null, null, grantId, List.of("github.issue.prepare"), List.of(), ignored -> true);
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
