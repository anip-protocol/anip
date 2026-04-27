package dev.anip.server;

import dev.anip.core.ApprovalGrant;
import dev.anip.core.ApprovalRequest;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.Checkpoint;
import dev.anip.core.DelegationToken;

import java.io.Closeable;
import java.util.List;
import java.util.Map;
import java.util.Optional;

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

    // --- v0.23: ApprovalRequest + ApprovalGrant persistence ---

    /**
     * Persists an ApprovalRequest. Idempotent on approval_request_id when the
     * stored content matches; raises an exception when an existing row has
     * different content. v0.23. See SPEC.md §4.7.
     */
    void storeApprovalRequest(ApprovalRequest req) throws Exception;

    /**
     * Loads an ApprovalRequest by ID. Returns Optional.empty() if not found.
     */
    Optional<ApprovalRequest> getApprovalRequest(String approvalRequestId) throws Exception;

    /**
     * Atomically transitions a pending ApprovalRequest to "approved" and
     * persists the corresponding ApprovalGrant in a single transaction.
     * v0.23. SPEC.md §4.9 (Decision 0.9a).
     *
     * <p>Failure reasons (non-ok result):
     * <ul>
     *   <li>{@code approval_request_not_found} — no row matches the id.</li>
     *   <li>{@code approval_request_expired} — request expired before this txn.</li>
     *   <li>{@code approval_request_already_decided} — status was not "pending".</li>
     * </ul></p>
     *
     * @param approvalRequestId the request id
     * @param grant             the grant to persist (must be fully signed)
     * @param approver          approver principal map
     * @param decidedAtIso      timestamp recorded on the request
     * @param nowIso            current time used for the expiry CAS
     */
    ApprovalDecisionResult approveRequestAndStoreGrant(String approvalRequestId,
                                                       ApprovalGrant grant,
                                                       Map<String, Object> approver,
                                                       String decidedAtIso,
                                                       String nowIso) throws Exception;

    /**
     * Internal/test-only direct insert of an ApprovalGrant.
     */
    void storeGrant(ApprovalGrant grant) throws Exception;

    /**
     * Loads an ApprovalGrant by ID. Returns Optional.empty() if not found.
     */
    Optional<ApprovalGrant> getGrant(String grantId) throws Exception;

    /**
     * Atomically reserves one use of an unexpired grant by incrementing
     * use_count via a conditional UPDATE: WHERE grant_id=? AND
     * use_count &lt; max_uses AND expires_at &gt; now. v0.23. SPEC.md §4.8 Phase B.
     *
     * <p>On 0 affected rows the implementation re-reads the grant to
     * disambiguate {@code grant_not_found}, {@code grant_expired},
     * {@code grant_consumed}.</p>
     */
    GrantReservationResult tryReserveGrant(String grantId, String nowIso) throws Exception;
}
