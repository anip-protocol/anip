package dev.anip.server;

import dev.anip.core.ApprovalGrant;
import dev.anip.core.ApprovalRequest;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.Checkpoint;
import dev.anip.core.DelegationToken;

import java.io.IOException;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * SQLite-backed Storage implementation using xerial sqlite-jdbc.
 * WAL mode for better concurrent read performance.
 * Uses synchronized blocks for thread safety (single-process).
 */
public class SqliteStorage implements Storage {

    private static final String SCHEMA = """
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
            """;

    private final Connection connection;
    private final Object lock = new Object();
    private final ConcurrentHashMap<String, LeaseEntry> exclusiveLeases = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, LeaseEntry> leaderLeases = new ConcurrentHashMap<>();

    private record LeaseEntry(String holder, Instant expiresAt) {}

    /**
     * Opens or creates a SQLite database at the given path.
     * Use ":memory:" for in-memory storage.
     */
    public SqliteStorage(String dbPath) throws SQLException {
        this.connection = DriverManager.getConnection("jdbc:sqlite:" + dbPath);

        // Enable WAL mode
        try (Statement stmt = connection.createStatement()) {
            stmt.execute("PRAGMA journal_mode=WAL");
        }

        // Create schema
        try (Statement stmt = connection.createStatement()) {
            for (String sql : SCHEMA.split(";")) {
                String trimmed = sql.trim();
                if (!trimmed.isEmpty()) {
                    stmt.execute(trimmed);
                }
            }
        }

        // Idempotent ALTER TABLE migrations for v0.23 audit_log columns.
        addColumnIfMissing("audit_log", "approval_request_id", "TEXT");
        addColumnIfMissing("audit_log", "approval_grant_id", "TEXT");
    }

