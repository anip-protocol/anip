using System.Text.Json;
using Anip.Core;
using Microsoft.Data.Sqlite;

namespace Anip.Server;

/// <summary>
/// SQLite implementation of IStorage using Microsoft.Data.Sqlite.
/// </summary>
public class SqliteStorage : IStorage
{
    private const string Schema = @"
CREATE TABLE IF NOT EXISTS delegation_tokens (
    token_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    capability TEXT,
    token_id TEXT,
    root_principal TEXT,
    invocation_id TEXT,
    client_reference_id TEXT,
    task_id TEXT,
    parent_invocation_id TEXT,
    upstream_service TEXT,
    approval_request_id TEXT,
    approval_grant_id TEXT,
    data TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    signature TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_task_id ON audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_parent_invocation_id ON audit_log(parent_invocation_id);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    signature TEXT NOT NULL
);

-- v0.23: approval requests + grants per SPEC.md §4.7 / §4.8.
CREATE TABLE IF NOT EXISTS approval_requests (
    approval_request_id TEXT PRIMARY KEY,
    capability TEXT NOT NULL,
    status TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_apreq_status ON approval_requests(status);

CREATE TABLE IF NOT EXISTS approval_grants (
    grant_id TEXT PRIMARY KEY,
    approval_request_id TEXT NOT NULL UNIQUE,
    capability TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    max_uses INTEGER NOT NULL,
    use_count INTEGER NOT NULL,
    data TEXT NOT NULL,
    FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id)
);
";

    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    private readonly SqliteConnection _connection;
    private readonly object _lock = new();
    private readonly Dictionary<string, LeaseEntry> _exclusiveLeases = new();

    /// <summary>
    /// Opens or creates a SQLite database at the given path.
    /// Use ":memory:" for in-memory storage.
    /// </summary>
    public SqliteStorage(string dbPath)
    {
        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = dbPath,
            Mode = dbPath == ":memory:" ? SqliteOpenMode.Memory : SqliteOpenMode.ReadWriteCreate
        }.ToString();

        _connection = new SqliteConnection(connectionString);
        _connection.Open();

        // Enable WAL mode for better concurrent read performance.
        using var walCmd = _connection.CreateCommand();
        walCmd.CommandText = "PRAGMA journal_mode=WAL";
        walCmd.ExecuteNonQuery();

        // Create schema.
        using var schemaCmd = _connection.CreateCommand();
        schemaCmd.CommandText = Schema;
        schemaCmd.ExecuteNonQuery();

