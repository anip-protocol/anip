package server

import (
	"crypto/sha256"
	"database/sql"
	"encoding/json"
	"fmt"
	"sort"
	"sync"

	"github.com/anip-protocol/anip/packages/go/core"
	_ "modernc.org/sqlite"
)

const sqliteSchema = `
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
	data TEXT NOT NULL,
	previous_hash TEXT NOT NULL,
	signature TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);

CREATE TABLE IF NOT EXISTS checkpoints (
	checkpoint_id TEXT PRIMARY KEY,
	data TEXT NOT NULL,
	signature TEXT NOT NULL
);
`

// SQLiteStorage implements Storage using modernc.org/sqlite.
type SQLiteStorage struct {
	db *sql.DB
	mu sync.Mutex
}

// NewSQLiteStorage opens or creates a SQLite database at the given path.
// Use ":memory:" for in-memory storage.
func NewSQLiteStorage(dbPath string) (*SQLiteStorage, error) {
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}

	// Enable WAL mode for better concurrent read performance.
	if _, err := db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		db.Close()
		return nil, fmt.Errorf("set WAL mode: %w", err)
	}

	if _, err := db.Exec(sqliteSchema); err != nil {
		db.Close()
		return nil, fmt.Errorf("create schema: %w", err)
	}

	return &SQLiteStorage{db: db}, nil
}

// Close closes the database connection.
func (s *SQLiteStorage) Close() error {
	return s.db.Close()
}

// --- Tokens ---

