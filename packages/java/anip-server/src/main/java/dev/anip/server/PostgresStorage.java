package dev.anip.server;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.Checkpoint;
import dev.anip.core.DelegationToken;

import java.io.IOException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * PostgreSQL-backed Storage implementation using HikariCP connection pool.
 * Uses FOR UPDATE on audit_append_head for serializable audit appends.
 * Lease tables use ON CONFLICT with expiry check.
 */
public class PostgresStorage implements Storage {

    private static final String SCHEMA = """
            CREATE TABLE IF NOT EXISTS delegation_tokens (
                token_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                sequence_number BIGSERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                capability TEXT NOT NULL,
                token_id TEXT NOT NULL,
                root_principal TEXT NOT NULL,
                invocation_id TEXT NOT NULL,
                client_reference_id TEXT,
                task_id TEXT,
                parent_invocation_id TEXT,
                data TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                signature TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS audit_append_head (
                id INTEGER PRIMARY KEY DEFAULT 1,
                last_sequence_number BIGINT NOT NULL DEFAULT 0,
                last_hash TEXT NOT NULL DEFAULT ''
            );

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
            """;

    private static final String INDEXES = """
            CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
            CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
            CREATE INDEX IF NOT EXISTS idx_audit_task_id ON audit_log(task_id);
            CREATE INDEX IF NOT EXISTS idx_audit_parent_invocation_id ON audit_log(parent_invocation_id);
            """;

    private static final String INIT_APPEND_HEAD =
            "INSERT INTO audit_append_head (id, last_sequence_number, last_hash) " +
            "VALUES (1, 0, '') ON CONFLICT (id) DO NOTHING";

    private final HikariDataSource dataSource;

    /**
     * Creates a new PostgreSQL-backed storage with a HikariCP connection pool.
     *
     * @param jdbcUrl  JDBC connection URL (e.g., jdbc:postgresql://localhost:5432/anip)
     * @param username database username
     * @param password database password
     */
    public PostgresStorage(String jdbcUrl, String username, String password) throws SQLException {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setUsername(username);
        config.setPassword(password);
        config.setMaximumPoolSize(10);

        this.dataSource = new HikariDataSource(config);
        initSchema();
    }

    /**
     * Creates a new PostgreSQL-backed storage from a DSN string.
     * Converts postgres:// DSN to JDBC URL.
     */
    public PostgresStorage(String dsn) throws SQLException {
        String jdbcUrl = dsn;
        if (dsn.startsWith("postgres://") || dsn.startsWith("postgresql://")) {
            jdbcUrl = "jdbc:" + dsn.replaceFirst("^postgres://", "postgresql://");
        }

        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setMaximumPoolSize(10);

        this.dataSource = new HikariDataSource(config);
        initSchema();
    }

