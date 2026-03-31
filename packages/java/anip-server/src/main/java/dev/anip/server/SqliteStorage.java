package dev.anip.server;

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
                            data, previous_hash, signature)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, Statement.RETURN_GENERATED_KEYS)) {
                    ps.setString(1, entry.getTimestamp());
                    ps.setString(2, entry.getCapability());
                    ps.setString(3, entry.getTokenId());
                    ps.setString(4, entry.getRootPrincipal());
                    ps.setString(5, entry.getInvocationId());
                    ps.setString(6, entry.getClientReferenceId());
                    ps.setString(7, entry.getTaskId());
                    ps.setString(8, entry.getParentInvocationId());
                    ps.setString(9, data);
                    ps.setString(10, prevHash);
                    ps.setString(11, entry.getSignature());
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
}
