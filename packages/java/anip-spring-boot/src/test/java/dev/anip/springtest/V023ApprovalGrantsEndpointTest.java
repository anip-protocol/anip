package dev.anip.springtest;

import dev.anip.core.ApprovalRequest;
import dev.anip.core.GrantPolicy;
import dev.anip.core.TokenRequest;
import dev.anip.server.SqliteStorage;
import dev.anip.service.ANIPService;
import dev.anip.service.V023;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.startsWith;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * SPEC.md §4.9 — POST /anip/approval_grants on the Spring Boot binding.
 * Mirrors the Quarkus binding's endpoint test.
 */
@SpringBootTest(classes = AnipControllerTest.TestApp.class)
@AutoConfigureMockMvc
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class V023ApprovalGrantsEndpointTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ANIPService service;

    private String approverJwt;
    private String otherJwt;

    @BeforeAll
    void setUp() throws Exception {
        approverJwt = service.issueToken("approver@test.com", new TokenRequest(
                "approver:test", List.of("approver:search_flights"), null,
                null, null, 0, null)).getToken();
        otherJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel", "approver:book_flight"), null,
                null, null, 0, null)).getToken();
    }

    private String persistRequest(String id, String status) throws Exception {
        SqliteStorage storage = (SqliteStorage) service.getStorage();
        storage.storeApprovalRequest(new ApprovalRequest(
                id, "search_flights", List.of("travel"),
                Map.of("subject", "alice"), null,
                Map.of(), V023.sha256Digest(Map.of()),
                Map.of("origin", "SEA"), V023.sha256Digest(Map.of("origin", "SEA")),
                new GrantPolicy(List.of("one_time", "session_bound"), "one_time", 600, 2),
                status, null, null,
                V023.utcNowIso(), V023.utcInIso(900)));
        return id;
    }

    private ResultActions issue(String jwt, String body) throws Exception {
        var request = post("/anip/approval_grants")
                .contentType(MediaType.APPLICATION_JSON).content(body);
        if (jwt != null) {
            request = request.header("Authorization", "Bearer " + jwt);
        }
        return mockMvc.perform(request);
    }

    private static String body(String id, String rest) {
        return "{\"approval_request_id\":\"" + id + "\"" + rest + "}";
    }

    @Test
    void discoveryAdvertisesTheEndpointThatExists() throws Exception {
        mockMvc.perform(get("/.well-known/anip"))
                .andExpect(jsonPath("$.anip_discovery.endpoints.approval_grants")
                        .value("/anip/approval_grants"));
    }

    @Test
    void approverReceivesTheBareSignedGrant() throws Exception {
        String id = persistRequest("apr_spring_ok", ApprovalRequest.STATUS_PENDING);
        issue(approverJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.grant_id").value(startsWith("grant_")))
                .andExpect(jsonPath("$.approval_request_id").value(id))
                .andExpect(jsonPath("$.capability").value("search_flights"))
                .andExpect(jsonPath("$.max_uses").value(1))
                .andExpect(jsonPath("$.signature").isNotEmpty());
    }

    @Test
    void missingBearerIs401() throws Exception {
        issue(null, body("apr_x", ",\"grant_type\":\"one_time\""))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.failure.type").value("authentication_required"))
                .andExpect(jsonPath("$.grant_id").doesNotExist());
    }

    @Test
    void malformedJsonIsInvalidParameters() throws Exception {
        issue(approverJwt, "{not json")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"));
    }

    @Test
    void nonObjectBodyIsInvalidParameters() throws Exception {
        issue(approverJwt, "[\"apr_x\"]")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"));
    }

    @Test
    void bodyOutsideTheSchemaIsInvalidParametersAndLeavesTheRequestPending() throws Exception {
        String id = persistRequest("apr_spring_schema", ApprovalRequest.STATUS_PENDING);
        String[] invalid = {
                "",
                ",\"grant_type\":\"forever\"",
                ",\"grant_type\":\"session_bound\"",
                ",\"grant_type\":\"one_time\",\"session_id\":\"s1\"",
                ",\"grant_type\":\"one_time\",\"max_uses\":2",
                ",\"grant_type\":\"one_time\",\"max_uses\":0",
                ",\"grant_type\":\"one_time\",\"expires_in_seconds\":0",
                ",\"grant_type\":\"one_time\",\"expires_in_seconds\":\"60\"",
                ",\"grant_type\":\"one_time\",\"expires_in_seconds\":1.5",
                ",\"grant_type\":7",
        };
        for (String rest : invalid) {
            issue(approverJwt, body(id, rest))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                    .andExpect(jsonPath("$.grant_id").doesNotExist());
        }
        issue(approverJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isOk());
    }

    @Test
    void unknownRequestIsNotFound() throws Exception {
        issue(approverJwt, body("apr_spring_missing", ",\"grant_type\":\"one_time\""))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.failure.type").value("approval_request_not_found"));
    }

    @Test
    void tokenWithoutApproverScopeForTheCapabilityIsRefused() throws Exception {
        String id = persistRequest("apr_spring_unauth", ApprovalRequest.STATUS_PENDING);
        issue(otherJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.failure.type").value("approver_not_authorized"))
                .andExpect(jsonPath("$.grant_id").doesNotExist());
        // Still pending: the real approver can decide it.
        issue(approverJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isOk());
    }

    @Test
    void decidedRequestIsRefusedBeforeApproverAuthorityIsChecked() throws Exception {
        String id = persistRequest("apr_spring_decided", ApprovalRequest.STATUS_PENDING);
        issue(approverJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isOk());

        issue(approverJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.failure.type").value("approval_request_already_decided"));
        issue(otherJwt, body(id, ",\"grant_type\":\"one_time\""))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.failure.type").value("approval_request_already_decided"));
    }

    @Test
    void sessionBoundGrantCarriesItsSessionAndStaysWithinPolicy() throws Exception {
        String id = persistRequest("apr_spring_session", ApprovalRequest.STATUS_PENDING);
        issue(approverJwt, body(id,
                ",\"grant_type\":\"session_bound\",\"session_id\":\"s1\",\"max_uses\":3"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.grant_id").doesNotExist());
        issue(approverJwt, body(id,
                ",\"grant_type\":\"session_bound\",\"session_id\":\"s1\",\"max_uses\":2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.session_id").value("s1"))
                .andExpect(jsonPath("$.max_uses").value(2));
    }
}