    private void initSchema() throws SQLException {
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement()) {
            for (String sql : SCHEMA.split(";")) {
                String trimmed = sql.trim();
                if (!trimmed.isEmpty()) {
                    stmt.execute(trimmed);
                }
            }
            for (String sql : INDEXES.split(";")) {
                String trimmed = sql.trim();
                if (!trimmed.isEmpty()) {
                    stmt.execute(trimmed);
                }
            }
            stmt.execute(INIT_APPEND_HEAD);
        }
    }

    @Override
    public void close() throws IOException {
        dataSource.close();
    }

    // --- Tokens ---

    @Override
    public void storeToken(DelegationToken token) throws Exception {
        String data = JsonHelper.toJson(token);
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO delegation_tokens (token_id, data) VALUES (?, ?) " +
                     "ON CONFLICT (token_id) DO UPDATE SET data = EXCLUDED.data")) {
            ps.setString(1, token.getTokenId());
            ps.setString(2, data);
            ps.executeUpdate();
        }
    }

    @Override
    public DelegationToken loadToken(String tokenId) throws Exception {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
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

    // --- Audit ---

    @Override
    public AuditEntry appendAuditEntry(AuditEntry entry) throws Exception {
        try (Connection conn = dataSource.getConnection()) {
            conn.setAutoCommit(false);
            try {
                // Lock the append head row and get the current state.
                long lastSeqNum;
                try (PreparedStatement ps = conn.prepareStatement(
                        "SELECT last_sequence_number, last_hash FROM audit_append_head WHERE id = 1 FOR UPDATE")) {
                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) {
                            throw new SQLException("audit_append_head row not found");
                        }
                        lastSeqNum = rs.getLong("last_sequence_number");
                    }
                }

                // Compute previous_hash.
                String prevHash;
                if (lastSeqNum == 0) {
                    prevHash = "sha256:0";
                } else {
                    try (PreparedStatement ps = conn.prepareStatement(
                            "SELECT data FROM audit_log WHERE sequence_number = ?")) {
                        ps.setLong(1, lastSeqNum);
                        try (ResultSet rs = ps.executeQuery()) {
                            if (!rs.next()) {
                                throw new SQLException("Last audit entry not found: " + lastSeqNum);
                            }
                            AuditEntry lastEntry = JsonHelper.fromJson(rs.getString("data"), AuditEntry.class);
                            prevHash = HashChain.computeEntryHash(lastEntry);
                        }
                    }
                }

                long newSeqNum = lastSeqNum + 1;
                entry.setPreviousHash(prevHash);
                entry.setSequenceNumber((int) newSeqNum);

                String data = JsonHelper.toJson(entry);

                // Insert with explicit sequence_number.
                try (PreparedStatement ps = conn.prepareStatement(
                        """
                        INSERT INTO audit_log (sequence_number, timestamp, capability, token_id, root_principal,
                            invocation_id, client_reference_id, task_id, parent_invocation_id,
                            data, previous_hash, signature)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """)) {
                    ps.setLong(1, newSeqNum);
                    ps.setString(2, entry.getTimestamp());
                    ps.setString(3, entry.getCapability());
                    ps.setString(4, entry.getTokenId());
                    ps.setString(5, entry.getRootPrincipal());
                    ps.setString(6, entry.getInvocationId());
                    ps.setString(7, entry.getClientReferenceId());
                    ps.setString(8, entry.getTaskId());
                    ps.setString(9, entry.getParentInvocationId());
                    ps.setString(10, data);
                    ps.setString(11, prevHash);
                    ps.setString(12, entry.getSignature() != null ? entry.getSignature() : "");
                    ps.executeUpdate();
                }

                // Update the append head.
                String newHash = HashChain.computeEntryHash(entry);
                try (PreparedStatement ps = conn.prepareStatement(
                        "UPDATE audit_append_head SET last_sequence_number = ?, last_hash = ? WHERE id = 1")) {
                    ps.setLong(1, newSeqNum);
                    ps.setString(2, newHash);
                    ps.executeUpdate();
                }

                conn.commit();
                return entry;
            } catch (Exception e) {
                conn.rollback();
                throw e;
            } finally {
                conn.setAutoCommit(true);
            }
        }
    }

    @Override
    public List<AuditEntry> queryAuditEntries(AuditFilters filters) throws Exception {
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

        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(query.toString())) {
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

    @Override
    public int getMaxAuditSequence() throws Exception {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT MAX(sequence_number) FROM audit_log")) {
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    long val = rs.getLong(1);
                    if (rs.wasNull()) {
                        return 0;
                    }
                    return (int) val;
                }
                return 0;
            }
        }
    }

    @Override
    public List<AuditEntry> getAuditEntriesRange(int first, int last) throws Exception {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
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

    @Override
    public void updateAuditSignature(int seqNum, String signature) throws Exception {
        try (Connection conn = dataSource.getConnection()) {
            // Update the signature column.
            try (PreparedStatement ps = conn.prepareStatement(
                    "UPDATE audit_log SET signature = ? WHERE sequence_number = ?")) {
                ps.setString(1, signature);
                ps.setInt(2, seqNum);
                ps.executeUpdate();
            }

            // Also update the signature in the JSON data blob.
            String data;
            try (PreparedStatement ps = conn.prepareStatement(
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

            try (PreparedStatement ps = conn.prepareStatement(
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
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO checkpoints (checkpoint_id, data, signature) VALUES (?, ?, ?)")) {
            ps.setString(1, cp.getCheckpointId());
            ps.setString(2, data);
            ps.setString(3, signature);
            ps.executeUpdate();
        }
    }

    @Override
    public List<Checkpoint> listCheckpoints(int limit) throws Exception {
        if (limit <= 0) {
            limit = 10;
        }
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT data FROM checkpoints ORDER BY checkpoint_id ASC LIMIT ?")) {
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

    @Override
    public Checkpoint getCheckpointById(String id) throws Exception {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
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

    // --- Retention ---

    @Override
    public int deleteExpiredAuditEntries(String now) throws Exception {
        try (Connection conn = dataSource.getConnection()) {
            // Scan all entries and check the JSON data blob for expires_at.
            List<Long> toDelete = new ArrayList<>();
            try (PreparedStatement ps = conn.prepareStatement(
                    "SELECT sequence_number, data FROM audit_log")) {
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        long seqNum = rs.getLong("sequence_number");
                        String data = rs.getString("data");
                        try {
                            AuditEntry entry = JsonHelper.fromJson(data, AuditEntry.class);
                            if (entry.getExpiresAt() != null && !entry.getExpiresAt().isEmpty()
                                    && entry.getExpiresAt().compareTo(now) < 0) {
                                toDelete.add(seqNum);
                            }
                        } catch (Exception ignored) {
                        }
                    }
                }
            }

            for (long seqNum : toDelete) {
                try (PreparedStatement ps = conn.prepareStatement(
                        "DELETE FROM audit_log WHERE sequence_number = ?")) {
                    ps.setLong(1, seqNum);
                    ps.executeUpdate();
                }
            }
            return toDelete.size();
        }
    }

    // --- Leases ---

    @Override
    public boolean tryAcquireExclusive(String key, String holder, int ttlSeconds) throws Exception {
        Instant now = Instant.now();
        Timestamp expires = Timestamp.from(now.plusSeconds(ttlSeconds));
        Timestamp nowTs = Timestamp.from(now);

        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     """
                     INSERT INTO exclusive_leases (key, holder, expires_at)
                     VALUES (?, ?, ?)
                     ON CONFLICT (key) DO UPDATE
                         SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
                         WHERE exclusive_leases.expires_at < ? OR exclusive_leases.holder = ?
                     """)) {
            ps.setString(1, key);
            ps.setString(2, holder);
            ps.setTimestamp(3, expires);
            ps.setTimestamp(4, nowTs);
            ps.setString(5, holder);
            int rows = ps.executeUpdate();
            return rows == 1;
        }
    }

    @Override
    public void releaseExclusive(String key, String holder) throws Exception {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "DELETE FROM exclusive_leases WHERE key = ? AND holder = ?")) {
            ps.setString(1, key);
            ps.setString(2, holder);
            ps.executeUpdate();
        }
    }

    @Override
    public boolean tryAcquireLeader(String role, String holder, int ttlSeconds) throws Exception {
        Instant now = Instant.now();
        Timestamp expires = Timestamp.from(now.plusSeconds(ttlSeconds));
        Timestamp nowTs = Timestamp.from(now);

        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     """
                     INSERT INTO leader_leases (role, holder, expires_at)
                     VALUES (?, ?, ?)
                     ON CONFLICT (role) DO UPDATE
                         SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
                         WHERE leader_leases.expires_at < ? OR leader_leases.holder = ?
                     """)) {
            ps.setString(1, role);
            ps.setString(2, holder);
            ps.setTimestamp(3, expires);
            ps.setTimestamp(4, nowTs);
            ps.setString(5, holder);
            int rows = ps.executeUpdate();
            return rows == 1;
        }
    }

    @Override
    public void releaseLeader(String role, String holder) throws Exception {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "DELETE FROM leader_leases WHERE role = ? AND holder = ?")) {
            ps.setString(1, role);
            ps.setString(2, holder);
            ps.executeUpdate();
        }
    }
}
