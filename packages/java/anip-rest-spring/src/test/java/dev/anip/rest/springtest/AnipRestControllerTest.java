package dev.anip.rest.springtest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.InputResolution;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.rest.spring.AnipRestController;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Bean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class AnipRestControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ANIPService anipService;

    private String validJwt;

    @SpringBootApplication
    static class TestApp {
        @Bean
        ANIPService anipService() {
            ANIPService svc = new ANIPService(new ServiceConfig()
                    .setServiceId("test-rest-svc")
                    .setCapabilities(List.of(
                            new CapabilityDef(
                                    new CapabilityDeclaration(
                                            "search_flights", "Search for flights", "1.0",
                                            List.of(
                                                    new CapabilityInput("origin", "string", true, "Origin airport"),
                                                    new CapabilityInput("destination", "string", true, "Destination airport"),
                                                    new CapabilityInput("max_results", "integer", false, "Max results"),
                                                    // Required, and the declaration says what happens when it is absent.
                                                    new CapabilityInput("cabin", "string", true, null,
                                                            "Cabin; asked for when absent", null, false, null, null, null,
                                                            new InputResolution(ResolutionMode.CLARIFY, null,
                                                                    ResolutionBehavior.CLARIFY, null, null))
                                            ),
                                            new CapabilityOutput("object", List.of("flights")),
                                            new SideEffect("read", "not_applicable"),
                                            List.of("travel"), null, null,
                                            List.of("sync")
                                    ),
                                    (ctx, params) -> Map.of("flights", List.of(
                                            Map.of("id", "FL-001", "price", 199.99)
                                    ))
                            ),
                            new CapabilityDef(
                                    new CapabilityDeclaration(
                                            "book_flight", "Book a flight", "1.0",
                                            List.of(
                                                    new CapabilityInput("flight_id", "string", true, "Flight ID")
                                            ),
                                            new CapabilityOutput("object", List.of("booking_id")),
                                            new SideEffect("irreversible", "none"),
                                            List.of("travel", "finance"), null, null,
                                            List.of("sync")
                                    ),
                                    (ctx, params) -> Map.of("booking_id", "BK-001", "status", "confirmed")
                            )
                    ))
                    .setStorage(":memory:")
                    .setAuthenticate(bearer -> {
                        if ("valid-api-key".equals(bearer)) {
                            return Optional.of("user@test.com");
                        }
                        return Optional.empty();
                    })
                    .setRetentionIntervalSeconds(-1));
            try {
                svc.start();
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
            return svc;
        }

        @Bean
        AnipRestController anipRestController(ANIPService service) {
            return new AnipRestController(service);
        }
    }

    @BeforeAll
    void setUp() throws Exception {
        TokenResponse resp = anipService.issueToken("user@test.com",
                new TokenRequest("agent@test.com", List.of("travel", "finance"),
                        "search_flights", null, null, 2, null));
        validJwt = resp.getToken();
    }

    // --- GET routing (read capability) ---

    @Test
    void testGetReadCapability() throws Exception {
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer valid-api-key")
                        .param("origin", "SFO")
                        .param("destination", "LAX"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.result.flights").isArray());
    }

    @Test
    void testGetReadCapabilityWithJwt() throws Exception {
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer " + validJwt)
                        .param("origin", "SFO")
                        .param("destination", "LAX"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    void testGetQueryParamTypeConversion() throws Exception {
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer valid-api-key")
                        .param("origin", "SFO")
                        .param("destination", "LAX")
                        .param("max_results", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    // --- POST routing (write capability) ---

    @Test
    void testPostWriteCapability() throws Exception {
        mockMvc.perform(post("/api/book_flight")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"flight_id\":\"FL-001\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.result.booking_id").value("BK-001"));
    }

    @Test
    void testPostWithParametersWrapper() throws Exception {
        mockMvc.perform(post("/api/book_flight")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"parameters\":{\"flight_id\":\"FL-001\"}}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    // --- Parameter validation (SPEC.md §6.3) ---

    @Test
    void testInputThatDeclaresOnMissingIsNotDemandedOfTheCaller() throws Exception {
        // 'cabin' is required and declares resolution.on_missing.
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer valid-api-key")
                        .param("origin", "SFO")
                        .param("destination", "LAX"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
        mockMvc.perform(get("/rest/openapi.json"))
                .andExpect(jsonPath("$.paths['/api/search_flights'].get.parameters[?(@.name=='cabin')].required")
                        .value(false))
                .andExpect(jsonPath("$.paths['/api/search_flights'].get.parameters[?(@.name=='origin')].required")
                        .value(true));
    }

    private static final String REQUIRES = "parameters that match the capability's declared inputs";

    @Test
    void testGetMissingRequiredInputIsInvalidParameters() throws Exception {
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer valid-api-key")
                        .param("origin", "SFO"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.failure.detail")
                        .value("search_flights is missing required input(s): destination"))
                .andExpect(jsonPath("$.failure.resolution.action").value("retry_now"))
                .andExpect(jsonPath("$.failure.resolution.recovery_class").value("retry_now"))
                .andExpect(jsonPath("$.failure.resolution.requires").value(REQUIRES))
                .andExpect(jsonPath("$.failure.retry").value(false))
                .andExpect(jsonPath("$.invocation_id").exists());
    }

    @Test
    void testGetQueryParamOfTheWrongTypeIsInvalidParameters() throws Exception {
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer valid-api-key")
                        .param("origin", "SFO")
                        .param("destination", "LAX")
                        .param("max_results", "many"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.failure.detail").value(
                        "search_flights has invalid input(s): 'max_results' must be integer, got string"));
    }

    @Test
    void testPostMissingRequiredInputIsInvalidParameters() throws Exception {
        mockMvc.perform(post("/api/book_flight")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.failure.detail")
                        .value("book_flight is missing required input(s): flight_id"))
                .andExpect(jsonPath("$.failure.resolution.action").value("retry_now"))
                .andExpect(jsonPath("$.failure.retry").value(false));
    }

    @Test
    void testPostWrongTypeIsInvalidParameters() throws Exception {
        mockMvc.perform(post("/api/book_flight")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"flight_id\":7}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.failure.detail").value(
                        "book_flight has invalid input(s): 'flight_id' must be string, got number"));
    }

    // --- A request body that is not JSON (SPEC.md §6.3, HTTP Status Codes) ---

    @Test
    void testPostBodyThatIsNotJsonIsInvalidParameters() throws Exception {
        for (String body : List.of("{\"flight_id\": ", "[\"FL-001\"]", "{\"parameters\":7}")) {
            mockMvc.perform(post("/api/book_flight")
                            .header("Authorization", "Bearer valid-api-key")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(body))
                    .andExpect(status().isBadRequest())
                    .andExpect(jsonPath("$.success").value(false))
                    .andExpect(jsonPath("$.failure.type").value("invalid_parameters"))
                    .andExpect(jsonPath("$.failure.resolution.action").value("retry_now"))
                    .andExpect(jsonPath("$.failure.resolution.recovery_class").value("retry_now"))
                    .andExpect(jsonPath("$.failure.retry").value(false));
        }
    }

    @Test
    void testPostBodyThatIsNotJsonWithoutCredentialIs401() throws Exception {
        mockMvc.perform(post("/api/book_flight")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"flight_id\": "))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
    }

    // --- Auth errors ---

    @Test
    void testMissingAuth() throws Exception {
        mockMvc.perform(get("/api/search_flights"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
    }

    @Test
    void testInvalidAuth() throws Exception {
        mockMvc.perform(get("/api/search_flights")
                        .header("Authorization", "Bearer bad-key"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false));
    }

    // --- Unknown capability ---

    @Test
    void testUnknownCapability() throws Exception {
        mockMvc.perform(get("/api/nonexistent")
                        .header("Authorization", "Bearer valid-api-key"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("unknown_capability"));
    }

    // --- OpenAPI ---

    @Test
    void testOpenApi() throws Exception {
        mockMvc.perform(get("/rest/openapi.json"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.openapi").value("3.1.0"))
                .andExpect(jsonPath("$.paths").exists())
                .andExpect(jsonPath("$.components").exists());
    }

    // --- Swagger UI ---

    @Test
    void testDocs() throws Exception {
        mockMvc.perform(get("/rest/docs"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML));
    }
}
