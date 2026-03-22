package dev.anip.server;

import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditResponse;
import dev.anip.crypto.KeyManager;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class AuditLogTest {

    private KeyManager km;
    private SqliteStorage storage;

    @BeforeEach
    void setUp() throws Exception {
        km = KeyManager.create(null);
        storage = new SqliteStorage(":memory:");
    }

    @AfterEach
    void tearDown() throws Exception {
        storage.close();
    }

    @Test
    void appendAndQuery() throws Exception {
        AuditEntry entry = createEntry("search_flights", "human@test.com");
        AuditLog.appendAudit(km, storage, entry);

        assertTrue(entry.getSequenceNumber() > 0);
        assertNotNull(entry.getPreviousHash());
        assertNotNull(entry.getSignature());
        assertTrue(entry.getSignature().length() > 10);

        AuditResponse response = AuditLog.queryAudit(storage, "human@test.com",
                new AuditFilters(null, null, null, null, 10));
        assertEquals(1, response.getEntries().size());
        assertEquals("search_flights", response.getEntries().get(0).getCapability());
        assertEquals("human@test.com", response.getRootPrincipal());
    }

    @Test
    void hashChainIntegrity() throws Exception {
        AuditEntry e1 = createEntry("cap1", "user@test.com");
        AuditLog.appendAudit(km, storage, e1);

        AuditEntry e2 = createEntry("cap2", "user@test.com");
        AuditLog.appendAudit(km, storage, e2);

        AuditEntry e3 = createEntry("cap3", "user@test.com");
        AuditLog.appendAudit(km, storage, e3);

        // First entry has sentinel hash.
        assertEquals("sha256:0", e1.getPreviousHash());

        // Subsequent entries should chain.
        assertNotEquals("sha256:0", e2.getPreviousHash());
        assertTrue(e2.getPreviousHash().startsWith("sha256:"));

        assertNotEquals(e2.getPreviousHash(), e3.getPreviousHash());
        assertTrue(e3.getPreviousHash().startsWith("sha256:"));

        // All should have unique signatures.
        assertNotEquals(e1.getSignature(), e2.getSignature());
        assertNotEquals(e2.getSignature(), e3.getSignature());
    }

    @Test
    void appendSetsTimestampIfMissing() throws Exception {
        AuditEntry entry = new AuditEntry();
        entry.setCapability("test_cap");
        entry.setTokenId("tok-1");
        entry.setRootPrincipal("user@test.com");
        entry.setInvocationId("inv-123456789012");
        entry.setSuccess(true);
        // No timestamp set.

        AuditLog.appendAudit(km, storage, entry);

        assertNotNull(entry.getTimestamp());
        assertFalse(entry.getTimestamp().isEmpty());
    }

    @Test
    void queryScopedToRootPrincipal() throws Exception {
        AuditEntry e1 = createEntry("cap1", "alice@test.com");
        AuditLog.appendAudit(km, storage, e1);

        AuditEntry e2 = createEntry("cap2", "bob@test.com");
        AuditLog.appendAudit(km, storage, e2);

        AuditResponse aliceEntries = AuditLog.queryAudit(storage, "alice@test.com",
                new AuditFilters(null, null, null, null, 10));
        assertEquals(1, aliceEntries.getEntries().size());
        assertEquals("cap1", aliceEntries.getEntries().get(0).getCapability());

        AuditResponse bobEntries = AuditLog.queryAudit(storage, "bob@test.com",
                new AuditFilters(null, null, null, null, 10));
        assertEquals(1, bobEntries.getEntries().size());
        assertEquals("cap2", bobEntries.getEntries().get(0).getCapability());
    }

    @Test
    void queryWithCapabilityFilter() throws Exception {
        AuditEntry e1 = createEntry("search_flights", "user@test.com");
        AuditLog.appendAudit(km, storage, e1);

        AuditEntry e2 = createEntry("book_flight", "user@test.com");
        AuditLog.appendAudit(km, storage, e2);

        AuditResponse response = AuditLog.queryAudit(storage, "user@test.com",
                new AuditFilters("search_flights", null, null, null, 10));
        assertEquals(1, response.getEntries().size());
        assertEquals("search_flights", response.getEntries().get(0).getCapability());
    }

    @Test
    void sequenceNumbersAreSequential() throws Exception {
        AuditEntry e1 = createEntry("cap1", "user@test.com");
        AuditLog.appendAudit(km, storage, e1);

        AuditEntry e2 = createEntry("cap2", "user@test.com");
        AuditLog.appendAudit(km, storage, e2);

        AuditEntry e3 = createEntry("cap3", "user@test.com");
        AuditLog.appendAudit(km, storage, e3);

        assertEquals(1, e1.getSequenceNumber());
        assertEquals(2, e2.getSequenceNumber());
        assertEquals(3, e3.getSequenceNumber());
    }

    private AuditEntry createEntry(String capability, String rootPrincipal) {
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
