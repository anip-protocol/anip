package dev.anip.server;

import dev.anip.core.ApprovalGrant;
import dev.anip.core.ApprovalRequest;
import dev.anip.core.GrantPolicy;

import java.time.Duration;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
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

/** v0.23 storage primitives — round-trip, idempotency, atomic CAS. */
class V023StorageTest {

    private SqliteStorage storage;

    @BeforeEach
    void setUp() throws Exception {
        storage = new SqliteStorage(":memory:");
    }

    @AfterEach
    void tearDown() throws Exception {
        storage.close();
    }

    private static String nowIso() {
        return DateTimeFormatter.ISO_INSTANT.format(Instant.now());
    }

    private static String inIso(int seconds) {
        return DateTimeFormatter.ISO_INSTANT.format(Instant.now().plus(Duration.ofSeconds(seconds)));
    }

    private static GrantPolicy gp() {
        return new GrantPolicy(List.of("one_time", "session_bound"), "one_time", 900, 5);
    }

    private static ApprovalRequest pendingRequest(String id) {
        return new ApprovalRequest(
                id, "cap", List.of("scope.read"),
                Map.of("subject", "alice"), null,
                Map.of(), "sha256:p", Map.of("x", 1), "sha256:q",
                gp(), ApprovalRequest.STATUS_PENDING, null, null,
                nowIso(), inIso(900));
    }

    private static ApprovalGrant grantFor(ApprovalRequest req, int maxUses, int useCount, int expiresInSeconds) {
        return new ApprovalGrant(
                "grant_" + req.getApprovalRequestId(),
                req.getApprovalRequestId(),
                ApprovalGrant.TYPE_ONE_TIME,
                req.getCapability(), new ArrayList<>(req.getScope()),
                req.getRequestedParametersDigest(), req.getPreviewDigest(),
                req.getRequester(), Map.of("subject", "approver"),
                nowIso(), inIso(expiresInSeconds), maxUses, useCount, null,
                "sig.sig.sig");
    }

    @Test
    void approvalRequestRoundTrip() throws Exception {
        ApprovalRequest req = pendingRequest("apr_round1");
        storage.storeApprovalRequest(req);
        Optional<ApprovalRequest> loaded = storage.getApprovalRequest("apr_round1");
        assertTrue(loaded.isPresent());
        assertEquals("apr_round1", loaded.get().getApprovalRequestId());
        assertEquals(ApprovalRequest.STATUS_PENDING, loaded.get().getStatus());
    }

    @Test
    void approvalRequestIdempotentSameContent() throws Exception {
        ApprovalRequest req = pendingRequest("apr_idem1");
        storage.storeApprovalRequest(req);
        // Same content — no exception.
        storage.storeApprovalRequest(req);
        assertTrue(storage.getApprovalRequest("apr_idem1").isPresent());
    }

    @Test
    void approvalRequestRejectsConflictingContent() throws Exception {
        ApprovalRequest req = pendingRequest("apr_conf");
        storage.storeApprovalRequest(req);
        ApprovalRequest mutated = new ApprovalRequest(
                "apr_conf", "different_cap", List.of("scope.read"),
                Map.of("subject", "alice"), null,
                Map.of(), "sha256:p", Map.of("x", 1), "sha256:q",
                gp(), ApprovalRequest.STATUS_PENDING, null, null,
                nowIso(), inIso(900));
        Exception ex = assertThrows(Exception.class, () -> storage.storeApprovalRequest(mutated));
        assertTrue(ex.getMessage().contains("already stored with different content"));
    }

    @Test
    void approveRequestAndStoreGrantHappyPath() throws Exception {
        ApprovalRequest req = pendingRequest("apr_happy");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant = grantFor(req, 3, 0, 300);
        ApprovalDecisionResult r = storage.approveRequestAndStoreGrant(
                "apr_happy", grant, Map.of("subject", "approver"), nowIso(), nowIso());
        assertTrue(r.ok());
        assertNotNull(r.grant());
        // Request transitioned.
        assertEquals(ApprovalRequest.STATUS_APPROVED,
                storage.getApprovalRequest("apr_happy").get().getStatus());
        assertTrue(storage.getGrant("grant_apr_happy").isPresent());
    }

    @Test
    void approveRequestAndStoreGrantRejectsNotFound() throws Exception {
        ApprovalRequest req = pendingRequest("apr_x");
        ApprovalGrant grant = grantFor(req, 1, 0, 300);
        ApprovalDecisionResult r = storage.approveRequestAndStoreGrant(
                "apr_missing", grant, Map.of("subject", "a"), nowIso(), nowIso());
        assertFalse(r.ok());
        assertEquals("approval_request_not_found", r.reason());
    }

    @Test
    void approveRequestAndStoreGrantRejectsAlreadyDecided() throws Exception {
        ApprovalRequest req = pendingRequest("apr_dec");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant1 = grantFor(req, 1, 0, 300);
        ApprovalDecisionResult first = storage.approveRequestAndStoreGrant(
                "apr_dec", grant1, Map.of("subject", "a"), nowIso(), nowIso());
        assertTrue(first.ok());
        // Second issuance with a different grant id must fail.
        ApprovalGrant grant2 = new ApprovalGrant(
                "grant_dup", req.getApprovalRequestId(), ApprovalGrant.TYPE_ONE_TIME,
                req.getCapability(), req.getScope(),
                req.getRequestedParametersDigest(), req.getPreviewDigest(),
                req.getRequester(), Map.of("subject", "b"),
                nowIso(), inIso(300), 1, 0, null, "sig");
        ApprovalDecisionResult second = storage.approveRequestAndStoreGrant(
                "apr_dec", grant2, Map.of("subject", "b"), nowIso(), nowIso());
        assertFalse(second.ok());
        assertEquals("approval_request_already_decided", second.reason());
    }

