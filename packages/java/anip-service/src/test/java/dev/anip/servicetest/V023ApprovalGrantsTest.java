package dev.anip.servicetest;

import dev.anip.core.ANIPError;
import dev.anip.core.ApprovalGrant;
import dev.anip.core.ApprovalRequest;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.core.GrantPolicy;
import dev.anip.core.SideEffect;
import dev.anip.core.TokenResponse;
import dev.anip.crypto.KeyManager;
import dev.anip.server.GrantReservationResult;
import dev.anip.server.SqliteStorage;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;
import dev.anip.service.V023;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V023ApprovalGrantsTest {

    private ANIPService service;
    private Path keyDir;

    private CapabilityDeclaration sensitiveDecl() {
        return new CapabilityDeclaration(
                "transfer_funds", "Transfer funds", "1.0",
                List.of(new CapabilityInput("amount", "number", true, null, "amount")),
                new CapabilityOutput("object", List.of("status")),
                new SideEffect("irreversible", "none"),
                List.of("finance.transfer"),
                null, null, List.of("sync", "streaming"))
                .setGrantPolicy(new GrantPolicy(
                        List.of("one_time", "session_bound"), "one_time", 600, 3));
    }

    @BeforeEach
    void setUp() throws Exception {
        keyDir = Files.createTempDirectory("anip-grants-test-");
        ServiceConfig cfg = new ServiceConfig()
                .setServiceId("test-service")
                .setStorage(":memory:")
                .setKeyPath(keyDir.toString())
                .setCapabilities(List.of(new CapabilityDef(sensitiveDecl(), (ctx, params) -> {
                    // Amounts above 1000 need approval unless a grant was reserved.
                    Object amount = params.get("amount");
                    if (amount instanceof Number n && n.doubleValue() > 1000
                            && ctx.getApprovalGrant() == null) {
                        throw new ANIPError(Constants.FAILURE_APPROVAL_REQUIRED, "approval needed");
                    }
                    return Map.of("status", "ok", "approval_grant", ctx.getApprovalGrant());
                })))
                .setAuthenticate(b -> "valid".equals(b) ? Optional.of("alice") : Optional.empty())
                .setRetentionIntervalSeconds(-1);
        service = new ANIPService(cfg);
        service.start();
    }

    @AfterEach
    void tearDown() throws Exception {
        if (service != null) service.shutdown();
        if (keyDir != null) {
            try (var s = Files.walk(keyDir)) {
                s.sorted((a, b) -> b.compareTo(a)).forEach(p -> { try { Files.delete(p); } catch (Exception ignored) {} });
            }
        }
    }

    private SqliteStorage storage() {
        return (SqliteStorage) service.getStorage();
    }

    private KeyManager keys() throws Exception {
        var f = ANIPService.class.getDeclaredField("keys");
        f.setAccessible(true);
        return (KeyManager) f.get(service);
    }

    private ApprovalRequest persistRequest(String id, GrantPolicy gp) throws Exception {
        ApprovalRequest req = new ApprovalRequest(
                id, "transfer_funds", List.of("finance.transfer"),
                Map.of("subject", "alice", "root_principal", "alice"), null,
                Map.of(), V023.sha256Digest(Map.of()),
                Map.of("amount", 100), V023.sha256Digest(Map.of("amount", 100)),
                gp, ApprovalRequest.STATUS_PENDING, null, null,
                V023.utcNowIso(), V023.utcInIso(900));
        storage().storeApprovalRequest(req);
        return req;
    }

    @Test
    void issueApprovalGrantHappyPath() throws Exception {
        persistRequest("apr_h1", new GrantPolicy(
                List.of("one_time", "session_bound"), "one_time", 600, 3));
        Map<String, Object> approver = Map.of("subject", "approver", "root_principal", "approver");
        ApprovalGrant g = service.issueApprovalGrant("apr_h1", "one_time", approver, null, null, null);
        assertNotNull(g);
        assertEquals("apr_h1", g.getApprovalRequestId());
        assertEquals(1, g.getMaxUses(), "one_time clamps max_uses to 1");
        assertNotNull(g.getSignature());
        // Signature must verify with the same key manager used to sign.
        assertTrue(V023.verifyGrantSignature(keys(), g));
    }

    @Test
    void clampingExpiresInSeconds() throws Exception {
        persistRequest("apr_clamp", new GrantPolicy(
                List.of("one_time"), "one_time", 60, 1));
        Map<String, Object> approver = Map.of("subject", "ap");
        ANIPError err = assertThrows(ANIPError.class, () ->
                service.issueApprovalGrant("apr_clamp", "one_time", approver, null, 600, null));
        assertEquals(Constants.FAILURE_GRANT_TYPE_NOT_ALLOWED, err.getErrorType());
    }

    @Test
    void sessionBoundRequiresSessionId() throws Exception {
        persistRequest("apr_sess", new GrantPolicy(
                List.of("session_bound"), "session_bound", 600, 3));
        Map<String, Object> approver = Map.of("subject", "ap");
        ANIPError err = assertThrows(ANIPError.class, () ->
                service.issueApprovalGrant("apr_sess", "session_bound", approver, null, null, null));
        assertEquals(Constants.FAILURE_GRANT_TYPE_NOT_ALLOWED, err.getErrorType());
    }

    @Test
    void oneTimeRejectsSessionId() throws Exception {
        persistRequest("apr_one", new GrantPolicy(
                List.of("one_time"), "one_time", 600, 1));
        ANIPError err = assertThrows(ANIPError.class, () ->
                service.issueApprovalGrant("apr_one", "one_time",
                        Map.of("subject", "ap"), "session-1", null, null));
        assertEquals(Constants.FAILURE_GRANT_TYPE_NOT_ALLOWED, err.getErrorType());
    }

    @Test
    void validateContinuationGrantHappyPath() throws Exception {
        ApprovalRequest req = persistRequest("apr_cont", new GrantPolicy(
                List.of("one_time"), "one_time", 600, 1));
        ApprovalGrant g = service.issueApprovalGrant("apr_cont", "one_time",
                Map.of("subject", "ap"), null, null, null);
        V023.ContinuationValidation cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "transfer_funds", Map.of("amount", 100),
                List.of("finance.transfer"), null, "alice", V023.utcNowIso());
        assertNull(cv.failureType());
        assertNotNull(cv.grant());
    }

    @Test
    void validateContinuationGrantParamDrift() throws Exception {
        persistRequest("apr_drift", new GrantPolicy(
                List.of("one_time"), "one_time", 600, 1));
        ApprovalGrant g = service.issueApprovalGrant("apr_drift", "one_time",
                Map.of("subject", "ap"), null, null, null);
        V023.ContinuationValidation cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "transfer_funds", Map.of("amount", 999),  // different param
                List.of("finance.transfer"), null, "alice", V023.utcNowIso());
        assertEquals(Constants.FAILURE_GRANT_PARAM_DRIFT, cv.failureType());
    }

    @Test
    void validateContinuationGrantSessionInvalid() throws Exception {
        persistRequest("apr_sb", new GrantPolicy(
                List.of("session_bound"), "session_bound", 600, 1));
        ApprovalGrant g = service.issueApprovalGrant("apr_sb", "session_bound",
                Map.of("subject", "ap"), "sess-A", null, null);
        // Token has no session_id; grant is session_bound.
        V023.ContinuationValidation cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "transfer_funds", Map.of("amount", 100),
                List.of("finance.transfer"), null, "alice", V023.utcNowIso());
        assertEquals(Constants.FAILURE_GRANT_SESSION_INVALID, cv.failureType());
        // Token with WRONG session_id — same failure.
        cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "transfer_funds", Map.of("amount", 100),
                List.of("finance.transfer"), "sess-B", "alice", V023.utcNowIso());
        assertEquals(Constants.FAILURE_GRANT_SESSION_INVALID, cv.failureType());
    }

    @Test
    void validateContinuationGrantScopeMismatch() throws Exception {
        persistRequest("apr_sc", new GrantPolicy(
                List.of("one_time"), "one_time", 600, 1));
        ApprovalGrant g = service.issueApprovalGrant("apr_sc", "one_time",
                Map.of("subject", "ap"), null, null, null);
        // Token scope is missing finance.transfer.
        V023.ContinuationValidation cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "transfer_funds", Map.of("amount", 100),
                List.of("other.scope"), null, "alice", V023.utcNowIso());
        assertEquals(Constants.FAILURE_GRANT_SCOPE_MISMATCH, cv.failureType());
    }

    @Test
    void validateContinuationGrantRequesterMismatchAfterCapabilityBeforeScope() throws Exception {
        persistRequest("apr_rq", new GrantPolicy(
                List.of("one_time"), "one_time", 600, 1));
        ApprovalGrant g = service.issueApprovalGrant("apr_rq", "one_time",
                Map.of("subject", "ap"), null, null, null);
        // SPEC.md §4.8 step 5: after the capability check, before the scope check.
        V023.ContinuationValidation cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "other_capability", Map.of("amount", 100),
                List.of("finance.transfer"), null, "bob", V023.utcNowIso());
        assertEquals(Constants.FAILURE_GRANT_CAPABILITY_MISMATCH, cv.failureType());
        cv = V023.validateContinuationGrant(
                storage(), keys(), g.getGrantId(),
                "transfer_funds", Map.of("amount", 100),
                List.of("other.scope"), null, "bob", V023.utcNowIso());
        assertEquals(Constants.FAILURE_GRANT_REQUESTER_MISMATCH, cv.failureType());
    }

    @Test
    void anotherPrincipalCannotRedeemAndTheGrantIsNotSpent() throws Exception {
        DelegationToken alice = service.resolveBearerToken(service.issueCapabilityToken(
                "alice", "transfer_funds", List.of("finance.transfer")).getToken());
        Map<String, Object> params = new HashMap<>();
        params.put("amount", 5000);
        @SuppressWarnings("unchecked")
        Map<String, Object> approval = (Map<String, Object>) ((Map<String, Object>)
                service.invoke("transfer_funds", alice, params, null).get("failure")).get("approval_required");
        String aprId = (String) approval.get("approval_request_id");
        ApprovalRequest stored = storage().getApprovalRequest(aprId).orElseThrow();
        assertEquals("alice", stored.getRequester().get("root_principal"));
        ApprovalGrant g = service.issueApprovalGrant(aprId, "one_time",
                Map.of("subject", "ap"), null, null, null);

        DelegationToken bob = service.resolveBearerToken(service.issueCapabilityToken(
                "bob", "transfer_funds", List.of("finance.transfer")).getToken());
        Map<String, Object> refused = service.invoke("transfer_funds", bob, params,
                new InvokeOpts().setApprovalGrant(g.getGrantId()));
        assertEquals(false, refused.get("success"));
        @SuppressWarnings("unchecked")
        Map<String, Object> failure = (Map<String, Object>) refused.get("failure");
        assertEquals(Constants.FAILURE_GRANT_REQUESTER_MISMATCH, failure.get("type"));
        @SuppressWarnings("unchecked")
        Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
        assertEquals("contact_service_owner", resolution.get("action"));
        assertEquals("terminal", resolution.get("recovery_class"));
        assertEquals(0, storage().getGrant(g.getGrantId()).orElseThrow().getUseCount());
        assertEquals(403, Constants.failureStatusCode(Constants.FAILURE_GRANT_REQUESTER_MISMATCH));
    }

    @Test
    void endToEndAuditLinkage() throws Exception {
        // Issue a token with finance.transfer scope.
        TokenResponse tok = service.issueCapabilityToken(
                "alice", "transfer_funds", List.of("finance.transfer"));
        DelegationToken token = service.resolveBearerToken(tok.getToken());

        // 1. First invocation: raises approval_required. Use ONLY business parameters
        // so the materialized request's digest matches the continuation submission.
        Map<String, Object> origParams = new HashMap<>();
        origParams.put("amount", 5000);
        Map<String, Object> failResp = service.invoke("transfer_funds", token, origParams, null);
        assertEquals(false, failResp.get("success"));
        @SuppressWarnings("unchecked")
        Map<String, Object> failure = (Map<String, Object>) failResp.get("failure");
        assertEquals(Constants.FAILURE_APPROVAL_REQUIRED, failure.get("type"));
        @SuppressWarnings("unchecked")
        Map<String, Object> approval = (Map<String, Object>) failure.get("approval_required");
        assertNotNull(approval, "approval_required block must be present");
        String aprId = (String) approval.get("approval_request_id");
        assertNotNull(aprId);

        // ApprovalRequest persisted with the same digests as the failed call.
        ApprovalRequest persisted = service.getApprovalRequest(aprId);
        assertNotNull(persisted);
        assertEquals(failResp.get("invocation_id"), persisted.getParentInvocationId());

        // 2. Issue grant (approver auth is enforced at HTTP layer, SPI trusts caller).
        Map<String, Object> approver = Map.of("subject", "approver", "root_principal", "approver");
        ApprovalGrant g = service.issueApprovalGrant(aprId, "one_time", approver, null, null, null);
        assertNotNull(g);

        // 3. Continuation invocation, against a second request whose digest
        // matches the continuation submission ({amount:100}).
        ApprovalRequest req2 = new ApprovalRequest(
                "apr_e2e", "transfer_funds", List.of("finance.transfer"),
                Map.of("subject", "alice", "root_principal", "alice"), failResp.get("invocation_id").toString(),
                Map.of(), V023.sha256Digest(Map.of()),
                Map.of("amount", 100), V023.sha256Digest(Map.of("amount", 100)),
                new GrantPolicy(List.of("one_time"), "one_time", 600, 1),
                ApprovalRequest.STATUS_PENDING, null, null,
                V023.utcNowIso(), V023.utcInIso(900));
        storage().storeApprovalRequest(req2);
        ApprovalGrant g2 = service.issueApprovalGrant("apr_e2e", "one_time", approver, null, null, null);

        InvokeOpts opts = new InvokeOpts();
        opts.setApprovalGrant(g2.getGrantId());
        Map<String, Object> success = service.invoke("transfer_funds", token,
                Map.of("amount", 100), opts);
        assertEquals(true, success.get("success"));
        @SuppressWarnings("unchecked")
        Map<String, Object> continuationResult = (Map<String, Object>) success.get("result");
        assertEquals(g2.getGrantId(), continuationResult.get("approval_grant"));

        // Alice-scoped audit: failure entry linked to approval_request_id,
        // approval_request_created event, and continuation success referencing
        // approval_grant_id. (The approval_grant_issued event is scoped to the
        // approver principal, so it's intentionally NOT in alice's audit query.)
        AuditFilters f = new AuditFilters(null, null, null, null, null, null, null, 100);
        var entries = service.queryAudit(token, f).getEntries();
        boolean failureLinked = false, requestCreated = false, contSuccess = false;
        for (AuditEntry e : entries) {
            if (Boolean.FALSE.equals(e.isSuccess())
                    && Constants.FAILURE_APPROVAL_REQUIRED.equals(e.getFailureType())
                    && aprId.equals(e.getApprovalRequestId())) {
                failureLinked = true;
            }
            if ("approval_request_created".equals(e.getEntryType())
                    && aprId.equals(e.getApprovalRequestId())) {
                requestCreated = true;
            }
            if (Boolean.TRUE.equals(e.isSuccess()) && e.getEntryType() == null
                    && g2.getGrantId().equals(e.getApprovalGrantId())) {
                contSuccess = true;
            }
        }
        assertTrue(failureLinked, "failure entry should reference approval_request_id");
        assertTrue(requestCreated, "approval_request_created entry should be emitted");
        assertTrue(contSuccess, "continuation success entry should reference approval_grant_id");

        // Storage-scoped check: approval_grant_issued event was emitted for the
        // approver — not visible via alice's audit query but verifiable via
        // storage's full audit table.
        var allEntries = storage().queryAuditEntries(
                new AuditFilters(null, null, null, null, null, null, null, 1000));
        boolean grantIssued = false;
        for (AuditEntry e : allEntries) {
            if ("approval_grant_issued".equals(e.getEntryType())
                    && (g.getGrantId().equals(e.getApprovalGrantId())
                        || g2.getGrantId().equals(e.getApprovalGrantId()))) {
                grantIssued = true;
                break;
            }
        }
        assertTrue(grantIssued, "approval_grant_issued entry should be emitted");
    }

    @Test
    void concurrentIssuanceLeavesOneSuccess() throws Exception {
        persistRequest("apr_cr", new GrantPolicy(
                List.of("one_time"), "one_time", 600, 1));
        int threads = 12;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        AtomicInteger okCount = new AtomicInteger();
        try {
            List<CompletableFuture<Void>> fs = new ArrayList<>();
            for (int i = 0; i < threads; i++) {
                fs.add(CompletableFuture.runAsync(() -> {
                    try {
                        service.issueApprovalGrant("apr_cr", "one_time",
                                Map.of("subject", "ap"), null, null, null);
                        okCount.incrementAndGet();
                    } catch (Exception ignored) {}
                }, pool));
            }
            CompletableFuture.allOf(fs.toArray(new CompletableFuture[0])).get(20, TimeUnit.SECONDS);
        } finally {
            pool.shutdown();
        }
        assertEquals(1, okCount.get());
    }

    @Test
    void discoveryAdvertisesApprovalGrantsEndpoint() {
        @SuppressWarnings("unchecked")
        Map<String, Object> doc = (Map<String, Object>) service.getDiscovery("http://test").get("anip_discovery");
        @SuppressWarnings("unchecked")
        Map<String, Object> endpoints = (Map<String, Object>) doc.get("endpoints");
        assertEquals("/anip/approval_grants", endpoints.get("approval_grants"));
    }

    // --- Blank grants, resolution and retry ---

    private DelegationToken aliceToken() throws Exception {
        TokenResponse tok = service.issueToken("alice", new dev.anip.core.TokenRequest(
                "alice", List.of("finance.transfer"), "transfer_funds", null, null, 1, null));
        return service.resolveBearerToken(tok.getToken());
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> failureOf(Map<String, Object> response) {
        assertEquals(false, response.get("success"), "expected a failure: " + response);
        return (Map<String, Object>) response.get("failure");
    }

    @Test
    void blankSuppliedGrantIsNotFoundBeforeTheHandler() throws Exception {
        // A supplied approval_grant is always validated. A blank one names no
        // grant, whether or not the invocation would have needed approval.
        DelegationToken token = aliceToken();
        for (String grant : List.of("", "   ", "\t\n")) {
            for (boolean needsApproval : List.of(true, false)) {
                Map<String, Object> params = new HashMap<>();
                params.put("amount", needsApproval ? 5000 : 100);
                Map<String, Object> failure = failureOf(service.invoke(
                        "transfer_funds", token, params, new InvokeOpts().setApprovalGrant(grant)));
                assertEquals(Constants.FAILURE_GRANT_NOT_FOUND, failure.get("type"));
                assertNull(failure.get("approval_required"));
                Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
                assertNotNull(resolution, "grant failures carry a resolution");
                assertEquals("contact_service_owner", resolution.get("action"));
                assertEquals("terminal", resolution.get("recovery_class"));
            }
        }
    }

    @Test
    void blankSuppliedGrantIsNotFoundOnTheStreamingPath() throws Exception {
        DelegationToken token = aliceToken();
        ANIPError error = assertThrows(ANIPError.class, () -> service.invokeStream(
                "transfer_funds", token, Map.of("amount", 100),
                new InvokeOpts().setApprovalGrant(" ")));
        assertEquals(Constants.FAILURE_GRANT_NOT_FOUND, error.getErrorType());
        assertNotNull(error.getResolution());
        assertEquals("terminal", error.getResolution().getRecoveryClass());
    }

    @Test
    void approvalGrantFromRequestKeepsAbsentAndSuppliedApart() {
        assertNull(InvokeOpts.approvalGrantFromRequest(null));
        assertEquals("", InvokeOpts.approvalGrantFromRequest(""));
        assertEquals("grant_1", InvokeOpts.approvalGrantFromRequest("grant_1"));
        assertEquals("", InvokeOpts.approvalGrantFromRequest(7));
    }

    @Test
    void unknownGrantFailureCarriesResolution() throws Exception {
        // SPEC.md §4.5: every failure carries a resolution with a recovery_class.
        Map<String, Object> failure = failureOf(service.invoke(
                "transfer_funds", aliceToken(), Map.of("amount", 100),
                new InvokeOpts().setApprovalGrant("grant_missing")));
        assertEquals(Constants.FAILURE_GRANT_NOT_FOUND, failure.get("type"));
        @SuppressWarnings("unchecked")
        Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
        assertNotNull(resolution);
        assertEquals("terminal", resolution.get("recovery_class"));
    }

    @Test
    void approvalRequiredCarriesRetryFalse() throws Exception {
        // SPEC.md §4.7: the approval_required failure carries retry: false.
        Map<String, Object> params = new HashMap<>();
        params.put("amount", 5000);
        Map<String, Object> failure = failureOf(service.invoke(
                "transfer_funds", aliceToken(), params, null));
        assertEquals(Constants.FAILURE_APPROVAL_REQUIRED, failure.get("type"));
        assertEquals(false, failure.get("retry"));
    }

    /**
     * SPEC.md §4.7: when the ApprovalRequest cannot be persisted the failure
     * is {@code service_unavailable} (HTTP 503), not {@code approval_required}.
     */
    @Test
    void approvalRequestPersistFailureIsServiceUnavailable() throws Exception {
        TokenResponse tok = service.issueToken("alice", new dev.anip.core.TokenRequest(
                "alice", List.of("finance.transfer"), "transfer_funds", null, null, 1, null));
        DelegationToken token = service.resolveBearerToken(tok.getToken());

        var field = ANIPService.class.getDeclaredField("storage");
        field.setAccessible(true);
        dev.anip.server.Storage real = (dev.anip.server.Storage) field.get(service);
        dev.anip.server.Storage failing = (dev.anip.server.Storage) java.lang.reflect.Proxy.newProxyInstance(
                dev.anip.server.Storage.class.getClassLoader(),
                new Class<?>[] {dev.anip.server.Storage.class},
                (proxy, method, args) -> {
                    if ("storeApprovalRequest".equals(method.getName())) {
                        throw new IllegalStateException("storage is down");
                    }
                    try {
                        return method.invoke(real, args);
                    } catch (java.lang.reflect.InvocationTargetException e) {
                        throw e.getCause();
                    }
                });
        field.set(service, failing);
        Map<String, Object> response;
        try {
            Map<String, Object> params = new HashMap<>();
            params.put("amount", 5000);
            response = service.invoke("transfer_funds", token, params, null);
        } finally {
            field.set(service, real);
        }

        assertEquals(false, response.get("success"));
        @SuppressWarnings("unchecked")
        Map<String, Object> failure = (Map<String, Object>) response.get("failure");
        assertEquals(Constants.FAILURE_SERVICE_UNAVAILABLE, failure.get("type"));
        assertEquals("service_unavailable", failure.get("type"));
        assertEquals(503, Constants.failureStatusCode((String) failure.get("type")));
        assertFalse(failure.containsKey("approval_required"));
        @SuppressWarnings("unchecked")
        Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
        assertEquals("wait_and_retry", resolution.get("action"));
        assertEquals("wait_then_retry", resolution.get("recovery_class"));
        assertEquals(true, failure.get("retry"));

        List<AuditEntry> entries = storage().queryAuditEntries(new AuditFilters(
                null, null, null, (String) response.get("invocation_id"), null, null, null, 10));
        assertEquals(1, entries.size());
        assertEquals("service_unavailable", entries.get(0).getFailureType());
        assertNull(entries.get(0).getApprovalRequestId());
    }
}