// StoreToken persists a delegation token.
func (s *SQLiteStorage) StoreToken(token *core.DelegationToken) error {
	data, err := json.Marshal(token)
	if err != nil {
		return fmt.Errorf("marshal token: %w", err)
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	_, err = s.db.Exec(
		"INSERT OR REPLACE INTO delegation_tokens (token_id, data) VALUES (?, ?)",
		token.TokenID, string(data),
	)
	return err
}

// LoadToken loads a delegation token by ID.
func (s *SQLiteStorage) LoadToken(tokenID string) (*core.DelegationToken, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	var data string
	err := s.db.QueryRow(
		"SELECT data FROM delegation_tokens WHERE token_id = ?", tokenID,
	).Scan(&data)
	if err == sql.ErrNoRows {
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

// computeEntryHash computes the canonical hash of an audit entry for hash-chain linking.
// Matches the Python implementation: excludes "signature" and "id" fields,
// sorts keys, uses compact JSON separators.
func computeEntryHash(entry *core.AuditEntry) string {
	// Marshal to map to get the JSON representation, then filter and sort.
	data, _ := json.Marshal(entry)
	var m map[string]any
	json.Unmarshal(data, &m)

	// Remove signature and id fields.
	delete(m, "signature")
	delete(m, "id")

	// Sort keys and build ordered JSON.
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	ordered := make(map[string]any)
	for _, k := range keys {
		ordered[k] = m[k]
	}

	canonical, _ := json.Marshal(ordered)
	h := sha256.Sum256(canonical)
	return fmt.Sprintf("sha256:%x", h)
}

// AppendAuditEntry atomically assigns sequence_number and computes previous_hash.
func (s *SQLiteStorage) AppendAuditEntry(entry *core.AuditEntry) (*core.AuditEntry, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	tx, err := s.db.Begin()
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// Get the last entry for hash chaining.
	var prevHash string
	var lastData sql.NullString
	err = tx.QueryRow(
		"SELECT data, previous_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1",
	).Scan(&lastData, &prevHash)
	if err == sql.ErrNoRows {
		// First entry: use the sentinel hash.
		prevHash = "sha256:0"
	} else if err != nil {
		return nil, fmt.Errorf("get last entry: %w", err)
	} else {
		// Compute hash of previous entry.
		var lastEntry core.AuditEntry
		if err := json.Unmarshal([]byte(lastData.String), &lastEntry); err != nil {
			return nil, fmt.Errorf("unmarshal last entry: %w", err)
		}
		prevHash = computeEntryHash(&lastEntry)
	}

	entry.PreviousHash = prevHash

	data, err := json.Marshal(entry)
	if err != nil {
		return nil, fmt.Errorf("marshal entry: %w", err)
	}

	result, err := tx.Exec(
		`INSERT INTO audit_log (timestamp, capability, token_id, root_principal,
		 invocation_id, client_reference_id, data, previous_hash, signature)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
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

	seqNum, err := result.LastInsertId()
	if err != nil {
		return nil, fmt.Errorf("get sequence number: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("commit: %w", err)
	}

	entry.SequenceNumber = int(seqNum)

	// Re-marshal with the correct sequence_number and update in the database.
	data, _ = json.Marshal(entry)
	s.db.Exec("UPDATE audit_log SET data = ? WHERE sequence_number = ?", string(data), seqNum)

	return entry, nil
}

// QueryAuditEntries queries audit entries with optional filters.
func (s *SQLiteStorage) QueryAuditEntries(filters AuditFilters) ([]core.AuditEntry, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	query := "SELECT data FROM audit_log WHERE 1=1"
	args := make([]any, 0)

	if filters.RootPrincipal != "" {
		query += " AND root_principal = ?"
		args = append(args, filters.RootPrincipal)
	}
	if filters.Capability != "" {
		query += " AND capability = ?"
		args = append(args, filters.Capability)
	}
	if filters.Since != "" {
		query += " AND timestamp >= ?"
		args = append(args, filters.Since)
	}
	if filters.InvocationID != "" {
		query += " AND invocation_id = ?"
		args = append(args, filters.InvocationID)
	}
	if filters.ClientReferenceID != "" {
		query += " AND client_reference_id = ?"
		args = append(args, filters.ClientReferenceID)
	}

	query += " ORDER BY sequence_number DESC"

	limit := filters.Limit
	if limit <= 0 {
		limit = 50
	}
	query += " LIMIT ?"
	args = append(args, limit)

	rows, err := s.db.Query(query, args...)
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
func (s *SQLiteStorage) GetMaxAuditSequence() (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	var maxSeq sql.NullInt64
	err := s.db.QueryRow("SELECT MAX(sequence_number) FROM audit_log").Scan(&maxSeq)
	if err != nil {
		return 0, err
	}
	if !maxSeq.Valid {
		return 0, nil
	}
	return int(maxSeq.Int64), nil
}

// GetAuditEntriesRange returns audit entries with sequence_number between first and last (inclusive).
func (s *SQLiteStorage) GetAuditEntriesRange(first, last int) ([]core.AuditEntry, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	rows, err := s.db.Query(
		"SELECT data FROM audit_log WHERE sequence_number BETWEEN ? AND ? ORDER BY sequence_number ASC",
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
func (s *SQLiteStorage) UpdateAuditSignature(seqNum int, signature string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Update the signature column.
	_, err := s.db.Exec(
		"UPDATE audit_log SET signature = ? WHERE sequence_number = ?",
		signature, seqNum,
	)
	if err != nil {
		return err
	}

	// Also update the signature in the JSON data blob.
	var data string
	err = s.db.QueryRow("SELECT data FROM audit_log WHERE sequence_number = ?", seqNum).Scan(&data)
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
	_, err = s.db.Exec("UPDATE audit_log SET data = ? WHERE sequence_number = ?", string(updated), seqNum)
	return err
}

// --- Checkpoints ---

// StoreCheckpoint persists a checkpoint.
func (s *SQLiteStorage) StoreCheckpoint(cp *core.Checkpoint, signature string) error {
	data, err := json.Marshal(cp)
	if err != nil {
		return fmt.Errorf("marshal checkpoint: %w", err)
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	_, err = s.db.Exec(
		"INSERT INTO checkpoints (checkpoint_id, data, signature) VALUES (?, ?, ?)",
		cp.CheckpointID, string(data), signature,
	)
	return err
}

// ListCheckpoints returns checkpoints ordered by checkpoint_id, limited by count.
func (s *SQLiteStorage) ListCheckpoints(limit int) ([]core.Checkpoint, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if limit <= 0 {
		limit = 10
	}

	rows, err := s.db.Query(
		"SELECT data FROM checkpoints ORDER BY rowid ASC LIMIT ?", limit,
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
func (s *SQLiteStorage) GetCheckpointByID(id string) (*core.Checkpoint, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	var data string
	err := s.db.QueryRow(
		"SELECT data FROM checkpoints WHERE checkpoint_id = ?", id,
	).Scan(&data)
	if err == sql.ErrNoRows {
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
