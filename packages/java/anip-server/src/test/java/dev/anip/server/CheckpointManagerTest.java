package dev.anip.server;

import dev.anip.core.AuditEntry;
import dev.anip.core.Checkpoint;
import dev.anip.crypto.KeyManager;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class CheckpointManagerTest {

    private KeyManager km;
    private SqliteStorage storage;
    private static final String SERVICE_ID = "test-service";

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
    void createCheckpointNoEntries() throws Exception {
        Checkpoint cp = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNull(cp);
    }

    @Test
    void createCheckpointWithEntries() throws Exception {
        // Add some audit entries.
        for (int i = 0; i < 5; i++) {
            AuditEntry entry = createEntry("cap-" + i);
            AuditLog.appendAudit(km, storage, entry);
        }

        Checkpoint cp = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNotNull(cp);
        assertEquals("ckpt-1", cp.getCheckpointId());
        assertEquals("0.3", cp.getVersion());
        assertEquals(SERVICE_ID, cp.getServiceId());
        assertEquals(5, cp.getEntryCount());
        assertEquals(1, cp.getRange().get("first_sequence"));
        assertEquals(5, cp.getRange().get("last_sequence"));
        assertTrue(cp.getMerkleRoot().startsWith("sha256:"));
        assertNull(cp.getPreviousCheckpoint());
    }

    @Test
    void createMultipleCheckpoints() throws Exception {
        // First batch.
        for (int i = 0; i < 3; i++) {
            AuditLog.appendAudit(km, storage, createEntry("cap-" + i));
        }
        Checkpoint cp1 = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNotNull(cp1);
        assertEquals("ckpt-1", cp1.getCheckpointId());

        // Second batch.
        for (int i = 3; i < 7; i++) {
            AuditLog.appendAudit(km, storage, createEntry("cap-" + i));
        }
        Checkpoint cp2 = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNotNull(cp2);
        assertEquals("ckpt-2", cp2.getCheckpointId());
        assertEquals(7, cp2.getEntryCount());
        assertEquals(7, cp2.getRange().get("last_sequence"));
        assertNotNull(cp2.getPreviousCheckpoint());
        assertTrue(cp2.getPreviousCheckpoint().startsWith("sha256:"));
    }

    @Test
    void noNewCheckpointWhenNoNewEntries() throws Exception {
        AuditLog.appendAudit(km, storage, createEntry("cap-1"));
        CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);

        // No new entries; should return null.
        Checkpoint cp2 = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNull(cp2);
    }

    @Test
    void inclusionProof() throws Exception {
        for (int i = 0; i < 5; i++) {
            AuditLog.appendAudit(km, storage, createEntry("cap-" + i));
        }

        Checkpoint cp = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNotNull(cp);

        // Generate inclusion proof for each leaf.
        for (int i = 0; i < 5; i++) {
            CheckpointManager.InclusionProofResult result =
                    CheckpointManager.generateInclusionProof(storage, cp, i);
            assertNotNull(result.proofSteps());
            assertNull(result.proofUnavailable());
        }
    }

    @Test
    void inclusionProofUnavailableAfterDeletion() throws Exception {
        for (int i = 0; i < 3; i++) {
            AuditEntry entry = createEntry("cap-" + i);
            entry.setExpiresAt("2020-01-01T00:00:00Z");
            AuditLog.appendAudit(km, storage, entry);
        }

        Checkpoint cp = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNotNull(cp);

        // Delete expired entries.
        storage.deleteExpiredAuditEntries("2025-01-01T00:00:00Z");

        // Proof should be unavailable.
        CheckpointManager.InclusionProofResult result =
                CheckpointManager.generateInclusionProof(storage, cp, 0);
        assertNull(result.proofSteps());
        assertEquals("audit_entries_expired", result.proofUnavailable());
    }

    @Test
    void inclusionProofInvalidIndex() throws Exception {
        AuditLog.appendAudit(km, storage, createEntry("cap-1"));
        Checkpoint cp = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);

        assertThrows(IllegalArgumentException.class, () ->
                CheckpointManager.generateInclusionProof(storage, cp, 5));
    }

    @Test
    void checkpointMerkleRootConsistency() throws Exception {
        // Verify the checkpoint's Merkle root matches a fresh tree built from the same entries.
        for (int i = 0; i < 4; i++) {
            AuditLog.appendAudit(km, storage, createEntry("cap-" + i));
        }

        Checkpoint cp = CheckpointManager.createCheckpoint(km, storage, SERVICE_ID);
        assertNotNull(cp);

        // Rebuild tree from storage.
        List<AuditEntry> entries = storage.getAuditEntriesRange(1, 4);
        MerkleTree tree = new MerkleTree();
        for (AuditEntry entry : entries) {
            tree.addLeaf(HashChain.canonicalBytes(entry));
        }

        assertEquals(tree.root(), cp.getMerkleRoot());
    }

    private AuditEntry createEntry(String capability) {
        AuditEntry entry = new AuditEntry();
        entry.setTimestamp("2025-06-15T12:00:00Z");
        entry.setCapability(capability);
        entry.setTokenId("tok-test");
        entry.setRootPrincipal("user@test.com");
        entry.setInvocationId("inv-test123456");
        entry.setSuccess(true);
        return entry;
    }
}
