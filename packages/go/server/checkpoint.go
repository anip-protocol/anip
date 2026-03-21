package server

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"sort"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/crypto"
)

// MerkleTree implements an RFC 6962 Merkle hash tree.
type MerkleTree struct {
	leaves [][]byte // leaf hashes (SHA256(0x00 || data))
}

// NewMerkleTree creates an empty Merkle tree.
func NewMerkleTree() *MerkleTree {
	return &MerkleTree{}
}

// AddLeaf adds a data element to the tree.
func (t *MerkleTree) AddLeaf(data []byte) {
	t.leaves = append(t.leaves, leafHash(data))
}

// LeafCount returns the number of leaves.
func (t *MerkleTree) LeafCount() int {
	return len(t.leaves)
}

// Root returns the Merkle root as "sha256:<hex>".
func (t *MerkleTree) Root() string {
	if len(t.leaves) == 0 {
		h := sha256.Sum256([]byte{})
		return fmt.Sprintf("sha256:%x", h)
	}
	root := t.computeRoot(0, len(t.leaves))
	return fmt.Sprintf("sha256:%x", root)
}

// InclusionProof generates the inclusion proof path for the leaf at index.
func (t *MerkleTree) InclusionProof(index int) ([]ProofStep, error) {
	if index < 0 || index >= len(t.leaves) {
		return nil, fmt.Errorf("leaf index %d out of range [0, %d)", index, len(t.leaves))
	}
	var path []ProofStep
	t.buildInclusionPath(index, 0, len(t.leaves), &path)
	return path, nil
}

// VerifyInclusion verifies that data at index is included in the tree.
func VerifyInclusion(data []byte, proof []ProofStep, expectedRoot string) bool {
	current := leafHash(data)
	for _, step := range proof {
		sibling := hexToBytes(step.Hash)
		if step.Side == "left" {
			current = nodeHash(sibling, current)
		} else {
			current = nodeHash(current, sibling)
		}
	}
	return fmt.Sprintf("sha256:%x", current) == expectedRoot
}

// ProofStep is a single step in a Merkle inclusion proof.
type ProofStep struct {
	Hash string `json:"hash"`
	Side string `json:"side"` // "left" or "right"
}

// leafHash computes SHA256(0x00 || data).
func leafHash(data []byte) []byte {
	input := append([]byte{core.LeafHashPrefix}, data...)
	h := sha256.Sum256(input)
	return h[:]
}

// nodeHash computes SHA256(0x01 || left || right).
func nodeHash(left, right []byte) []byte {
	input := append([]byte{core.NodeHashPrefix}, left...)
	input = append(input, right...)
	h := sha256.Sum256(input)
	return h[:]
}

// largestPowerOf2LessThan returns the largest power of 2 less than n.
func largestPowerOf2LessThan(n int) int {
	if n <= 1 {
		return 0
	}
	k := 1
	for k*2 < n {
		k *= 2
	}
	return k
}

// computeRoot recursively computes the Merkle root for leaves[lo:hi].
func (t *MerkleTree) computeRoot(lo, hi int) []byte {
	n := hi - lo
	if n == 1 {
		return t.leaves[lo]
	}
	split := largestPowerOf2LessThan(n)
	left := t.computeRoot(lo, lo+split)
	right := t.computeRoot(lo+split, hi)
	return nodeHash(left, right)
}

// buildInclusionPath recursively builds the inclusion proof path.
func (t *MerkleTree) buildInclusionPath(index, lo, hi int, path *[]ProofStep) {
	n := hi - lo
	if n == 1 {
		return
	}
	split := largestPowerOf2LessThan(n)
	if index-lo < split {
		t.buildInclusionPath(index, lo, lo+split, path)
		right := t.computeRoot(lo+split, hi)
		*path = append(*path, ProofStep{Hash: fmt.Sprintf("%x", right), Side: "right"})
	} else {
		t.buildInclusionPath(index, lo+split, hi, path)
		left := t.computeRoot(lo, lo+split)
		*path = append(*path, ProofStep{Hash: fmt.Sprintf("%x", left), Side: "left"})
	}
}

// hexToBytes converts a hex string to bytes.
func hexToBytes(h string) []byte {
	b := make([]byte, len(h)/2)
	for i := 0; i < len(h)/2; i++ {
		fmt.Sscanf(h[2*i:2*i+2], "%02x", &b[i])
	}
	return b
}

// canonicalBytes returns the canonical JSON bytes of an audit entry for Merkle leaf hashing.
// Matches the Python implementation: excludes "signature" and "id", sorts keys, compact separators.
func canonicalBytes(entry *core.AuditEntry) []byte {
	data, _ := json.Marshal(entry)
	var m map[string]any
	json.Unmarshal(data, &m)

	// Remove signature and id.
	delete(m, "signature")
	delete(m, "id")

	// Sort keys.
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// Build with sorted keys using ordered map representation.
	ordered := make(map[string]any)
	for _, k := range keys {
		ordered[k] = m[k]
	}

	canonical, _ := json.Marshal(ordered)
	return canonical
}

