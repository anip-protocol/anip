package server

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const postgresSchema = `
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
	data TEXT NOT NULL,
	previous_hash TEXT NOT NULL,
	signature TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);

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
`

// PostgresStorage implements Storage using pgxpool.Pool.
type PostgresStorage struct {
	pool *pgxpool.Pool
}

// NewPostgresStorage creates a new PostgreSQL-backed storage.
// The dsn should be a postgres:// or postgresql:// connection string.
func NewPostgresStorage(dsn string) (*PostgresStorage, error) {
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		return nil, fmt.Errorf("connect to postgres: %w", err)
	}

	// Verify connectivity.
	if err := pool.Ping(context.Background()); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}

	// Create schema.
	if _, err := pool.Exec(context.Background(), postgresSchema); err != nil {
		pool.Close()
		return nil, fmt.Errorf("create schema: %w", err)
	}

	return &PostgresStorage{pool: pool}, nil
}

// Close closes the connection pool.
func (s *PostgresStorage) Close() error {
	s.pool.Close()
	return nil
}

// --- Tokens ---

// StoreToken persists a delegation token.
func (s *PostgresStorage) StoreToken(token *core.DelegationToken) error {
	data, err := json.Marshal(token)
	if err != nil {
		return fmt.Errorf("marshal token: %w", err)
	}

	_, err = s.pool.Exec(context.Background(),
		`INSERT INTO delegation_tokens (token_id, data) VALUES ($1, $2)
		 ON CONFLICT (token_id) DO UPDATE SET data = EXCLUDED.data`,
		token.TokenID, string(data),
	)
	return err
}

// LoadToken loads a delegation token by ID.
func (s *PostgresStorage) LoadToken(tokenID string) (*core.DelegationToken, error) {
	var data string
	err := s.pool.QueryRow(context.Background(),
		"SELECT data FROM delegation_tokens WHERE token_id = $1", tokenID,
	).Scan(&data)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	var token core.DelegationToken
	if err := json.Unmarshal([]byte(data), &token); err != nil {
		return nil, fmt.Errorf("unmarshal token: %w", err)
	}
	return &token, nil
}

// --- Audit ---

