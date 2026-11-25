package dev.anip.graphql.springtest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.graphql.spring.AnipGraphQLController;
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

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class AnipGraphQLControllerTest {

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
                    .setServiceId("test-graphql-svc")
                    .setCapabilities(List.of(
                            new CapabilityDef(
                                    new CapabilityDeclaration(
                                            "search_flights", "Search for flights", "1.0",
                                            List.of(
                                                    new CapabilityInput("origin", "string", true, "Origin airport"),
                                                    new CapabilityInput("destination", "string", true, "Destination airport"),
                                                    // Required, and the declaration says what happens when it is absent.
                                                    new CapabilityInput("cabin", "string", true, null,
                                                            "Cabin; asked for when absent", null, false, null, null, null,
                                                            new dev.anip.core.InputResolution(
                                                                dev.anip.core.ResolutionMode.CLARIFY, null,
                                                                dev.anip.core.ResolutionBehavior.CLARIFY, null, null))
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
                                                    new CapabilityInput("flight_id", "string", true, "Flight ID"),
                                                    new CapabilityInput("options", "object", false, "Booking options")
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
        AnipGraphQLController graphQLController(ANIPService service) {
            return new AnipGraphQLController(service);
        }
    }

    @BeforeAll
    void setUp() throws Exception {
        TokenResponse resp = anipService.issueToken("user@test.com",
                new TokenRequest("agent@test.com", List.of("travel", "finance"),
                        "search_flights", null, null, 2, null));
        validJwt = resp.getToken();
    }

    // --- Query execution ---

    @Test
    void testQueryWithApiKey() throws Exception {
        String query = """
                {"query":"{ searchFlights(origin: \\"SFO\\", destination: \\"LAX\\") { success result } }"}""";

        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.searchFlights.success").value(true))
                .andExpect(jsonPath("$.data.searchFlights.result").exists());
    }

    @Test
    void testQueryWithJwt() throws Exception {
        String query = """
                {"query":"{ searchFlights(origin: \\"SFO\\", destination: \\"LAX\\") { success result } }"}""";

        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer " + validJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.searchFlights.success").value(true));
    }

    // --- Mutation execution ---

    @Test
    void testMutation() throws Exception {
        String query = """
                {"query":"mutation { bookFlight(flightId: \\"FL-001\\") { success result failure { type detail } } }"}""";

        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.bookFlight.success").value(true))
                .andExpect(jsonPath("$.data.bookFlight.result").exists());
    }

    // --- Parameter validation (SPEC.md §6.3) in the result body ---

    @Test
    void testInputThatDeclaresOnMissingIsNotANonNullArgument() throws Exception {
        // 'cabin' is required and declares resolution.on_missing: the schema
        // does not demand it, and the call reaches the handler without it.
        String query = """
                {"query":"{ searchFlights(origin: \\"SFO\\", destination: \\"LAX\\") { success result } }"}""";
        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errors").doesNotExist())
                .andExpect(jsonPath("$.data.searchFlights.success").value(true));

        mockMvc.perform(get("/schema.graphql"))
                .andExpect(content().string(containsString("cabin: String)")))
                .andExpect(content().string(containsString("origin: String!")));
    }

    @Test
    void testInvalidParametersInResultBody() throws Exception {
        // GraphQL's own schema refuses a missing non-null argument; a value of
        // the wrong JSON type for a JSON-typed argument reaches the service.
        String query = """
                {"query":"mutation { bookFlight(flightId: \\"FL-001\\", options: \\"window\\") { success result failure { type detail retry resolution { action recoveryClass requires } } } }"}""";

        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.bookFlight.success").value(false))
                .andExpect(jsonPath("$.data.bookFlight.result").doesNotExist())
                .andExpect(jsonPath("$.data.bookFlight.failure.type").value("invalid_parameters"))
                .andExpect(jsonPath("$.data.bookFlight.failure.detail").value(
                        "book_flight has invalid input(s): 'options' must be object, got string"))
                .andExpect(jsonPath("$.data.bookFlight.failure.retry").value(false))
                .andExpect(jsonPath("$.data.bookFlight.failure.resolution.action").value("retry_now"))
                .andExpect(jsonPath("$.data.bookFlight.failure.resolution.recoveryClass").value("retry_now"))
                .andExpect(jsonPath("$.data.bookFlight.failure.resolution.requires")
                        .value("parameters that match the capability's declared inputs"));
    }

    @Test
    void testMissingRequiredArgumentIsRefusedBeforeTheHandler() throws Exception {
        String query = """
                {"query":"mutation { bookFlight { success result } }"}""";

        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errors").isNotEmpty())
                .andExpect(jsonPath("$.data.bookFlight").doesNotExist());
    }

    // --- Auth errors in result body ---

    @Test
    void testAuthErrorInResultBody() throws Exception {
        String query = """
                {"query":"{ searchFlights(origin: \\"SFO\\", destination: \\"LAX\\") { success failure { type detail retry } } }"}""";

        mockMvc.perform(post("/graphql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.searchFlights.success").value(false))
                .andExpect(jsonPath("$.data.searchFlights.failure.type").value("authentication_required"));
    }

    @Test
    void testInvalidAuthInResultBody() throws Exception {
        String query = """
                {"query":"{ searchFlights(origin: \\"SFO\\", destination: \\"LAX\\") { success failure { type detail } } }"}""";

        mockMvc.perform(post("/graphql")
                        .header("Authorization", "Bearer bad-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(query))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.searchFlights.success").value(false))
                .andExpect(jsonPath("$.data.searchFlights.failure.type").exists());
    }

    // --- SDL endpoint ---

    @Test
    void testSchemaEndpoint() throws Exception {
        mockMvc.perform(get("/schema.graphql"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("text/plain"))
                .andExpect(content().string(containsString("type Query")))
                .andExpect(content().string(containsString("searchFlights")))
                .andExpect(content().string(containsString("@anipSideEffect")));
    }

    // --- Playground ---

    @Test
    void testPlayground() throws Exception {
        mockMvc.perform(get("/graphql"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_HTML))
                .andExpect(content().string(containsString("ANIP GraphQL")));
    }

    // --- Missing query ---

    @Test
    void testMissingQuery() throws Exception {
        mockMvc.perform(post("/graphql")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"query\":\"\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errors").exists());
    }
}
