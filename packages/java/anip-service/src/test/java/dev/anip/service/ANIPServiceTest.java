package dev.anip.service;

import dev.anip.core.ANIPError;
import dev.anip.core.AuditFilters;
import dev.anip.core.Budget;
import dev.anip.core.AuditResponse;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Checkpoint;
import dev.anip.core.Constants;
import dev.anip.core.CostActual;
import dev.anip.core.DelegationToken;
import dev.anip.core.HealthReport;
import dev.anip.core.PermissionResponse;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

class ANIPServiceTest {

    private ANIPService service;

    private CapabilityDeclaration searchDecl() {
        return new CapabilityDeclaration(
                "search_flights",
                "Search for flights",
                "1.0",
                List.of(
                        new CapabilityInput("origin", "string", true, null, "Origin airport"),
                        new CapabilityInput("destination", "string", true, null, "Destination airport")
                ),
                new CapabilityOutput("object", List.of("flights")),
                new SideEffect("read", "not_applicable"),
                List.of("travel"),
                null, null,
                List.of("sync", "streaming")
        );
    }

    private CapabilityDeclaration bookDecl() {
        return new CapabilityDeclaration(
                "book_flight",
                "Book a flight",
                "1.0",
                List.of(
                        new CapabilityInput("flight_id", "string", true, null, "Flight ID")
                ),
                new CapabilityOutput("object", List.of("booking_id", "status")),
                new SideEffect("irreversible", "none"),
                List.of("travel", "finance"),
                null, null,
                List.of("sync")
        );
    }

    private CapabilityDef searchCap() {
        return new CapabilityDef(searchDecl(), (ctx, params) ->
                Map.of("flights", List.of(Map.of("id", "FL-001", "price", 199.99)))
        );
    }

    private CapabilityDef bookCap() {
        return new CapabilityDef(bookDecl(), (ctx, params) ->
                Map.of("booking_id", "BK-001", "status", "confirmed")
        );
    }

