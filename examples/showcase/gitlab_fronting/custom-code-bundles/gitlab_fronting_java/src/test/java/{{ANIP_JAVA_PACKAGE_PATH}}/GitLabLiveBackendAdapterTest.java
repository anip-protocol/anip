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

class GitLabLiveBackendAdapterTest {

    @Test
    @EnabledIfEnvironmentVariable(named = "GITLAB_TOKEN", matches = ".+")
    void executesLiveReadsAndPreparedPreviewsWithoutMutation() {
        String project = projectId();
        assertTrue(project != null && !project.isBlank(), "GITLAB_PROJECT_ID or GITLAB_NAMESPACE/GITLAB_PROJECT is required");

        BackendAdapter adapter = BackendAdapter.defaultAdapter();
        assertEquals("completed", adapter.execute(capability("gitlab.project.search_context"), plan(record("project_id", project, "query", "ANIP", "limit", 5)), record("project_id", project, "query", "ANIP", "limit", 5), null).get("execution_status"));
        Map<String, Object> issue = adapter.execute(capability("gitlab.issue.prepare"), plan(record("project_id", project, "title", "ANIP GitLab Java preview", "body", "Preview only")), record("project_id", project, "title", "ANIP GitLab Java preview", "body", "Preview only"), null);
        assertEquals("prepared", issue.get("execution_status"));
        assertEquals(false, issue.get("mutation_performed"));
        assertEquals("completed", adapter.execute(capability("gitlab.release_notes.prepare"), plan(record("project_id", project, "range", "HEAD", "audience", "internal")), record("project_id", project, "range", "HEAD", "audience", "internal"), null).get("execution_status"));
    }

    @Test
    @EnabledIfEnvironmentVariable(named = "GITLAB_TOKEN", matches = ".+")
    void generatedHandlerStopsWithoutApprovalAndCreatesWithGrant() {
        String project = projectId();
        assertTrue(project != null && !project.isBlank(), "GITLAB_PROJECT_ID or GITLAB_NAMESPACE/GITLAB_PROJECT is required");
        CapabilityDef capability = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
                .filter(item -> "gitlab.issue.prepare".equals(item.getDeclaration().getName()))
                .findFirst()
                .orElseThrow();
        Map<String, Object> params = record("project_id", project, "namespace", namespace(project), "project", projectName(project), "title", "ANIP approved GitLab Java issue at " + Instant.now(), "body", "Created by explicit ANIP GitLab Java generated-handler smoke.");

        Map<String, Object> preview = capability.getHandler().apply(approvalContext(null), withApprovalRequest(params));
        assertEquals("prepared", preview.get("execution_status"));
        assertEquals(false, preview.get("mutation_performed"));

        if ("true".equals(System.getenv("ANIP_GITLAB_ALLOW_MUTATION"))) {
            Map<String, Object> created = capability.getHandler().apply(approvalContext("grant_live_java_gitlab_smoke"), params);
            assertEquals("completed", created.get("execution_status"));
            assertEquals(true, created.get("mutation_performed"));
            assertTrue(((Map<?, ?>) created.get("created_issue")).get("iid") != null);
        }
    }

    private static String projectId() {
        String explicit = System.getenv("GITLAB_PROJECT_ID");
        if (explicit != null && !explicit.isBlank()) return explicit;
        String namespace = System.getenv("GITLAB_NAMESPACE");
        String project = System.getenv("GITLAB_PROJECT");
        return namespace != null && !namespace.isBlank() && project != null && !project.isBlank() ? namespace + "/" + project : "";
    }

    private static String namespace(String projectId) {
        String explicit = System.getenv("GITLAB_NAMESPACE");
        if (explicit != null && !explicit.isBlank()) return explicit;
        String[] parts = projectId.split("/", 2);
        return parts.length == 2 ? parts[0] : "";
    }

    private static String projectName(String projectId) {
        String explicit = System.getenv("GITLAB_PROJECT");
        if (explicit != null && !explicit.isBlank()) return explicit;
        String[] parts = projectId.split("/", 2);
        return parts.length == 2 ? parts[1] : "";
    }

    private static Map<String, Object> capability(String id) {
        return GeneratedRuntimeTarget.capabilities().stream().filter(item -> id.equals(item.get("capability_id"))).findFirst().orElseThrow();
    }

    private static Map<String, Object> plan(Map<String, Object> params) {
        return record("selected_binding", null, "semantic_input", params, "adapter_input", params, "backend_input_contract", record("mode", "explicit", "required", List.of(), "optional", List.of()), "unresolved_required_backend_inputs", List.of());
    }

    private static InvocationContext approvalContext(String grantId) {
        return new InvocationContext(null, "human:local-dev|actor_id=gitlab_fronting_consumer", "agent:gitlab-live-smoke", "inv-test", null, null, null, null, grantId, List.of("gitlab.issue.prepare"), List.of(), ignored -> true);
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
