package server

import (
	"crypto/sha256"
	"database/sql"
	"encoding/json"
	"fmt"
	"sort"
	"sync"
	"time"

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
	task_id TEXT,
	parent_invocation_id TEXT,
	upstream_service TEXT,
	approval_request_id TEXT,
	approval_grant_id TEXT,
	entry_type TEXT,
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
CREATE INDEX IF NOT EXISTS idx_audit_approval_request_id ON audit_log(approval_request_id);
CREATE INDEX IF NOT EXISTS idx_audit_approval_grant_id ON audit_log(approval_grant_id);

CREATE TABLE IF NOT EXISTS checkpoints (
	checkpoint_id TEXT PRIMARY KEY,
	data TEXT NOT NULL,
	signature TEXT NOT NULL
);

-- v0.23: approval requests
CREATE TABLE IF NOT EXISTS approval_requests (
	approval_request_id TEXT PRIMARY KEY,
	capability TEXT NOT NULL,
	scope TEXT NOT NULL,                      -- JSON array
	requester TEXT NOT NULL,                  -- JSON
	parent_invocation_id TEXT,
	preview TEXT NOT NULL,                    -- JSON
	preview_digest TEXT NOT NULL,
	requested_parameters TEXT NOT NULL,       -- JSON
	requested_parameters_digest TEXT NOT NULL,
	grant_policy TEXT NOT NULL,               -- JSON
	status TEXT NOT NULL CHECK (status IN ('pending','approved','denied','expired')),
	approver TEXT,                            -- JSON, null until decided
	decided_at TEXT,
	created_at TEXT NOT NULL,
	expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_expires ON approval_requests(expires_at);

-- v0.23: approval grants. UNIQUE on approval_request_id is defense-in-depth
-- against concurrent approvals; the atomic UPDATE+INSERT is the boundary.
CREATE TABLE IF NOT EXISTS approval_grants (
	grant_id TEXT PRIMARY KEY,
	approval_request_id TEXT NOT NULL UNIQUE,
	grant_type TEXT NOT NULL CHECK (grant_type IN ('one_time','session_bound')),
	capability TEXT NOT NULL,
	scope TEXT NOT NULL,                      -- JSON array
	approved_parameters_digest TEXT NOT NULL,
	preview_digest TEXT NOT NULL,
	requester TEXT NOT NULL,                  -- JSON
	approver TEXT NOT NULL,                   -- JSON
	issued_at TEXT NOT NULL,
	expires_at TEXT NOT NULL,
	max_uses INTEGER NOT NULL CHECK (max_uses >= 1),
	use_count INTEGER NOT NULL DEFAULT 0,
	session_id TEXT,
	signature TEXT NOT NULL,
	FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id)
);
CREATE INDEX IF NOT EXISTS idx_grants_approval_request_id ON approval_grants(approval_request_id);
CREATE INDEX IF NOT EXISTS idx_grants_expires ON approval_grants(expires_at);
`

// sqliteAuditMigrations adds v0.23 audit-log columns to pre-existing
// databases. Each statement is run independently so a failed ALTER (because
// the column already exists) doesn't abort the rest.
var sqliteAuditMigrations = []string{
	"ALTER TABLE audit_log ADD COLUMN approval_request_id TEXT",
	"ALTER TABLE audit_log ADD COLUMN approval_grant_id TEXT",
	"ALTER TABLE audit_log ADD COLUMN entry_type TEXT",
	"ALTER TABLE delegation_tokens ADD COLUMN session_id TEXT",
}

// SQLiteStorage implements Storage using modernc.org/sqlite.
type SQLiteStorage struct {
	db              *sql.DB
	mu              sync.Mutex
	exclusiveLeases map[string]leaseEntry
	leaderLeases    map[string]leaseEntry
}

// leaseEntry tracks holder and expiry for in-memory leases.
type leaseEntry struct {
	holder    string
	expiresAt time.Time
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

	// Idempotent ALTER TABLE migrations for pre-existing databases. We
	// ignore "duplicate column" errors so already-migrated databases boot
	// cleanly. SQLite has no IF NOT EXISTS on ADD COLUMN.
	for _, stmt := range sqliteAuditMigrations {
		_, _ = db.Exec(stmt)
	}

	return &SQLiteStorage{
		db:              db,
		exclusiveLeases: make(map[string]leaseEntry),
		leaderLeases:    make(map[string]leaseEntry),
	}, nil
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
		 invocation_id, client_reference_id, task_id, parent_invocation_id,
		 upstream_service, approval_request_id, approval_grant_id, entry_type,
		 data, previous_hash, signature)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		entry.Timestamp,
		entry.Capability,
		entry.TokenID,
		entry.RootPrincipal,
		entry.InvocationID,
		entry.ClientReferenceID,
		entry.TaskID,
		entry.ParentInvocationID,
		entry.UpstreamService,
		nilIfEmpty(entry.ApprovalRequestID),
		nilIfEmpty(entry.ApprovalGrantID),
		nilIfEmpty(entry.EntryType),
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
	if filters.TaskID != "" {
		query += " AND task_id = ?"
		args = append(args, filters.TaskID)
	}
	if filters.ParentInvocationID != "" {
		query += " AND parent_invocation_id = ?"
		args = append(args, filters.ParentInvocationID)
	}
	if filters.ApprovalRequestID != "" {
		query += " AND approval_request_id = ?"
		args = append(args, filters.ApprovalRequestID)
	}
	if filters.ApprovalGrantID != "" {
		query += " AND approval_grant_id = ?"
		args = append(args, filters.ApprovalGrantID)
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

// --- Retention ---

// DeleteExpiredAuditEntries deletes audit entries whose expires_at in the JSON data is before now.
// Since the Go SQLite backend stores entries as a JSON data blob, we parse and filter.
func (s *SQLiteStorage) DeleteExpiredAuditEntries(now string) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Find expired entries by scanning the data blobs.
	rows, err := s.db.Query("SELECT sequence_number, data FROM audit_log")
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	var toDelete []int
	for rows.Next() {
		var seqNum int
		var data string
		if err := rows.Scan(&seqNum, &data); err != nil {
			return 0, err
		}
		var entry core.AuditEntry
		if err := json.Unmarshal([]byte(data), &entry); err != nil {
			continue
		}
		if entry.ExpiresAt != "" && entry.ExpiresAt < now {
			toDelete = append(toDelete, seqNum)
		}
	}
	if err := rows.Err(); err != nil {
		return 0, err
	}

	for _, seqNum := range toDelete {
		if _, err := s.db.Exec("DELETE FROM audit_log WHERE sequence_number = ?", seqNum); err != nil {
			return 0, err
		}
	}
	return len(toDelete), nil
}

// --- Leases (in-memory, single-process) ---

// TryAcquireExclusive attempts to acquire an exclusive lease. Returns true if acquired.
func (s *SQLiteStorage) TryAcquireExclusive(key, holder string, ttlSeconds int) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now().UTC()
	existing, ok := s.exclusiveLeases[key]
	if !ok || existing.expiresAt.Before(now) || existing.holder == holder {
		s.exclusiveLeases[key] = leaseEntry{
			holder:    holder,
			expiresAt: now.Add(time.Duration(ttlSeconds) * time.Second),
		}
		return true, nil
	}
	return false, nil
}

// ReleaseExclusive releases an exclusive lease if held by the given holder.
func (s *SQLiteStorage) ReleaseExclusive(key, holder string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	existing, ok := s.exclusiveLeases[key]
	if ok && existing.holder == holder {
		delete(s.exclusiveLeases, key)
	}
	return nil
}

// TryAcquireLeader attempts to acquire a leader lease for a background role.
func (s *SQLiteStorage) TryAcquireLeader(role, holder string, ttlSeconds int) (bool, error) {
	return s.TryAcquireExclusive("leader:"+role, holder, ttlSeconds)
}

// ReleaseLeader releases a leader lease if held by the given holder.
func (s *SQLiteStorage) ReleaseLeader(role, holder string) error {
	return s.ReleaseExclusive("leader:"+role, holder)
}

// nilIfEmpty returns nil for empty strings, else the string. SQLite stores
// nil as NULL — nicer for filter queries than empty strings.
func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// --- v0.23: Approval requests + grants ---

// StoreApprovalRequest persists a new ApprovalRequest. Idempotent on
// approval_request_id when content is identical; conflicting re-store with
// the same id is an error. SPEC.md §4.7.
func (s *SQLiteStorage) StoreApprovalRequest(req *core.ApprovalRequest) error {
	scopeJSON, _ := json.Marshal(req.Scope)
	requesterJSON, _ := json.Marshal(req.Requester)
	previewJSON, _ := json.Marshal(req.Preview)
	paramsJSON, _ := json.Marshal(req.RequestedParameters)
	policyJSON, _ := json.Marshal(req.GrantPolicy)
	var approverJSON []byte
	if req.Approver != nil {
		approverJSON, _ = json.Marshal(req.Approver)
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	// Idempotency: SELECT-then-INSERT under the same lock.
	existing, err := s.loadApprovalRequestLocked(req.ApprovalRequestID)
	if err != nil {
		return err
	}
	if existing != nil {
		if !approvalRequestsEqual(existing, req) {
			return fmt.Errorf("approval_request_id %q already stored with different content", req.ApprovalRequestID)
		}
		return nil
	}

	_, err = s.db.Exec(
		`INSERT INTO approval_requests (
			approval_request_id, capability, scope, requester, parent_invocation_id,
			preview, preview_digest, requested_parameters, requested_parameters_digest,
			grant_policy, status, approver, decided_at, created_at, expires_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		req.ApprovalRequestID,
		req.Capability,
		string(scopeJSON),
		string(requesterJSON),
		nilIfEmpty(req.ParentInvocationID),
		string(previewJSON),
		req.PreviewDigest,
		string(paramsJSON),
		req.RequestedParametersDigest,
		string(policyJSON),
		req.Status,
		nullableJSON(approverJSON),
		nilIfEmpty(req.DecidedAt),
		req.CreatedAt,
		req.ExpiresAt,
	)
	return err
}