    /** Adds a column if it doesn't already exist on the table. SQLite has no native idempotency. */
    private void addColumnIfMissing(String table, String column, String type) throws SQLException {
        try (PreparedStatement ps = connection.prepareStatement("PRAGMA table_info(" + table + ")");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                if (column.equals(rs.getString("name"))) {
                    return;
                }
            }
        }
        try (Statement stmt = connection.createStatement()) {
            stmt.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + type);
        }
    }

    @Override
    public void close() throws IOException {
        try {
            connection.close();
        } catch (SQLException e) {
            throw new IOException("Failed to close SQLite connection", e);
        }
    }

    // --- Tokens ---

    @Override
    public void storeToken(DelegationToken token) throws Exception {
        String data = JsonHelper.toJson(token);
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "INSERT OR REPLACE INTO delegation_tokens (token_id, data) VALUES (?, ?)")) {
                ps.setString(1, token.getTokenId());
                ps.setString(2, data);
                ps.executeUpdate();
            }
        }
    }

    @Override
    public DelegationToken loadToken(String tokenId) throws Exception {
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM delegation_tokens WHERE token_id = ?")) {
                ps.setString(1, tokenId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        return null;
                    }
                    return JsonHelper.fromJson(rs.getString("data"), DelegationToken.class);
                }
            }
        }
    }

    // --- Audit ---

    @Override
    public AuditEntry appendAuditEntry(AuditEntry entry) throws Exception {
        synchronized (lock) {
            connection.setAutoCommit(false);
            try {
                // Get the last entry for hash chaining.
                String prevHash;
                try (PreparedStatement ps = connection.prepareStatement(
                        "SELECT data, previous_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1")) {
                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) {
                            // First entry: use the sentinel hash.
                            prevHash = "sha256:0";
                        } else {
                            String lastData = rs.getString("data");
                            AuditEntry lastEntry = JsonHelper.fromJson(lastData, AuditEntry.class);
                            prevHash = HashChain.computeEntryHash(lastEntry);
                        }
                    }
                }

                entry.setPreviousHash(prevHash);
                String data = JsonHelper.toJson(entry);

                try (PreparedStatement ps = connection.prepareStatement(
                        """
                        INSERT INTO audit_log (timestamp, capability, token_id, root_principal,
                            invocation_id, client_reference_id, task_id, parent_invocation_id,
                            upstream_service, approval_request_id, approval_grant_id,
                            data, previous_hash, signature)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, Statement.RETURN_GENERATED_KEYS)) {
                    ps.setString(1, entry.getTimestamp());
                    ps.setString(2, entry.getCapability());
                    ps.setString(3, entry.getTokenId());
                    ps.setString(4, entry.getRootPrincipal());
                    ps.setString(5, entry.getInvocationId());
                    ps.setString(6, entry.getClientReferenceId());
                    ps.setString(7, entry.getTaskId());
                    ps.setString(8, entry.getParentInvocationId());
                    ps.setString(9, entry.getUpstreamService());
                    ps.setString(10, entry.getApprovalRequestId());
                    ps.setString(11, entry.getApprovalGrantId());
                    ps.setString(12, data);
                    ps.setString(13, prevHash);
                    ps.setString(14, entry.getSignature());
                    ps.executeUpdate();

                    try (ResultSet keys = ps.getGeneratedKeys()) {
                        if (keys.next()) {
                            entry.setSequenceNumber(keys.getInt(1));
                        }
                    }
                }

                connection.commit();

                // Re-serialize with the correct sequence_number and update in the database.
                data = JsonHelper.toJson(entry);
                try (PreparedStatement ps = connection.prepareStatement(
                        "UPDATE audit_log SET data = ? WHERE sequence_number = ?")) {
                    ps.setString(1, data);
                    ps.setInt(2, entry.getSequenceNumber());
                    ps.executeUpdate();
                }

                return entry;
            } catch (Exception e) {
                connection.rollback();
                throw e;
            } finally {
                connection.setAutoCommit(true);
            }
        }
    }

    @Override
    public List<AuditEntry> queryAuditEntries(AuditFilters filters) throws Exception {
        synchronized (lock) {
            StringBuilder query = new StringBuilder("SELECT data FROM audit_log WHERE 1=1");
            List<Object> args = new ArrayList<>();

            if (filters.getRootPrincipal() != null && !filters.getRootPrincipal().isEmpty()) {
                query.append(" AND root_principal = ?");
                args.add(filters.getRootPrincipal());
            }
            if (filters.getCapability() != null && !filters.getCapability().isEmpty()) {
                query.append(" AND capability = ?");
                args.add(filters.getCapability());
            }
            if (filters.getSince() != null && !filters.getSince().isEmpty()) {
                query.append(" AND timestamp >= ?");
                args.add(filters.getSince());
            }
            if (filters.getInvocationId() != null && !filters.getInvocationId().isEmpty()) {
                query.append(" AND invocation_id = ?");
                args.add(filters.getInvocationId());
            }
            if (filters.getClientReferenceId() != null && !filters.getClientReferenceId().isEmpty()) {
                query.append(" AND client_reference_id = ?");
                args.add(filters.getClientReferenceId());
            }
            if (filters.getTaskId() != null && !filters.getTaskId().isEmpty()) {
                query.append(" AND task_id = ?");
                args.add(filters.getTaskId());
            }
            if (filters.getParentInvocationId() != null && !filters.getParentInvocationId().isEmpty()) {
                query.append(" AND parent_invocation_id = ?");
                args.add(filters.getParentInvocationId());
            }

            query.append(" ORDER BY sequence_number DESC");

            int limit = filters.getLimit();
            if (limit <= 0) {
                limit = 50;
            }
            query.append(" LIMIT ?");
            args.add(limit);

            try (PreparedStatement ps = connection.prepareStatement(query.toString())) {
                for (int i = 0; i < args.size(); i++) {
                    ps.setObject(i + 1, args.get(i));
                }

                List<AuditEntry> entries = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        entries.add(JsonHelper.fromJson(rs.getString("data"), AuditEntry.class));
                    }
                }
                return entries;
            }
        }
    }

    @Override
    public int getMaxAuditSequence() throws Exception {
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT MAX(sequence_number) FROM audit_log")) {
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) {
                        int val = rs.getInt(1);
                        if (rs.wasNull()) {
                            return 0;
                        }
                        return val;
                    }
                    return 0;
                }
            }
        }
    }

    @Override
    public List<AuditEntry> getAuditEntriesRange(int first, int last) throws Exception {
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM audit_log WHERE sequence_number BETWEEN ? AND ? ORDER BY sequence_number ASC")) {
                ps.setInt(1, first);
                ps.setInt(2, last);

                List<AuditEntry> entries = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        entries.add(JsonHelper.fromJson(rs.getString("data"), AuditEntry.class));
                    }
                }
                return entries;
            }
        }
    }

    @Override
    public void updateAuditSignature(int seqNum, String signature) throws Exception {
        synchronized (lock) {
            // Update the signature column.
            try (PreparedStatement ps = connection.prepareStatement(
                    "UPDATE audit_log SET signature = ? WHERE sequence_number = ?")) {
                ps.setString(1, signature);
                ps.setInt(2, seqNum);
                ps.executeUpdate();
            }

            // Also update the signature in the JSON data blob.
            String data;
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM audit_log WHERE sequence_number = ?")) {
                ps.setInt(1, seqNum);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        return;
                    }
                    data = rs.getString("data");
                }
            }

            AuditEntry entry = JsonHelper.fromJson(data, AuditEntry.class);
            entry.setSignature(signature);
            String updated = JsonHelper.toJson(entry);

            try (PreparedStatement ps = connection.prepareStatement(
                    "UPDATE audit_log SET data = ? WHERE sequence_number = ?")) {
                ps.setString(1, updated);
                ps.setInt(2, seqNum);
                ps.executeUpdate();
            }
        }
    }

    // --- Checkpoints ---

    @Override
    public void storeCheckpoint(Checkpoint cp, String signature) throws Exception {
        String data = JsonHelper.toJson(cp);
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "INSERT INTO checkpoints (checkpoint_id, data, signature) VALUES (?, ?, ?)")) {
                ps.setString(1, cp.getCheckpointId());
                ps.setString(2, data);
                ps.setString(3, signature);
                ps.executeUpdate();
            }
        }
    }

    @Override
    public List<Checkpoint> listCheckpoints(int limit) throws Exception {
        if (limit <= 0) {
            limit = 10;
        }
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM checkpoints ORDER BY rowid ASC LIMIT ?")) {
                ps.setInt(1, limit);

                List<Checkpoint> checkpoints = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        checkpoints.add(JsonHelper.fromJson(rs.getString("data"), Checkpoint.class));
                    }
                }
                return checkpoints;
            }
        }
    }

    @Override
    public Checkpoint getCheckpointById(String id) throws Exception {
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM checkpoints WHERE checkpoint_id = ?")) {
                ps.setString(1, id);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        return null;
                    }
                    return JsonHelper.fromJson(rs.getString("data"), Checkpoint.class);
                }
            }
        }
    }

    // --- Retention ---

    @Override
    public int deleteExpiredAuditEntries(String now) throws Exception {
        synchronized (lock) {
            // Find expired entries by scanning the data blobs.
            List<Integer> toDelete = new ArrayList<>();
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT sequence_number, data FROM audit_log")) {
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        int seqNum = rs.getInt("sequence_number");
                        String data = rs.getString("data");
                        try {
                            AuditEntry entry = JsonHelper.fromJson(data, AuditEntry.class);
                            if (entry.getExpiresAt() != null && !entry.getExpiresAt().isEmpty()
                                    && entry.getExpiresAt().compareTo(now) < 0) {
                                toDelete.add(seqNum);
                            }
                        } catch (Exception ignored) {
                            // Skip entries that can't be parsed.
                        }
                    }
                }
            }

            for (int seqNum : toDelete) {
                try (PreparedStatement ps = connection.prepareStatement(
                        "DELETE FROM audit_log WHERE sequence_number = ?")) {
                    ps.setInt(1, seqNum);
                    ps.executeUpdate();
                }
            }
            return toDelete.size();
        }
    }

    // --- Leases (in-memory, single-process) ---

    @Override
    public boolean tryAcquireExclusive(String key, String holder, int ttlSeconds) {
        Instant now = Instant.now();
        Instant expires = now.plusSeconds(ttlSeconds);

        LeaseEntry existing = exclusiveLeases.get(key);
        if (existing == null || existing.expiresAt().isBefore(now) || existing.holder().equals(holder)) {
            exclusiveLeases.put(key, new LeaseEntry(holder, expires));
            return true;
        }
        return false;
    }

    @Override
    public void releaseExclusive(String key, String holder) {
        LeaseEntry existing = exclusiveLeases.get(key);
        if (existing != null && existing.holder().equals(holder)) {
            exclusiveLeases.remove(key);
        }
    }

    @Override
    public boolean tryAcquireLeader(String role, String holder, int ttlSeconds) {
        return tryAcquireExclusive("leader:" + role, holder, ttlSeconds);
    }

    @Override
    public void releaseLeader(String role, String holder) {
        releaseExclusive("leader:" + role, holder);
    }

    // --- v0.23: ApprovalRequest + ApprovalGrant ---

    @Override
    public void storeApprovalRequest(ApprovalRequest req) throws SQLException {
        String data = JsonHelper.toJson(req);
        synchronized (lock) {
            // Idempotency: same content is no-op; conflicting content raises.
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM approval_requests WHERE approval_request_id = ?")) {
                ps.setString(1, req.getApprovalRequestId());
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) {
                        String existing = rs.getString("data");
                        if (existing != null && existing.equals(data)) {
                            return;
                        }
                        throw new SQLException("approval_request_id " + req.getApprovalRequestId()
                                + " already stored with different content");
                    }
                }
            }
            try (PreparedStatement ps = connection.prepareStatement(
                    "INSERT INTO approval_requests (approval_request_id, capability, status, expires_at, data) VALUES (?, ?, ?, ?, ?)")) {
                ps.setString(1, req.getApprovalRequestId());
                ps.setString(2, req.getCapability());
                ps.setString(3, req.getStatus());
                ps.setString(4, req.getExpiresAt());
                ps.setString(5, data);
                ps.executeUpdate();
            }
        }
    }

    @Override
    public Optional<ApprovalRequest> getApprovalRequest(String approvalRequestId) throws SQLException {
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM approval_requests WHERE approval_request_id = ?")) {
                ps.setString(1, approvalRequestId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        return Optional.empty();
                    }
                    return Optional.of(JsonHelper.fromJson(rs.getString("data"), ApprovalRequest.class));
                }
            }
        }
    }

    @Override
    public ApprovalDecisionResult approveRequestAndStoreGrant(String approvalRequestId,
                                                              ApprovalGrant grant,
                                                              Map<String, Object> approver,
                                                              String decidedAtIso,
                                                              String nowIso) throws SQLException {
        synchronized (lock) {
            connection.setAutoCommit(false);
            try {
                // Load + validate state.
                ApprovalRequest existing;
                try (PreparedStatement ps = connection.prepareStatement(
                        "SELECT data, status, expires_at FROM approval_requests WHERE approval_request_id = ?")) {
                    ps.setString(1, approvalRequestId);
                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) {
                            connection.rollback();
                            return ApprovalDecisionResult.failure("approval_request_not_found");
                        }
                        existing = JsonHelper.fromJson(rs.getString("data"), ApprovalRequest.class);
                        String status = rs.getString("status");
                        String expiresAt = rs.getString("expires_at");
                        if (!"pending".equals(status)) {
                            connection.rollback();
                            return ApprovalDecisionResult.failure("approval_request_already_decided");
                        }
                        if (expiresAt != null && expiresAt.compareTo(nowIso) <= 0) {
                            connection.rollback();
                            return ApprovalDecisionResult.failure("approval_request_expired");
                        }
                    }
                }

                // Mutate the request to approved + record approver + decided_at.
                existing.setStatus("approved");
                existing.setApprover(approver);
                existing.setDecidedAt(decidedAtIso);
                String updatedReq = JsonHelper.toJson(existing);
                try (PreparedStatement ps = connection.prepareStatement(
                        "UPDATE approval_requests SET status = 'approved', data = ? WHERE approval_request_id = ? AND status = 'pending'")) {
                    ps.setString(1, updatedReq);
                    ps.setString(2, approvalRequestId);
                    int affected = ps.executeUpdate();
                    if (affected != 1) {
                        connection.rollback();
                        return ApprovalDecisionResult.failure("approval_request_already_decided");
                    }
                }

                // Insert the grant. Unique constraint on approval_request_id is the
                // defense-in-depth (in addition to the conditional UPDATE above).
                String grantJson = JsonHelper.toJson(grant);
                try (PreparedStatement ps = connection.prepareStatement(
                        "INSERT INTO approval_grants (grant_id, approval_request_id, capability, expires_at, max_uses, use_count, data) VALUES (?, ?, ?, ?, ?, ?, ?)")) {
                    ps.setString(1, grant.getGrantId());
                    ps.setString(2, grant.getApprovalRequestId());
                    ps.setString(3, grant.getCapability());
                    ps.setString(4, grant.getExpiresAt());
                    ps.setInt(5, grant.getMaxUses());
                    ps.setInt(6, grant.getUseCount());
                    ps.setString(7, grantJson);
                    ps.executeUpdate();
                }

                connection.commit();
                return ApprovalDecisionResult.success(grant);
            } catch (SQLException e) {
                try { connection.rollback(); } catch (SQLException ignored) {}
                throw e;
            } finally {
                try { connection.setAutoCommit(true); } catch (SQLException ignored) {}
            }
        }
    }

    @Override
    public void storeGrant(ApprovalGrant grant) throws SQLException {
        String data = JsonHelper.toJson(grant);
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "INSERT INTO approval_grants (grant_id, approval_request_id, capability, expires_at, max_uses, use_count, data) VALUES (?, ?, ?, ?, ?, ?, ?)")) {
                ps.setString(1, grant.getGrantId());
                ps.setString(2, grant.getApprovalRequestId());
                ps.setString(3, grant.getCapability());
                ps.setString(4, grant.getExpiresAt());
                ps.setInt(5, grant.getMaxUses());
                ps.setInt(6, grant.getUseCount());
                ps.setString(7, data);
                ps.executeUpdate();
            }
        }
    }

    @Override
    public Optional<ApprovalGrant> getGrant(String grantId) throws SQLException {
        synchronized (lock) {
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT data FROM approval_grants WHERE grant_id = ?")) {
                ps.setString(1, grantId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        return Optional.empty();
                    }
                    return Optional.of(JsonHelper.fromJson(rs.getString("data"), ApprovalGrant.class));
                }
            }
        }
    }

    @Override
    public GrantReservationResult tryReserveGrant(String grantId, String nowIso) throws SQLException {
        synchronized (lock) {
            // Atomic CAS: only succeeds if grant exists, not consumed, not expired.
            int affected;
            try (PreparedStatement ps = connection.prepareStatement(
                    "UPDATE approval_grants SET use_count = use_count + 1 WHERE grant_id = ? AND use_count < max_uses AND expires_at > ?")) {
                ps.setString(1, grantId);
                ps.setString(2, nowIso);
                affected = ps.executeUpdate();
            }
            if (affected == 1) {
                // Re-load to populate post-reservation use_count + sync data blob.
                ApprovalGrant grant;
                try (PreparedStatement ps = connection.prepareStatement(
                        "SELECT data, use_count FROM approval_grants WHERE grant_id = ?")) {
                    ps.setString(1, grantId);
                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) {
                            return GrantReservationResult.failure("grant_not_found");
                        }
                        grant = JsonHelper.fromJson(rs.getString("data"), ApprovalGrant.class);
                        int newUseCount = rs.getInt("use_count");
                        grant.setUseCount(newUseCount);
                    }
                }
                // Persist the updated use_count back into the JSON blob to keep
                // the data column consistent for cross-runtime readers.
                try (PreparedStatement ps = connection.prepareStatement(
                        "UPDATE approval_grants SET data = ? WHERE grant_id = ?")) {
                    ps.setString(1, JsonHelper.toJson(grant));
                    ps.setString(2, grantId);
                    ps.executeUpdate();
                }
                return GrantReservationResult.success(grant);
            }
            // 0 rows — disambiguate by re-fetching.
            try (PreparedStatement ps = connection.prepareStatement(
                    "SELECT use_count, max_uses, expires_at FROM approval_grants WHERE grant_id = ?")) {
                ps.setString(1, grantId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (!rs.next()) {
                        return GrantReservationResult.failure("grant_not_found");
                    }
                    int useCount = rs.getInt("use_count");
                    int maxUses = rs.getInt("max_uses");
                    String expiresAt = rs.getString("expires_at");
                    if (expiresAt != null && expiresAt.compareTo(nowIso) <= 0) {
                        return GrantReservationResult.failure("grant_expired");
                    }
                    if (useCount >= maxUses) {
                        return GrantReservationResult.failure("grant_consumed");
                    }
                    // Should not happen, but treat as not found for safety.
                    return GrantReservationResult.failure("grant_not_found");
                }
            }
        }
    }
}
