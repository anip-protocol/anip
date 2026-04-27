using System.Text.Json;
using Anip.Core;
using Npgsql;

namespace Anip.Server;

/// <summary>
/// PostgreSQL implementation of IStorage using Npgsql.
/// Uses connection pooling (Npgsql default) and row-level locking for concurrency.
/// </summary>
public class NpgsqlStorage : IStorage
{
    private const string Schema = @"
CREATE TABLE IF NOT EXISTS delegation_tokens (
    token_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    sequence_number BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS audit_append_head (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_sequence_number BIGINT NOT NULL DEFAULT 0,
    last_hash TEXT NOT NULL DEFAULT ''
);
INSERT INTO audit_append_head (id, last_sequence_number, last_hash)
VALUES (1, 0, '') ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    signature TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS exclusive_leases (
    key TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_leases (
    role TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
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

    private readonly NpgsqlDataSource _dataSource;

    /// <summary>
    /// Creates a new PostgreSQL-backed storage.
    /// Accepts a PostgreSQL connection string or DSN (postgres://... or postgresql://...).
    /// Creates all required tables on initialization.
    /// </summary>
    public NpgsqlStorage(string connectionString)
    {
        var connStr = NormalizeConnectionString(connectionString);
        _dataSource = NpgsqlDataSource.Create(connStr);

        // Verify connectivity and create schema.
        using var conn = _dataSource.OpenConnection();
        using (var cmd = conn.CreateCommand())
        {
            cmd.CommandText = Schema;
            cmd.ExecuteNonQuery();
        }

        // v0.23 idempotent column migrations for audit_log (existing DBs).
        using (var alter = conn.CreateCommand())
        {
            alter.CommandText = @"
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS approval_request_id TEXT;
                ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS approval_grant_id TEXT;";
            alter.ExecuteNonQuery();
        }
    }

    public void Dispose()
    {
        _dataSource.Dispose();
    }

    // --- Tokens ---

    public void StoreToken(DelegationToken token)
    {
        var data = JsonSerializer.Serialize(token, s_serializerOptions);

        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO delegation_tokens (token_id, data) VALUES (@tokenId, @data)
            ON CONFLICT (token_id) DO UPDATE SET data = EXCLUDED.data";
        cmd.Parameters.AddWithValue("tokenId", token.TokenId);
        cmd.Parameters.AddWithValue("data", data);
        cmd.ExecuteNonQuery();
    }

    public DelegationToken? LoadToken(string tokenId)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data FROM delegation_tokens WHERE token_id = @tokenId";
        cmd.Parameters.AddWithValue("tokenId", tokenId);

        var result = cmd.ExecuteScalar();
        if (result == null || result == DBNull.Value)
            return null;

        return JsonSerializer.Deserialize<DelegationToken>((string)result, s_serializerOptions);
    }

    // --- Audit ---

    public AuditEntry AppendAuditEntry(AuditEntry entry)
    {
        using var conn = _dataSource.OpenConnection();
        using var transaction = conn.BeginTransaction();

        try
        {
            // Lock the append head row and get the current state.
            long lastSeqNum;
            string lastHash;
            using (var headCmd = conn.CreateCommand())
            {
                headCmd.Transaction = transaction;
                headCmd.CommandText = "SELECT last_sequence_number, last_hash FROM audit_append_head WHERE id = 1 FOR UPDATE";
                using var reader = headCmd.ExecuteReader();
                if (!reader.Read())
                    throw new InvalidOperationException("audit_append_head row not found");

                lastSeqNum = reader.GetInt64(0);
                lastHash = reader.GetString(1);
            }

            // Compute previous_hash.
            string prevHash;
            if (lastSeqNum == 0)
            {
                // First entry: use the sentinel hash.
                prevHash = "sha256:0";
            }
            else
            {
                // Get the last entry's data to compute its hash.
                using var lastCmd = conn.CreateCommand();
                lastCmd.Transaction = transaction;
                lastCmd.CommandText = "SELECT data FROM audit_log WHERE sequence_number = @seqNum";
                lastCmd.Parameters.AddWithValue("seqNum", lastSeqNum);

                var lastData = (string)lastCmd.ExecuteScalar()!;
                var lastEntry = JsonSerializer.Deserialize<AuditEntry>(lastData, s_serializerOptions)!;
                prevHash = HashChain.ComputeEntryHash(lastEntry);
            }

            entry.PreviousHash = prevHash;

            // Insert the audit entry — sequence_number is auto-generated.
            var data = JsonSerializer.Serialize(entry, s_serializerOptions);

            long newSeqNum;
            using (var insertCmd = conn.CreateCommand())
            {
                insertCmd.Transaction = transaction;
                insertCmd.CommandText = @"
                    INSERT INTO audit_log (timestamp, capability, token_id, root_principal,
                        invocation_id, client_reference_id, task_id, parent_invocation_id,
                        upstream_service, approval_request_id, approval_grant_id,
                        data, previous_hash, signature)
                    VALUES (@timestamp, @capability, @tokenId, @rootPrincipal,
                        @invocationId, @clientReferenceId, @taskId, @parentInvocationId,
                        @upstreamService, @approvalRequestId, @approvalGrantId,
                        @data, @previousHash, @signature)
                    RETURNING sequence_number";
                insertCmd.Parameters.AddWithValue("timestamp", (object?)entry.Timestamp ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("capability", (object?)entry.Capability ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("tokenId", (object?)entry.TokenId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("rootPrincipal", (object?)entry.RootPrincipal ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("invocationId", (object?)entry.InvocationId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("clientReferenceId", (object?)entry.ClientReferenceId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("taskId", (object?)entry.TaskId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("parentInvocationId", (object?)entry.ParentInvocationId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("upstreamService", (object?)entry.UpstreamService ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("approvalRequestId", (object?)entry.ApprovalRequestId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("approvalGrantId", (object?)entry.ApprovalGrantId ?? DBNull.Value);
                insertCmd.Parameters.AddWithValue("data", data);
                insertCmd.Parameters.AddWithValue("previousHash", prevHash);
                insertCmd.Parameters.AddWithValue("signature", (object?)entry.Signature ?? DBNull.Value);

                newSeqNum = (long)insertCmd.ExecuteScalar()!;
            }

            entry.SequenceNumber = (int)newSeqNum;

            // Re-serialize with the correct sequence_number and update the data column.
            data = JsonSerializer.Serialize(entry, s_serializerOptions);
            using (var updateDataCmd = conn.CreateCommand())
            {
                updateDataCmd.Transaction = transaction;
                updateDataCmd.CommandText = "UPDATE audit_log SET data = @data WHERE sequence_number = @seqNum";
                updateDataCmd.Parameters.AddWithValue("data", data);
                updateDataCmd.Parameters.AddWithValue("seqNum", newSeqNum);
                updateDataCmd.ExecuteNonQuery();
            }

            // Compute hash of the newly inserted entry for the append head.
            var newHash = HashChain.ComputeEntryHash(entry);

            // Update the append head.
            using (var updateHeadCmd = conn.CreateCommand())
            {
                updateHeadCmd.Transaction = transaction;
                updateHeadCmd.CommandText = "UPDATE audit_append_head SET last_sequence_number = @seqNum, last_hash = @hash WHERE id = 1";
                updateHeadCmd.Parameters.AddWithValue("seqNum", newSeqNum);
                updateHeadCmd.Parameters.AddWithValue("hash", newHash);
                updateHeadCmd.ExecuteNonQuery();
            }

            transaction.Commit();
            return entry;
        }
        catch
        {
            transaction.Rollback();
            throw;
        }
    }

    public List<AuditEntry> QueryAuditEntries(AuditFilters filters)
    {
        using var conn = _dataSource.OpenConnection();

        var query = "SELECT data FROM audit_log WHERE 1=1";
        var parameters = new List<NpgsqlParameter>();
        int argIdx = 1;

        if (!string.IsNullOrEmpty(filters.RootPrincipal))
        {
            query += $" AND root_principal = @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.RootPrincipal));
            argIdx++;
        }
        if (!string.IsNullOrEmpty(filters.Capability))
        {
            query += $" AND capability = @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.Capability));
            argIdx++;
        }
        if (!string.IsNullOrEmpty(filters.Since))
        {
            query += $" AND timestamp >= @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.Since));
            argIdx++;
        }
        if (!string.IsNullOrEmpty(filters.InvocationId))
        {
            query += $" AND invocation_id = @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.InvocationId));
            argIdx++;
        }
        if (!string.IsNullOrEmpty(filters.ClientReferenceId))
        {
            query += $" AND client_reference_id = @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.ClientReferenceId));
            argIdx++;
        }
        if (!string.IsNullOrEmpty(filters.TaskId))
        {
            query += $" AND task_id = @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.TaskId));
            argIdx++;
        }
        if (!string.IsNullOrEmpty(filters.ParentInvocationId))
        {
            query += $" AND parent_invocation_id = @p{argIdx}";
            parameters.Add(new NpgsqlParameter($"p{argIdx}", filters.ParentInvocationId));
            argIdx++;
        }

        query += " ORDER BY sequence_number DESC";

        var limit = filters.Limit > 0 ? filters.Limit : 50;
        query += $" LIMIT @p{argIdx}";
        parameters.Add(new NpgsqlParameter($"p{argIdx}", limit));

        using var cmd = conn.CreateCommand();
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

    public int GetMaxAuditSequence()
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT MAX(sequence_number) FROM audit_log";

        var result = cmd.ExecuteScalar();
        if (result == null || result == DBNull.Value)
            return 0;

        return Convert.ToInt32(result);
    }

    public List<AuditEntry> GetAuditEntriesRange(int first, int last)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data FROM audit_log WHERE sequence_number BETWEEN @first AND @last ORDER BY sequence_number ASC";
        cmd.Parameters.AddWithValue("first", (long)first);
        cmd.Parameters.AddWithValue("last", (long)last);

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

    public void UpdateAuditSignature(int seqNum, string signature)
    {
        using var conn = _dataSource.OpenConnection();

        // Update the signature column.
        using (var updateSigCmd = conn.CreateCommand())
        {
            updateSigCmd.CommandText = "UPDATE audit_log SET signature = @signature WHERE sequence_number = @seqNum";
            updateSigCmd.Parameters.AddWithValue("signature", signature);
            updateSigCmd.Parameters.AddWithValue("seqNum", (long)seqNum);
            updateSigCmd.ExecuteNonQuery();
        }

        // Also update the signature in the JSON data blob.
        string data;
        using (var selectCmd = conn.CreateCommand())
        {
            selectCmd.CommandText = "SELECT data FROM audit_log WHERE sequence_number = @seqNum";
            selectCmd.Parameters.AddWithValue("seqNum", (long)seqNum);
            data = (string)selectCmd.ExecuteScalar()!;
        }

        var entry = JsonSerializer.Deserialize<AuditEntry>(data, s_serializerOptions)!;
        entry.Signature = signature;

        var updated = JsonSerializer.Serialize(entry, s_serializerOptions);
        using (var updateDataCmd = conn.CreateCommand())
        {
            updateDataCmd.CommandText = "UPDATE audit_log SET data = @data WHERE sequence_number = @seqNum";
            updateDataCmd.Parameters.AddWithValue("data", updated);
            updateDataCmd.Parameters.AddWithValue("seqNum", (long)seqNum);
            updateDataCmd.ExecuteNonQuery();
        }
    }

    // --- Checkpoints ---

    public void StoreCheckpoint(Checkpoint checkpoint, string signature)
    {
        var data = JsonSerializer.Serialize(checkpoint, s_serializerOptions);

        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "INSERT INTO checkpoints (checkpoint_id, data, signature) VALUES (@checkpointId, @data, @signature)";
        cmd.Parameters.AddWithValue("checkpointId", checkpoint.CheckpointId);
        cmd.Parameters.AddWithValue("data", data);
        cmd.Parameters.AddWithValue("signature", signature);
        cmd.ExecuteNonQuery();
    }

    public List<Checkpoint> ListCheckpoints(int limit)
    {
        if (limit <= 0)
            limit = 10;

        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data FROM checkpoints ORDER BY checkpoint_id ASC LIMIT @limit";
        cmd.Parameters.AddWithValue("limit", limit);

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

    public Checkpoint? GetCheckpointById(string id)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data FROM checkpoints WHERE checkpoint_id = @checkpointId";
        cmd.Parameters.AddWithValue("checkpointId", id);

        var result = cmd.ExecuteScalar();
        if (result == null || result == DBNull.Value)
            return null;

        return JsonSerializer.Deserialize<Checkpoint>((string)result, s_serializerOptions);
    }

    // --- Retention ---

    public int DeleteExpiredAuditEntries(string now)
    {
        using var conn = _dataSource.OpenConnection();

        // Scan all entries and check the JSON data blob for expires_at.
        var toDelete = new List<long>();

        using (var selectCmd = conn.CreateCommand())
        {
            selectCmd.CommandText = "SELECT sequence_number, data FROM audit_log";
            using var reader = selectCmd.ExecuteReader();
            while (reader.Read())
            {
                var seqNum = reader.GetInt64(0);
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
            using var deleteCmd = conn.CreateCommand();
            deleteCmd.CommandText = "DELETE FROM audit_log WHERE sequence_number = @seqNum";
            deleteCmd.Parameters.AddWithValue("seqNum", seqNum);
            deleteCmd.ExecuteNonQuery();
        }

        return toDelete.Count;
    }

    // --- Leases (database-backed, multi-process safe) ---

    public bool TryAcquireExclusive(string key, string holder, int ttlSeconds)
    {
        var now = DateTime.UtcNow;
        var expires = now.AddSeconds(ttlSeconds);

        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO exclusive_leases (key, holder, expires_at)
            VALUES (@key, @holder, @expires)
            ON CONFLICT (key) DO UPDATE
                SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
                WHERE exclusive_leases.expires_at < @now
                   OR exclusive_leases.holder = @holder2";
        cmd.Parameters.AddWithValue("key", key);
        cmd.Parameters.AddWithValue("holder", holder);
        cmd.Parameters.AddWithValue("expires", expires);
        cmd.Parameters.AddWithValue("now", now);
        cmd.Parameters.AddWithValue("holder2", holder);

        var rowsAffected = cmd.ExecuteNonQuery();
        return rowsAffected == 1;
    }

    public void ReleaseExclusive(string key, string holder)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "DELETE FROM exclusive_leases WHERE key = @key AND holder = @holder";
        cmd.Parameters.AddWithValue("key", key);
        cmd.Parameters.AddWithValue("holder", holder);
        cmd.ExecuteNonQuery();
    }

    public bool TryAcquireLeader(string role, string holder, int ttlSeconds)
    {
        var now = DateTime.UtcNow;
        var expires = now.AddSeconds(ttlSeconds);

        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO leader_leases (role, holder, expires_at)
            VALUES (@role, @holder, @expires)
            ON CONFLICT (role) DO UPDATE
                SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
                WHERE leader_leases.expires_at < @now
                   OR leader_leases.holder = @holder2";
        cmd.Parameters.AddWithValue("role", role);
        cmd.Parameters.AddWithValue("holder", holder);
        cmd.Parameters.AddWithValue("expires", expires);
        cmd.Parameters.AddWithValue("now", now);
        cmd.Parameters.AddWithValue("holder2", holder);

        var rowsAffected = cmd.ExecuteNonQuery();
        return rowsAffected == 1;
    }

    public void ReleaseLeader(string role, string holder)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "DELETE FROM leader_leases WHERE role = @role AND holder = @holder";
        cmd.Parameters.AddWithValue("role", role);
        cmd.Parameters.AddWithValue("holder", holder);
        cmd.ExecuteNonQuery();
    }

    // --- v0.23: ApprovalRequest + ApprovalGrant ---

    public void StoreApprovalRequest(ApprovalRequest request)
    {
        var data = JsonSerializer.Serialize(request, s_serializerOptions);
        using var conn = _dataSource.OpenConnection();
        // Idempotency: same content is no-op; conflicting content throws.
        using (var sel = conn.CreateCommand())
        {
            sel.CommandText = "SELECT data FROM approval_requests WHERE approval_request_id = @id";
            sel.Parameters.AddWithValue("id", request.ApprovalRequestId);
            var existing = sel.ExecuteScalar();
            if (existing != null && existing != DBNull.Value)
            {
                if ((string)existing == data) return;
                throw new InvalidOperationException(
                    $"approval_request_id {request.ApprovalRequestId} already stored with different content");
            }
        }

        using var insert = conn.CreateCommand();
        insert.CommandText = @"
            INSERT INTO approval_requests (approval_request_id, capability, status, expires_at, data)
            VALUES (@id, @capability, @status, @expiresAt, @data)";
        insert.Parameters.AddWithValue("id", request.ApprovalRequestId);
        insert.Parameters.AddWithValue("capability", request.Capability);
        insert.Parameters.AddWithValue("status", request.Status);
        insert.Parameters.AddWithValue("expiresAt", request.ExpiresAt);
        insert.Parameters.AddWithValue("data", data);
        insert.ExecuteNonQuery();
    }

    public ApprovalRequest? GetApprovalRequest(string approvalRequestId)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data FROM approval_requests WHERE approval_request_id = @id";
        cmd.Parameters.AddWithValue("id", approvalRequestId);
        var result = cmd.ExecuteScalar();
        if (result == null || result == DBNull.Value) return null;
        return JsonSerializer.Deserialize<ApprovalRequest>((string)result, s_serializerOptions);
    }

    public ApprovalDecisionResult ApproveRequestAndStoreGrant(
        string approvalRequestId,
        ApprovalGrant grant,
        IDictionary<string, object?> approver,
        string decidedAtIso,
        string nowIso)
    {
        using var conn = _dataSource.OpenConnection();
        using var transaction = conn.BeginTransaction();
        try
        {
            ApprovalRequest existing;
            using (var sel = conn.CreateCommand())
            {
                sel.Transaction = transaction;
                sel.CommandText = "SELECT data, status, expires_at FROM approval_requests WHERE approval_request_id = @id FOR UPDATE";
                sel.Parameters.AddWithValue("id", approvalRequestId);
                using var reader = sel.ExecuteReader();
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

            using (var update = conn.CreateCommand())
            {
                update.Transaction = transaction;
                update.CommandText = @"
                    UPDATE approval_requests
                    SET status = 'approved', data = @data
                    WHERE approval_request_id = @id AND status = 'pending'";
                update.Parameters.AddWithValue("data", updatedReq);
                update.Parameters.AddWithValue("id", approvalRequestId);
                if (update.ExecuteNonQuery() != 1)
                {
                    transaction.Rollback();
                    return ApprovalDecisionResult.Failure("approval_request_already_decided");
                }
            }

            var grantJson = JsonSerializer.Serialize(grant, s_serializerOptions);
            using (var insert = conn.CreateCommand())
            {
                insert.Transaction = transaction;
                insert.CommandText = @"
                    INSERT INTO approval_grants (grant_id, approval_request_id, capability,
                        expires_at, max_uses, use_count, data)
                    VALUES (@gid, @arid, @cap, @expires, @maxUses, @useCount, @data)";
                insert.Parameters.AddWithValue("gid", grant.GrantId);
                insert.Parameters.AddWithValue("arid", grant.ApprovalRequestId);
                insert.Parameters.AddWithValue("cap", grant.Capability);
                insert.Parameters.AddWithValue("expires", grant.ExpiresAt);
                insert.Parameters.AddWithValue("maxUses", grant.MaxUses);
                insert.Parameters.AddWithValue("useCount", grant.UseCount);
                insert.Parameters.AddWithValue("data", grantJson);
                insert.ExecuteNonQuery();
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

    public void StoreGrant(ApprovalGrant grant)
    {
        var data = JsonSerializer.Serialize(grant, s_serializerOptions);
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            INSERT INTO approval_grants (grant_id, approval_request_id, capability,
                expires_at, max_uses, use_count, data)
            VALUES (@gid, @arid, @cap, @expires, @maxUses, @useCount, @data)";
        cmd.Parameters.AddWithValue("gid", grant.GrantId);
        cmd.Parameters.AddWithValue("arid", grant.ApprovalRequestId);
        cmd.Parameters.AddWithValue("cap", grant.Capability);
        cmd.Parameters.AddWithValue("expires", grant.ExpiresAt);
        cmd.Parameters.AddWithValue("maxUses", grant.MaxUses);
        cmd.Parameters.AddWithValue("useCount", grant.UseCount);
        cmd.Parameters.AddWithValue("data", data);
        cmd.ExecuteNonQuery();
    }

    public ApprovalGrant? GetGrant(string grantId)
    {
        using var conn = _dataSource.OpenConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT data FROM approval_grants WHERE grant_id = @gid";
        cmd.Parameters.AddWithValue("gid", grantId);
        var result = cmd.ExecuteScalar();
        if (result == null || result == DBNull.Value) return null;
        return JsonSerializer.Deserialize<ApprovalGrant>((string)result, s_serializerOptions);
    }

    public GrantReservationResult TryReserveGrant(string grantId, string nowIso)
    {
        using var conn = _dataSource.OpenConnection();
        // The atomic UPDATE ... RETURNING pattern collapses Phase B's CAS into
        // a single statement. SPEC.md §4.8 — once-only redemption.
        ApprovalGrant? grant = null;
        using (var update = conn.CreateCommand())
        {
            update.CommandText = @"
                UPDATE approval_grants
                SET use_count = use_count + 1
                WHERE grant_id = @gid AND use_count < max_uses AND expires_at > @now
                RETURNING data, use_count";
            update.Parameters.AddWithValue("gid", grantId);
            update.Parameters.AddWithValue("now", nowIso);
            using var reader = update.ExecuteReader();
            if (reader.Read())
            {
                grant = JsonSerializer.Deserialize<ApprovalGrant>(reader.GetString(0), s_serializerOptions)!;
                grant.UseCount = reader.GetInt32(1);
            }
        }

        if (grant != null)
        {
            using var write = conn.CreateCommand();
            write.CommandText = "UPDATE approval_grants SET data = @data WHERE grant_id = @gid";
            write.Parameters.AddWithValue("data", JsonSerializer.Serialize(grant, s_serializerOptions));
            write.Parameters.AddWithValue("gid", grantId);
            write.ExecuteNonQuery();
            return GrantReservationResult.Success(grant);
        }

        // 0 rows → disambiguate.
        using (var probe = conn.CreateCommand())
        {
            probe.CommandText = "SELECT use_count, max_uses, expires_at FROM approval_grants WHERE grant_id = @gid";
            probe.Parameters.AddWithValue("gid", grantId);
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

    // --- Helpers ---

    /// <summary>
    /// Normalizes a postgres:// or postgresql:// DSN into an Npgsql connection string,
    /// or passes through an already-formed connection string.
    /// </summary>
    private static string NormalizeConnectionString(string input)
    {
        if (input.StartsWith("postgres://", StringComparison.OrdinalIgnoreCase) ||
            input.StartsWith("postgresql://", StringComparison.OrdinalIgnoreCase))
        {
            // Parse URI-style DSN into Npgsql connection string.
            var uri = new Uri(input);
            var builder = new NpgsqlConnectionStringBuilder
            {
                Host = uri.Host,
                Database = uri.AbsolutePath.TrimStart('/'),
            };

            if (uri.Port > 0)
                builder.Port = uri.Port;

            if (!string.IsNullOrEmpty(uri.UserInfo))
            {
                var parts = uri.UserInfo.Split(':', 2);
                builder.Username = Uri.UnescapeDataString(parts[0]);
                if (parts.Length > 1)
                    builder.Password = Uri.UnescapeDataString(parts[1]);
            }

            // Parse query string parameters (e.g., ?sslmode=require).
            if (!string.IsNullOrEmpty(uri.Query))
            {
                var queryParams = uri.Query.TrimStart('?').Split('&');
                foreach (var param in queryParams)
                {
                    var kv = param.Split('=', 2);
                    if (kv.Length == 2)
                    {
                        var key = Uri.UnescapeDataString(kv[0]);
                        var value = Uri.UnescapeDataString(kv[1]);
                        switch (key.ToLowerInvariant())
                        {
                            case "sslmode":
                                builder.SslMode = Enum.Parse<SslMode>(value, ignoreCase: true);
                                break;
                            default:
                                // Try to set it directly; Npgsql will throw for unknown keys.
                                builder[key] = value;
                                break;
                        }
                    }
                }
            }

            return builder.ToString();
        }

        // Already a connection string format.
        return input;
    }
}
