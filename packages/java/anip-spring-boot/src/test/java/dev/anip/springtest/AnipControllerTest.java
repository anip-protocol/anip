package dev.anip.springtest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;
import dev.anip.spring.AnipController;
import dev.anip.spring.AnipLifecycle;

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
class AnipControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ANIPService anipService;

    private String validJwt;

    @SpringBootApplication
    static class TestApp {
        @Bean
        ANIPService anipService() {
            return new ANIPService(new ServiceConfig()
                    .setServiceId("test-spring-svc")
                    .setCapabilities(List.of(
                            new CapabilityDef(
                                    new CapabilityDeclaration(
                                            "search_flights", "Search for flights", "1.0",
                                            List.of(
                                                    new CapabilityInput("origin", "string", true, "Origin airport"),
                                                    new CapabilityInput("destination", "string", true, "Destination airport")
                                            ),
                                            new CapabilityOutput("object", List.of("flights")),
                                            new SideEffect("read", "not_applicable"),
                                            List.of("travel"), null, null,
                                            List.of("sync", "streaming")
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
        }

        @Bean
        AnipController anipController(ANIPService service) {
            return new AnipController(service);
        }

        @Bean
        AnipLifecycle anipLifecycle(ANIPService service) {
            return new AnipLifecycle(service);
        }
    }

    @BeforeAll
    void setUp() throws Exception {
        TokenResponse resp = anipService.issueToken("user@test.com",
                new TokenRequest("agent@test.com", List.of("travel", "finance"),
                        "search_flights", null, null, 2, null));
        validJwt = resp.getToken();
    }

    // --- Discovery ---

    @Test
    void testDiscovery() throws Exception {
        mockMvc.perform(get("/.well-known/anip"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.anip_discovery.protocol").value("anip/0.13"))
                .andExpect(jsonPath("$.anip_discovery.compliance").value("anip-compliant"))
                .andExpect(jsonPath("$.anip_discovery.base_url").exists())
                .andExpect(jsonPath("$.anip_discovery.capabilities").exists());
    }

    // --- JWKS ---

    @Test
    void testJwks() throws Exception {
        mockMvc.perform(get("/.well-known/jwks.json"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.keys").isArray())
                .andExpect(jsonPath("$.keys").isNotEmpty());
    }

    // --- Manifest ---

    @Test
    void testManifest() throws Exception {
        mockMvc.perform(get("/anip/manifest"))
                .andExpect(status().isOk())
                .andExpect(header().exists("X-ANIP-Signature"))
                .andExpect(jsonPath("$.protocol").value("anip/0.13"))
                .andExpect(jsonPath("$.capabilities").exists());
    }

    // --- Token issuance ---

    @Test
    void testTokenIssuanceValid() throws Exception {
        mockMvc.perform(post("/anip/tokens")
                        .header("Authorization", "Bearer valid-api-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"subject\":\"agent\",\"scope\":[\"travel\"],\"capability\":\"search_flights\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.issued").value(true))
                .andExpect(jsonPath("$.token_id").exists())
                .andExpect(jsonPath("$.token").exists());
    }

    @Test
    void testTokenIssuanceMissingAuth() throws Exception {
        mockMvc.perform(post("/anip/tokens")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"subject\":\"agent\",\"scope\":[\"travel\"]}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
    }

    @Test
    void testTokenIssuanceInvalidKey() throws Exception {
        mockMvc.perform(post("/anip/tokens")
                        .header("Authorization", "Bearer bad-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"subject\":\"agent\",\"scope\":[\"travel\"]}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("invalid_token"));
    }

    // --- Invoke ---

    @Test
    void testInvokeValid() throws Exception {
        mockMvc.perform(post("/anip/invoke/search_flights")
                        .header("Authorization", "Bearer " + validJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"parameters\":{\"origin\":\"SFO\",\"destination\":\"LAX\"}}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.result.flights").isArray())
                .andExpect(jsonPath("$.invocation_id").exists());
    }

    @Test
    void testInvokeMissingAuth() throws Exception {
        mockMvc.perform(post("/anip/invoke/search_flights")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"parameters\":{}}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("authentication_required"));
    }

    @Test
    void testInvokeInvalidJwt() throws Exception {
        mockMvc.perform(post("/anip/invoke/search_flights")
                        .header("Authorization", "Bearer not-a-valid-jwt")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"parameters\":{}}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void testInvokeUnknownCapability() throws Exception {
        mockMvc.perform(post("/anip/invoke/nonexistent")
                        .header("Authorization", "Bearer " + validJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"parameters\":{}}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.failure.type").value("unknown_capability"));
    }

    // --- Permissions ---

    @Test
    void testPermissions() throws Exception {
        mockMvc.perform(post("/anip/permissions")
                        .header("Authorization", "Bearer " + validJwt)
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.available").isArray());
    }

    @Test
    void testPermissionsMissingAuth() throws Exception {
        mockMvc.perform(post("/anip/permissions")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false));
    }

    // --- Audit ---

    @Test
    void testAudit() throws Exception {
        mockMvc.perform(post("/anip/invoke/search_flights")
                .header("Authorization", "Bearer " + validJwt)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"parameters\":{\"origin\":\"SFO\",\"destination\":\"LAX\"}}"));

        mockMvc.perform(post("/anip/audit")
                        .header("Authorization", "Bearer " + validJwt)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"limit\":10}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.count").isNumber());
    }

    // --- Checkpoints ---

    @Test
    void testCheckpointsList() throws Exception {
        mockMvc.perform(get("/anip/checkpoints"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.checkpoints").isArray());
    }

    // --- Health ---

    @Test
    void testHealth() throws Exception {
        mockMvc.perform(get("/-/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("healthy"))
                .andExpect(jsonPath("$.storage").exists())
                .andExpect(jsonPath("$.version").exists());
    }
}
