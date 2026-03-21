package server

import (
	"context"
	"fmt"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/jackc/pgx/v5/pgxpool"
)

func getPostgresDSN(t *testing.T) string {
	dsn := os.Getenv("ANIP_TEST_POSTGRES_DSN")
	if dsn == "" {
		t.Skip("ANIP_TEST_POSTGRES_DSN not set, skipping Postgres tests")
	}
	return dsn
}

// cleanPostgres truncates all tables and re-inserts the append_head sentinel row.
func cleanPostgres(t *testing.T, dsn string) {
	t.Helper()
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("cleanPostgres connect: %v", err)
	}
	defer pool.Close()

	_, err = pool.Exec(context.Background(),
		"TRUNCATE delegation_tokens, audit_log, audit_append_head, checkpoints")
	if err != nil {
		t.Fatalf("cleanPostgres truncate: %v", err)
	}

	_, err = pool.Exec(context.Background(),
		"INSERT INTO audit_append_head (id, last_sequence_number, last_hash) VALUES (1, 0, '') ON CONFLICT (id) DO NOTHING")
	if err != nil {
		t.Fatalf("cleanPostgres re-insert sentinel: %v", err)
	}
}

func newPostgresStorage(t *testing.T) *PostgresStorage {
	t.Helper()
	dsn := getPostgresDSN(t)
	cleanPostgres(t, dsn)

	s, err := NewPostgresStorage(dsn)
	if err != nil {
		t.Fatalf("NewPostgresStorage: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func TestPostgresTokenCRUD(t *testing.T) {
	s := newPostgresStorage(t)

	token := &core.DelegationToken{
		TokenID:       "tok-pg-1",
		Issuer:        "test-service",
		Subject:       "agent:test",
		Scope:         []string{"travel.search"},
		Purpose:       core.Purpose{Capability: "search_flights", Parameters: map[string]any{}, TaskID: "task-1"},
		Expires:       time.Now().Add(2 * time.Hour).UTC().Format(time.RFC3339),
		Constraints:   core.DelegationConstraints{MaxDelegationDepth: 3, ConcurrentBranches: "allowed"},
		RootPrincipal: "human:test@example.com",
	}

	// Store.
	if err := s.StoreToken(token); err != nil {
		t.Fatalf("StoreToken: %v", err)
	}

	// Load.
	loaded, err := s.LoadToken("tok-pg-1")
	if err != nil {
		t.Fatalf("LoadToken: %v", err)
	}
	if loaded == nil {
		t.Fatal("LoadToken returned nil")
	}
	if loaded.TokenID != token.TokenID {
		t.Errorf("TokenID = %q, want %q", loaded.TokenID, token.TokenID)
	}
	if loaded.Subject != token.Subject {
		t.Errorf("Subject = %q, want %q", loaded.Subject, token.Subject)
	}
	if loaded.RootPrincipal != token.RootPrincipal {
		t.Errorf("RootPrincipal = %q, want %q", loaded.RootPrincipal, token.RootPrincipal)
	}
	if len(loaded.Scope) != 1 || loaded.Scope[0] != "travel.search" {
		t.Errorf("Scope = %v, want [travel.search]", loaded.Scope)
	}

	// Store again (upsert).
	token.Subject = "agent:updated"
	if err := s.StoreToken(token); err != nil {
		t.Fatalf("StoreToken (upsert): %v", err)
	}
	loaded, err = s.LoadToken("tok-pg-1")
	if err != nil {
		t.Fatalf("LoadToken after upsert: %v", err)
	}
	if loaded.Subject != "agent:updated" {
		t.Errorf("Subject after upsert = %q, want agent:updated", loaded.Subject)
	}

	// Load non-existent.
	missing, err := s.LoadToken("tok-nonexistent")
	if err != nil {
		t.Fatalf("LoadToken non-existent: %v", err)
	}
	if missing != nil {
		t.Error("expected nil for non-existent token")
	}
}

func TestPostgresAuditCRUD(t *testing.T) {
	s := newPostgresStorage(t)

	// Append first entry.
	entry1 := &core.AuditEntry{
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Capability:    "search_flights",
		TokenID:       "tok-1",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-aaa111",
		Success:       true,
	}
	appended1, err := s.AppendAuditEntry(entry1)
	if err != nil {
		t.Fatalf("AppendAuditEntry: %v", err)
	}
	if appended1.SequenceNumber != 1 {
		t.Errorf("SequenceNumber = %d, want 1", appended1.SequenceNumber)
	}
	if appended1.PreviousHash != "sha256:0" {
		t.Errorf("PreviousHash = %q, want sha256:0", appended1.PreviousHash)
	}

	// Append second entry.
	entry2 := &core.AuditEntry{
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Capability:    "book_flight",
		TokenID:       "tok-2",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-bbb222",
		Success:       false,
		FailureType:   "scope_insufficient",
	}
	appended2, err := s.AppendAuditEntry(entry2)
	if err != nil {
		t.Fatalf("AppendAuditEntry: %v", err)
	}
	if appended2.SequenceNumber != 2 {
		t.Errorf("SequenceNumber = %d, want 2", appended2.SequenceNumber)
	}
	if appended2.PreviousHash == "sha256:0" {
		t.Error("second entry should have a computed previous_hash, not sha256:0")
	}
	if !strings.HasPrefix(appended2.PreviousHash, "sha256:") {
		t.Errorf("PreviousHash should start with sha256:, got %q", appended2.PreviousHash)
	}

	// Query by capability.
	entries, err := s.QueryAuditEntries(AuditFilters{Capability: "search_flights"})
	if err != nil {
		t.Fatalf("QueryAuditEntries: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(entries))
	}
	if entries[0].Capability != "search_flights" {
		t.Errorf("Capability = %q, want search_flights", entries[0].Capability)
	}

	// Query by root_principal.
	entries, err = s.QueryAuditEntries(AuditFilters{RootPrincipal: "human:test@example.com"})
	if err != nil {
		t.Fatalf("QueryAuditEntries: %v", err)
	}
	if len(entries) != 2 {
		t.Errorf("expected 2 entries, got %d", len(entries))
	}

	// Max sequence.
	maxSeq, err := s.GetMaxAuditSequence()
	if err != nil {
		t.Fatalf("GetMaxAuditSequence: %v", err)
	}
	if maxSeq != 2 {
		t.Errorf("MaxAuditSequence = %d, want 2", maxSeq)
	}

	// Range query.
	rangeEntries, err := s.GetAuditEntriesRange(1, 2)
	if err != nil {
		t.Fatalf("GetAuditEntriesRange: %v", err)
	}
	if len(rangeEntries) != 2 {
		t.Errorf("expected 2 entries in range, got %d", len(rangeEntries))
	}
}

func TestPostgresAuditHashChain(t *testing.T) {
	s := newPostgresStorage(t)

	// Append 5 entries.
	for i := 0; i < 5; i++ {
		entry := &core.AuditEntry{
			Timestamp:     time.Now().UTC().Format(time.RFC3339),
			Capability:    fmt.Sprintf("cap_%d", i),
			TokenID:       fmt.Sprintf("tok-%d", i),
			RootPrincipal: "human:test@example.com",
			InvocationID:  fmt.Sprintf("inv-%03d", i),
			Success:       true,
		}
		_, err := s.AppendAuditEntry(entry)
		if err != nil {
			t.Fatalf("AppendAuditEntry entry %d: %v", i, err)
		}
	}

	// Retrieve all entries and verify the chain.
	entries, err := s.GetAuditEntriesRange(1, 5)
	if err != nil {
		t.Fatalf("GetAuditEntriesRange: %v", err)
	}
	if len(entries) != 5 {
		t.Fatalf("expected 5 entries, got %d", len(entries))
	}

	// First entry should have sha256:0 as previous hash.
	if entries[0].PreviousHash != "sha256:0" {
		t.Errorf("first entry previous_hash = %q, want sha256:0", entries[0].PreviousHash)
	}

	// Verify the chain: each entry's previous_hash should be the hash of the prior entry.
	for i := 1; i < len(entries); i++ {
		expectedHash := computeEntryHash(&entries[i-1])
		if entries[i].PreviousHash != expectedHash {
			t.Errorf("entry %d previous_hash = %q, expected %q", i, entries[i].PreviousHash, expectedHash)
		}
	}
}

func TestPostgresAuditQueryFilters(t *testing.T) {
	s := newPostgresStorage(t)

	// Entry with an older timestamp.
	entry1 := &core.AuditEntry{
		Timestamp:         "2025-01-01T00:00:00Z",
		Capability:        "old_cap",
		TokenID:           "tok-old",
		RootPrincipal:     "human:test@example.com",
		InvocationID:      "inv-old",
		ClientReferenceID: "ref-old",
		Success:           true,
	}
	if _, err := s.AppendAuditEntry(entry1); err != nil {
		t.Fatalf("AppendAuditEntry: %v", err)
	}

	// Entry with a newer timestamp.
	entry2 := &core.AuditEntry{
		Timestamp:         "2026-06-01T00:00:00Z",
		Capability:        "new_cap",
		TokenID:           "tok-new",
		RootPrincipal:     "human:test@example.com",
		InvocationID:      "inv-new",
		ClientReferenceID: "ref-new",
		Success:           true,
	}
	if _, err := s.AppendAuditEntry(entry2); err != nil {
		t.Fatalf("AppendAuditEntry: %v", err)
	}

	// Filter by since.
	entries, err := s.QueryAuditEntries(AuditFilters{Since: "2026-01-01T00:00:00Z"})
	if err != nil {
		t.Fatalf("QueryAuditEntries (since): %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry with since filter, got %d", len(entries))
	}
	if entries[0].Capability != "new_cap" {
		t.Errorf("Capability = %q, want new_cap", entries[0].Capability)
	}

	// Filter by invocation_id.
	entries, err = s.QueryAuditEntries(AuditFilters{InvocationID: "inv-old"})
	if err != nil {
		t.Fatalf("QueryAuditEntries (invocation_id): %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry with invocation_id filter, got %d", len(entries))
	}

	// Filter by client_reference_id.
	entries, err = s.QueryAuditEntries(AuditFilters{ClientReferenceID: "ref-new"})
	if err != nil {
		t.Fatalf("QueryAuditEntries (client_reference_id): %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry with client_reference_id filter, got %d", len(entries))
	}

	// Filter with limit.
	entries, err = s.QueryAuditEntries(AuditFilters{RootPrincipal: "human:test@example.com", Limit: 1})
	if err != nil {
		t.Fatalf("QueryAuditEntries (limit): %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry with limit=1, got %d", len(entries))
	}

	// Filter with no results.
	entries, err = s.QueryAuditEntries(AuditFilters{RootPrincipal: "human:other@example.com"})
	if err != nil {
		t.Fatalf("QueryAuditEntries (no results): %v", err)
	}
	if len(entries) != 0 {
		t.Errorf("expected 0 entries for different principal, got %d", len(entries))
	}
}

func TestPostgresUpdateSignature(t *testing.T) {
	s := newPostgresStorage(t)

	entry := &core.AuditEntry{
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Capability:    "test",
		TokenID:       "tok-sig",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-sig",
		Success:       true,
	}
	appended, err := s.AppendAuditEntry(entry)
	if err != nil {
		t.Fatalf("AppendAuditEntry: %v", err)
	}

	if err := s.UpdateAuditSignature(appended.SequenceNumber, "sig-test-123"); err != nil {
		t.Fatalf("UpdateAuditSignature: %v", err)
	}

	// Verify the signature was updated in the data blob.
	entries, err := s.GetAuditEntriesRange(1, 1)
	if err != nil {
		t.Fatalf("GetAuditEntriesRange: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(entries))
	}
	if entries[0].Signature != "sig-test-123" {
		t.Errorf("Signature = %q, want sig-test-123", entries[0].Signature)
	}
}

func TestPostgresCheckpointCRUD(t *testing.T) {
	s := newPostgresStorage(t)

	cp := &core.Checkpoint{
		Version:      "0.3",
		ServiceID:    "test-service",
		CheckpointID: "ckpt-1",
		Range:        map[string]int{"first_sequence": 1, "last_sequence": 5},
		MerkleRoot:   "sha256:abc123",
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
		EntryCount:   5,
	}

	if err := s.StoreCheckpoint(cp, "sig-ckpt-1"); err != nil {
		t.Fatalf("StoreCheckpoint: %v", err)
	}

	// List.
	cps, err := s.ListCheckpoints(10)
	if err != nil {
		t.Fatalf("ListCheckpoints: %v", err)
	}
	if len(cps) != 1 {
		t.Fatalf("expected 1 checkpoint, got %d", len(cps))
	}
	if cps[0].CheckpointID != "ckpt-1" {
		t.Errorf("CheckpointID = %q, want ckpt-1", cps[0].CheckpointID)
	}

	// Get by ID.
	loaded, err := s.GetCheckpointByID("ckpt-1")
	if err != nil {
		t.Fatalf("GetCheckpointByID: %v", err)
	}
	if loaded == nil {
		t.Fatal("GetCheckpointByID returned nil")
	}
	if loaded.MerkleRoot != "sha256:abc123" {
		t.Errorf("MerkleRoot = %q, want sha256:abc123", loaded.MerkleRoot)
	}
	if loaded.EntryCount != 5 {
		t.Errorf("EntryCount = %d, want 5", loaded.EntryCount)
	}

	// Get non-existent.
	missing, err := s.GetCheckpointByID("ckpt-nonexistent")
	if err != nil {
		t.Fatalf("GetCheckpointByID non-existent: %v", err)
	}
	if missing != nil {
		t.Error("expected nil for non-existent checkpoint")
	}

	// Multiple checkpoints for ordering.
	cp2 := &core.Checkpoint{
		Version:      "0.3",
		ServiceID:    "test-service",
		CheckpointID: "ckpt-2",
		Range:        map[string]int{"first_sequence": 6, "last_sequence": 10},
		MerkleRoot:   "sha256:def456",
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
		EntryCount:   5,
	}
	if err := s.StoreCheckpoint(cp2, "sig-ckpt-2"); err != nil {
		t.Fatalf("StoreCheckpoint: %v", err)
	}

	cps, err = s.ListCheckpoints(10)
	if err != nil {
		t.Fatalf("ListCheckpoints: %v", err)
	}
	if len(cps) != 2 {
		t.Fatalf("expected 2 checkpoints, got %d", len(cps))
	}
	// Should be ordered by checkpoint_id ASC.
	if cps[0].CheckpointID != "ckpt-1" || cps[1].CheckpointID != "ckpt-2" {
		t.Errorf("checkpoints not in expected order: %q, %q", cps[0].CheckpointID, cps[1].CheckpointID)
	}
}

func TestPostgresConcurrentAuditAppends(t *testing.T) {
	s := newPostgresStorage(t)

	const numGoroutines = 10
	const entriesPerGoroutine = 5

	var wg sync.WaitGroup
	errCh := make(chan error, numGoroutines*entriesPerGoroutine)

	for g := 0; g < numGoroutines; g++ {
		wg.Add(1)
		go func(goroutineID int) {
			defer wg.Done()
			for i := 0; i < entriesPerGoroutine; i++ {
				entry := &core.AuditEntry{
					Timestamp:     time.Now().UTC().Format(time.RFC3339),
					Capability:    fmt.Sprintf("cap_g%d_i%d", goroutineID, i),
					TokenID:       fmt.Sprintf("tok-g%d", goroutineID),
					RootPrincipal: "human:concurrent@example.com",
					InvocationID:  fmt.Sprintf("inv-g%d-i%d", goroutineID, i),
					Success:       true,
				}
				if _, err := s.AppendAuditEntry(entry); err != nil {
					errCh <- fmt.Errorf("goroutine %d, entry %d: %w", goroutineID, i, err)
					return
				}
			}
		}(g)
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		t.Fatalf("concurrent append error: %v", err)
	}

	totalExpected := numGoroutines * entriesPerGoroutine

	// Verify total count.
	maxSeq, err := s.GetMaxAuditSequence()
	if err != nil {
		t.Fatalf("GetMaxAuditSequence: %v", err)
	}
	if maxSeq != totalExpected {
		t.Errorf("MaxAuditSequence = %d, want %d", maxSeq, totalExpected)
	}

	// Verify sequence numbers are contiguous and hash chain is valid.
	entries, err := s.GetAuditEntriesRange(1, totalExpected)
	if err != nil {
		t.Fatalf("GetAuditEntriesRange: %v", err)
	}
	if len(entries) != totalExpected {
		t.Fatalf("expected %d entries, got %d", totalExpected, len(entries))
	}

	// First entry should have sha256:0.
	if entries[0].PreviousHash != "sha256:0" {
		t.Errorf("first entry previous_hash = %q, want sha256:0", entries[0].PreviousHash)
	}

	// Verify contiguous sequence numbers and hash chain.
	for i := 0; i < len(entries); i++ {
		if entries[i].SequenceNumber != i+1 {
			t.Errorf("entry %d: SequenceNumber = %d, want %d", i, entries[i].SequenceNumber, i+1)
		}
		if i > 0 {
			expectedHash := computeEntryHash(&entries[i-1])
			if entries[i].PreviousHash != expectedHash {
				t.Errorf("entry %d: previous_hash mismatch", i)
			}
		}
	}
}

func TestPostgresMaxAuditSequenceEmpty(t *testing.T) {
	s := newPostgresStorage(t)

	maxSeq, err := s.GetMaxAuditSequence()
	if err != nil {
		t.Fatalf("GetMaxAuditSequence: %v", err)
	}
	if maxSeq != 0 {
		t.Errorf("MaxAuditSequence on empty table = %d, want 0", maxSeq)
	}
}
