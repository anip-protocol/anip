package dev.anip.stdiotest;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.DelegationToken;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;
import dev.anip.stdio.AnipStdioServer;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class AnipStdioServerTest {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    private ANIPService service;
    private AnipStdioServer server;

    @BeforeEach
    void setUp() throws Exception {
        CapabilityDeclaration echoDecl = new CapabilityDeclaration(
                "echo",
                "Echoes input back",
                "1.0",
                List.of(new CapabilityInput("message", "string", true, null, "Message to echo")),
                new CapabilityOutput("object", List.of("echo")),
                new SideEffect("read", "not_applicable"),
                List.of("general"),
                null, null,
                List.of("sync")
        );

        CapabilityDef echoCap = new CapabilityDef(echoDecl, (ctx, params) -> {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("echo", params.get("message"));
            return result;
        });

        ServiceConfig config = new ServiceConfig()
                .setServiceId("stdio-test-service")
                .setCapabilities(List.of(echoCap))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> {
                    if ("test-api-key".equals(bearer)) {
                        return Optional.of("user@test.com");
                    }
                    return Optional.empty();
                })
                .setRetentionIntervalSeconds(-1);

        service = new ANIPService(config);
        service.start();
        server = new AnipStdioServer(service);
    }

    @AfterEach
    void tearDown() {
        if (service != null) {
            service.shutdown();
        }
    }

    // --- Helper methods ---

    private Map<String, Object> request(String method, Map<String, Object> params) {
        Map<String, Object> msg = new LinkedHashMap<>();
        msg.put("jsonrpc", "2.0");
        msg.put("id", 1);
        msg.put("method", method);
        if (params != null) {
            msg.put("params", params);
        }
        return msg;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> call(String method, Map<String, Object> params) {
        Map<String, Object> req = request(method, params);
        Object result = server.handleRequest(req);
        return (Map<String, Object>) result;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> getResult(Map<String, Object> response) {
        return (Map<String, Object>) response.get("result");
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> getError(Map<String, Object> response) {
        return (Map<String, Object>) response.get("error");
    }

    private String issueTestToken() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@test.com", List.of("general"), "echo",
                null, null, 2, null
        );
        TokenResponse resp = service.issueToken("user@test.com", req);
        return resp.getToken();
    }

    private Map<String, Object> authParams(String jwt) {
        return authParams(jwt, Map.of());
    }

    private Map<String, Object> authParams(String jwt, Map<String, Object> extra) {
        Map<String, Object> params = new LinkedHashMap<>(extra);
        params.put("auth", Map.of("bearer", jwt));
        return params;
    }

    // --- Validation tests ---

    @Test
    void testInvalidJsonRpcVersion() {
        Map<String, Object> msg = new LinkedHashMap<>();
        msg.put("jsonrpc", "1.0");
        msg.put("id", 1);
        msg.put("method", "anip.discovery");

        @SuppressWarnings("unchecked")
        Map<String, Object> resp = (Map<String, Object>) server.handleRequest(msg);
        assertNotNull(resp.get("error"));
        Map<String, Object> error = getError(resp);
        assertEquals(-32600, error.get("code"));
    }

    @Test
    void testMissingMethod() {
        Map<String, Object> msg = new LinkedHashMap<>();
        msg.put("jsonrpc", "2.0");
        msg.put("id", 1);

        @SuppressWarnings("unchecked")
        Map<String, Object> resp = (Map<String, Object>) server.handleRequest(msg);
        assertNotNull(resp.get("error"));
    }

    @Test
    void testMissingId() {
        Map<String, Object> msg = new LinkedHashMap<>();
        msg.put("jsonrpc", "2.0");
        msg.put("method", "anip.discovery");

        @SuppressWarnings("unchecked")
        Map<String, Object> resp = (Map<String, Object>) server.handleRequest(msg);
        assertNotNull(resp.get("error"));
    }

    @Test
    void testUnknownMethod() {
        Map<String, Object> resp = call("anip.nonexistent", null);
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32601, error.get("code"));
    }

    // --- anip.discovery ---

    @Test
    void testDiscovery() {
        Map<String, Object> resp = call("anip.discovery", null);
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertNotNull(result.get("anip_discovery"));
    }

    // --- anip.manifest ---

    @Test
    void testManifest() {
        Map<String, Object> resp = call("anip.manifest", null);
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertNotNull(result.get("manifest"));
        assertNotNull(result.get("signature"));
    }

    // --- anip.jwks ---

    @Test
    void testJwks() {
        Map<String, Object> resp = call("anip.jwks", null);
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertNotNull(result.get("keys"));
    }

    // --- anip.tokens.issue ---

    @Test
    void testTokensIssue() {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("auth", Map.of("bearer", "test-api-key"));
        params.put("subject", "agent@test.com");
        params.put("scope", List.of("general"));
        params.put("capability", "echo");
        params.put("ttl_hours", 2);

        Map<String, Object> resp = call("anip.tokens.issue", params);
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertTrue((Boolean) result.get("issued"));
        assertNotNull(result.get("token"));
        assertNotNull(result.get("token_id"));
    }

    @Test
    void testTokensIssueMissingAuth() {
        Map<String, Object> resp = call("anip.tokens.issue", Map.of());
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32001, error.get("code"));
    }

    @Test
    void testTokensIssueInvalidAuth() {
        Map<String, Object> params = Map.of("auth", Map.of("bearer", "bad-key"));
        Map<String, Object> resp = call("anip.tokens.issue", params);
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32001, error.get("code"));
    }

    // --- anip.permissions ---

    @Test
    void testPermissions() throws Exception {
        String jwt = issueTestToken();
        Map<String, Object> resp = call("anip.permissions", authParams(jwt));
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertNotNull(result.get("available"));
    }

    @Test
    void testPermissionsMissingAuth() {
        Map<String, Object> resp = call("anip.permissions", Map.of());
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32001, error.get("code"));
    }

    // --- anip.invoke ---

    @Test
    void testInvoke() throws Exception {
        String jwt = issueTestToken();
        Map<String, Object> extra = new LinkedHashMap<>();
        extra.put("capability", "echo");
        extra.put("parameters", Map.of("message", "hello"));
        Map<String, Object> params = authParams(jwt, extra);

        Map<String, Object> resp = call("anip.invoke", params);
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertTrue((Boolean) result.get("success"));
        assertNotNull(result.get("invocation_id"));
        @SuppressWarnings("unchecked")
        Map<String, Object> innerResult = (Map<String, Object>) result.get("result");
        assertEquals("hello", innerResult.get("echo"));
    }

    @Test
    void testInvokeMissingCapability() throws Exception {
        String jwt = issueTestToken();
        Map<String, Object> resp = call("anip.invoke", authParams(jwt));
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32004, error.get("code"));
    }

    @Test
    void testInvokeMissingAuth() {
        Map<String, Object> params = Map.of("capability", "echo");
        Map<String, Object> resp = call("anip.invoke", params);
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32001, error.get("code"));
    }

    // --- anip.audit.query ---

    @Test
    void testAuditQuery() throws Exception {
        // Make an invocation first so there's something to audit.
        String jwt = issueTestToken();
        Map<String, Object> invokeExtra = new LinkedHashMap<>();
        invokeExtra.put("capability", "echo");
        invokeExtra.put("parameters", Map.of("message", "audit-me"));
        call("anip.invoke", authParams(jwt, invokeExtra));

        Map<String, Object> resp = call("anip.audit.query", authParams(jwt, Map.of("limit", 50)));
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertNotNull(result.get("entries"));
        assertTrue(((Number) result.get("count")).intValue() > 0);
    }

    @Test
    void testAuditQueryMissingAuth() {
        Map<String, Object> resp = call("anip.audit.query", Map.of());
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32001, error.get("code"));
    }

    // --- anip.checkpoints.list ---

    @Test
    void testCheckpointsList() {
        Map<String, Object> resp = call("anip.checkpoints.list", Map.of());
        assertNull(resp.get("error"));
        Map<String, Object> result = getResult(resp);
        assertNotNull(result);
        assertNotNull(result.get("checkpoints"));
    }

    // --- anip.checkpoints.get ---

    @Test
    void testCheckpointsGetMissingId() {
        Map<String, Object> resp = call("anip.checkpoints.get", Map.of());
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32004, error.get("code"));
    }

    @Test
    void testCheckpointsGetNotFound() {
        Map<String, Object> params = Map.of("id", "nonexistent-id");
        Map<String, Object> resp = call("anip.checkpoints.get", params);
        Map<String, Object> error = getError(resp);
        assertNotNull(error);
        assertEquals(-32004, error.get("code"));
    }

    // --- serve() integration test ---

    @Test
    void testServeIntegration() throws Exception {
        // Build a multi-line input with two requests.
        String discoveryReq = MAPPER.writeValueAsString(request("anip.discovery", null));
        String jwksReq = MAPPER.writeValueAsString(request("anip.jwks", null));
        String input = discoveryReq + "\n" + jwksReq + "\n";

        ByteArrayInputStream in = new ByteArrayInputStream(input.getBytes(StandardCharsets.UTF_8));
        ByteArrayOutputStream out = new ByteArrayOutputStream();

        server.serve(in, out);

        String output = out.toString(StandardCharsets.UTF_8);
        String[] lines = output.trim().split("\n");
        assertEquals(2, lines.length);

        // First response should be a discovery result.
        @SuppressWarnings("unchecked")
        Map<String, Object> resp1 = MAPPER.readValue(lines[0], Map.class);
        assertEquals("2.0", resp1.get("jsonrpc"));
        assertNotNull(resp1.get("result"));

        // Second response should be a JWKS result.
        @SuppressWarnings("unchecked")
        Map<String, Object> resp2 = MAPPER.readValue(lines[1], Map.class);
        assertEquals("2.0", resp2.get("jsonrpc"));
        assertNotNull(resp2.get("result"));
    }

    @Test
    void testServeParseError() throws Exception {
        String input = "not valid json\n";
        ByteArrayInputStream in = new ByteArrayInputStream(input.getBytes(StandardCharsets.UTF_8));
        ByteArrayOutputStream out = new ByteArrayOutputStream();

        server.serve(in, out);

        String output = out.toString(StandardCharsets.UTF_8);
        @SuppressWarnings("unchecked")
        Map<String, Object> resp = MAPPER.readValue(output.trim(), Map.class);
        assertNotNull(resp.get("error"));
        @SuppressWarnings("unchecked")
        Map<String, Object> error = (Map<String, Object>) resp.get("error");
        assertEquals(-32700, error.get("code"));
    }

    // --- extractAuth tests ---

    @Test
    void testExtractAuthNull() {
        assertNull(AnipStdioServer.extractAuth(null));
        assertNull(AnipStdioServer.extractAuth(Map.of()));
        assertNull(AnipStdioServer.extractAuth(Map.of("auth", "not-a-map")));
    }

    @Test
    void testExtractAuthPresent() {
        Map<String, Object> params = Map.of("auth", Map.of("bearer", "my-token"));
        assertEquals("my-token", AnipStdioServer.extractAuth(params));
    }
}