// AppendAuditEntry atomically assigns sequence_number and computes previous_hash.
// Uses FOR UPDATE on audit_append_head for serializable appends across concurrent connections.
func (s *PostgresStorage) AppendAuditEntry(entry *core.AuditEntry) (*core.AuditEntry, error) {
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(context.Background())

	// Lock the append head row and get the current state.
	var lastSeqNum int64
	var lastHash string
	err = tx.QueryRow(context.Background(),
		"SELECT last_sequence_number, last_hash FROM audit_append_head WHERE id = 1 FOR UPDATE",
	).Scan(&lastSeqNum, &lastHash)
	if err != nil {
		return nil, fmt.Errorf("get append head: %w", err)
	}

	// Compute previous_hash.
	var prevHash string
	if lastSeqNum == 0 {
		// First entry: use the sentinel hash.
		prevHash = "sha256:0"
	} else {
		// Get the last entry's data to compute its hash.
		var lastData string
		err = tx.QueryRow(context.Background(),
			"SELECT data FROM audit_log WHERE sequence_number = $1", lastSeqNum,
		).Scan(&lastData)
		if err != nil {
			return nil, fmt.Errorf("get last entry: %w", err)
		}
		var lastEntry core.AuditEntry
		if err := json.Unmarshal([]byte(lastData), &lastEntry); err != nil {
			return nil, fmt.Errorf("unmarshal last entry: %w", err)
		}
		prevHash = computeEntryHash(&lastEntry)
	}

	newSeqNum := lastSeqNum + 1
	entry.PreviousHash = prevHash
	entry.SequenceNumber = int(newSeqNum)

	data, err := json.Marshal(entry)
	if err != nil {
		return nil, fmt.Errorf("marshal entry: %w", err)
	}

	// Insert the audit entry with an explicit sequence_number.
	_, err = tx.Exec(context.Background(),
		`INSERT INTO audit_log (sequence_number, timestamp, capability, token_id, root_principal,
		 invocation_id, client_reference_id, data, previous_hash, signature)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		newSeqNum,
		entry.Timestamp,
		entry.Capability,
		entry.TokenID,
		entry.RootPrincipal,
		entry.InvocationID,
		entry.ClientReferenceID,
		string(data),
		prevHash,
		entry.Signature,
	)
	if err != nil {
		return nil, fmt.Errorf("insert audit entry: %w", err)
	}

	// Compute hash of the newly inserted entry for the append head.
	newHash := computeEntryHash(entry)

	// Update the append head.
	_, err = tx.Exec(context.Background(),
		"UPDATE audit_append_head SET last_sequence_number = $1, last_hash = $2 WHERE id = 1",
		newSeqNum, newHash,
	)
	if err != nil {
		return nil, fmt.Errorf("update append head: %w", err)
	}

	if err := tx.Commit(context.Background()); err != nil {
		return nil, fmt.Errorf("commit: %w", err)
	}

	return entry, nil
}

// QueryAuditEntries queries audit entries with optional filters.
func (s *PostgresStorage) QueryAuditEntries(filters AuditFilters) ([]core.AuditEntry, error) {
	query := "SELECT data FROM audit_log WHERE 1=1"
	args := make([]any, 0)
	argIdx := 1

	if filters.RootPrincipal != "" {
		query += " AND root_principal = $" + strconv.Itoa(argIdx)
		args = append(args, filters.RootPrincipal)
		argIdx++
	}
	if filters.Capability != "" {
		query += " AND capability = $" + strconv.Itoa(argIdx)
		args = append(args, filters.Capability)
		argIdx++
	}
	if filters.Since != "" {
		query += " AND timestamp >= $" + strconv.Itoa(argIdx)
		args = append(args, filters.Since)
		argIdx++
	}
	if filters.InvocationID != "" {
		query += " AND invocation_id = $" + strconv.Itoa(argIdx)
		args = append(args, filters.InvocationID)
		argIdx++
	}
	if filters.ClientReferenceID != "" {
		query += " AND client_reference_id = $" + strconv.Itoa(argIdx)
		args = append(args, filters.ClientReferenceID)
		argIdx++
	}

	query += " ORDER BY sequence_number DESC"

	limit := filters.Limit
	if limit <= 0 {
		limit = 50
	}
	query += " LIMIT $" + strconv.Itoa(argIdx)
	args = append(args, limit)

	rows, err := s.pool.Query(context.Background(), query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []core.AuditEntry
	for rows.Next() {
		var data string
		if err := rows.Scan(&data); err != nil {
			return nil, err
		}
		var entry core.AuditEntry
		if err := json.Unmarshal([]byte(data), &entry); err != nil {
			return nil, err
		}
		entries = append(entries, entry)
	}

	if entries == nil {
		entries = []core.AuditEntry{}
	}
	return entries, rows.Err()
}

// GetMaxAuditSequence returns the highest sequence_number, or 0 if empty.
func (s *PostgresStorage) GetMaxAuditSequence() (int, error) {
	var maxSeq *int64
	err := s.pool.QueryRow(context.Background(),
		"SELECT MAX(sequence_number) FROM audit_log",
	).Scan(&maxSeq)
	if err != nil {
		return 0, err
	}
	if maxSeq == nil {
		return 0, nil
	}
	return int(*maxSeq), nil
}

// GetAuditEntriesRange returns audit entries with sequence_number between first and last (inclusive).
func (s *PostgresStorage) GetAuditEntriesRange(first, last int) ([]core.AuditEntry, error) {
	rows, err := s.pool.Query(context.Background(),
		"SELECT data FROM audit_log WHERE sequence_number BETWEEN $1 AND $2 ORDER BY sequence_number ASC",
		first, last,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []core.AuditEntry
	for rows.Next() {
		var data string
		if err := rows.Scan(&data); err != nil {
			return nil, err
		}
		var entry core.AuditEntry
		if err := json.Unmarshal([]byte(data), &entry); err != nil {
			return nil, err
		}
		entries = append(entries, entry)
	}

	if entries == nil {
		entries = []core.AuditEntry{}
	}
	return entries, rows.Err()
}

// UpdateAuditSignature updates the signature on an existing audit entry.
func (s *PostgresStorage) UpdateAuditSignature(seqNum int, signature string) error {
	// Update the signature column.
	_, err := s.pool.Exec(context.Background(),
		"UPDATE audit_log SET signature = $1 WHERE sequence_number = $2",
		signature, seqNum,
	)
	if err != nil {
		return err
	}

	// Also update the signature in the JSON data blob.
	var data string
	err = s.pool.QueryRow(context.Background(),
		"SELECT data FROM audit_log WHERE sequence_number = $1", seqNum,
	).Scan(&data)
	if err != nil {
		return err
	}

	var entry core.AuditEntry
	if err := json.Unmarshal([]byte(data), &entry); err != nil {
		return err
	}
	entry.Signature = signature
	updated, err := json.Marshal(&entry)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(context.Background(),
		"UPDATE audit_log SET data = $1 WHERE sequence_number = $2",
		string(updated), seqNum,
	)
	return err
}

// --- Checkpoints ---

// StoreCheckpoint persists a checkpoint.
func (s *PostgresStorage) StoreCheckpoint(cp *core.Checkpoint, signature string) error {
	data, err := json.Marshal(cp)
	if err != nil {
		return fmt.Errorf("marshal checkpoint: %w", err)
	}

	_, err = s.pool.Exec(context.Background(),
		"INSERT INTO checkpoints (checkpoint_id, data, signature) VALUES ($1, $2, $3)",
		cp.CheckpointID, string(data), signature,
	)
	return err
}

// ListCheckpoints returns checkpoints ordered by checkpoint_id, limited by count.
func (s *PostgresStorage) ListCheckpoints(limit int) ([]core.Checkpoint, error) {
	if limit <= 0 {
		limit = 10
	}

	rows, err := s.pool.Query(context.Background(),
		"SELECT data FROM checkpoints ORDER BY checkpoint_id ASC LIMIT $1", limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var checkpoints []core.Checkpoint
	for rows.Next() {
		var data string
		if err := rows.Scan(&data); err != nil {
			return nil, err
		}
		var cp core.Checkpoint
		if err := json.Unmarshal([]byte(data), &cp); err != nil {
			return nil, err
		}
		checkpoints = append(checkpoints, cp)
	}

	if checkpoints == nil {
		checkpoints = []core.Checkpoint{}
	}
	return checkpoints, rows.Err()
}

// GetCheckpointByID returns a checkpoint by its ID.
func (s *PostgresStorage) GetCheckpointByID(id string) (*core.Checkpoint, error) {
	var data string
	err := s.pool.QueryRow(context.Background(),
		"SELECT data FROM checkpoints WHERE checkpoint_id = $1", id,
	).Scan(&data)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	var cp core.Checkpoint
	if err := json.Unmarshal([]byte(data), &cp); err != nil {
		return nil, fmt.Errorf("unmarshal checkpoint: %w", err)
	}
	return &cp, nil
}
