using Anip.Core;

namespace Anip.Server;

/// <summary>
/// Abstract storage interface for ANIP server components.
/// </summary>
public interface IStorage : IDisposable
{
    // Tokens
    void StoreToken(DelegationToken token);
    DelegationToken? LoadToken(string tokenId);

    // Audit
    AuditEntry AppendAuditEntry(AuditEntry entry);
    List<AuditEntry> QueryAuditEntries(AuditFilters filters);
    int GetMaxAuditSequence();
    List<AuditEntry> GetAuditEntriesRange(int first, int last);
    void UpdateAuditSignature(int seqNum, string signature);

    // Checkpoints
    void StoreCheckpoint(Checkpoint checkpoint, string signature);
    List<Checkpoint> ListCheckpoints(int limit);
    Checkpoint? GetCheckpointById(string id);

    // Retention
    int DeleteExpiredAuditEntries(string now);

    // Leases (for horizontal scaling coordination)
    bool TryAcquireExclusive(string key, string holder, int ttlSeconds);
    void ReleaseExclusive(string key, string holder);
    bool TryAcquireLeader(string role, string holder, int ttlSeconds);
    void ReleaseLeader(string role, string holder);

    // --- v0.23: ApprovalRequest + ApprovalGrant persistence ---

    /// <summary>
    /// Persists an ApprovalRequest. Idempotent on approval_request_id when
    /// the stored content is identical; throws when an existing row has
    /// different content. v0.23. SPEC.md §4.7.
    /// </summary>
    void StoreApprovalRequest(ApprovalRequest request);

    /// <summary>
    /// Loads an ApprovalRequest by ID. Returns null if not found.
    /// </summary>
    ApprovalRequest? GetApprovalRequest(string approvalRequestId);

    /// <summary>
    /// Atomically transitions a pending ApprovalRequest to "approved" and
    /// persists the corresponding ApprovalGrant in a single transaction.
    /// SPEC.md §4.9 (Decision 0.9a).
    /// </summary>
    ApprovalDecisionResult ApproveRequestAndStoreGrant(
        string approvalRequestId,
        ApprovalGrant grant,
        IDictionary<string, object?> approver,
        string decidedAtIso,
        string nowIso);

    /// <summary>
    /// Internal/test-only direct insert of an ApprovalGrant.
    /// </summary>
    void StoreGrant(ApprovalGrant grant);

    /// <summary>
    /// Loads an ApprovalGrant by ID. Returns null if not found.
    /// </summary>
    ApprovalGrant? GetGrant(string grantId);

    /// <summary>
    /// Atomically reserves one use of an unexpired grant by incrementing
    /// use_count via a conditional UPDATE: WHERE grant_id=? AND
    /// use_count &lt; max_uses AND expires_at &gt; now. SPEC.md §4.8 Phase B.
    /// On 0 affected rows the implementation re-reads the grant to
    /// disambiguate grant_not_found / grant_expired / grant_consumed.
    /// </summary>
    GrantReservationResult TryReserveGrant(string grantId, string nowIso);
}