        // v0.23 idempotent column migrations for audit_log (existing DBs).
        AddColumnIfMissing("audit_log", "approval_request_id", "TEXT");
        AddColumnIfMissing("audit_log", "approval_grant_id", "TEXT");
    }

    private void AddColumnIfMissing(string table, string column, string sqlType)
    {
        using var pragmaCmd = _connection.CreateCommand();
        pragmaCmd.CommandText = $"PRAGMA table_info({table})";
        using (var reader = pragmaCmd.ExecuteReader())
        {
            while (reader.Read())
            {
                if (reader.GetString(1) == column)
                {
                    return;
                }
            }
        }
        using var alter = _connection.CreateCommand();
        alter.CommandText = $"ALTER TABLE {table} ADD COLUMN {column} {sqlType}";
        alter.ExecuteNonQuery();
    }

    public void Dispose()
    {
        _connection.Dispose();
    }

    // --- Tokens ---

    public void StoreToken(DelegationToken token)
    {
        var data = JsonSerializer.Serialize(token, s_serializerOptions);

        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "INSERT OR REPLACE INTO delegation_tokens (token_id, data) VALUES ($tokenId, $data)";
            cmd.Parameters.AddWithValue("$tokenId", token.TokenId);
            cmd.Parameters.AddWithValue("$data", data);
            cmd.ExecuteNonQuery();
        }
    }

    public DelegationToken? LoadToken(string tokenId)
    {
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT data FROM delegation_tokens WHERE token_id = $tokenId";
            cmd.Parameters.AddWithValue("$tokenId", tokenId);

            var result = cmd.ExecuteScalar();
            if (result == null || result == DBNull.Value)
                return null;

            return JsonSerializer.Deserialize<DelegationToken>((string)result, s_serializerOptions);
        }
    }

    // --- Audit ---

    public AuditEntry AppendAuditEntry(AuditEntry entry)
    {
        lock (_lock)
        {
            using var transaction = _connection.BeginTransaction();

            try
            {
                // Get the last entry for hash chaining.
                string prevHash;
                using (var lastCmd = _connection.CreateCommand())
                {
                    lastCmd.Transaction = transaction;
                    lastCmd.CommandText = "SELECT data, previous_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1";
                    using var reader = lastCmd.ExecuteReader();

                    if (reader.Read())
                    {
                        var lastData = reader.GetString(0);
                        var lastEntry = JsonSerializer.Deserialize<AuditEntry>(lastData, s_serializerOptions)!;
                        prevHash = HashChain.ComputeEntryHash(lastEntry);
                    }
                    else
                    {
                        // First entry: sentinel hash.
                        prevHash = "sha256:0";
                    }
                }

                entry.PreviousHash = prevHash;

                var data = JsonSerializer.Serialize(entry, s_serializerOptions);

                using var insertCmd = _connection.CreateCommand();
                insertCmd.Transaction = transaction;
                insertCmd.CommandText = @"
                    INSERT INTO audit_log (timestamp, capability, token_id, root_principal,
                        invocation_id, client_reference_id, task_id, parent_invocation_id,
                        upstream_service, approval_request_id, approval_grant_id,
                        data, previous_hash, signature)
                    VALUES ($timestamp, $capability, $tokenId, $rootPrincipal,
                        $invocationId, $clientReferenceId, $taskId, $parentInvocationId,
                        $upstreamService, $approvalRequestId, $approvalGrantId,
                        $data, $previousHash, $signature);
                    SELECT last_insert_rowid();";
                insertCmd.Parameters.AddWithValue("$timestamp", (object?)entry.Timestamp ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$capability", (object?)entry.Capability ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$tokenId", (object?)entry.TokenId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$rootPrincipal", (object?)entry.RootPrincipal ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$invocationId", (object?)entry.InvocationId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$clientReferenceId", (object?)entry.ClientReferenceId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$taskId", (object?)entry.TaskId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$parentInvocationId", (object?)entry.ParentInvocationId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$upstreamService", (object?)entry.UpstreamService ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$approvalRequestId", (object?)entry.ApprovalRequestId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$approvalGrantId", (object?)entry.ApprovalGrantId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("$data", data);
                insertCmd.Parameters.AddWithValue("$previousHash", prevHash);
                insertCmd.Parameters.AddWithValue("$signature", (object?)entry.Signature ?? DBNull.Value);

                var seqNum = Convert.ToInt32(insertCmd.ExecuteScalar());

                transaction.Commit();

                entry.SequenceNumber = seqNum;

                // Re-marshal with the correct sequence_number and update in the database.
                data = JsonSerializer.Serialize(entry, s_serializerOptions);
                using var updateCmd = _connection.CreateCommand();
                updateCmd.CommandText = "UPDATE audit_log SET data = $data WHERE sequence_number = $seqNum";
                updateCmd.Parameters.AddWithValue("$data", data);
                updateCmd.Parameters.AddWithValue("$seqNum", seqNum);
                updateCmd.ExecuteNonQuery();

                return entry;
            }
            catch
            {
                transaction.Rollback();
                throw;
            }
        }
    }

    public List<AuditEntry> QueryAuditEntries(AuditFilters filters)
    {
        lock (_lock)
        {
            var query = "SELECT data FROM audit_log WHERE 1=1";
            var parameters = new List<SqliteParameter>();

            if (!string.IsNullOrEmpty(filters.RootPrincipal))
            {
                query += " AND root_principal = $rootPrincipal";
                parameters.Add(new SqliteParameter("$rootPrincipal", filters.RootPrincipal));
            }
            if (!string.IsNullOrEmpty(filters.Capability))
            {
                query += " AND capability = $capability";
                parameters.Add(new SqliteParameter("$capability", filters.Capability));
            }
            if (!string.IsNullOrEmpty(filters.Since))
            {
                query += " AND timestamp >= $since";
                parameters.Add(new SqliteParameter("$since", filters.Since));
            }
            if (!string.IsNullOrEmpty(filters.InvocationId))
            {
                query += " AND invocation_id = $invocationId";
                parameters.Add(new SqliteParameter("$invocationId", filters.InvocationId));
            }
            if (!string.IsNullOrEmpty(filters.ClientReferenceId))
            {
                query += " AND client_reference_id = $clientReferenceId";
                parameters.Add(new SqliteParameter("$clientReferenceId", filters.ClientReferenceId));
            }
            if (!string.IsNullOrEmpty(filters.TaskId))
            {
                query += " AND task_id = $taskId";
                parameters.Add(new SqliteParameter("$taskId", filters.TaskId));
            }
            if (!string.IsNullOrEmpty(filters.ParentInvocationId))
            {
                query += " AND parent_invocation_id = $parentInvocationId";
                parameters.Add(new SqliteParameter("$parentInvocationId", filters.ParentInvocationId));
            }

            query += " ORDER BY sequence_number DESC";

            var limit = filters.Limit > 0 ? filters.Limit : 50;
            query += " LIMIT $limit";
            parameters.Add(new SqliteParameter("$limit", limit));

            using var cmd = _connection.CreateCommand();
            cmd.CommandText = query;
            cmd.Parameters.AddRange(parameters.ToArray());

            var entries = new List<AuditEntry>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var data = reader.GetString(0);
                var entry = JsonSerializer.Deserialize<AuditEntry>(data, s_serializerOptions)!;
                entries.Add(entry);
            }

            return entries;
        }
    }

    public int GetMaxAuditSequence()
    {
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT MAX(sequence_number) FROM audit_log";

            var result = cmd.ExecuteScalar();
            if (result == null || result == DBNull.Value)
                return 0;

            return Convert.ToInt32(result);
        }
    }

    public List<AuditEntry> GetAuditEntriesRange(int first, int last)
    {
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT data FROM audit_log WHERE sequence_number BETWEEN $first AND $last ORDER BY sequence_number ASC";
            cmd.Parameters.AddWithValue("$first", first);
            cmd.Parameters.AddWithValue("$last", last);

            var entries = new List<AuditEntry>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var data = reader.GetString(0);
                var entry = JsonSerializer.Deserialize<AuditEntry>(data, s_serializerOptions)!;
                entries.Add(entry);
            }

            return entries;
        }
    }

    public void UpdateAuditSignature(int seqNum, string signature)
    {
        lock (_lock)
        {
            // Update the signature column.
            using var updateSigCmd = _connection.CreateCommand();
            updateSigCmd.CommandText = "UPDATE audit_log SET signature = $signature WHERE sequence_number = $seqNum";
            updateSigCmd.Parameters.AddWithValue("$signature", signature);
            updateSigCmd.Parameters.AddWithValue("$seqNum", seqNum);
            updateSigCmd.ExecuteNonQuery();

            // Also update the signature in the JSON data blob.
            using var selectCmd = _connection.CreateCommand();
            selectCmd.CommandText = "SELECT data FROM audit_log WHERE sequence_number = $seqNum";
            selectCmd.Parameters.AddWithValue("$seqNum", seqNum);

            var data = (string)selectCmd.ExecuteScalar()!;
            var entry = JsonSerializer.Deserialize<AuditEntry>(data, s_serializerOptions)!;
            entry.Signature = signature;

            var updated = JsonSerializer.Serialize(entry, s_serializerOptions);
            using var updateDataCmd = _connection.CreateCommand();
            updateDataCmd.CommandText = "UPDATE audit_log SET data = $data WHERE sequence_number = $seqNum";
            updateDataCmd.Parameters.AddWithValue("$data", updated);
            updateDataCmd.Parameters.AddWithValue("$seqNum", seqNum);
            updateDataCmd.ExecuteNonQuery();
        }
    }

    // --- Checkpoints ---

    public void StoreCheckpoint(Checkpoint checkpoint, string signature)
    {
        var data = JsonSerializer.Serialize(checkpoint, s_serializerOptions);

        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "INSERT INTO checkpoints (checkpoint_id, data, signature) VALUES ($checkpointId, $data, $signature)";
            cmd.Parameters.AddWithValue("$checkpointId", checkpoint.CheckpointId);
            cmd.Parameters.AddWithValue("$data", data);
            cmd.Parameters.AddWithValue("$signature", signature);
            cmd.ExecuteNonQuery();
        }
    }

    public List<Checkpoint> ListCheckpoints(int limit)
    {
        if (limit <= 0)
            limit = 10;

        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT data FROM checkpoints ORDER BY rowid ASC LIMIT $limit";
            cmd.Parameters.AddWithValue("$limit", limit);

            var checkpoints = new List<Checkpoint>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var data = reader.GetString(0);
                var cp = JsonSerializer.Deserialize<Checkpoint>(data, s_serializerOptions)!;
                checkpoints.Add(cp);
            }

            return checkpoints;
        }
    }

    public Checkpoint? GetCheckpointById(string id)
    {
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT data FROM checkpoints WHERE checkpoint_id = $checkpointId";
            cmd.Parameters.AddWithValue("$checkpointId", id);

            var result = cmd.ExecuteScalar();
            if (result == null || result == DBNull.Value)
                return null;

            return JsonSerializer.Deserialize<Checkpoint>((string)result, s_serializerOptions);
        }
    }

    // --- Retention ---

    public int DeleteExpiredAuditEntries(string now)
    {
        lock (_lock)
        {
            // Find expired entries by scanning the data blobs.
            var toDelete = new List<int>();

            using (var selectCmd = _connection.CreateCommand())
            {
                selectCmd.CommandText = "SELECT sequence_number, data FROM audit_log";
                using var reader = selectCmd.ExecuteReader();
                while (reader.Read())
                {
                    var seqNum = reader.GetInt32(0);
                    var data = reader.GetString(1);
                    try
                    {
                        var entry = JsonSerializer.Deserialize<AuditEntry>(data, s_serializerOptions)!;
                        if (!string.IsNullOrEmpty(entry.ExpiresAt) && string.Compare(entry.ExpiresAt, now, StringComparison.Ordinal) < 0)
                        {
                            toDelete.Add(seqNum);
                        }
                    }
                    catch
                    {
                        // Skip entries that fail to deserialize.
                    }
                }
            }

            foreach (var seqNum in toDelete)
            {
                using var deleteCmd = _connection.CreateCommand();
                deleteCmd.CommandText = "DELETE FROM audit_log WHERE sequence_number = $seqNum";
                deleteCmd.Parameters.AddWithValue("$seqNum", seqNum);
                deleteCmd.ExecuteNonQuery();
            }

            return toDelete.Count;
        }
    }

    // --- Leases (in-memory, single-process) ---

    public bool TryAcquireExclusive(string key, string holder, int ttlSeconds)
    {
        lock (_lock)
        {
            var now = DateTime.UtcNow;
            if (_exclusiveLeases.TryGetValue(key, out var existing))
            {
                if (existing.ExpiresAt > now && existing.Holder != holder)
                    return false;
            }

            _exclusiveLeases[key] = new LeaseEntry
            {
                Holder = holder,
                ExpiresAt = now.AddSeconds(ttlSeconds)
            };
            return true;
        }
    }

    public void ReleaseExclusive(string key, string holder)
    {
        lock (_lock)
        {
            if (_exclusiveLeases.TryGetValue(key, out var existing) && existing.Holder == holder)
            {
                _exclusiveLeases.Remove(key);
            }
        }
    }

    public bool TryAcquireLeader(string role, string holder, int ttlSeconds)
    {
        return TryAcquireExclusive("leader:" + role, holder, ttlSeconds);
    }

    public void ReleaseLeader(string role, string holder)
    {
        ReleaseExclusive("leader:" + role, holder);
    }

    // --- v0.23: ApprovalRequest + ApprovalGrant ---

    public void StoreApprovalRequest(ApprovalRequest request)
    {
        var data = JsonSerializer.Serialize(request, s_serializerOptions);
        lock (_lock)
        {
            // Idempotency: same content is a no-op; conflicting content throws.
            using (var selectCmd = _connection.CreateCommand())
            {
                selectCmd.CommandText = "SELECT data FROM approval_requests WHERE approval_request_id = $id";
                selectCmd.Parameters.AddWithValue("$id", request.ApprovalRequestId);
                var existing = selectCmd.ExecuteScalar();
                if (existing != null && existing != DBNull.Value)
                {
                    if ((string)existing == data) return;
                    throw new InvalidOperationException(
                        $"approval_request_id {request.ApprovalRequestId} already stored with different content");
                }
            }

            using var insertCmd = _connection.CreateCommand();
            insertCmd.CommandText = @"
                INSERT INTO approval_requests (approval_request_id, capability, status, expires_at, data)
                VALUES ($id, $capability, $status, $expiresAt, $data)";
            insertCmd.Parameters.AddWithValue("$id", request.ApprovalRequestId);
            insertCmd.Parameters.AddWithValue("$capability", request.Capability);
            insertCmd.Parameters.AddWithValue("$status", request.Status);
            insertCmd.Parameters.AddWithValue("$expiresAt", request.ExpiresAt);
            insertCmd.Parameters.AddWithValue("$data", data);
            insertCmd.ExecuteNonQuery();
        }
    }

    public ApprovalRequest? GetApprovalRequest(string approvalRequestId)
    {
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT data FROM approval_requests WHERE approval_request_id = $id";
            cmd.Parameters.AddWithValue("$id", approvalRequestId);
            var result = cmd.ExecuteScalar();
            if (result == null || result == DBNull.Value) return null;
            return JsonSerializer.Deserialize<ApprovalRequest>((string)result, s_serializerOptions);
        }
    }

    public ApprovalDecisionResult ApproveRequestAndStoreGrant(
        string approvalRequestId,
        ApprovalGrant grant,
        IDictionary<string, object?> approver,
        string decidedAtIso,
        string nowIso)
    {
        lock (_lock)
        {
            // SQLite "BEGIN IMMEDIATE" acquires a RESERVED lock immediately,
            // ensuring serial txns when multiple writers race for the same
            // approval request id. Matches Java/Go semantics for atomicity.
            using var transaction = _connection.BeginTransaction(System.Data.IsolationLevel.Serializable);
            try
            {
                ApprovalRequest existing;
                using (var selectCmd = _connection.CreateCommand())
                {
                    selectCmd.Transaction = transaction;
                    selectCmd.CommandText =
                        "SELECT data, status, expires_at FROM approval_requests WHERE approval_request_id = $id";
                    selectCmd.Parameters.AddWithValue("$id", approvalRequestId);
                    using var reader = selectCmd.ExecuteReader();
                    if (!reader.Read())
                    {
                        transaction.Rollback();
                        return ApprovalDecisionResult.Failure("approval_request_not_found");
                    }
                    var data = reader.GetString(0);
                    var status = reader.GetString(1);
                    var expiresAt = reader.IsDBNull(2) ? null : reader.GetString(2);
                    existing = JsonSerializer.Deserialize<ApprovalRequest>(data, s_serializerOptions)!;
                    if (status != ApprovalRequest.StatusPending)
                    {
                        transaction.Rollback();
                        return ApprovalDecisionResult.Failure("approval_request_already_decided");
                    }
                    if (!string.IsNullOrEmpty(expiresAt) &&
                        string.CompareOrdinal(expiresAt, nowIso) <= 0)
                    {
                        transaction.Rollback();
                        return ApprovalDecisionResult.Failure("approval_request_expired");
                    }
                }

                existing.Status = ApprovalRequest.StatusApproved;
                existing.Approver = approver.ToDictionary(kv => kv.Key, kv => kv.Value!);
                existing.DecidedAt = decidedAtIso;
                var updatedReq = JsonSerializer.Serialize(existing, s_serializerOptions);

                using (var updateCmd = _connection.CreateCommand())
                {
                    updateCmd.Transaction = transaction;
                    updateCmd.CommandText = @"
                        UPDATE approval_requests
                        SET status = 'approved', data = $data
                        WHERE approval_request_id = $id AND status = 'pending'";
                    updateCmd.Parameters.AddWithValue("$data", updatedReq);
                    updateCmd.Parameters.AddWithValue("$id", approvalRequestId);
                    if (updateCmd.ExecuteNonQuery() != 1)
                    {
                        transaction.Rollback();
                        return ApprovalDecisionResult.Failure("approval_request_already_decided");
                    }
                }

                var grantJson = JsonSerializer.Serialize(grant, s_serializerOptions);
                using (var insertCmd = _connection.CreateCommand())
                {
                    insertCmd.Transaction = transaction;
                    insertCmd.CommandText = @"
                        INSERT INTO approval_grants (grant_id, approval_request_id, capability,
                            expires_at, max_uses, use_count, data)
                        VALUES ($gid, $arid, $cap, $expires, $maxUses, $useCount, $data)";
                    insertCmd.Parameters.AddWithValue("$gid", grant.GrantId);
                    insertCmd.Parameters.AddWithValue("$arid", grant.ApprovalRequestId);
                    insertCmd.Parameters.AddWithValue("$cap", grant.Capability);
                    insertCmd.Parameters.AddWithValue("$expires", grant.ExpiresAt);
                    insertCmd.Parameters.AddWithValue("$maxUses", grant.MaxUses);
                    insertCmd.Parameters.AddWithValue("$useCount", grant.UseCount);
                    insertCmd.Parameters.AddWithValue("$data", grantJson);
                    insertCmd.ExecuteNonQuery();
                }

                transaction.Commit();
                return ApprovalDecisionResult.Success(grant);
            }
            catch
            {
                try { transaction.Rollback(); } catch { /* ignore */ }
                throw;
            }
        }
    }

    public void StoreGrant(ApprovalGrant grant)
    {
        var data = JsonSerializer.Serialize(grant, s_serializerOptions);
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = @"
                INSERT INTO approval_grants (grant_id, approval_request_id, capability,
                    expires_at, max_uses, use_count, data)
                VALUES ($gid, $arid, $cap, $expires, $maxUses, $useCount, $data)";
            cmd.Parameters.AddWithValue("$gid", grant.GrantId);
            cmd.Parameters.AddWithValue("$arid", grant.ApprovalRequestId);
            cmd.Parameters.AddWithValue("$cap", grant.Capability);
            cmd.Parameters.AddWithValue("$expires", grant.ExpiresAt);
            cmd.Parameters.AddWithValue("$maxUses", grant.MaxUses);
            cmd.Parameters.AddWithValue("$useCount", grant.UseCount);
            cmd.Parameters.AddWithValue("$data", data);
            cmd.ExecuteNonQuery();
        }
    }

    public ApprovalGrant? GetGrant(string grantId)
    {
        lock (_lock)
        {
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = "SELECT data FROM approval_grants WHERE grant_id = $gid";
            cmd.Parameters.AddWithValue("$gid", grantId);
            var result = cmd.ExecuteScalar();
            if (result == null || result == DBNull.Value) return null;
            return JsonSerializer.Deserialize<ApprovalGrant>((string)result, s_serializerOptions);
        }
    }

    public GrantReservationResult TryReserveGrant(string grantId, string nowIso)
    {
        lock (_lock)
        {
            int affected;
            using (var update = _connection.CreateCommand())
            {
                update.CommandText = @"
                    UPDATE approval_grants
                    SET use_count = use_count + 1
                    WHERE grant_id = $gid AND use_count < max_uses AND expires_at > $now";
                update.Parameters.AddWithValue("$gid", grantId);
                update.Parameters.AddWithValue("$now", nowIso);
                affected = update.ExecuteNonQuery();
            }

            if (affected == 1)
            {
                ApprovalGrant grant;
                int newUseCount;
                using (var sel = _connection.CreateCommand())
                {
                    sel.CommandText = "SELECT data, use_count FROM approval_grants WHERE grant_id = $gid";
                    sel.Parameters.AddWithValue("$gid", grantId);
                    using var reader = sel.ExecuteReader();
                    if (!reader.Read())
                    {
                        return GrantReservationResult.Failure("grant_not_found");
                    }
                    grant = JsonSerializer.Deserialize<ApprovalGrant>(reader.GetString(0), s_serializerOptions)!;
                    newUseCount = reader.GetInt32(1);
                }
                grant.UseCount = newUseCount;
                using (var write = _connection.CreateCommand())
                {
                    write.CommandText = "UPDATE approval_grants SET data = $data WHERE grant_id = $gid";
                    write.Parameters.AddWithValue("$data", JsonSerializer.Serialize(grant, s_serializerOptions));
                    write.Parameters.AddWithValue("$gid", grantId);
                    write.ExecuteNonQuery();
                }
                return GrantReservationResult.Success(grant);
            }

            // 0 rows → disambiguate by re-fetching.
            using (var probe = _connection.CreateCommand())
            {
                probe.CommandText = "SELECT use_count, max_uses, expires_at FROM approval_grants WHERE grant_id = $gid";
                probe.Parameters.AddWithValue("$gid", grantId);
                using var reader = probe.ExecuteReader();
                if (!reader.Read())
                {
                    return GrantReservationResult.Failure("grant_not_found");
                }
                var useCount = reader.GetInt32(0);
                var maxUses = reader.GetInt32(1);
                var expiresAt = reader.IsDBNull(2) ? null : reader.GetString(2);
                if (!string.IsNullOrEmpty(expiresAt) &&
                    string.CompareOrdinal(expiresAt, nowIso) <= 0)
                {
                    return GrantReservationResult.Failure("grant_expired");
                }
                if (useCount >= maxUses)
                {
                    return GrantReservationResult.Failure("grant_consumed");
                }
                return GrantReservationResult.Failure("grant_not_found");
            }
        }
    }

    private class LeaseEntry
    {
        public string Holder { get; set; } = "";
        public DateTime ExpiresAt { get; set; }
    }
}
