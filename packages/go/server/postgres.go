package server

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

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
	task_id TEXT,
	parent_invocation_id TEXT,
	upstream_service TEXT,
	data TEXT NOT NULL,
	previous_hash TEXT NOT NULL,
	signature TEXT NOT NULL DEFAULT ''
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

-- v0.23: approval requests
CREATE TABLE IF NOT EXISTS approval_requests (
	approval_request_id TEXT PRIMARY KEY,
	capability TEXT NOT NULL,
	scope TEXT NOT NULL,
	requester TEXT NOT NULL,
	parent_invocation_id TEXT,
	preview TEXT NOT NULL,
	preview_digest TEXT NOT NULL,
	requested_parameters TEXT NOT NULL,
	requested_parameters_digest TEXT NOT NULL,
	grant_policy TEXT NOT NULL,
	status TEXT NOT NULL CHECK (status IN ('pending','approved','denied','expired')),
	approver TEXT,
	decided_at TEXT,
	created_at TEXT NOT NULL,
	expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_expires ON approval_requests(expires_at);

-- v0.23: approval grants. UNIQUE on approval_request_id is defense-in-depth.
CREATE TABLE IF NOT EXISTS approval_grants (
	grant_id TEXT PRIMARY KEY,
	approval_request_id TEXT NOT NULL UNIQUE,
	grant_type TEXT NOT NULL CHECK (grant_type IN ('one_time','session_bound')),
	capability TEXT NOT NULL,
	scope TEXT NOT NULL,
	approved_parameters_digest TEXT NOT NULL,
	preview_digest TEXT NOT NULL,
	requester TEXT NOT NULL,
	approver TEXT NOT NULL,
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

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS approval_request_id TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS approval_grant_id TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS entry_type TEXT;
ALTER TABLE delegation_tokens ADD COLUMN IF NOT EXISTS session_id TEXT;
CREATE INDEX IF NOT EXISTS idx_audit_approval_request_id ON audit_log(approval_request_id);
CREATE INDEX IF NOT EXISTS idx_audit_approval_grant_id ON audit_log(approval_grant_id);
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
		 invocation_id, client_reference_id, task_id, parent_invocation_id,
		 upstream_service, approval_request_id, approval_grant_id, entry_type,
		 data, previous_hash, signature)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)`,
		newSeqNum,
		entry.Timestamp,
		entry.Capability,
		entry.TokenID,
		entry.RootPrincipal,
		entry.InvocationID,
		entry.ClientReferenceID,
		entry.TaskID,
		entry.ParentInvocationID,
		entry.UpstreamService,
		nullIfEmpty(entry.ApprovalRequestID),
		nullIfEmpty(entry.ApprovalGrantID),
		nullIfEmpty(entry.EntryType),
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
	if filters.TaskID != "" {
		query += " AND task_id = $" + strconv.Itoa(argIdx)
		args = append(args, filters.TaskID)
		argIdx++
	}
	if filters.ParentInvocationID != "" {
		query += " AND parent_invocation_id = $" + strconv.Itoa(argIdx)
		args = append(args, filters.ParentInvocationID)
		argIdx++
	}
	if filters.ApprovalRequestID != "" {
		query += " AND approval_request_id = $" + strconv.Itoa(argIdx)
		args = append(args, filters.ApprovalRequestID)
		argIdx++
	}
	if filters.ApprovalGrantID != "" {
		query += " AND approval_grant_id = $" + strconv.Itoa(argIdx)
		args = append(args, filters.ApprovalGrantID)
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

// --- Retention ---

// DeleteExpiredAuditEntries deletes audit entries whose expires_at in the JSON data is before now.
func (s *PostgresStorage) DeleteExpiredAuditEntries(now string) (int, error) {
	// Scan all entries and check the JSON data blob for expires_at.
	rows, err := s.pool.Query(context.Background(),
		"SELECT sequence_number, data FROM audit_log",
	)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	var toDelete []int64
	for rows.Next() {
		var seqNum int64
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
		if _, err := s.pool.Exec(context.Background(),
			"DELETE FROM audit_log WHERE sequence_number = $1", seqNum,
		); err != nil {
			return 0, err
		}
	}
	return len(toDelete), nil
}

// --- Leases ---

// TryAcquireExclusive attempts to acquire an exclusive lease. Returns true if acquired.
func (s *PostgresStorage) TryAcquireExclusive(key, holder string, ttlSeconds int) (bool, error) {
	now := time.Now().UTC()
	expires := now.Add(time.Duration(ttlSeconds) * time.Second)
	tag, err := s.pool.Exec(context.Background(),
		`INSERT INTO exclusive_leases (key, holder, expires_at)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (key) DO UPDATE
		     SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
		     WHERE exclusive_leases.expires_at < $4
		        OR exclusive_leases.holder = $5`,
		key, holder, expires, now, holder,
	)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// ReleaseExclusive releases an exclusive lease if held by the given holder.
func (s *PostgresStorage) ReleaseExclusive(key, holder string) error {
	_, err := s.pool.Exec(context.Background(),
		"DELETE FROM exclusive_leases WHERE key = $1 AND holder = $2",
		key, holder,
	)
	return err
}

// TryAcquireLeader attempts to acquire a leader lease for a background role.
func (s *PostgresStorage) TryAcquireLeader(role, holder string, ttlSeconds int) (bool, error) {
	now := time.Now().UTC()
	expires := now.Add(time.Duration(ttlSeconds) * time.Second)
	tag, err := s.pool.Exec(context.Background(),
		`INSERT INTO leader_leases (role, holder, expires_at)
		 VALUES ($1, $2, $3)
		 ON CONFLICT (role) DO UPDATE
		     SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
		     WHERE leader_leases.expires_at < $4
		        OR leader_leases.holder = $5`,
		role, holder, expires, now, holder,
	)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// ReleaseLeader releases a leader lease if held by the given holder.
func (s *PostgresStorage) ReleaseLeader(role, holder string) error {
	_, err := s.pool.Exec(context.Background(),
		"DELETE FROM leader_leases WHERE role = $1 AND holder = $2",
		role, holder,
	)
	return err
}

// nullIfEmpty maps "" → nil so optional TEXT columns receive SQL NULL.
func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// nullableJSONBytes maps an empty/nil byte slice to NULL, else the JSON
// content as a string. Used for optional JSON columns.
func nullableJSONBytes(b []byte) any {
	if len(b) == 0 {
		return nil
	}
	return string(b)
}

// --- v0.23: Approval requests + grants ---

// StoreApprovalRequest persists a new ApprovalRequest. Idempotent on
// approval_request_id when content is identical.
func (s *PostgresStorage) StoreApprovalRequest(req *core.ApprovalRequest) error {
	scopeJSON, _ := json.Marshal(req.Scope)
	requesterJSON, _ := json.Marshal(req.Requester)
	previewJSON, _ := json.Marshal(req.Preview)
	paramsJSON, _ := json.Marshal(req.RequestedParameters)
	policyJSON, _ := json.Marshal(req.GrantPolicy)
	var approverJSON []byte
	if req.Approver != nil {
		approverJSON, _ = json.Marshal(req.Approver)
	}

	existing, err := s.GetApprovalRequest(req.ApprovalRequestID)
	if err != nil {
		return err
	}
	if existing != nil {
		eJSON, _ := json.Marshal(existing)
		nJSON, _ := json.Marshal(req)
		if string(eJSON) != string(nJSON) {
			return fmt.Errorf("approval_request_id %q already stored with different content", req.ApprovalRequestID)
		}
		return nil
	}

	_, err = s.pool.Exec(context.Background(),
		`INSERT INTO approval_requests (
			approval_request_id, capability, scope, requester, parent_invocation_id,
			preview, preview_digest, requested_parameters, requested_parameters_digest,
			grant_policy, status, approver, decided_at, created_at, expires_at
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`,
		req.ApprovalRequestID,
		req.Capability,
		string(scopeJSON),
		string(requesterJSON),
		nullIfEmpty(req.ParentInvocationID),
		string(previewJSON),
		req.PreviewDigest,
		string(paramsJSON),
		req.RequestedParametersDigest,
		string(policyJSON),
		req.Status,
		nullableJSONBytes(approverJSON),
		nullIfEmpty(req.DecidedAt),
		req.CreatedAt,
		req.ExpiresAt,
	)
	return err
}

// GetApprovalRequest loads an ApprovalRequest by id, or nil if not found.
func (s *PostgresStorage) GetApprovalRequest(id string) (*core.ApprovalRequest, error) {
	row := s.pool.QueryRow(context.Background(),
		`SELECT approval_request_id, capability, scope, requester, parent_invocation_id,
		        preview, preview_digest, requested_parameters, requested_parameters_digest,
		        grant_policy, status, approver, decided_at, created_at, expires_at
		 FROM approval_requests WHERE approval_request_id = $1`, id,
	)
	return scanApprovalRequestPgx(row)
}

func scanApprovalRequestPgx(row pgx.Row) (*core.ApprovalRequest, error) {
	var (
		id, capability, scopeJSON, requesterJSON, previewJSON, paramsJSON, policyJSON, status, createdAt, expiresAt string
		previewDigest, paramsDigest                                                                                  string
		parentInvID, approverJSON, decidedAt                                                                         *string
	)
	err := row.Scan(
		&id, &capability, &scopeJSON, &requesterJSON, &parentInvID,
		&previewJSON, &previewDigest, &paramsJSON, &paramsDigest,
		&policyJSON, &status, &approverJSON, &decidedAt, &createdAt, &expiresAt,
	)
	if err == pgx.ErrNoRows {
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
	if parentInvID != nil {
		req.ParentInvocationID = *parentInvID
	}
	if decidedAt != nil {
		req.DecidedAt = *decidedAt
	}
	_ = json.Unmarshal([]byte(scopeJSON), &req.Scope)
	_ = json.Unmarshal([]byte(requesterJSON), &req.Requester)
	_ = json.Unmarshal([]byte(previewJSON), &req.Preview)
	_ = json.Unmarshal([]byte(paramsJSON), &req.RequestedParameters)
	_ = json.Unmarshal([]byte(policyJSON), &req.GrantPolicy)
	if approverJSON != nil && *approverJSON != "" {
		_ = json.Unmarshal([]byte(*approverJSON), &req.Approver)
	}
	return req, nil
}

// ApproveRequestAndStoreGrant atomically transitions to approved and stores
// the signed grant in one transaction.
func (s *PostgresStorage) ApproveRequestAndStoreGrant(
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

	ctx := context.Background()
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return ApprovalDecisionResult{}, fmt.Errorf("begin tx: %w", err)
	}
	rolled := false
	rollback := func() {
		if !rolled {
			_ = tx.Rollback(ctx)
			rolled = true
		}
	}
	defer rollback()

	tag, err := tx.Exec(ctx,
		`UPDATE approval_requests
		 SET status = 'approved', approver = $1, decided_at = $2
		 WHERE approval_request_id = $3
		   AND status = 'pending'
		   AND expires_at > $4`,
		string(approverJSON), decidedAtIso, approvalRequestID, nowIso,
	)
	if err != nil {
		return ApprovalDecisionResult{}, fmt.Errorf("update request: %w", err)
	}
	if tag.RowsAffected() == 0 {
		var status, expiresAt string
		err := tx.QueryRow(ctx,
			"SELECT status, expires_at FROM approval_requests WHERE approval_request_id = $1",
			approvalRequestID,
		).Scan(&status, &expiresAt)
		rollback()
		if err == pgx.ErrNoRows {
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

	_, err = tx.Exec(ctx,
		`INSERT INTO approval_grants (
			grant_id, approval_request_id, grant_type, capability, scope,
			approved_parameters_digest, preview_digest, requester, approver,
			issued_at, expires_at, max_uses, use_count, session_id, signature
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`,
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
		nullIfEmpty(grant.SessionID),
		grant.Signature,
	)
	if err != nil {
		// UNIQUE on approval_request_id means another approver got there first.
		rollback()
		return ApprovalDecisionResult{OK: false, Reason: "approval_request_already_decided"}, nil
	}

	if err := tx.Commit(ctx); err != nil {
		return ApprovalDecisionResult{}, fmt.Errorf("commit: %w", err)
	}
	rolled = true
	persisted := *grant
	return ApprovalDecisionResult{OK: true, Grant: &persisted}, nil
}

// StoreGrant inserts or replaces a grant — internal/test-only.
func (s *PostgresStorage) StoreGrant(grant *core.ApprovalGrant) error {
	scopeJSON, _ := json.Marshal(grant.Scope)
	requesterJSON, _ := json.Marshal(grant.Requester)
	approverJSON, _ := json.Marshal(grant.Approver)
	_, err := s.pool.Exec(context.Background(),
		`INSERT INTO approval_grants (
			grant_id, approval_request_id, grant_type, capability, scope,
			approved_parameters_digest, preview_digest, requester, approver,
			issued_at, expires_at, max_uses, use_count, session_id, signature
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
		 ON CONFLICT (grant_id) DO UPDATE SET
		     use_count = EXCLUDED.use_count, signature = EXCLUDED.signature`,
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
		nullIfEmpty(grant.SessionID),
		grant.Signature,
	)
	return err
}

// GetGrant loads a grant by grant_id, or nil if not found.
func (s *PostgresStorage) GetGrant(grantID string) (*core.ApprovalGrant, error) {
	row := s.pool.QueryRow(context.Background(),
		`SELECT grant_id, approval_request_id, grant_type, capability, scope,
		        approved_parameters_digest, preview_digest, requester, approver,
		        issued_at, expires_at, max_uses, use_count, session_id, signature
		 FROM approval_grants WHERE grant_id = $1`, grantID,
	)
	return scanGrantPgx(row)
}

func scanGrantPgx(row pgx.Row) (*core.ApprovalGrant, error) {
	var (
		id, reqID, grantType, capability, scopeJSON, paramsDigest, previewDigest, requesterJSON, approverJSON, issuedAt, expiresAt, signature string
		maxUses, useCount                                                                                                                      int
		sessionID                                                                                                                              *string
	)
	err := row.Scan(
		&id, &reqID, &grantType, &capability, &scopeJSON,
		&paramsDigest, &previewDigest, &requesterJSON, &approverJSON,
		&issuedAt, &expiresAt, &maxUses, &useCount, &sessionID, &signature,
	)
	if err == pgx.ErrNoRows {
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
	if sessionID != nil {
		g.SessionID = *sessionID
	}
	_ = json.Unmarshal([]byte(scopeJSON), &g.Scope)
	_ = json.Unmarshal([]byte(requesterJSON), &g.Requester)
	_ = json.Unmarshal([]byte(approverJSON), &g.Approver)
	return g, nil
}

// TryReserveGrant atomically increments use_count if the grant is usable.
// SPEC.md §4.8 Phase B.
func (s *PostgresStorage) TryReserveGrant(grantID string, nowIso string) (GrantReservationResult, error) {
	ctx := context.Background()
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return GrantReservationResult{}, fmt.Errorf("begin tx: %w", err)
	}
	rolled := false
	rollback := func() {
		if !rolled {
			_ = tx.Rollback(ctx)
			rolled = true
		}
	}
	defer rollback()

	tag, err := tx.Exec(ctx,
		`UPDATE approval_grants
		 SET use_count = use_count + 1
		 WHERE grant_id = $1
		   AND use_count < max_uses
		   AND expires_at > $2`,
		grantID, nowIso,
	)
	if err != nil {
		return GrantReservationResult{}, fmt.Errorf("update grant: %w", err)
	}
	if tag.RowsAffected() == 0 {
		var useCount, maxUses int
		var expiresAt string
		err := tx.QueryRow(ctx,
			"SELECT use_count, max_uses, expires_at FROM approval_grants WHERE grant_id = $1",
			grantID,
		).Scan(&useCount, &maxUses, &expiresAt)
		rollback()
		if err == pgx.ErrNoRows {
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

	if err := tx.Commit(ctx); err != nil {
		return GrantReservationResult{}, fmt.Errorf("commit: %w", err)
	}
	rolled = true
	g, err := s.GetGrant(grantID)
	if err != nil {
		return GrantReservationResult{}, err
	}
	return GrantReservationResult{OK: true, Grant: g}, nil
}
