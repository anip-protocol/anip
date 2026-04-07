package server

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/crypto"
)

// --- Helpers ---

func newTestStorage(t *testing.T) Storage {
	t.Helper()
	s, err := NewSQLiteStorage(":memory:")
	if err != nil {
		t.Fatalf("NewSQLiteStorage: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func newTestKM(t *testing.T) *crypto.KeyManager {
	t.Helper()
	km, err := crypto.NewKeyManager("")
	if err != nil {
		t.Fatalf("NewKeyManager: %v", err)
	}
	return km
}

// --- SQLite Storage Tests ---

func TestSQLiteTokenCRUD(t *testing.T) {
	s := newTestStorage(t)

	token := &core.DelegationToken{
		TokenID:       "tok-test-1",
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
	loaded, err := s.LoadToken("tok-test-1")
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

	// Load non-existent.
	missing, err := s.LoadToken("tok-nonexistent")
	if err != nil {
		t.Fatalf("LoadToken non-existent: %v", err)
	}
	if missing != nil {
		t.Error("expected nil for non-existent token")
	}
}

func TestSQLiteAuditCRUD(t *testing.T) {
	s := newTestStorage(t)

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

func TestSQLiteUpdateSignature(t *testing.T) {
	s := newTestStorage(t)

	entry := &core.AuditEntry{
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Capability:    "test",
		RootPrincipal: "human:test@example.com",
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

func TestSQLiteCheckpointCRUD(t *testing.T) {
	s := newTestStorage(t)

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
}

// --- Delegation Tests ---

func TestDelegationIssueResolve(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	serviceID := "test-service"

	// Issue a token.
	resp, err := IssueDelegationToken(km, s, serviceID, "human:test@example.com", core.TokenRequest{
		Subject:    "agent:demo",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueDelegationToken: %v", err)
	}
	if !resp.Issued {
		t.Error("expected Issued = true")
	}
	if resp.Token == "" {
		t.Error("expected non-empty Token")
	}
	if resp.TokenID == "" {
		t.Error("expected non-empty TokenID")
	}
	if !strings.HasPrefix(resp.TokenID, "anip-") {
		t.Errorf("TokenID should start with anip-, got %q", resp.TokenID)
	}

	// Resolve the token.
	resolved, err := ResolveBearerToken(km, s, serviceID, resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken: %v", err)
	}
	if resolved == nil {
		t.Fatal("ResolveBearerToken returned nil")
	}
	if resolved.TokenID != resp.TokenID {
		t.Errorf("TokenID = %q, want %q", resolved.TokenID, resp.TokenID)
	}
	if resolved.Subject != "agent:demo" {
		t.Errorf("Subject = %q, want agent:demo", resolved.Subject)
	}
	if resolved.RootPrincipal != "human:test@example.com" {
		t.Errorf("RootPrincipal = %q, want human:test@example.com", resolved.RootPrincipal)
	}
	if len(resolved.Scope) != 1 || resolved.Scope[0] != "travel.search" {
		t.Errorf("Scope = %v, want [travel.search]", resolved.Scope)
	}
}

func TestDelegationWrongKey(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	km2 := newTestKM(t) // Different key pair.
	serviceID := "test-service"

	// Issue with km.
	resp, err := IssueDelegationToken(km, s, serviceID, "human:test@example.com", core.TokenRequest{
		Subject:    "agent:demo",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueDelegationToken: %v", err)
	}

	// Try to resolve with a different key manager.
	_, err = ResolveBearerToken(km2, s, serviceID, resp.Token)
	if err == nil {
		t.Fatal("expected error when resolving with wrong key")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected ANIPError, got %T", err)
	}
	if anipErr.ErrorType != core.FailureInvalidToken {
		t.Errorf("ErrorType = %q, want %q", anipErr.ErrorType, core.FailureInvalidToken)
	}
}

func TestScopeValidation(t *testing.T) {
	tests := []struct {
		name     string
		scope    []string
		minScope []string
		wantErr  bool
	}{
		{
			name:     "exact match",
			scope:    []string{"travel.search"},
			minScope: []string{"travel.search"},
			wantErr:  false,
		},
		{
			name:     "parent scope covers child",
			scope:    []string{"travel"},
			minScope: []string{"travel.search"},
			wantErr:  false,
		},
		{
			name:     "missing scope",
			scope:    []string{"travel.search"},
			minScope: []string{"travel.book"},
			wantErr:  true,
		},
		{
			name:     "multiple scopes all covered",
			scope:    []string{"travel.search", "travel.book"},
			minScope: []string{"travel.search", "travel.book"},
			wantErr:  false,
		},
		{
			name:     "one scope missing",
			scope:    []string{"travel.search"},
			minScope: []string{"travel.search", "travel.book"},
			wantErr:  true,
		},
		{
			name:     "scope with budget constraint",
			scope:    []string{"travel.search:max_$500"},
			minScope: []string{"travel.search"},
			wantErr:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			token := &core.DelegationToken{Scope: tt.scope}
			err := ValidateScope(token, tt.minScope)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateScope() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// --- Audit Tests ---

func TestAuditAppendQuery(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)

	entry1 := &core.AuditEntry{
		Capability:    "search_flights",
		TokenID:       "tok-1",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-001",
		Success:       true,
	}
	if err := AppendAudit(km, s, entry1); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}
	if entry1.SequenceNumber != 1 {
		t.Errorf("SequenceNumber = %d, want 1", entry1.SequenceNumber)
	}
	if entry1.Signature == "" {
		t.Error("expected non-empty signature")
	}
	if entry1.PreviousHash != "sha256:0" {
		t.Errorf("PreviousHash = %q, want sha256:0", entry1.PreviousHash)
	}

	entry2 := &core.AuditEntry{
		Capability:    "book_flight",
		TokenID:       "tok-2",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-002",
		Success:       true,
	}
	if err := AppendAudit(km, s, entry2); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}
	if entry2.SequenceNumber != 2 {
		t.Errorf("SequenceNumber = %d, want 2", entry2.SequenceNumber)
	}

	// Hash chain: entry2.PreviousHash should be the hash of entry1.
	if entry2.PreviousHash == "sha256:0" {
		t.Error("second entry previous_hash should not be sha256:0")
	}

	// Query scoped by root principal.
	result, err := QueryAudit(s, "human:test@example.com", AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(result.Entries) != 2 {
		t.Errorf("expected 2 entries, got %d", len(result.Entries))
	}

	// Query with capability filter.
	result, err = QueryAudit(s, "human:test@example.com", AuditFilters{Capability: "search_flights"})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(result.Entries) != 1 {
		t.Errorf("expected 1 entry with capability filter, got %d", len(result.Entries))
	}

	// Query different principal.
	result, err = QueryAudit(s, "human:other@example.com", AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(result.Entries) != 0 {
		t.Errorf("expected 0 entries for different principal, got %d", len(result.Entries))
	}
}

func TestAuditHashChainVerification(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)

	// Append 5 entries.
	for i := 0; i < 5; i++ {
		entry := &core.AuditEntry{
			Capability:    fmt.Sprintf("cap_%d", i),
			RootPrincipal: "human:test@example.com",
			InvocationID:  fmt.Sprintf("inv-%03d", i),
			Success:       true,
		}
		if err := AppendAudit(km, s, entry); err != nil {
			t.Fatalf("AppendAudit entry %d: %v", i, err)
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

func TestAuditSinceFilter(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)

	// First entry with an older timestamp.
	entry1 := &core.AuditEntry{
		Timestamp:     "2025-01-01T00:00:00Z",
		Capability:    "old_cap",
		RootPrincipal: "human:test@example.com",
		Success:       true,
	}
	if err := AppendAudit(km, s, entry1); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}

	// Second entry with a newer timestamp.
	entry2 := &core.AuditEntry{
		Timestamp:     "2026-06-01T00:00:00Z",
		Capability:    "new_cap",
		RootPrincipal: "human:test@example.com",
		Success:       true,
	}
	if err := AppendAudit(km, s, entry2); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}

	result, err := QueryAudit(s, "human:test@example.com", AuditFilters{Since: "2026-01-01T00:00:00Z"})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(result.Entries) != 1 {
		t.Fatalf("expected 1 entry with since filter, got %d", len(result.Entries))
	}
	if result.Entries[0].Capability != "new_cap" {
		t.Errorf("Capability = %q, want new_cap", result.Entries[0].Capability)
	}
}

// --- Merkle Tree Tests ---

func TestMerkleTreeSingleLeaf(t *testing.T) {
	tree := NewMerkleTree()
	tree.AddLeaf([]byte("hello"))

	root := tree.Root()
	if !strings.HasPrefix(root, "sha256:") {
		t.Errorf("root should start with sha256:, got %q", root)
	}

	// Verify manually: leaf hash = SHA256(0x00 || "hello").
	input := append([]byte{0x00}, []byte("hello")...)
	expected := sha256.Sum256(input)
	expectedRoot := fmt.Sprintf("sha256:%x", expected)
	if root != expectedRoot {
		t.Errorf("root = %q, want %q", root, expectedRoot)
	}
}

func TestMerkleTreeTwoLeaves(t *testing.T) {
	tree := NewMerkleTree()
	tree.AddLeaf([]byte("a"))
	tree.AddLeaf([]byte("b"))

	root := tree.Root()

	// Manually compute:
	// leaf_a = SHA256(0x00 || "a")
	// leaf_b = SHA256(0x00 || "b")
	// root = SHA256(0x01 || leaf_a || leaf_b)
	leafA := sha256.Sum256(append([]byte{0x00}, 'a'))
	leafB := sha256.Sum256(append([]byte{0x00}, 'b'))
	combined := append([]byte{0x01}, leafA[:]...)
	combined = append(combined, leafB[:]...)
	expectedRoot := sha256.Sum256(combined)

	if root != fmt.Sprintf("sha256:%x", expectedRoot) {
		t.Errorf("root = %q, want sha256:%x", root, expectedRoot)
	}
}

func TestMerkleTreeFourLeaves(t *testing.T) {
	tree := NewMerkleTree()
	for _, s := range []string{"a", "b", "c", "d"} {
		tree.AddLeaf([]byte(s))
	}

	root := tree.Root()

	// Manually compute RFC 6962 tree for 4 leaves:
	// leaf_a = SHA256(0x00 || "a"), etc.
	// node_ab = SHA256(0x01 || leaf_a || leaf_b)
	// node_cd = SHA256(0x01 || leaf_c || leaf_d)
	// root = SHA256(0x01 || node_ab || node_cd)
	leafA := sha256.Sum256(append([]byte{0x00}, 'a'))
	leafB := sha256.Sum256(append([]byte{0x00}, 'b'))
	leafC := sha256.Sum256(append([]byte{0x00}, 'c'))
	leafD := sha256.Sum256(append([]byte{0x00}, 'd'))

	nodeAB := sha256.Sum256(append(append([]byte{0x01}, leafA[:]...), leafB[:]...))
	nodeCD := sha256.Sum256(append(append([]byte{0x01}, leafC[:]...), leafD[:]...))
	expectedRoot := sha256.Sum256(append(append([]byte{0x01}, nodeAB[:]...), nodeCD[:]...))

	if root != fmt.Sprintf("sha256:%x", expectedRoot) {
		t.Errorf("root = %q, want sha256:%x", root, expectedRoot)
	}
}

func TestMerkleTreeThreeLeaves(t *testing.T) {
	// 3 leaves: non-power-of-2, tests the split logic.
	tree := NewMerkleTree()
	tree.AddLeaf([]byte("x"))
	tree.AddLeaf([]byte("y"))
	tree.AddLeaf([]byte("z"))

	root := tree.Root()

	// Split: largest power of 2 less than 3 = 2.
	// Left subtree: leaves 0,1 (x,y).
	// Right subtree: leaf 2 (z).
	leafX := sha256.Sum256(append([]byte{0x00}, 'x'))
	leafY := sha256.Sum256(append([]byte{0x00}, 'y'))
	leafZ := sha256.Sum256(append([]byte{0x00}, 'z'))

	nodeXY := sha256.Sum256(append(append([]byte{0x01}, leafX[:]...), leafY[:]...))
	expectedRoot := sha256.Sum256(append(append([]byte{0x01}, nodeXY[:]...), leafZ[:]...))

	if root != fmt.Sprintf("sha256:%x", expectedRoot) {
		t.Errorf("root = %q, want sha256:%x", root, expectedRoot)
	}
}

func TestMerkleInclusionProof(t *testing.T) {
	tree := NewMerkleTree()
	data := [][]byte{[]byte("a"), []byte("b"), []byte("c"), []byte("d")}
	for _, d := range data {
		tree.AddLeaf(d)
	}

	root := tree.Root()

	// Verify inclusion proof for each leaf.
	for i := 0; i < 4; i++ {
		proof, err := tree.InclusionProof(i)
		if err != nil {
			t.Fatalf("InclusionProof(%d): %v", i, err)
		}
		if !VerifyInclusion(data[i], proof, root) {
			t.Errorf("VerifyInclusion(%d) failed", i)
		}
	}
}

func TestMerkleInclusionProofSingleLeaf(t *testing.T) {
	tree := NewMerkleTree()
	tree.AddLeaf([]byte("only"))

	root := tree.Root()

	proof, err := tree.InclusionProof(0)
	if err != nil {
		t.Fatalf("InclusionProof: %v", err)
	}
	if len(proof) != 0 {
		t.Errorf("expected empty proof for single leaf, got %d steps", len(proof))
	}
	if !VerifyInclusion([]byte("only"), proof, root) {
		t.Error("VerifyInclusion failed for single leaf")
	}
}

func TestMerkleInclusionProofFiveLeaves(t *testing.T) {
	tree := NewMerkleTree()
	data := [][]byte{[]byte("1"), []byte("2"), []byte("3"), []byte("4"), []byte("5")}
	for _, d := range data {
		tree.AddLeaf(d)
	}

	root := tree.Root()

	for i := 0; i < 5; i++ {
		proof, err := tree.InclusionProof(i)
		if err != nil {
			t.Fatalf("InclusionProof(%d): %v", i, err)
		}
		if !VerifyInclusion(data[i], proof, root) {
			t.Errorf("VerifyInclusion(%d) failed", i)
		}
	}
}

func TestMerkleInclusionProofInvalidIndex(t *testing.T) {
	tree := NewMerkleTree()
	tree.AddLeaf([]byte("a"))

	_, err := tree.InclusionProof(1)
	if err == nil {
		t.Error("expected error for out-of-range index")
	}

	_, err = tree.InclusionProof(-1)
	if err == nil {
		t.Error("expected error for negative index")
	}
}

func TestMerkleEmptyTree(t *testing.T) {
	tree := NewMerkleTree()
	root := tree.Root()

	// Empty tree root should be SHA256("").
	expected := sha256.Sum256([]byte{})
	if root != fmt.Sprintf("sha256:%x", expected) {
		t.Errorf("empty tree root = %q, want sha256:%x", root, expected)
	}
}

// --- Consistency Proof Tests ---

func TestMerkleConsistencyProofTwoToFour(t *testing.T) {
	// Build a tree with 4 leaves and generate a consistency proof from size 2 to 4.
	tree := NewMerkleTree()
	for _, s := range []string{"a", "b", "c", "d"} {
		tree.AddLeaf([]byte(s))
	}

	proof, err := tree.ConsistencyProof(2)
	if err != nil {
		t.Fatalf("ConsistencyProof(2) error: %v", err)
	}

	// For a 4-leaf tree with old_size=2:
	// Tree structure:
	//        root
	//       /    \
	//     AB      CD
	//    / \     / \
	//   A   B  C   D
	//
	// SUBPROOF(2, [0:4], true):
	//   n=4, m=2, k=2 (largest power of 2 < 4)
	//   m <= k, so:
	//     SUBPROOF(2, [0:2], true) → m==n with start=true → []
	//     + computeRoot([2:4]) → hash(CD)
	// Result: [CD]
	leafC := sha256.Sum256(append([]byte{0x00}, 'c'))
	leafD := sha256.Sum256(append([]byte{0x00}, 'd'))
	nodeCD := sha256.Sum256(append(append([]byte{0x01}, leafC[:]...), leafD[:]...))

	if len(proof) != 1 {
		t.Fatalf("expected 1 proof element, got %d", len(proof))
	}
	if fmt.Sprintf("%x", proof[0]) != fmt.Sprintf("%x", nodeCD) {
		t.Errorf("proof[0] = %x, want %x", proof[0], nodeCD)
	}
}

func TestMerkleConsistencyProofThreeToFive(t *testing.T) {
	// Build a tree with 5 leaves and prove consistency from size 3.
	tree := NewMerkleTree()
	for _, s := range []string{"a", "b", "c", "d", "e"} {
		tree.AddLeaf([]byte(s))
	}

	proof, err := tree.ConsistencyProof(3)
	if err != nil {
		t.Fatalf("ConsistencyProof(3) error: %v", err)
	}

	// The proof should be non-empty and verifiable.
	if len(proof) == 0 {
		t.Fatal("expected non-empty proof")
	}

	// Verify that old tree root and new tree root can be reconstructed.
	// Build the old tree for comparison.
	oldTree := NewMerkleTree()
	for _, s := range []string{"a", "b", "c"} {
		oldTree.AddLeaf([]byte(s))
	}

	// The proof must have the right number of elements.
	// For old_size=3, new_size=5:
	// SUBPROOF(3, [0:5], true):
	//   n=5, k=4 (largest power of 2 < 5), m=3 <= 4
	//   SUBPROOF(3, [0:4], true):
	//     n=4, k=2, m=3 > 2
	//     SUBPROOF(1, [2:4], false):
	//       n=2, k=1, m=1 <= 1
	//       SUBPROOF(1, [2:3], false):
	//         m==n=1, start=false → [leaf_c]
	//       + computeRoot([3:4]) → leaf_d
	//     + computeRoot([0:2]) → node_ab
	//   + computeRoot([4:5]) → leaf_e
	// Total: [leaf_c, leaf_d, node_ab, leaf_e] = 4 elements
	if len(proof) != 4 {
		t.Fatalf("expected 4 proof elements, got %d", len(proof))
	}
}

func TestMerkleConsistencyProofSameSize(t *testing.T) {
	tree := NewMerkleTree()
	for _, s := range []string{"a", "b"} {
		tree.AddLeaf([]byte(s))
	}

	proof, err := tree.ConsistencyProof(2)
	if err != nil {
		t.Fatalf("ConsistencyProof(2) error: %v", err)
	}
	if len(proof) != 0 {
		t.Fatalf("expected empty proof for same size, got %d elements", len(proof))
	}
}

func TestMerkleConsistencyProofInvalidSize(t *testing.T) {
	tree := NewMerkleTree()
	tree.AddLeaf([]byte("a"))

	_, err := tree.ConsistencyProof(2)
	if err == nil {
		t.Error("expected error for old_size > leaf count")
	}

	_, err = tree.ConsistencyProof(-1)
	if err == nil {
		t.Error("expected error for negative old_size")
	}
}

func TestMerkleConsistencyProofOneToFour(t *testing.T) {
	// Build a tree with 4 leaves, prove from size 1.
	tree := NewMerkleTree()
	for _, s := range []string{"a", "b", "c", "d"} {
		tree.AddLeaf([]byte(s))
	}

	proof, err := tree.ConsistencyProof(1)
	if err != nil {
		t.Fatalf("ConsistencyProof(1) error: %v", err)
	}

	// SUBPROOF(1, [0:4], true):
	//   n=4, k=2, m=1 <= 2
	//   SUBPROOF(1, [0:2], true):
	//     n=2, k=1, m=1 <= 1
	//     SUBPROOF(1, [0:1], true):
	//       m==n=1, start=true → []
	//     + computeRoot([1:2]) → leaf_b
	//   + computeRoot([2:4]) → node_cd
	// Total: [leaf_b, node_cd]
	leafB := sha256.Sum256(append([]byte{0x00}, 'b'))
	leafC := sha256.Sum256(append([]byte{0x00}, 'c'))
	leafD := sha256.Sum256(append([]byte{0x00}, 'd'))
	nodeCD := sha256.Sum256(append(append([]byte{0x01}, leafC[:]...), leafD[:]...))

	if len(proof) != 2 {
		t.Fatalf("expected 2 proof elements, got %d", len(proof))
	}
	if fmt.Sprintf("%x", proof[0]) != fmt.Sprintf("%x", leafB) {
		t.Errorf("proof[0] = %x, want %x (leaf_b)", proof[0], leafB)
	}
	if fmt.Sprintf("%x", proof[1]) != fmt.Sprintf("%x", nodeCD) {
		t.Errorf("proof[1] = %x, want %x (node_cd)", proof[1], nodeCD)
	}
}

// --- Checkpoint Tests ---

func TestCheckpointCreation(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	serviceID := "test-service"

	// Append some audit entries.
	for i := 0; i < 3; i++ {
		entry := &core.AuditEntry{
			Capability:    fmt.Sprintf("cap_%d", i),
			RootPrincipal: "human:test@example.com",
			InvocationID:  fmt.Sprintf("inv-%03d", i),
			Success:       true,
		}
		if err := AppendAudit(km, s, entry); err != nil {
			t.Fatalf("AppendAudit: %v", err)
		}
	}

	// Create checkpoint.
	cp, err := CreateCheckpoint(km, s, serviceID)
	if err != nil {
		t.Fatalf("CreateCheckpoint: %v", err)
	}
	if cp == nil {
		t.Fatal("CreateCheckpoint returned nil")
	}
	if cp.CheckpointID != "ckpt-1" {
		t.Errorf("CheckpointID = %q, want ckpt-1", cp.CheckpointID)
	}
	if cp.EntryCount != 3 {
		t.Errorf("EntryCount = %d, want 3", cp.EntryCount)
	}
	if cp.Range["first_sequence"] != 1 {
		t.Errorf("Range.first_sequence = %d, want 1", cp.Range["first_sequence"])
	}
	if cp.Range["last_sequence"] != 3 {
		t.Errorf("Range.last_sequence = %d, want 3", cp.Range["last_sequence"])
	}
	if !strings.HasPrefix(cp.MerkleRoot, "sha256:") {
		t.Errorf("MerkleRoot should start with sha256:, got %q", cp.MerkleRoot)
	}
	if cp.ServiceID != serviceID {
		t.Errorf("ServiceID = %q, want %q", cp.ServiceID, serviceID)
	}

	// Verify the checkpoint is stored.
	stored, err := s.GetCheckpointByID("ckpt-1")
	if err != nil {
		t.Fatalf("GetCheckpointByID: %v", err)
	}
	if stored == nil {
		t.Fatal("stored checkpoint is nil")
	}
	if stored.MerkleRoot != cp.MerkleRoot {
		t.Errorf("stored MerkleRoot = %q, want %q", stored.MerkleRoot, cp.MerkleRoot)
	}

	// No new entries: CreateCheckpoint should return nil.
	cp2, err := CreateCheckpoint(km, s, serviceID)
	if err != nil {
		t.Fatalf("CreateCheckpoint (no new): %v", err)
	}
	if cp2 != nil {
		t.Error("expected nil when no new entries")
	}
}

func TestCheckpointInclusionProof(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	serviceID := "test-service"

	// Append 4 entries.
	for i := 0; i < 4; i++ {
		entry := &core.AuditEntry{
			Capability:    fmt.Sprintf("cap_%d", i),
			RootPrincipal: "human:test@example.com",
			InvocationID:  fmt.Sprintf("inv-%03d", i),
			Success:       true,
		}
		if err := AppendAudit(km, s, entry); err != nil {
			t.Fatalf("AppendAudit: %v", err)
		}
	}

	// Create checkpoint.
	cp, err := CreateCheckpoint(km, s, serviceID)
	if err != nil {
		t.Fatalf("CreateCheckpoint: %v", err)
	}

	// Generate and verify inclusion proof for each leaf.
	entries, err := s.GetAuditEntriesRange(1, 4)
	if err != nil {
		t.Fatalf("GetAuditEntriesRange: %v", err)
	}

	for i := 0; i < 4; i++ {
		proof, unavailable, err := GenerateInclusionProof(s, cp, i)
		if err != nil {
			t.Fatalf("GenerateInclusionProof(%d): %v", i, err)
		}
		if unavailable != "" {
			t.Fatalf("unexpected proof_unavailable: %s", unavailable)
		}
		if !VerifyInclusion(canonicalBytes(&entries[i]), proof, cp.MerkleRoot) {
			t.Errorf("VerifyInclusion(%d) failed against checkpoint root", i)
		}
	}
}

func TestCheckpointSequencing(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	serviceID := "test-service"

	// Create first batch of entries + checkpoint.
	for i := 0; i < 3; i++ {
		entry := &core.AuditEntry{
			Capability:    fmt.Sprintf("cap_%d", i),
			RootPrincipal: "human:test@example.com",
			Success:       true,
		}
		if err := AppendAudit(km, s, entry); err != nil {
			t.Fatalf("AppendAudit batch 1: %v", err)
		}
	}
	cp1, err := CreateCheckpoint(km, s, serviceID)
	if err != nil {
		t.Fatalf("CreateCheckpoint 1: %v", err)
	}
	if cp1.CheckpointID != "ckpt-1" {
		t.Errorf("first checkpoint ID = %q, want ckpt-1", cp1.CheckpointID)
	}

	// Add more entries and create second checkpoint.
	for i := 3; i < 6; i++ {
		entry := &core.AuditEntry{
			Capability:    fmt.Sprintf("cap_%d", i),
			RootPrincipal: "human:test@example.com",
			Success:       true,
		}
		if err := AppendAudit(km, s, entry); err != nil {
			t.Fatalf("AppendAudit batch 2: %v", err)
		}
	}
	cp2, err := CreateCheckpoint(km, s, serviceID)
	if err != nil {
		t.Fatalf("CreateCheckpoint 2: %v", err)
	}
	if cp2.CheckpointID != "ckpt-2" {
		t.Errorf("second checkpoint ID = %q, want ckpt-2", cp2.CheckpointID)
	}
	if cp2.PreviousCheckpoint == "" {
		t.Error("second checkpoint should reference previous checkpoint")
	}
	if !strings.HasPrefix(cp2.PreviousCheckpoint, "sha256:") {
		t.Errorf("PreviousCheckpoint should start with sha256:, got %q", cp2.PreviousCheckpoint)
	}

	// List checkpoints.
	cps, err := s.ListCheckpoints(10)
	if err != nil {
		t.Fatalf("ListCheckpoints: %v", err)
	}
	if len(cps) != 2 {
		t.Errorf("expected 2 checkpoints, got %d", len(cps))
	}
}

// --- Integration Tests ---

func TestFullDelegationAuditFlow(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	serviceID := "test-service"

	// 1. Issue token.
	resp, err := IssueDelegationToken(km, s, serviceID, "human:test@example.com", core.TokenRequest{
		Subject:    "agent:demo",
		Scope:      []string{"travel.search", "travel.book"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueDelegationToken: %v", err)
	}

	// 2. Resolve token.
	token, err := ResolveBearerToken(km, s, serviceID, resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken: %v", err)
	}

	// 3. Validate scope for search_flights.
	if err := ValidateScope(token, []string{"travel.search"}); err != nil {
		t.Fatalf("ValidateScope for search: %v", err)
	}

	// 4. Validate scope for book_flight.
	if err := ValidateScope(token, []string{"travel.book"}); err != nil {
		t.Fatalf("ValidateScope for book: %v", err)
	}

	// 5. Log audit entries.
	auditEntry := &core.AuditEntry{
		Capability:    "search_flights",
		TokenID:       token.TokenID,
		RootPrincipal: token.RootPrincipal,
		InvocationID:  core.GenerateInvocationID(),
		Success:       true,
		ResultSummary: map[string]any{"count": 3},
	}
	if err := AppendAudit(km, s, auditEntry); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}

	// 6. Query audit.
	result, err := QueryAudit(s, "human:test@example.com", AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(result.Entries) != 1 {
		t.Errorf("expected 1 audit entry, got %d", len(result.Entries))
	}
	if result.Entries[0].InvocationID != auditEntry.InvocationID {
		t.Errorf("InvocationID = %q, want %q", result.Entries[0].InvocationID, auditEntry.InvocationID)
	}

	// 7. Create checkpoint.
	cp, err := CreateCheckpoint(km, s, serviceID)
	if err != nil {
		t.Fatalf("CreateCheckpoint: %v", err)
	}
	if cp == nil {
		t.Fatal("CreateCheckpoint returned nil")
	}
	if cp.EntryCount != 1 {
		t.Errorf("EntryCount = %d, want 1", cp.EntryCount)
	}
}

// --- Lease Tests ---

func TestExclusiveLeaseAcquireRelease(t *testing.T) {
	s := newTestStorage(t)

	// Acquire should succeed.
	acquired, err := s.TryAcquireExclusive("my-key", "holder-1", 60)
	if err != nil {
		t.Fatalf("TryAcquireExclusive: %v", err)
	}
	if !acquired {
		t.Fatal("expected to acquire exclusive lease")
	}

	// Different holder should fail.
	acquired, err = s.TryAcquireExclusive("my-key", "holder-2", 60)
	if err != nil {
		t.Fatalf("TryAcquireExclusive: %v", err)
	}
	if acquired {
		t.Fatal("expected NOT to acquire lease held by another holder")
	}

	// Same holder can re-acquire (renew).
	acquired, err = s.TryAcquireExclusive("my-key", "holder-1", 60)
	if err != nil {
		t.Fatalf("TryAcquireExclusive: %v", err)
	}
	if !acquired {
		t.Fatal("expected same holder to renew lease")
	}

	// Release.
	if err := s.ReleaseExclusive("my-key", "holder-1"); err != nil {
		t.Fatalf("ReleaseExclusive: %v", err)
	}

	// Now holder-2 can acquire.
	acquired, err = s.TryAcquireExclusive("my-key", "holder-2", 60)
	if err != nil {
		t.Fatalf("TryAcquireExclusive: %v", err)
	}
	if !acquired {
		t.Fatal("expected holder-2 to acquire after release")
	}
}

func TestLeaderLeaseAcquireRelease(t *testing.T) {
	s := newTestStorage(t)

	acquired, err := s.TryAcquireLeader("retention", "instance-1", 60)
	if err != nil {
		t.Fatalf("TryAcquireLeader: %v", err)
	}
	if !acquired {
		t.Fatal("expected to acquire leader lease")
	}

	// Different holder should fail.
	acquired, err = s.TryAcquireLeader("retention", "instance-2", 60)
	if err != nil {
		t.Fatalf("TryAcquireLeader: %v", err)
	}
	if acquired {
		t.Fatal("expected NOT to acquire leader held by another")
	}

	// Release and re-acquire.
	if err := s.ReleaseLeader("retention", "instance-1"); err != nil {
		t.Fatalf("ReleaseLeader: %v", err)
	}
	acquired, err = s.TryAcquireLeader("retention", "instance-2", 60)
	if err != nil {
		t.Fatalf("TryAcquireLeader: %v", err)
	}
	if !acquired {
		t.Fatal("expected instance-2 to acquire after release")
	}
}

// --- Retention Tests ---

func TestDeleteExpiredAuditEntries(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)

	// Entry with past expiry.
	entry1 := &core.AuditEntry{
		Capability:    "cap_expired",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-exp",
		Success:       true,
		ExpiresAt:     "2020-01-01T00:00:00Z",
	}
	if err := AppendAudit(km, s, entry1); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}

	// Entry with future expiry.
	entry2 := &core.AuditEntry{
		Capability:    "cap_future",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-future",
		Success:       true,
		ExpiresAt:     "2099-01-01T00:00:00Z",
	}
	if err := AppendAudit(km, s, entry2); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}

	// Entry with no expiry.
	entry3 := &core.AuditEntry{
		Capability:    "cap_no_exp",
		RootPrincipal: "human:test@example.com",
		InvocationID:  "inv-noexp",
		Success:       true,
	}
	if err := AppendAudit(km, s, entry3); err != nil {
		t.Fatalf("AppendAudit: %v", err)
	}

	// Delete expired.
	deleted, err := s.DeleteExpiredAuditEntries("2025-01-01T00:00:00Z")
	if err != nil {
		t.Fatalf("DeleteExpiredAuditEntries: %v", err)
	}
	if deleted != 1 {
		t.Fatalf("expected 1 deleted, got %d", deleted)
	}

	// Verify remaining entries.
	entries, err := s.GetAuditEntriesRange(1, 3)
	if err != nil {
		t.Fatalf("GetAuditEntriesRange: %v", err)
	}
	if len(entries) != 2 {
		t.Fatalf("expected 2 remaining entries, got %d", len(entries))
	}
}

func TestTokenResponseJSON(t *testing.T) {
	resp := core.TokenResponse{
		Issued:  true,
		TokenID: "anip-abc123",
		Token:   "eyJ...",
		Expires: "2026-03-20T12:00:00Z",
	}
	data, err := json.Marshal(resp)
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	var m map[string]any
	json.Unmarshal(data, &m)
	if m["issued"] != true {
		t.Error("expected issued = true")
	}
	if m["token_id"] != "anip-abc123" {
		t.Errorf("token_id = %v, want anip-abc123", m["token_id"])
	}
}

func TestTaskIdEchoedInIssuanceResponse(t *testing.T) {
	s := newTestStorage(t)
	km := newTestKM(t)
	serviceID := "test-service"

	// 1. Caller-supplied task_id is echoed
	resp, err := IssueDelegationToken(km, s, serviceID, "human:alice@example.com", core.TokenRequest{
		Subject:           "agent:demo",
		Scope:             []string{"travel.search"},
		Capability:        "search_flights",
		PurposeParameters: map[string]any{"task_id": "my-custom-task"},
	})
	if err != nil {
		t.Fatalf("IssueDelegationToken: %v", err)
	}
	if resp.TaskID != "my-custom-task" {
		t.Errorf("TaskID = %q, want my-custom-task", resp.TaskID)
	}

	// 2. Auto-generated task_id when no purpose_parameters
	resp2, err := IssueDelegationToken(km, s, serviceID, "human:bob@example.com", core.TokenRequest{
		Subject:    "agent:demo",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueDelegationToken: %v", err)
	}
	if resp2.TaskID == "" {
		t.Error("expected non-empty auto-generated TaskID")
	}
	if !strings.HasPrefix(resp2.TaskID, "task-") {
		t.Errorf("TaskID should start with task-, got %q", resp2.TaskID)
	}

	// 3. No task_id when purpose_parameters is provided without task_id
	resp3, err := IssueDelegationToken(km, s, serviceID, "human:carol@example.com", core.TokenRequest{
		Subject:           "agent:demo",
		Scope:             []string{"travel.search"},
		Capability:        "search_flights",
		PurposeParameters: map[string]any{"source": "test"},
	})
	if err != nil {
		t.Fatalf("IssueDelegationToken: %v", err)
	}
	if resp3.TaskID != "" {
		t.Errorf("TaskID should be empty when purpose_parameters has no task_id, got %q", resp3.TaskID)
	}

	// Verify JSON serialization omits task_id when empty
	data, _ := json.Marshal(resp3)
	var m map[string]any
	json.Unmarshal(data, &m)
	if _, found := m["task_id"]; found {
		t.Error("task_id should be omitted from JSON when empty")
	}
}
