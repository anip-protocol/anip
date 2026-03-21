package dev.anip.server;

import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.Checkpoint;
import dev.anip.core.DelegationConstraints;
import dev.anip.core.DelegationToken;
import dev.anip.core.Purpose;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class SqliteStorageTest {

    private SqliteStorage storage;

    @BeforeEach
    void setUp() throws Exception {
        storage = new SqliteStorage(":memory:");
    }

    @AfterEach
    void tearDown() throws Exception {
        storage.close();
    }

    // --- Token CRUD ---

    @Test
    void storeAndLoadToken() throws Exception {
        DelegationToken token = createToken("tok-1", "human@example.com");
        storage.storeToken(token);

        DelegationToken loaded = storage.loadToken("tok-1");
        assertNotNull(loaded);
        assertEquals("tok-1", loaded.getTokenId());
        assertEquals("human@example.com", loaded.getRootPrincipal());
        assertEquals("test-subject", loaded.getSubject());
        assertEquals(List.of("travel.search", "travel.book"), loaded.getScope());
    }

    @Test
    void loadTokenNotFound() throws Exception {
        DelegationToken loaded = storage.loadToken("nonexistent");
        assertNull(loaded);
    }

    @Test
    void storeTokenOverwrites() throws Exception {
        DelegationToken token1 = createToken("tok-1", "human@example.com");
        storage.storeToken(token1);

        DelegationToken token2 = new DelegationToken(
                "tok-1", "test-service", "new-subject",
                List.of("admin"), new Purpose("admin_op", Map.of(), "task-1"),
                "", "2025-12-31T23:59:59Z",
                new DelegationConstraints(), "admin@example.com", "human"
        );
        storage.storeToken(token2);

        DelegationToken loaded = storage.loadToken("tok-1");
        assertNotNull(loaded);
        assertEquals("new-subject", loaded.getSubject());
    }

    // --- Audit CRUD ---

    @Test
    void appendAndQueryAuditEntry() throws Exception {
        AuditEntry entry = createAuditEntry("search_flights", "human@example.com");
        AuditEntry appended = storage.appendAuditEntry(entry);

        assertTrue(appended.getSequenceNumber() > 0);
        assertEquals("sha256:0", appended.getPreviousHash());

        AuditFilters filters = new AuditFilters(null, "human@example.com",
                null, null, null, 10);
        List<AuditEntry> entries = storage.queryAuditEntries(filters);
        assertEquals(1, entries.size());
        assertEquals("search_flights", entries.get(0).getCapability());
    }

    @Test
    void auditHashChain() throws Exception {
        AuditEntry e1 = createAuditEntry("cap1", "user@test.com");
        storage.appendAuditEntry(e1);

        AuditEntry e2 = createAuditEntry("cap2", "user@test.com");
        AuditEntry appended2 = storage.appendAuditEntry(e2);

        // Second entry should have a hash of the first entry, not the sentinel.
        assertNotEquals("sha256:0", appended2.getPreviousHash());
        assertTrue(appended2.getPreviousHash().startsWith("sha256:"));
    }

    @Test
    void queryAuditWithFilters() throws Exception {
        AuditEntry e1 = createAuditEntry("search_flights", "alice@test.com");
        e1.setTimestamp("2025-01-01T00:00:00Z");
        storage.appendAuditEntry(e1);

        AuditEntry e2 = createAuditEntry("book_flight", "bob@test.com");
        e2.setTimestamp("2025-06-01T00:00:00Z");
        storage.appendAuditEntry(e2);

        // Filter by capability
        List<AuditEntry> results = storage.queryAuditEntries(
                new AuditFilters("search_flights", null, null, null, null, 10));
        assertEquals(1, results.size());
        assertEquals("search_flights", results.get(0).getCapability());

        // Filter by root_principal
        results = storage.queryAuditEntries(
                new AuditFilters(null, "bob@test.com", null, null, null, 10));
        assertEquals(1, results.size());
        assertEquals("book_flight", results.get(0).getCapability());

        // Filter by since
        results = storage.queryAuditEntries(
                new AuditFilters(null, null, "2025-03-01T00:00:00Z", null, null, 10));
        assertEquals(1, results.size());
        assertEquals("book_flight", results.get(0).getCapability());
    }

    @Test
    void getMaxAuditSequenceEmpty() throws Exception {
        assertEquals(0, storage.getMaxAuditSequence());
    }

    @Test
    void getMaxAuditSequence() throws Exception {
        storage.appendAuditEntry(createAuditEntry("cap1", "user@test.com"));
        storage.appendAuditEntry(createAuditEntry("cap2", "user@test.com"));
        storage.appendAuditEntry(createAuditEntry("cap3", "user@test.com"));

        assertEquals(3, storage.getMaxAuditSequence());
    }

    @Test
    void getAuditEntriesRange() throws Exception {
        storage.appendAuditEntry(createAuditEntry("cap1", "user@test.com"));
        storage.appendAuditEntry(createAuditEntry("cap2", "user@test.com"));
        storage.appendAuditEntry(createAuditEntry("cap3", "user@test.com"));

        List<AuditEntry> range = storage.getAuditEntriesRange(1, 2);
        assertEquals(2, range.size());
        assertEquals("cap1", range.get(0).getCapability());
        assertEquals("cap2", range.get(1).getCapability());
    }

    @Test
    void updateAuditSignature() throws Exception {
        AuditEntry entry = createAuditEntry("cap1", "user@test.com");
        AuditEntry appended = storage.appendAuditEntry(entry);

        storage.updateAuditSignature(appended.getSequenceNumber(), "test-signature");

        List<AuditEntry> entries = storage.getAuditEntriesRange(
                appended.getSequenceNumber(), appended.getSequenceNumber());
        assertEquals(1, entries.size());
        assertEquals("test-signature", entries.get(0).getSignature());
    }

    // --- Checkpoint CRUD ---

    @Test
    void storeAndListCheckpoints() throws Exception {
        Checkpoint cp1 = new Checkpoint("0.3", "test-service", "ckpt-1",
                Map.of("first_sequence", 1, "last_sequence", 5),
                "sha256:abc", null, "2025-01-01T00:00:00Z", 5, null);
        storage.storeCheckpoint(cp1, "sig1");

        Checkpoint cp2 = new Checkpoint("0.3", "test-service", "ckpt-2",
                Map.of("first_sequence", 1, "last_sequence", 10),
                "sha256:def", "sha256:prevhash", "2025-01-02T00:00:00Z", 10, null);
        storage.storeCheckpoint(cp2, "sig2");

        List<Checkpoint> checkpoints = storage.listCheckpoints(10);
        assertEquals(2, checkpoints.size());
        assertEquals("ckpt-1", checkpoints.get(0).getCheckpointId());
        assertEquals("ckpt-2", checkpoints.get(1).getCheckpointId());
    }

    @Test
    void getCheckpointById() throws Exception {
        Checkpoint cp = new Checkpoint("0.3", "test-service", "ckpt-1",
                Map.of("first_sequence", 1, "last_sequence", 5),
                "sha256:abc", null, "2025-01-01T00:00:00Z", 5, null);
        storage.storeCheckpoint(cp, "sig1");

        Checkpoint loaded = storage.getCheckpointById("ckpt-1");
        assertNotNull(loaded);
        assertEquals("ckpt-1", loaded.getCheckpointId());
        assertEquals("sha256:abc", loaded.getMerkleRoot());
        assertEquals(5, loaded.getEntryCount());
    }

    @Test
    void getCheckpointByIdNotFound() throws Exception {
        assertNull(storage.getCheckpointById("nonexistent"));
    }

    // --- Retention ---

    @Test
    void deleteExpiredAuditEntries() throws Exception {
        AuditEntry e1 = createAuditEntry("cap1", "user@test.com");
        e1.setExpiresAt("2020-01-01T00:00:00Z"); // already expired
        storage.appendAuditEntry(e1);

        AuditEntry e2 = createAuditEntry("cap2", "user@test.com");
        e2.setExpiresAt("2030-01-01T00:00:00Z"); // not expired
        storage.appendAuditEntry(e2);

        AuditEntry e3 = createAuditEntry("cap3", "user@test.com");
        // no expiry set
        storage.appendAuditEntry(e3);

        int deleted = storage.deleteExpiredAuditEntries("2025-06-01T00:00:00Z");
        assertEquals(1, deleted);

        // Only 2 entries should remain.
        assertEquals(2, storage.getAuditEntriesRange(1, 100).size());
    }

    // --- Leases ---

    @Test
    void exclusiveLeaseAcquireRelease() throws Exception {
        assertTrue(storage.tryAcquireExclusive("lock-1", "holder-a", 60));
        // Same holder can re-acquire.
        assertTrue(storage.tryAcquireExclusive("lock-1", "holder-a", 60));
        // Different holder cannot acquire.
        assertFalse(storage.tryAcquireExclusive("lock-1", "holder-b", 60));

        // Release.
        storage.releaseExclusive("lock-1", "holder-a");
        // Now holder-b can acquire.
        assertTrue(storage.tryAcquireExclusive("lock-1", "holder-b", 60));
    }

    @Test
    void exclusiveLeaseExpiry() throws Exception {
        // Acquire with 0-second TTL (immediately expired).
        assertTrue(storage.tryAcquireExclusive("lock-1", "holder-a", 0));
        // Different holder can acquire since it's expired.
        assertTrue(storage.tryAcquireExclusive("lock-1", "holder-b", 60));
    }

    @Test
    void leaderLeaseAcquireRelease() throws Exception {
        assertTrue(storage.tryAcquireLeader("checkpoint", "worker-1", 60));
        assertFalse(storage.tryAcquireLeader("checkpoint", "worker-2", 60));

        storage.releaseLeader("checkpoint", "worker-1");
        assertTrue(storage.tryAcquireLeader("checkpoint", "worker-2", 60));
    }

    @Test
    void releaseExclusiveWrongHolder() throws Exception {
        assertTrue(storage.tryAcquireExclusive("lock-1", "holder-a", 60));
        // Release with wrong holder should do nothing.
        storage.releaseExclusive("lock-1", "holder-b");
        // Original holder still has the lock.
        assertFalse(storage.tryAcquireExclusive("lock-1", "holder-b", 60));
    }

    // --- Helpers ---

    private DelegationToken createToken(String tokenId, String rootPrincipal) {
        return new DelegationToken(
                tokenId, "test-service", "test-subject",
                List.of("travel.search", "travel.book"),
                new Purpose("search_flights", Map.of(), "task-1"),
                "", "2025-12-31T23:59:59Z",
                new DelegationConstraints(), rootPrincipal, "human"
        );
    }

    private AuditEntry createAuditEntry(String capability, String rootPrincipal) {
        AuditEntry entry = new AuditEntry();
        entry.setTimestamp("2025-06-15T12:00:00Z");
        entry.setCapability(capability);
        entry.setTokenId("tok-test");
        entry.setRootPrincipal(rootPrincipal);
        entry.setInvocationId("inv-test123456");
        entry.setSuccess(true);
        return entry;
    }
}
