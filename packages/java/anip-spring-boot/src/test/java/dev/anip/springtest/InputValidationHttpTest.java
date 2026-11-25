package dev.anip.springtest;

import dev.anip.core.TokenRequest;
import dev.anip.service.ANIPService;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.ResultActions;

import java.util.List;

import static org.hamcrest.Matchers.startsWith;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * SPEC.md §6.3 "Parameter Validation" and "HTTP Status Codes" on the Spring
 * Boot binding. The Quarkus binding runs the same cases
 * ({@code dev.anip.quarkustest.InputValidationHttpTest}).
 */
@SpringBootTest(classes = AnipControllerTest.TestApp.class)
@AutoConfigureMockMvc
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class InputValidationHttpTest {

    private static final String REQUIRES = "parameters that match the capability's declared inputs";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ANIPService service;

    private String searchJwt;
    private String bookJwt;

    @BeforeAll
    void setUp() throws Exception {
        searchJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel", "finance"), "search_flights",
                null, null, 0, null)).getToken();
        bookJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel", "finance"), "book_flight",
                null, null, 0, null)).getToken();
    }

    private ResultActions invoke(String capability, String jwt, String body) throws Exception {
        var builder = post("/anip/invoke/" + capability)
                .contentType(MediaType.APPLICATION_JSON).content(body);
        if (jwt != null) {
            builder = builder.header("Authorization", "Bearer " + jwt);
        }
        return mockMvc.perform(builder);
    }

    private static ResultActions expectInvalidParameters(ResultActions result, String detail) throws Exception {
        return result
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.result").doesNotExist())
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.failure.detail").value(detail))
                .andExpect(jsonPath("$.failure.resolution.action").value("retry_now"))
                .andExpect(jsonPath("$.failure.resolution.recovery_class").value("retry_now"))
                .andExpect(jsonPath("$.failure.resolution.requires").value(REQUIRES))
                .andExpect(jsonPath("$.failure.retry").value(false))
                .andExpect(jsonPath("$.invocation_id").value(startsWith("inv-")));
    }

    // --- parameter validation, unary ---

    @Test
    void missingRequiredInputIs400InvalidParameters() throws Exception {
        expectInvalidParameters(
                invoke("search_flights", searchJwt, "{\"parameters\":{\"origin\":\"SEA\"}}"),
                "search_flights is missing required input(s): destination");
    }

    @Test
    void emptyBodyHasNoParameters() throws Exception {
        expectInvalidParameters(
                invoke("search_flights", searchJwt, "{}"),
                "search_flights is missing required input(s): origin, destination");
    }

    @Test
    void nullForARequiredInputIs400InvalidParameters() throws Exception {
        expectInvalidParameters(
                invoke("search_flights", searchJwt,
                        "{\"parameters\":{\"origin\":null,\"destination\":\"SFO\"}}"),
                "search_flights is missing required input(s): origin");
    }

    @Test
    void wrongTypeIs400InvalidParameters() throws Exception {
        expectInvalidParameters(
                invoke("search_flights", searchJwt,
                        "{\"parameters\":{\"origin\":5,\"destination\":[\"SFO\"]}}"),
                "search_flights has invalid input(s): 'origin' must be string, got number; "
                        + "'destination' must be string, got array");
    }

    @Test
    void validParametersStillSucceed() throws Exception {
        invoke("search_flights", searchJwt,
                "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\",\"extra\":[1]}}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    // --- parameter validation, streaming ---

    /** The body of an SSE response, once the stream has completed. */
    private String sse(ResultActions result) throws Exception {
        MvcResult started = result.andExpect(request().asyncStarted()).andReturn();
        started.getAsyncResult(5000);
        assertEquals(200, started.getResponse().getStatus());
        return started.getResponse().getContentAsString();
    }

    @Test
    void streamingInvocationIsRefusedWithTheSameFailure() throws Exception {
        String body = sse(invoke("search_flights", searchJwt,
                "{\"parameters\":{\"origin\":\"SEA\"},\"stream\":true}"));

        assertTrue(body.contains("event:failed"), body);
        assertTrue(body.contains("\"type\":\"invalid_parameters\""), body);
        assertTrue(body.contains(
                "\"detail\":\"search_flights is missing required input(s): destination\""), body);
        assertTrue(body.contains("\"action\":\"retry_now\""), body);
        assertTrue(body.contains("\"recovery_class\":\"retry_now\""), body);
        assertTrue(body.contains("\"requires\":\"" + REQUIRES + "\""), body);
        assertTrue(body.contains("\"retry\":false"), body);
        assertTrue(body.contains("\"invocation_id\":\"inv-"), body);
        assertTrue(!body.contains("event:completed"), body);
    }

    // --- the streaming path runs the unary pre-handler checks ---

    @Test
    void streamingInvocationWithoutItsBindingIsRefusedBeforeTheHandler() throws Exception {
        String holdJwt = service.issueToken("user@test.com", new TokenRequest(
                "agent:test", List.of("travel"), "hold_seat", null, null, 0, null)).getToken();
        String body = sse(invoke("hold_seat", holdJwt, "{\"parameters\":{},\"stream\":true}"));

        assertTrue(body.contains("event:failed"), body);
        assertTrue(body.contains("\"type\":\"binding_missing\""), body);
        assertTrue(body.contains("\"action\":\"obtain_binding\""), body);
        assertTrue(body.contains("\"invocation_id\":\"inv-"), body);
        assertTrue(!body.contains("event:completed"), body);

        // The same request, unary.
        invoke("hold_seat", holdJwt, "{\"parameters\":{}}")
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.failure.type").value("binding_missing"));
    }

    @Test
    void streamingInvocationWithATokenForAnotherCapabilityCarriesTheUnaryFailure() throws Exception {
        String body = sse(invoke("search_flights", bookJwt,
                "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"},\"stream\":true}"));

        assertTrue(body.contains("event:failed"), body);
        assertTrue(body.contains("\"type\":\"purpose_mismatch\""), body);
        assertTrue(body.contains("\"resolution\":{\"action\":"), body);
        assertTrue(body.contains("\"retry\":false"), body);
        assertTrue(!body.contains("event:completed"), body);
    }

    @Test
    void streamingInvocationWithAnUnknownGrantCarriesTheUnaryFailure() throws Exception {
        for (String grant : List.of("", "grant_0123456789ab")) {
            String body = sse(invoke("search_flights", searchJwt,
                    "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"},"
                            + "\"approval_grant\":\"" + grant + "\",\"stream\":true}"));

            assertTrue(body.contains("event:failed"), body);
            assertTrue(body.contains("\"type\":\"grant_not_found\""), body);
            assertTrue(body.contains("\"action\":\"contact_service_owner\""), body);
            assertTrue(!body.contains("event:completed"), body);
        }
    }

    @Test
    void streamingInvocationWithValidParametersCompletes() throws Exception {
        String body = sse(invoke("search_flights", searchJwt,
                "{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"},\"stream\":true}"));
        assertTrue(body.contains("event:completed"), body);
    }

    // --- a request body that is not JSON (SPEC.md §6.3, HTTP Status Codes) ---

    private static ResultActions expectBodyRefused(ResultActions result) throws Exception {
        return result
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.failure.detail").isNotEmpty())
                .andExpect(jsonPath("$.failure.resolution.action").value("retry_now"))
                .andExpect(jsonPath("$.failure.resolution.recovery_class").value("retry_now"))
                .andExpect(jsonPath("$.failure.retry").value(false));
    }

    @Test
    void invokeBodyThatIsNotJsonIs400InvalidParameters() throws Exception {
        expectBodyRefused(invoke("search_flights", searchJwt, "{\"parameters\": "));
    }

    @Test
    void invokeBodyThatIsNotAnObjectIs400InvalidParameters() throws Exception {
        expectBodyRefused(invoke("search_flights", searchJwt, "[\"SEA\"]"));
        expectBodyRefused(invoke("search_flights", searchJwt, "{\"parameters\":[\"SEA\"]}"));
    }

    @Test
    void parametersThatAreNotAnObjectAreRefusedWithTheSpecifiedDetail() throws Exception {
        // SPEC.md §6.3: "<capability> parameters must be an object, got <JSON type>".
        String[][] cases = {
                {"[\"SEA\"]", "array"}, {"\"SEA\"", "string"}, {"1.5", "number"}, {"true", "boolean"}};
        for (String[] c : cases) {
            expectBodyRefused(invoke("search_flights", searchJwt, "{\"parameters\":" + c[0] + "}"))
                    .andExpect(jsonPath("$.failure.detail")
                            .value("search_flights parameters must be an object, got " + c[1]))
                    .andExpect(jsonPath("$.failure.resolution.requires").value(REQUIRES));
        }
    }

    @Test
    void invokeBodyThatIsNotJsonWithoutCredentialIs401() throws Exception {
        invoke("search_flights", null, "{\"parameters\": ")
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
        invoke("search_flights", "not-a-token", "{\"parameters\": ")
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.failure.type").value("invalid_token"));
    }

    private ResultActions tokens(String bearer, String body) throws Exception {
        var builder = post("/anip/tokens").contentType(MediaType.APPLICATION_JSON).content(body);
        if (bearer != null) {
            builder = builder.header("Authorization", "Bearer " + bearer);
        }
        return mockMvc.perform(builder);
    }

    @Test
    void tokenRequestBodyThatIsNotJsonIs400InvalidParameters() throws Exception {
        expectBodyRefused(tokens("valid-api-key", "{\"scope\": "));
        expectBodyRefused(tokens("valid-api-key", "[]"));
        expectBodyRefused(tokens("valid-api-key", ""));
    }

    @Test
    void tokenRequestBodyThatIsNotJsonWithoutCredentialIs401() throws Exception {
        tokens(null, "{\"scope\": ")
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
        tokens("bad-key", "{\"scope\": ")
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
    }

    @Test
    void wellFormedTokenRequestStillIssues() throws Exception {
        tokens("valid-api-key",
                "{\"subject\":\"agent\",\"scope\":[\"travel\"],\"capability\":\"search_flights\"}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.issued").value(true));
    }

    // --- stream: true on a capability that only supports unary ---

    @Test
    void streamingRequestedFromAUnaryCapabilityIsAJsonFailure() throws Exception {
        invoke("book_flight", bookJwt, "{\"parameters\":{\"flight_id\":\"FL-001\"},\"stream\":true}")
                .andExpect(request().asyncNotStarted())
                .andExpect(status().isBadRequest())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("streaming_not_supported"))
                .andExpect(jsonPath("$.failure.detail").isNotEmpty())
                .andExpect(jsonPath("$.failure.resolution.action").value("check_manifest"))
                .andExpect(jsonPath("$.failure.resolution.recovery_class").value("revalidate_then_retry"))
                .andExpect(jsonPath("$.failure.retry").value(false));
    }
}
