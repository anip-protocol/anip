package dev.anip.rest.springtest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
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
                                                    new CapabilityInput("max_results", "integer", false, "Max results")
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
