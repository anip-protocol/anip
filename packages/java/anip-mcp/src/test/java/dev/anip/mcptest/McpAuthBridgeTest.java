package dev.anip.mcptest;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.DelegationToken;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.mcp.McpAuthBridge;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class McpAuthBridgeTest {

    private ANIPService service;
    private String validJwt;

    @BeforeEach
    void setUp() throws Exception {
        service = new ANIPService(new ServiceConfig()
                .setServiceId("test-auth-bridge-svc")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search_flights", "Search for flights", "1.0",
                                        List.of(
                                                new CapabilityInput("origin", "string", true, "Origin airport")
                                        ),
                                        new CapabilityOutput("object", List.of("flights")),
                                        new SideEffect("read", "not_applicable"),
                                        List.of("travel"), null, null,
                                        List.of("sync")
                                ),
                                (ctx, params) -> Map.of("flights", List.of())
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
        service.start();

        // Issue a valid JWT for tests.
        TokenResponse resp = service.issueToken("user@test.com",
                new TokenRequest("agent@test.com", List.of("travel"),
                        "search_flights", null, null, 2, null));
        validJwt = resp.getToken();
    }

    @AfterEach
    void tearDown() {
        if (service != null) {
            service.shutdown();
        }
    }

    @Test
    void testJwtSuccess() throws Exception {
        DelegationToken token = McpAuthBridge.resolveAuth(validJwt, service, "search_flights");
        assertNotNull(token);
        assertEquals("agent@test.com", token.getSubject());
    }

    @Test
    void testApiKeyFallback() throws Exception {
        DelegationToken token = McpAuthBridge.resolveAuth("valid-api-key", service, "search_flights");
        assertNotNull(token);
        assertEquals("adapter:anip-mcp", token.getSubject());
    }

    @Test
    void testInvalidBearerThrows() {
        assertThrows(ANIPError.class, () ->
                McpAuthBridge.resolveAuth("bad-key", service, "search_flights"));
    }
}
