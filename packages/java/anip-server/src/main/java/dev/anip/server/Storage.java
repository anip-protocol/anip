package dev.anip.server;

import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.Checkpoint;
import dev.anip.core.DelegationToken;

import java.io.Closeable;
import java.util.List;

/**
 * Abstract storage interface for ANIP server components.
 * Implementations handle tokens, audit log, checkpoints, and leases.
 */
public interface Storage extends Closeable {

    // --- Tokens ---

    /**
     * Persists a delegation token.
     */
    void storeToken(DelegationToken token) throws Exception;

    /**
     * Loads a delegation token by ID. Returns null if not found.
     */
    DelegationToken loadToken(String tokenId) throws Exception;

    // --- Audit ---

    /**
     * Atomically assigns sequence_number and computes previous_hash, then appends.
     * Returns the entry with sequence_number and previous_hash set.
     */
    AuditEntry appendAuditEntry(AuditEntry entry) throws Exception;

    /**
     * Queries audit entries with optional filters.
     */
    List<AuditEntry> queryAuditEntries(AuditFilters filters) throws Exception;

    /**
     * Returns the highest sequence_number, or 0 if empty.
     */
    int getMaxAuditSequence() throws Exception;

    /**
     * Returns audit entries with sequence_number between first and last (inclusive).
     */
    List<AuditEntry> getAuditEntriesRange(int first, int last) throws Exception;

    /**
     * Updates the signature on an existing audit entry (both column and JSON data blob).
     */
    void updateAuditSignature(int seqNum, String signature) throws Exception;

    // --- Checkpoints ---

    /**
     * Persists a checkpoint with its signature.
     */
    void storeCheckpoint(Checkpoint cp, String signature) throws Exception;

    /**
     * Returns checkpoints ordered by ID, limited by count.
     */
    List<Checkpoint> listCheckpoints(int limit) throws Exception;

    /**
     * Returns a checkpoint by its ID, or null if not found.
     */
    Checkpoint getCheckpointById(String id) throws Exception;

    // --- Retention ---

    /**
     * Deletes audit entries whose expires_at is before the given ISO timestamp.
     * Returns the number of deleted entries.
     */
    int deleteExpiredAuditEntries(String now) throws Exception;

    // --- Leases ---

    /**
     * Attempts to acquire an exclusive lease. Returns true if acquired.
     */
    boolean tryAcquireExclusive(String key, String holder, int ttlSeconds) throws Exception;

    /**
     * Releases an exclusive lease if held by the given holder.
     */
    void releaseExclusive(String key, String holder) throws Exception;

    /**
     * Attempts to acquire a leader lease for a background role.
     */
    boolean tryAcquireLeader(String role, String holder, int ttlSeconds) throws Exception;

    /**
     * Releases a leader lease if held by the given holder.
     */
    void releaseLeader(String role, String holder) throws Exception;
}
