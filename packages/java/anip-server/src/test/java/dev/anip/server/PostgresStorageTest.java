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
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration tests for PostgresStorage.
 * Skipped unless ANIP_TEST_POSTGRES_DSN environment variable is set.
 */
@EnabledIfEnvironmentVariable(named = "ANIP_TEST_POSTGRES_DSN", matches = ".+")
class PostgresStorageTest {

    private PostgresStorage storage;

    @BeforeEach
    void setUp() throws Exception {
        String dsn = System.getenv("ANIP_TEST_POSTGRES_DSN");
        storage = new PostgresStorage(dsn);
    }

    @AfterEach
    void tearDown() throws Exception {
        if (storage != null) {
            storage.close();
        }
    }

    @Test
    void storeAndLoadToken() throws Exception {
        DelegationToken token = new DelegationToken(
                "pg-tok-1", "test-service", "test-subject",
                List.of("travel.search"), new Purpose("cap", Map.of(), "task"),
                "", "2025-12-31T23:59:59Z",
                new DelegationConstraints(), "user@test.com", "human"
        );
        storage.storeToken(token);

        DelegationToken loaded = storage.loadToken("pg-tok-1");
        assertNotNull(loaded);
        assertEquals("pg-tok-1", loaded.getTokenId());
    }

    @Test
    void appendAndQueryAudit() throws Exception {
        AuditEntry entry = new AuditEntry();
        entry.setTimestamp("2025-06-15T12:00:00Z");
        entry.setCapability("pg_test_cap");
        entry.setTokenId("tok-pg");
        entry.setRootPrincipal("pg-user@test.com");
        entry.setInvocationId("inv-pg12345678");
        entry.setSuccess(true);

        AuditEntry appended = storage.appendAuditEntry(entry);
        assertTrue(appended.getSequenceNumber() > 0);

        List<AuditEntry> entries = storage.queryAuditEntries(
                new AuditFilters("pg_test_cap", null, null, null, null, 10));
        assertFalse(entries.isEmpty());
    }

    @Test
    void leaseAcquireRelease() throws Exception {
        assertTrue(storage.tryAcquireExclusive("pg-lock", "holder-a", 60));
        assertFalse(storage.tryAcquireExclusive("pg-lock", "holder-b", 60));
        storage.releaseExclusive("pg-lock", "holder-a");
        assertTrue(storage.tryAcquireExclusive("pg-lock", "holder-b", 60));
        storage.releaseExclusive("pg-lock", "holder-b");
    }
}
