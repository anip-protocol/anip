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
}