// CreateCheckpoint builds a checkpoint from audit entries and stores it.
func CreateCheckpoint(
	km *crypto.KeyManager,
	storage Storage,
	serviceID string,
) (*core.Checkpoint, error) {
	// Get max sequence.
	maxSeq, err := storage.GetMaxAuditSequence()
	if err != nil {
		return nil, fmt.Errorf("get max audit sequence: %w", err)
	}
	if maxSeq == 0 {
		return nil, nil // No entries.
	}

	// Get the last checkpoint to determine the range.
	checkpoints, err := storage.ListCheckpoints(100)
	if err != nil {
		return nil, fmt.Errorf("list checkpoints: %w", err)
	}

	var lastCP *core.Checkpoint
	var lastCovered int
	if len(checkpoints) > 0 {
		lastCP = &checkpoints[len(checkpoints)-1]
		lastCovered = lastCP.Range["last_sequence"]
	}

	if maxSeq <= lastCovered {
		return nil, nil // No new entries.
	}

	// Full reconstruction from entry 1 (cumulative tree).
	entries, err := storage.GetAuditEntriesRange(1, maxSeq)
	if err != nil {
		return nil, fmt.Errorf("get audit entries range: %w", err)
	}

	// Build Merkle tree.
	tree := NewMerkleTree()
	for i := range entries {
		tree.AddLeaf(canonicalBytes(&entries[i]))
	}

	// Compute checkpoint number.
	cpNumber := 1
	var prevCheckpointHash string
	if lastCP != nil {
		// Parse number from last checkpoint ID.
		var n int
		if _, err := fmt.Sscanf(lastCP.CheckpointID, "ckpt-%d", &n); err == nil {
			cpNumber = n + 1
		}

		// Compute hash of previous checkpoint.
		prevBody, _ := json.Marshal(lastCP)
		// Re-serialize with sorted keys and compact separators.
		var prevMap map[string]any
		json.Unmarshal(prevBody, &prevMap)
		canonicalPrev, _ := json.Marshal(prevMap)
		h := sha256.Sum256(canonicalPrev)
		prevCheckpointHash = fmt.Sprintf("sha256:%x", h)
	}

	cp := &core.Checkpoint{
		Version:            "0.3",
		ServiceID:          serviceID,
		CheckpointID:       fmt.Sprintf("ckpt-%d", cpNumber),
		Range:              map[string]int{"first_sequence": 1, "last_sequence": maxSeq},
		MerkleRoot:         tree.Root(),
		PreviousCheckpoint: prevCheckpointHash,
		Timestamp:          time.Now().UTC().Format(time.RFC3339),
		EntryCount:         len(entries),
	}

	// Sign the checkpoint.
	cpJSON, _ := json.Marshal(cp)
	signature, err := crypto.SignDetachedJWSAudit(km, cpJSON)
	if err != nil {
		return nil, fmt.Errorf("sign checkpoint: %w", err)
	}

	// Store the checkpoint.
	if err := storage.StoreCheckpoint(cp, signature); err != nil {
		return nil, fmt.Errorf("store checkpoint: %w", err)
	}

	return cp, nil
}

// GenerateInclusionProof generates an inclusion proof for a leaf at the given index
// within the checkpoint's range. Returns the proof steps and the Merkle root.
// If entries have been deleted (expired), returns nil with a "proof_unavailable" indicator.
func GenerateInclusionProof(
	storage Storage,
	cp *core.Checkpoint,
	leafIndex int,
) ([]ProofStep, string, error) {
	firstSeq := cp.Range["first_sequence"]
	lastSeq := cp.Range["last_sequence"]

	// Get entries in the checkpoint range.
	entries, err := storage.GetAuditEntriesRange(firstSeq, lastSeq)
	if err != nil {
		return nil, "", fmt.Errorf("get audit entries: %w", err)
	}

	expectedCount := lastSeq - firstSeq + 1
	if len(entries) < expectedCount {
		// Entries have been deleted/expired.
		return nil, "audit_entries_expired", nil
	}

	// Rebuild Merkle tree.
	tree := NewMerkleTree()
	for i := range entries {
		tree.AddLeaf(canonicalBytes(&entries[i]))
	}

	// Validate leaf index.
	if leafIndex < 0 || leafIndex >= tree.LeafCount() {
		return nil, "", fmt.Errorf("leaf index %d out of range [0, %d)", leafIndex, tree.LeafCount())
	}

	proof, err := tree.InclusionProof(leafIndex)
	if err != nil {
		return nil, "", err
	}

	return proof, "", nil
}