    @Test
    void approveRequestAndStoreGrantRejectsExpired() throws Exception {
        // Build a request whose expires_at is already in the past.
        ApprovalRequest req = new ApprovalRequest(
                "apr_exp", "cap", List.of("s"),
                Map.of("subject", "alice"), null,
                Map.of(), "p", Map.of(), "q",
                gp(), ApprovalRequest.STATUS_PENDING, null, null,
                "2000-01-01T00:00:00Z", "2000-01-01T00:00:01Z");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant = grantFor(req, 1, 0, 60);
        ApprovalDecisionResult r = storage.approveRequestAndStoreGrant(
                "apr_exp", grant, Map.of("subject", "a"), nowIso(), nowIso());
        assertFalse(r.ok());
        assertEquals("approval_request_expired", r.reason());
    }

    @Test
    void concurrentIssuanceRaceLeavesExactlyOneSuccess() throws Exception {
        ApprovalRequest req = pendingRequest("apr_race");
        storage.storeApprovalRequest(req);
        int threads = 16;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        AtomicInteger okCount = new AtomicInteger();
        try {
            List<CompletableFuture<Void>> futures = new ArrayList<>();
            for (int i = 0; i < threads; i++) {
                final int idx = i;
                futures.add(CompletableFuture.runAsync(() -> {
                    try {
                        ApprovalGrant grant = new ApprovalGrant(
                                "grant_race_" + idx, req.getApprovalRequestId(),
                                ApprovalGrant.TYPE_ONE_TIME, req.getCapability(),
                                req.getScope(), req.getRequestedParametersDigest(),
                                req.getPreviewDigest(), req.getRequester(),
                                Map.of("subject", "approver_" + idx),
                                nowIso(), inIso(60), 1, 0, null, "sig");
                        ApprovalDecisionResult r = storage.approveRequestAndStoreGrant(
                                req.getApprovalRequestId(), grant,
                                Map.of("subject", "approver_" + idx), nowIso(), nowIso());
                        if (r.ok()) okCount.incrementAndGet();
                    } catch (Exception ignored) {}
                }, pool));
            }
            CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get(20, TimeUnit.SECONDS);
        } finally {
            pool.shutdown();
        }
        assertEquals(1, okCount.get(), "exactly one issuer should succeed");
    }

    @Test
    void tryReserveGrantHappyPath() throws Exception {
        ApprovalRequest req = pendingRequest("apr_res1");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant = grantFor(req, 3, 0, 300);
        storage.approveRequestAndStoreGrant("apr_res1", grant,
                Map.of("subject", "approver"), nowIso(), nowIso());
        GrantReservationResult r = storage.tryReserveGrant(grant.getGrantId(), nowIso());
        assertTrue(r.ok());
        assertEquals(1, r.grant().getUseCount());
    }

    @Test
    void tryReserveGrantNotFound() throws Exception {
        GrantReservationResult r = storage.tryReserveGrant("nope", nowIso());
        assertFalse(r.ok());
        assertEquals("grant_not_found", r.reason());
    }

    @Test
    void tryReserveGrantExpired() throws Exception {
        ApprovalRequest req = pendingRequest("apr_exp2");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant = new ApprovalGrant(
                "grant_exp", req.getApprovalRequestId(), ApprovalGrant.TYPE_ONE_TIME,
                req.getCapability(), req.getScope(),
                req.getRequestedParametersDigest(), req.getPreviewDigest(),
                req.getRequester(), Map.of("subject", "approver"),
                "2000-01-01T00:00:00Z", "2000-01-01T00:00:01Z", 1, 0, null, "sig");
        storage.storeGrant(grant);
        GrantReservationResult r = storage.tryReserveGrant("grant_exp", nowIso());
        assertFalse(r.ok());
        assertEquals("grant_expired", r.reason());
    }

    @Test
    void tryReserveGrantConsumed() throws Exception {
        ApprovalRequest req = pendingRequest("apr_cons");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant = grantFor(req, 1, 1, 300);  // already at max_uses
        storage.storeGrant(grant);
        GrantReservationResult r = storage.tryReserveGrant(grant.getGrantId(), nowIso());
        assertFalse(r.ok());
        assertEquals("grant_consumed", r.reason());
    }

    @Test
    void concurrentReservationNeverExceedsMaxUses() throws Exception {
        ApprovalRequest req = pendingRequest("apr_concres");
        storage.storeApprovalRequest(req);
        ApprovalGrant grant = grantFor(req, 5, 0, 300);
        storage.approveRequestAndStoreGrant("apr_concres", grant,
                Map.of("subject", "approver"), nowIso(), nowIso());

        int threads = 20;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        AtomicInteger okCount = new AtomicInteger();
        try {
            List<CompletableFuture<Void>> futures = new ArrayList<>();
            for (int i = 0; i < threads; i++) {
                futures.add(CompletableFuture.runAsync(() -> {
                    try {
                        GrantReservationResult r = storage.tryReserveGrant(grant.getGrantId(), nowIso());
                        if (r.ok()) okCount.incrementAndGet();
                    } catch (Exception ignored) {}
                }, pool));
            }
            CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).get(20, TimeUnit.SECONDS);
        } finally {
            pool.shutdown();
        }
        // Exactly max_uses successful reservations.
        assertEquals(5, okCount.get());
        ApprovalGrant after = storage.getGrant(grant.getGrantId()).orElseThrow();
        assertEquals(5, after.getUseCount());
    }
}