    private ServiceConfig defaultConfig() {
        return new ServiceConfig()
                .setServiceId("test-service")
                .setCapabilities(List.of(searchCap(), bookCap()))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> {
                    if ("valid-key".equals(bearer)) {
                        return Optional.of("user@test.com");
                    }
                    return Optional.empty();
                })
                .setRetentionIntervalSeconds(-1); // disable retention for tests
    }

    @BeforeEach
    void setUp() throws Exception {
        service = new ANIPService(defaultConfig());
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) {
            service.shutdown();
        }
    }

    // --- Lifecycle tests ---

    @Test
    void testLifecycle() throws Exception {
        ANIPService svc = new ANIPService(defaultConfig());
        svc.start();
        assertNotNull(svc.getServiceId());
        assertEquals("test-service", svc.getServiceId());
        svc.shutdown();
        // Shutdown is safe to call multiple times.
        svc.shutdown();
    }

    // --- AuthenticateBearer tests ---

    @Test
    void testAuthenticateBearerValid() {
        Optional<String> result = service.authenticateBearer("valid-key");
        assertTrue(result.isPresent());
        assertEquals("user@test.com", result.get());
    }

    @Test
    void testAuthenticateBearerInvalid() {
        Optional<String> result = service.authenticateBearer("bad-key");
        assertFalse(result.isPresent());
    }

    @Test
    void testAuthenticateBearerNoAuthenticator() throws Exception {
        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("no-auth-svc")
                .setCapabilities(List.of())
                .setStorage(":memory:")
                .setRetentionIntervalSeconds(-1));
        svc.start();
        try {
            Optional<String> result = svc.authenticateBearer("anything");
            assertFalse(result.isPresent());
        } finally {
            svc.shutdown();
        }
    }

    // --- Token issuance and resolution ---

    @Test
    void testTokenIssuanceAndResolution() throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@test.com", List.of("travel"), "search_flights",
                null, null, 2, null
        );

        TokenResponse resp = service.issueToken("user@test.com", req);
        assertTrue(resp.isIssued());
        assertNotNull(resp.getTokenId());
        assertNotNull(resp.getToken());
        assertNotNull(resp.getExpires());

        // Resolve the token.
        DelegationToken token = service.resolveBearerToken(resp.getToken());
        assertNotNull(token);
        assertEquals(resp.getTokenId(), token.getTokenId());
        assertEquals("agent@test.com", token.getSubject());
    }

    @Test
    void testResolveBearerTokenInvalid() {
        assertThrows(ANIPError.class, () -> service.resolveBearerToken("not-a-jwt"));
    }

    // --- Invoke tests ---

    @Test
    void testInvokeSuccess() throws Exception {
        DelegationToken token = issueTestToken(List.of("travel"));

        Map<String, Object> result = service.invoke(
                "search_flights", token,
                Map.of("origin", "SFO", "destination", "LAX"),
                new InvokeOpts()
        );

        assertTrue((Boolean) result.get("success"));
        assertNotNull(result.get("invocation_id"));
        @SuppressWarnings("unchecked")
        Map<String, Object> resultData = (Map<String, Object>) result.get("result");
        assertNotNull(resultData);
        assertNotNull(resultData.get("flights"));
    }

    @Test
    void testInvokeUnknownCapability() throws Exception {
        DelegationToken token = issueTestToken(List.of("travel"));

        Map<String, Object> result = service.invoke(
                "nonexistent", token, Map.of(), new InvokeOpts()
        );

        assertFalse((Boolean) result.get("success"));
        @SuppressWarnings("unchecked")
        Map<String, Object> failure = (Map<String, Object>) result.get("failure");
        assertEquals(Constants.FAILURE_UNKNOWN_CAPABILITY, failure.get("type"));
    }

    @Test
    void testInvokeScopeMismatch() throws Exception {
        // Issue token with 'finance' scope only (search_flights needs 'travel').
        DelegationToken token = issueTestToken(List.of("finance"));

        Map<String, Object> result = service.invoke(
                "search_flights", token, Map.of(), new InvokeOpts()
        );

        assertFalse((Boolean) result.get("success"));
        @SuppressWarnings("unchecked")
        Map<String, Object> failure = (Map<String, Object>) result.get("failure");
        assertEquals(Constants.FAILURE_SCOPE_INSUFFICIENT, failure.get("type"));
    }

    @Test
    void testInvokeHandlerError() throws Exception {
        CapabilityDef failCap = new CapabilityDef(
                new CapabilityDeclaration(
                        "failing_cap", "Always fails", "1.0",
                        List.of(), new CapabilityOutput("object", List.of()), new SideEffect("read", "not_applicable"),
                        List.of("travel"), null, null, List.of("sync")
                ),
                (ctx, params) -> {
                    throw new ANIPError(Constants.FAILURE_UNAVAILABLE, "service down");
                }
        );

        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("fail-svc")
                .setCapabilities(List.of(failCap))
                .setStorage(":memory:")
                .setAuthenticate(b -> "valid-key".equals(b) ? Optional.of("user@test.com") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        svc.start();
        try {
            DelegationToken token = issueToken(svc, List.of("travel"));
            Map<String, Object> result = svc.invoke("failing_cap", token, Map.of(), new InvokeOpts());
            assertFalse((Boolean) result.get("success"));
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) result.get("failure");
            assertEquals(Constants.FAILURE_UNAVAILABLE, failure.get("type"));
        } finally {
            svc.shutdown();
        }
    }

    // --- Streaming tests ---

    @Test
    void testInvokeStreamProgressAndCompleted() throws Exception {
        CapabilityDef streamCap = new CapabilityDef(
                new CapabilityDeclaration(
                        "stream_cap", "Streaming capability", "1.0",
                        List.of(), new CapabilityOutput("object", List.of()),
                        new SideEffect("read", "not_applicable"),
                        List.of("travel"), null, null, List.of("sync", "streaming")
                ),
                (ctx, params) -> {
                    ctx.getEmitProgress().apply(Map.of("step", 1));
                    ctx.getEmitProgress().apply(Map.of("step", 2));
                    return Map.of("done", true);
                }
        );

        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("stream-svc")
                .setCapabilities(List.of(streamCap))
                .setStorage(":memory:")
                .setAuthenticate(b -> "valid-key".equals(b) ? Optional.of("user@test.com") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        svc.start();
        try {
            DelegationToken token = issueToken(svc, List.of("travel"));
            StreamResult sr = svc.invokeStream("stream_cap", token, Map.of(), new InvokeOpts());

            BlockingQueue<StreamEvent> events = sr.getEvents();
            List<StreamEvent> collected = new ArrayList<>();

            while (true) {
                StreamEvent event = events.poll(5, TimeUnit.SECONDS);
                assertNotNull(event, "Timed out waiting for stream event");
                if (StreamResult.DONE_TYPE.equals(event.getType())) break;
                collected.add(event);
            }

            // Should have 2 progress events and 1 completed event.
            assertEquals(3, collected.size());
            assertEquals("progress", collected.get(0).getType());
            assertEquals("progress", collected.get(1).getType());
            assertEquals("completed", collected.get(2).getType());
            assertTrue((Boolean) collected.get(2).getPayload().get("success"));
        } finally {
            svc.shutdown();
        }
    }

    @Test
    void testInvokeStreamHandlerError() throws Exception {
        CapabilityDef failStreamCap = new CapabilityDef(
                new CapabilityDeclaration(
                        "fail_stream", "Fails during stream", "1.0",
                        List.of(), new CapabilityOutput("object", List.of()),
                        new SideEffect("read", "not_applicable"),
                        List.of("travel"), null, null, List.of("sync", "streaming")
                ),
                (ctx, params) -> {
                    ctx.getEmitProgress().apply(Map.of("step", 1));
                    throw new ANIPError(Constants.FAILURE_INTERNAL_ERROR, "stream broke");
                }
        );

        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("fail-stream-svc")
                .setCapabilities(List.of(failStreamCap))
                .setStorage(":memory:")
                .setAuthenticate(b -> "valid-key".equals(b) ? Optional.of("user@test.com") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        svc.start();
        try {
            DelegationToken token = issueToken(svc, List.of("travel"));
            StreamResult sr = svc.invokeStream("fail_stream", token, Map.of(), new InvokeOpts());

            BlockingQueue<StreamEvent> events = sr.getEvents();
            List<StreamEvent> collected = new ArrayList<>();

            while (true) {
                StreamEvent event = events.poll(5, TimeUnit.SECONDS);
                assertNotNull(event, "Timed out waiting for stream event");
                if (StreamResult.DONE_TYPE.equals(event.getType())) break;
                collected.add(event);
            }

            // Should have 1 progress and 1 failed.
            assertEquals(2, collected.size());
            assertEquals("progress", collected.get(0).getType());
            assertEquals("failed", collected.get(1).getType());
            assertFalse((Boolean) collected.get(1).getPayload().get("success"));
        } finally {
            svc.shutdown();
        }
    }

    @Test
    void testInvokeStreamUnknownCapability() throws Exception {
        DelegationToken token = issueTestToken(List.of("travel"));
        assertThrows(ANIPError.class, () ->
                service.invokeStream("nonexistent", token, Map.of(), new InvokeOpts()));
    }

    // --- Permissions tests ---

    @Test
    void testPermissionsAvailable() throws Exception {
        // Token with both 'travel' and 'finance' scopes.
        DelegationToken token = issueTestToken(List.of("travel", "finance"));
        PermissionResponse resp = service.discoverPermissions(token);

        assertNotNull(resp.getAvailable());
        assertFalse(resp.getAvailable().isEmpty());

        // Both capabilities should be available.
        List<String> availableNames = resp.getAvailable().stream()
                .map(PermissionResponse.AvailableCapability::getCapability).toList();
        assertTrue(availableNames.contains("search_flights"));
        assertTrue(availableNames.contains("book_flight"));
    }

    @Test
    void testPermissionsRestricted() throws Exception {
        // Token with only 'travel' scope -- book_flight needs 'travel' + 'finance'.
        DelegationToken token = issueTestToken(List.of("travel"));
        PermissionResponse resp = service.discoverPermissions(token);

        List<String> availableNames = resp.getAvailable().stream()
                .map(PermissionResponse.AvailableCapability::getCapability).toList();
        assertTrue(availableNames.contains("search_flights"));

        List<String> restrictedNames = resp.getRestricted().stream()
                .map(PermissionResponse.RestrictedCapability::getCapability).toList();
        assertTrue(restrictedNames.contains("book_flight"));
    }

    // --- Discovery tests ---

    @Test
    void testDiscoveryDocument() {
        Map<String, Object> discovery = service.getDiscovery("http://localhost:8080");

        assertNotNull(discovery.get("anip_discovery"));
        @SuppressWarnings("unchecked")
        Map<String, Object> doc = (Map<String, Object>) discovery.get("anip_discovery");
        assertEquals(Constants.PROTOCOL_VERSION, doc.get("protocol"));
        assertEquals("anip-compliant", doc.get("compliance"));
        assertEquals("http://localhost:8080", doc.get("base_url"));
        assertNotNull(doc.get("profile"));
        assertNotNull(doc.get("auth"));
        assertNotNull(doc.get("capabilities"));
        assertNotNull(doc.get("trust_level"));
        assertNotNull(doc.get("posture"));
        assertNotNull(doc.get("endpoints"));
    }

    @Test
    void testDiscoveryDocumentNoBaseUrl() {
        Map<String, Object> discovery = service.getDiscovery(null);
        @SuppressWarnings("unchecked")
        Map<String, Object> doc = (Map<String, Object>) discovery.get("anip_discovery");
        assertFalse(doc.containsKey("base_url"));
    }

    // --- Manifest tests ---

    @Test
    void testManifest() {
        Object manifest = service.getManifest();
        assertNotNull(manifest);
        @SuppressWarnings("unchecked")
        Map<String, Object> m = (Map<String, Object>) manifest;
        assertEquals(Constants.PROTOCOL_VERSION, m.get("protocol"));
        assertNotNull(m.get("capabilities"));
        assertNotNull(m.get("trust"));
        assertNotNull(m.get("service_identity"));
    }

    @Test
    void testSignedManifest() {
        SignedManifest sm = service.getSignedManifest();
        assertNotNull(sm.getManifestJson());
        assertTrue(sm.getManifestJson().length > 0);
        assertNotNull(sm.getSignature());
        assertFalse(sm.getSignature().isEmpty());
    }

    // --- JWKS tests ---

    @Test
    void testJwks() {
        Map<String, Object> jwks = service.getJwks();
        assertNotNull(jwks);
        assertNotNull(jwks.get("keys"));
        @SuppressWarnings("unchecked")
        List<Object> keys = (List<Object>) jwks.get("keys");
        assertFalse(keys.isEmpty());
    }

    // --- Capability declaration tests ---

    @Test
    void testGetCapabilityDeclaration() {
        CapabilityDeclaration decl = service.getCapabilityDeclaration("search_flights");
        assertNotNull(decl);
        assertEquals("search_flights", decl.getName());

        assertNull(service.getCapabilityDeclaration("nonexistent"));
    }

    // --- Health tests ---

    @Test
    void testHealth() {
        HealthReport health = service.getHealth();
        assertEquals("healthy", health.getStatus());
        assertTrue(health.getStorage().isConnected());
        assertEquals("sqlite", health.getStorage().getType());
        assertNotNull(health.getUptime());
        assertEquals(Constants.PROTOCOL_VERSION, health.getVersion());
    }

    // --- Hooks tests ---

    @Test
    void testHooksFiredOnInvokeSuccess() throws Exception {
        AtomicBoolean invokeStartFired = new AtomicBoolean(false);
        AtomicBoolean invokeCompleteFired = new AtomicBoolean(false);
        AtomicBoolean invokeCompletedSuccess = new AtomicBoolean(false);
        AtomicBoolean durationFired = new AtomicBoolean(false);
        AtomicBoolean scopeValidationFired = new AtomicBoolean(false);
        AtomicBoolean scopeGranted = new AtomicBoolean(false);

        ObservabilityHooks hooks = new ObservabilityHooks()
                .setOnInvokeStart((id, cap, sub) -> invokeStartFired.set(true))
                .setOnInvokeComplete((id, cap, success, dur) -> {
                    invokeCompleteFired.set(true);
                    invokeCompletedSuccess.set(success);
                })
                .setOnInvokeDuration((cap, dur, success) -> durationFired.set(true))
                .setOnScopeValidation((cap, granted) -> {
                    scopeValidationFired.set(true);
                    scopeGranted.set(granted);
                });

        ANIPService svc = new ANIPService(defaultConfig().setHooks(hooks));
        svc.start();
        try {
            DelegationToken token = issueToken(svc, List.of("travel"));
            svc.invoke("search_flights", token, Map.of(), new InvokeOpts());

            assertTrue(invokeStartFired.get());
            assertTrue(invokeCompleteFired.get());
            assertTrue(invokeCompletedSuccess.get());
            assertTrue(durationFired.get());
            assertTrue(scopeValidationFired.get());
            assertTrue(scopeGranted.get());
        } finally {
            svc.shutdown();
        }
    }

    @Test
    void testHooksFiredOnInvokeFailure() throws Exception {
        AtomicBoolean invokeCompleteFired = new AtomicBoolean(false);
        AtomicBoolean invokeCompletedSuccess = new AtomicBoolean(true); // starts true
        AtomicBoolean durationFired = new AtomicBoolean(false);

        ObservabilityHooks hooks = new ObservabilityHooks()
                .setOnInvokeComplete((id, cap, success, dur) -> {
                    invokeCompleteFired.set(true);
                    invokeCompletedSuccess.set(success);
                })
                .setOnInvokeDuration((cap, dur, success) -> durationFired.set(true));

        CapabilityDef failCap = new CapabilityDef(
                new CapabilityDeclaration(
                        "fail_cap", "Always fails", "1.0",
                        List.of(), new CapabilityOutput("object", List.of()),
                        new SideEffect("read", "not_applicable"),
                        List.of("travel"), null, null, List.of("sync")
                ),
                (ctx, params) -> {
                    throw new RuntimeException("handler blew up");
                }
        );

        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("fail-hook-svc")
                .setCapabilities(List.of(failCap))
                .setStorage(":memory:")
                .setAuthenticate(b -> "valid-key".equals(b) ? Optional.of("user@test.com") : Optional.empty())
                .setHooks(hooks)
                .setRetentionIntervalSeconds(-1));
        svc.start();
        try {
            DelegationToken token = issueToken(svc, List.of("travel"));
            Map<String, Object> result = svc.invoke("fail_cap", token, Map.of(), new InvokeOpts());

            assertFalse((Boolean) result.get("success"));
            assertTrue(invokeCompleteFired.get());
            assertFalse(invokeCompletedSuccess.get()); // success should be false
            assertTrue(durationFired.get());
        } finally {
            svc.shutdown();
        }
    }

    @Test
    void testHooksTokenIssueAndResolve() throws Exception {
        AtomicBoolean tokenIssuedFired = new AtomicBoolean(false);
        AtomicBoolean tokenResolvedFired = new AtomicBoolean(false);

        ObservabilityHooks hooks = new ObservabilityHooks()
                .setOnTokenIssued((id, sub, cap) -> tokenIssuedFired.set(true))
                .setOnTokenResolved((id, sub) -> tokenResolvedFired.set(true));

        ANIPService svc = new ANIPService(defaultConfig().setHooks(hooks));
        svc.start();
        try {
            TokenRequest req = new TokenRequest("user@test.com", List.of("travel"),
                    "search_flights", null, null, 2, null);
            TokenResponse resp = svc.issueToken("user@test.com", req);

            assertTrue(tokenIssuedFired.get());

            svc.resolveBearerToken(resp.getToken());
            assertTrue(tokenResolvedFired.get());
        } finally {
            svc.shutdown();
        }
    }

    @Test
    void testHooksAuthFailure() throws Exception {
        AtomicBoolean authFailureFired = new AtomicBoolean(false);

        ObservabilityHooks hooks = new ObservabilityHooks()
                .setOnAuthFailure((type, detail) -> authFailureFired.set(true));

        ANIPService svc = new ANIPService(defaultConfig().setHooks(hooks));
        svc.start();
        try {
            assertThrows(Exception.class, () -> svc.resolveBearerToken("bad-jwt"));
            assertTrue(authFailureFired.get());
        } finally {
            svc.shutdown();
        }
    }

    @Test
    void testHookExceptionDoesNotCrashService() throws Exception {
        ObservabilityHooks hooks = new ObservabilityHooks()
                .setOnInvokeStart((id, cap, sub) -> {
                    throw new RuntimeException("hook explosion");
                })
                .setOnInvokeComplete((id, cap, success, dur) -> {
                    throw new RuntimeException("hook explosion 2");
                });

        ANIPService svc = new ANIPService(defaultConfig().setHooks(hooks));
        svc.start();
        try {
            DelegationToken token = issueToken(svc, List.of("travel"));
            // Should not throw even though hooks throw.
            Map<String, Object> result = svc.invoke("search_flights", token, Map.of(), new InvokeOpts());
            assertTrue((Boolean) result.get("success"));
        } finally {
            svc.shutdown();
        }
    }

    // --- Background workers tests ---

    @Test
    void testBackgroundWorkersConfigurable() throws Exception {
        // Test that configuring checkpoint policy and retention works without errors.
        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("bg-test-svc")
                .setCapabilities(List.of(searchCap()))
                .setStorage(":memory:")
                .setAuthenticate(b -> "valid-key".equals(b) ? Optional.of("user@test.com") : Optional.empty())
                .setCheckpointPolicy(new CheckpointPolicy(120, 5))
                .setRetentionIntervalSeconds(30));
        svc.start();
        // Verify health is still healthy with workers enabled.
        assertEquals("healthy", svc.getHealth().getStatus());
        svc.shutdown();
    }

    @Test
    void testRetentionDisabledByNegativeOne() throws Exception {
        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("no-retention-svc")
                .setCapabilities(List.of(searchCap()))
                .setStorage(":memory:")
                .setRetentionIntervalSeconds(-1));
        svc.start();
        // Discovery should show retention_enforced = false.
        @SuppressWarnings("unchecked")
        Map<String, Object> disc = (Map<String, Object>)
                ((Map<String, Object>) svc.getDiscovery(null).get("anip_discovery"))
                        .get("posture");
        @SuppressWarnings("unchecked")
        Map<String, Object> audit = (Map<String, Object>) disc.get("audit");
        assertEquals(false, audit.get("retention_enforced"));
        svc.shutdown();
    }

    // --- Audit tests ---

    @Test
    void testAuditQueryAfterInvoke() throws Exception {
        DelegationToken token = issueTestToken(List.of("travel"));
        service.invoke("search_flights", token, Map.of(), new InvokeOpts());

        AuditResponse auditResp = service.queryAudit(token,
                new AuditFilters(null, null, null, null, 50));
        assertNotNull(auditResp);
        assertTrue(auditResp.getCount() > 0);
    }

    // --- Checkpoint tests ---

    @Test
    void testCheckpointListEmpty() throws Exception {
        var resp = service.listCheckpoints(10);
        assertNotNull(resp.getCheckpoints());
    }

    @Test
    void testCreateAndListCheckpoint() throws Exception {
        // Create some audit entries first.
        DelegationToken token = issueTestToken(List.of("travel"));
        service.invoke("search_flights", token, Map.of(), new InvokeOpts());

        Checkpoint cp = service.createCheckpoint();
        assertNotNull(cp);
        assertNotNull(cp.getCheckpointId());

        var listResp = service.listCheckpoints(10);
        assertFalse(listResp.getCheckpoints().isEmpty());
    }

    // --- Helper methods ---

    private DelegationToken issueTestToken(List<String> scopes) throws Exception {
        return issueToken(service, scopes);
    }

    private DelegationToken issueToken(ANIPService svc, List<String> scopes) throws Exception {
        TokenRequest req = new TokenRequest(
                "agent@test.com", scopes, "search_flights",
                null, null, 2, null
        );
        TokenResponse resp = svc.issueToken("user@test.com", req);
        return svc.resolveBearerToken(resp.getToken());
    }

    // --- issueCapabilityToken ---

    @Test
    void testIssueCapabilityToken() throws Exception {
        TokenResponse resp = service.issueCapabilityToken(
                "user@test.com", "search_flights", List.of("travel"));
        assertTrue(resp.isIssued());
        assertNotNull(resp.getTokenId());
        assertNotNull(resp.getToken());

        // Resolve and verify capability binding.
        DelegationToken token = service.resolveBearerToken(resp.getToken());
        assertEquals("user@test.com", token.getSubject());
        assertEquals("search_flights", token.getPurpose().getCapability());
    }

    @Test
    void testIssueCapabilityTokenFull() throws Exception {
        TokenResponse resp = service.issueCapabilityToken(
                "user@test.com", "search_flights", List.of("travel"),
                Map.of("task_id", "task-123"), 4,
                new Budget("USD", 100.0));
        assertTrue(resp.isIssued());
        assertNotNull(resp.getTokenId());
    }

    @Test
    void testIssueCapabilityTokenScopeIsExplicit() throws Exception {
        // Scope that differs from capability name — should still work.
        TokenResponse resp = service.issueCapabilityToken(
                "user@test.com", "search_flights", List.of("custom.scope"));
        assertTrue(resp.isIssued());
    }
}