// GetApprovalRequest loads an ApprovalRequest by id, or nil if not found.
func (s *SQLiteStorage) GetApprovalRequest(id string) (*core.ApprovalRequest, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.loadApprovalRequestLocked(id)
}

func (s *SQLiteStorage) loadApprovalRequestLocked(id string) (*core.ApprovalRequest, error) {
	row := s.db.QueryRow(
		`SELECT approval_request_id, capability, scope, requester, parent_invocation_id,
		        preview, preview_digest, requested_parameters, requested_parameters_digest,
		        grant_policy, status, approver, decided_at, created_at, expires_at
		 FROM approval_requests WHERE approval_request_id = ?`, id,
	)
	return scanApprovalRequest(row)
}

type approvalRowScanner interface {
	Scan(dest ...any) error
}

func scanApprovalRequest(row approvalRowScanner) (*core.ApprovalRequest, error) {
	var (
		id, capability, scopeJSON, requesterJSON, previewJSON, paramsJSON, policyJSON, status, createdAt, expiresAt string
		previewDigest, paramsDigest                                                                                  string
		parentInvID, approverJSON, decidedAt                                                                         sql.NullString
	)
	err := row.Scan(
		&id, &capability, &scopeJSON, &requesterJSON, &parentInvID,
		&previewJSON, &previewDigest, &paramsJSON, &paramsDigest,
		&policyJSON, &status, &approverJSON, &decidedAt, &createdAt, &expiresAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	req := &core.ApprovalRequest{
		ApprovalRequestID:         id,
		Capability:                capability,
		PreviewDigest:             previewDigest,
		RequestedParametersDigest: paramsDigest,
		Status:                    status,
		CreatedAt:                 createdAt,
		ExpiresAt:                 expiresAt,
	}
	if parentInvID.Valid {
		req.ParentInvocationID = parentInvID.String
	}
	if decidedAt.Valid {
		req.DecidedAt = decidedAt.String
	}
	_ = json.Unmarshal([]byte(scopeJSON), &req.Scope)
	_ = json.Unmarshal([]byte(requesterJSON), &req.Requester)
	_ = json.Unmarshal([]byte(previewJSON), &req.Preview)
	_ = json.Unmarshal([]byte(paramsJSON), &req.RequestedParameters)
	_ = json.Unmarshal([]byte(policyJSON), &req.GrantPolicy)
	if approverJSON.Valid && approverJSON.String != "" {
		_ = json.Unmarshal([]byte(approverJSON.String), &req.Approver)
	}
	return req, nil
}

// ApproveRequestAndStoreGrant atomically transitions an ApprovalRequest to
// approved and persists the signed ApprovalGrant. Decision 0.9a: this is
// the security boundary — UPDATE+INSERT happen in a single transaction.
func (s *SQLiteStorage) ApproveRequestAndStoreGrant(
	approvalRequestID string,
	grant *core.ApprovalGrant,
	approver map[string]any,
	decidedAtIso string,
	nowIso string,
) (ApprovalDecisionResult, error) {
	approverJSON, _ := json.Marshal(approver)
	scopeJSON, _ := json.Marshal(grant.Scope)
	requesterJSON, _ := json.Marshal(grant.Requester)
	grantApproverJSON, _ := json.Marshal(grant.Approver)

	s.mu.Lock()
	defer s.mu.Unlock()

	tx, err := s.db.Begin()
	if err != nil {
		return ApprovalDecisionResult{}, fmt.Errorf("begin tx: %w", err)
	}
	rolled := false
	rollback := func() {
		if !rolled {
			_ = tx.Rollback()
			rolled = true
		}
	}
	defer rollback()

	res, err := tx.Exec(
		`UPDATE approval_requests
		 SET status = 'approved', approver = ?, decided_at = ?
		 WHERE approval_request_id = ?
		   AND status = 'pending'
		   AND expires_at > ?`,
		string(approverJSON), decidedAtIso, approvalRequestID, nowIso,
	)
	if err != nil {
		return ApprovalDecisionResult{}, fmt.Errorf("update request: %w", err)
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		// Disambiguate: not found vs expired vs already decided.
		var status, expiresAt string
		err := tx.QueryRow(
			"SELECT status, expires_at FROM approval_requests WHERE approval_request_id = ?",
			approvalRequestID,
		).Scan(&status, &expiresAt)
		rollback()
		if err == sql.ErrNoRows {
			return ApprovalDecisionResult{OK: false, Reason: "approval_request_not_found"}, nil
		}
		if err != nil {
			return ApprovalDecisionResult{}, err
		}
		if expiresAt <= nowIso {
			return ApprovalDecisionResult{OK: false, Reason: "approval_request_expired"}, nil
		}
		return ApprovalDecisionResult{OK: false, Reason: "approval_request_already_decided"}, nil
	}

	_, err = tx.Exec(
		`INSERT INTO approval_grants (
			grant_id, approval_request_id, grant_type, capability, scope,
			approved_parameters_digest, preview_digest, requester, approver,
			issued_at, expires_at, max_uses, use_count, session_id, signature
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		grant.GrantID,
		grant.ApprovalRequestID,
		grant.GrantType,
		grant.Capability,
		string(scopeJSON),
		grant.ApprovedParametersDigest,
		grant.PreviewDigest,
		string(requesterJSON),
		string(grantApproverJSON),
		grant.IssuedAt,
		grant.ExpiresAt,
		grant.MaxUses,
		grant.UseCount,
		nilIfEmpty(grant.SessionID),
		grant.Signature,
	)
	if err != nil {
		// UNIQUE constraint on approval_request_id => concurrent approval.
		rollback()
		return ApprovalDecisionResult{OK: false, Reason: "approval_request_already_decided"}, nil
	}

	if err := tx.Commit(); err != nil {
		return ApprovalDecisionResult{}, fmt.Errorf("commit: %w", err)
	}
	rolled = true
	persisted := *grant
	return ApprovalDecisionResult{OK: true, Grant: &persisted}, nil
}

// StoreGrant inserts or replaces an ApprovalGrant — internal/test-only.
func (s *SQLiteStorage) StoreGrant(grant *core.ApprovalGrant) error {
	scopeJSON, _ := json.Marshal(grant.Scope)
	requesterJSON, _ := json.Marshal(grant.Requester)
	approverJSON, _ := json.Marshal(grant.Approver)

	s.mu.Lock()
	defer s.mu.Unlock()
	_, err := s.db.Exec(
		`INSERT OR REPLACE INTO approval_grants (
			grant_id, approval_request_id, grant_type, capability, scope,
			approved_parameters_digest, preview_digest, requester, approver,
			issued_at, expires_at, max_uses, use_count, session_id, signature
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		grant.GrantID,
		grant.ApprovalRequestID,
		grant.GrantType,
		grant.Capability,
		string(scopeJSON),
		grant.ApprovedParametersDigest,
		grant.PreviewDigest,
		string(requesterJSON),
		string(approverJSON),
		grant.IssuedAt,
		grant.ExpiresAt,
		grant.MaxUses,
		grant.UseCount,
		nilIfEmpty(grant.SessionID),
		grant.Signature,
	)
	return err
}

// GetGrant loads an ApprovalGrant by grant_id, or nil if not found.
func (s *SQLiteStorage) GetGrant(grantID string) (*core.ApprovalGrant, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.loadGrantLocked(grantID)
}

func (s *SQLiteStorage) loadGrantLocked(grantID string) (*core.ApprovalGrant, error) {
	row := s.db.QueryRow(
		`SELECT grant_id, approval_request_id, grant_type, capability, scope,
		        approved_parameters_digest, preview_digest, requester, approver,
		        issued_at, expires_at, max_uses, use_count, session_id, signature
		 FROM approval_grants WHERE grant_id = ?`, grantID,
	)
	return scanGrant(row)
}

func scanGrant(row approvalRowScanner) (*core.ApprovalGrant, error) {
	var (
		id, reqID, grantType, capability, scopeJSON, paramsDigest, previewDigest, requesterJSON, approverJSON, issuedAt, expiresAt, signature string
		maxUses, useCount                                                                                                                      int
		sessionID                                                                                                                              sql.NullString
	)
	err := row.Scan(
		&id, &reqID, &grantType, &capability, &scopeJSON,
		&paramsDigest, &previewDigest, &requesterJSON, &approverJSON,
		&issuedAt, &expiresAt, &maxUses, &useCount, &sessionID, &signature,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	g := &core.ApprovalGrant{
		GrantID:                  id,
		ApprovalRequestID:        reqID,
		GrantType:                grantType,
		Capability:               capability,
		ApprovedParametersDigest: paramsDigest,
		PreviewDigest:            previewDigest,
		IssuedAt:                 issuedAt,
		ExpiresAt:                expiresAt,
		MaxUses:                  maxUses,
		UseCount:                 useCount,
		Signature:                signature,
	}
	if sessionID.Valid {
		g.SessionID = sessionID.String
	}
	_ = json.Unmarshal([]byte(scopeJSON), &g.Scope)
	_ = json.Unmarshal([]byte(requesterJSON), &g.Requester)
	_ = json.Unmarshal([]byte(approverJSON), &g.Approver)
	return g, nil
}

// TryReserveGrant atomically increments use_count if the grant is still
// usable. SPEC.md §4.8 Phase B.
func (s *SQLiteStorage) TryReserveGrant(grantID string, nowIso string) (GrantReservationResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	tx, err := s.db.Begin()
	if err != nil {
		return GrantReservationResult{}, fmt.Errorf("begin tx: %w", err)
	}
	rolled := false
	rollback := func() {
		if !rolled {
			_ = tx.Rollback()
			rolled = true
		}
	}
	defer rollback()

	res, err := tx.Exec(
		`UPDATE approval_grants
		 SET use_count = use_count + 1
		 WHERE grant_id = ?
		   AND use_count < max_uses
		   AND expires_at > ?`,
		grantID, nowIso,
	)
	if err != nil {
		return GrantReservationResult{}, fmt.Errorf("update grant: %w", err)
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		var useCount, maxUses int
		var expiresAt string
		err := tx.QueryRow(
			"SELECT use_count, max_uses, expires_at FROM approval_grants WHERE grant_id = ?",
			grantID,
		).Scan(&useCount, &maxUses, &expiresAt)
		rollback()
		if err == sql.ErrNoRows {
			return GrantReservationResult{OK: false, Reason: "grant_not_found"}, nil
		}
		if err != nil {
			return GrantReservationResult{}, err
		}
		if expiresAt <= nowIso {
			return GrantReservationResult{OK: false, Reason: "grant_expired"}, nil
		}
		if useCount >= maxUses {
			return GrantReservationResult{OK: false, Reason: "grant_consumed"}, nil
		}
		return GrantReservationResult{OK: false, Reason: "grant_not_found"}, nil
	}

	if err := tx.Commit(); err != nil {
		return GrantReservationResult{}, fmt.Errorf("commit: %w", err)
	}
	rolled = true
	g, err := s.loadGrantLocked(grantID)
	if err != nil {
		return GrantReservationResult{}, err
	}
	return GrantReservationResult{OK: true, Grant: g}, nil
}

// nullableJSON returns nil for an empty byte slice, else the JSON bytes as
// a string. Used to map Go nil into SQLite NULL for optional JSON columns.
func nullableJSON(b []byte) any {
	if len(b) == 0 {
		return nil
	}
	return string(b)
}

// approvalRequestsEqual compares two ApprovalRequest pointers for content
// equality via canonical JSON. Used by the idempotent StoreApprovalRequest.
func approvalRequestsEqual(a, b *core.ApprovalRequest) bool {
	aJSON, _ := json.Marshal(a)
	bJSON, _ := json.Marshal(b)
	return string(aJSON) == string(bJSON)
}
