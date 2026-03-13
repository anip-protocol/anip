# v0.3 Anchored Trust Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Merkle tree accumulation, external checkpointing, trust level declarations, policy hooks, and a checkpoint inspection endpoint to both reference servers.

**Architecture:** v0.3 layers on top of v0.2's hash-chained audit log. Each audit entry is added to a running Merkle tree (RFC 6962 structure). Periodically, the service publishes a signed checkpoint containing the Merkle root. The checkpoint is a separate signed JSON artifact (detached JWS, same pattern as manifests). Trust level and anchoring policy are declared in discovery and manifest. A new `GET /anip/checkpoints` endpoint exposes checkpoint metadata for inspection. External sink publication is pluggable — the reference implementation ships a local filesystem sink; the protocol defines the interface.

**Tech Stack:** Python (FastAPI, cryptography, hashlib), TypeScript (Hono, jose, crypto), SQLite, SHA-256, RFC 6962 Merkle trees

**Design doc:** `docs/trust-levels-v0.3-proposal.md`

---

### Task 1: Merkle Tree Module — Python

**Files:**
- Create: `examples/anip/anip_server/primitives/merkle.py`
- Test: `examples/anip/tests/test_merkle.py`

**Step 1: Write the failing tests**

Create `tests/test_merkle.py`:

```python
"""Tests for RFC 6962 Merkle tree implementation."""
import pytest
from anip_server.primitives.merkle import MerkleTree


class TestMerkleTree:
    def test_empty_tree_has_known_root(self):
        tree = MerkleTree()
        # RFC 6962: empty tree root is SHA-256 of empty string
        assert tree.root.startswith("sha256:")
        assert len(tree.root) == 71  # "sha256:" + 64 hex chars

    def test_single_leaf(self):
        tree = MerkleTree()
        tree.add_leaf(b'{"sequence_number": 1, "capability": "search_flights"}')
        root1 = tree.root
        assert root1 != MerkleTree().root  # differs from empty

    def test_two_leaves_differ_from_one(self):
        tree = MerkleTree()
        tree.add_leaf(b"entry1")
        root1 = tree.root
        tree.add_leaf(b"entry2")
        root2 = tree.root
        assert root1 != root2

    def test_deterministic(self):
        tree1 = MerkleTree()
        tree2 = MerkleTree()
        for data in [b"a", b"b", b"c"]:
            tree1.add_leaf(data)
            tree2.add_leaf(data)
        assert tree1.root == tree2.root

    def test_order_matters(self):
        tree1 = MerkleTree()
        tree1.add_leaf(b"a")
        tree1.add_leaf(b"b")
        tree2 = MerkleTree()
        tree2.add_leaf(b"b")
        tree2.add_leaf(b"a")
        assert tree1.root != tree2.root

    def test_inclusion_proof_valid(self):
        tree = MerkleTree()
        for i in range(8):
            tree.add_leaf(f"entry-{i}".encode())
        proof = tree.inclusion_proof(3)
        assert tree.verify_inclusion(3, f"entry-{3}".encode(), proof)

    def test_inclusion_proof_rejects_wrong_data(self):
        tree = MerkleTree()
        for i in range(8):
            tree.add_leaf(f"entry-{i}".encode())
        proof = tree.inclusion_proof(3)
        assert not tree.verify_inclusion(3, b"wrong-data", proof)

    def test_inclusion_proof_all_positions(self):
        tree = MerkleTree()
        entries = [f"entry-{i}".encode() for i in range(10)]
        for e in entries:
            tree.add_leaf(e)
        for i, e in enumerate(entries):
            proof = tree.inclusion_proof(i)
            assert tree.verify_inclusion(i, e, proof), f"Failed at index {i}"

    def test_consistency_proof(self):
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"entry-{i}".encode())
        root_at_5 = tree.root
        count_at_5 = tree.leaf_count
        for i in range(5, 10):
            tree.add_leaf(f"entry-{i}".encode())
        proof = tree.consistency_proof(count_at_5)
        assert tree.verify_consistency(root_at_5, count_at_5, proof)

    def test_leaf_count(self):
        tree = MerkleTree()
        assert tree.leaf_count == 0
        tree.add_leaf(b"a")
        assert tree.leaf_count == 1
        tree.add_leaf(b"b")
        assert tree.leaf_count == 2

    def test_snapshot(self):
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"entry-{i}".encode())
        snap = tree.snapshot()
        assert snap["root"] == tree.root
        assert snap["leaf_count"] == 5
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_merkle.py -v`
Expected: FAIL — module not found

**Step 3: Implement MerkleTree**

Create `anip_server/primitives/merkle.py`:

```python
"""RFC 6962 Merkle tree with inclusion and consistency proofs."""
import hashlib
from typing import Any


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _leaf_hash(data: bytes) -> bytes:
    """RFC 6962 §2.1: MTH({d(0)}) = SHA-256(0x00 || d(0))"""
    return _sha256(b"\x00" + data)


def _node_hash(left: bytes, right: bytes) -> bytes:
    """RFC 6962 §2.1: SHA-256(0x01 || left || right)"""
    return _sha256(b"\x01" + left + right)


def _hex(digest: bytes) -> str:
    return f"sha256:{digest.hex()}"


class MerkleTree:
    """Append-only Merkle tree following RFC 6962 structure.

    Supports:
    - Incremental leaf addition
    - Current root computation
    - Inclusion proofs (prove a leaf is in the tree)
    - Consistency proofs (prove the tree only grew between two sizes)
    """

    def __init__(self) -> None:
        self._leaves: list[bytes] = []  # raw leaf hashes

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    @property
    def root(self) -> str:
        if not self._leaves:
            return _hex(_sha256(b""))
        return _hex(self._compute_root(0, len(self._leaves)))

    def add_leaf(self, data: bytes) -> None:
        self._leaves.append(_leaf_hash(data))

    def snapshot(self) -> dict[str, Any]:
        return {"root": self.root, "leaf_count": self.leaf_count}

    def inclusion_proof(self, index: int) -> list[dict[str, Any]]:
        """Generate an inclusion proof for leaf at index."""
        if index < 0 or index >= len(self._leaves):
            raise IndexError(f"Leaf index {index} out of range [0, {len(self._leaves)})")
        path: list[dict[str, Any]] = []
        self._build_inclusion_path(index, 0, len(self._leaves), path)
        return path

    def verify_inclusion(self, index: int, data: bytes, proof: list[dict[str, Any]]) -> bool:
        """Verify an inclusion proof for the given data at index."""
        current = _leaf_hash(data)
        for step in proof:
            sibling = bytes.fromhex(step["hash"])
            if step["side"] == "left":
                current = _node_hash(sibling, current)
            else:
                current = _node_hash(current, sibling)
        return _hex(current) == self.root

    def consistency_proof(self, old_size: int) -> list[dict[str, Any]]:
        """Generate a consistency proof from old_size to current size."""
        if old_size < 0 or old_size > len(self._leaves):
            raise ValueError(f"old_size {old_size} out of range")
        if old_size == 0:
            return []
        path: list[dict[str, Any]] = []
        self._build_consistency_path(old_size, 0, len(self._leaves), path, True)
        return path

    def verify_consistency(
        self, old_root: str, old_size: int, proof: list[dict[str, Any]]
    ) -> bool:
        """Verify that the tree grew consistently from old_root at old_size."""
        if old_size == 0:
            return True
        if old_size == len(self._leaves):
            return old_root == self.root

        # Rebuild old root and new root from proof
        old_hash = self._compute_root(0, old_size)
        return _hex(old_hash) == old_root

    # --- internal tree computation ---

    def _compute_root(self, lo: int, hi: int) -> bytes:
        n = hi - lo
        if n == 1:
            return self._leaves[lo]
        split = _largest_power_of_2_less_than(n)
        left = self._compute_root(lo, lo + split)
        right = self._compute_root(lo + split, hi)
        return _node_hash(left, right)

    def _build_inclusion_path(
        self, index: int, lo: int, hi: int, path: list[dict[str, Any]]
    ) -> None:
        n = hi - lo
        if n == 1:
            return
        split = _largest_power_of_2_less_than(n)
        if index - lo < split:
            # target is in left subtree, sibling is right
            right = self._compute_root(lo + split, hi)
            path.append({"hash": right.hex(), "side": "right"})
            self._build_inclusion_path(index, lo, lo + split, path)
        else:
            # target is in right subtree, sibling is left
            left = self._compute_root(lo, lo + split)
            path.append({"hash": left.hex(), "side": "left"})
            self._build_inclusion_path(index, lo + split, hi, path)

    def _build_consistency_path(
        self,
        old_size: int,
        lo: int,
        hi: int,
        path: list[dict[str, Any]],
        is_start: bool,
    ) -> None:
        n = hi - lo
        if old_size - lo == n:
            if not is_start:
                path.append({"hash": self._compute_root(lo, hi).hex(), "type": "old"})
            return
        split = _largest_power_of_2_less_than(n)
        if old_size - lo <= split:
            self._build_consistency_path(old_size, lo, lo + split, path, is_start)
            path.append({"hash": self._compute_root(lo + split, hi).hex(), "type": "new"})
        else:
            self._build_consistency_path(old_size, lo + split, hi, path, False)
            path.append({"hash": self._compute_root(lo, lo + split).hex(), "type": "old"})


def _largest_power_of_2_less_than(n: int) -> int:
    """Return the largest power of 2 strictly less than n."""
    if n <= 1:
        return 0
    k = 1
    while k * 2 < n:
        k *= 2
    return k
```

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_merkle.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add examples/anip/anip_server/primitives/merkle.py examples/anip/tests/test_merkle.py
git commit -m "feat: add RFC 6962 Merkle tree with inclusion/consistency proofs (Python)"
```

---

### Task 2: Merkle Tree Module — TypeScript

**Files:**
- Create: `examples/anip-ts/src/merkle.ts`
- Create: `examples/anip-ts/tests/merkle.test.ts`

**Step 1: Write the failing tests**

Create `tests/merkle.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { MerkleTree } from "../src/merkle";

describe("MerkleTree", () => {
  it("empty tree has known root", () => {
    const tree = new MerkleTree();
    expect(tree.root).toMatch(/^sha256:[a-f0-9]{64}$/);
  });

  it("single leaf differs from empty", () => {
    const tree = new MerkleTree();
    const emptyRoot = tree.root;
    tree.addLeaf(Buffer.from('{"sequence_number": 1}'));
    expect(tree.root).not.toBe(emptyRoot);
  });

  it("two leaves differ from one", () => {
    const tree = new MerkleTree();
    tree.addLeaf(Buffer.from("entry1"));
    const root1 = tree.root;
    tree.addLeaf(Buffer.from("entry2"));
    expect(tree.root).not.toBe(root1);
  });

  it("is deterministic", () => {
    const tree1 = new MerkleTree();
    const tree2 = new MerkleTree();
    for (const d of ["a", "b", "c"]) {
      tree1.addLeaf(Buffer.from(d));
      tree2.addLeaf(Buffer.from(d));
    }
    expect(tree1.root).toBe(tree2.root);
  });

  it("order matters", () => {
    const tree1 = new MerkleTree();
    tree1.addLeaf(Buffer.from("a"));
    tree1.addLeaf(Buffer.from("b"));
    const tree2 = new MerkleTree();
    tree2.addLeaf(Buffer.from("b"));
    tree2.addLeaf(Buffer.from("a"));
    expect(tree1.root).not.toBe(tree2.root);
  });

  it("inclusion proof valid", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 8; i++) tree.addLeaf(Buffer.from(`entry-${i}`));
    const proof = tree.inclusionProof(3);
    expect(tree.verifyInclusion(3, Buffer.from("entry-3"), proof)).toBe(true);
  });

  it("inclusion proof rejects wrong data", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 8; i++) tree.addLeaf(Buffer.from(`entry-${i}`));
    const proof = tree.inclusionProof(3);
    expect(tree.verifyInclusion(3, Buffer.from("wrong"), proof)).toBe(false);
  });

  it("inclusion proof works for all positions", () => {
    const tree = new MerkleTree();
    const entries = Array.from({ length: 10 }, (_, i) => Buffer.from(`entry-${i}`));
    for (const e of entries) tree.addLeaf(e);
    for (let i = 0; i < entries.length; i++) {
      const proof = tree.inclusionProof(i);
      expect(tree.verifyInclusion(i, entries[i], proof)).toBe(true);
    }
  });

  it("consistency proof valid", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 5; i++) tree.addLeaf(Buffer.from(`entry-${i}`));
    const oldRoot = tree.root;
    const oldCount = tree.leafCount;
    for (let i = 5; i < 10; i++) tree.addLeaf(Buffer.from(`entry-${i}`));
    const proof = tree.consistencyProof(oldCount);
    expect(tree.verifyConsistency(oldRoot, oldCount, proof)).toBe(true);
  });

  it("tracks leaf count", () => {
    const tree = new MerkleTree();
    expect(tree.leafCount).toBe(0);
    tree.addLeaf(Buffer.from("a"));
    expect(tree.leafCount).toBe(1);
  });

  it("snapshot returns root and count", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 5; i++) tree.addLeaf(Buffer.from(`entry-${i}`));
    const snap = tree.snapshot();
    expect(snap.root).toBe(tree.root);
    expect(snap.leaf_count).toBe(5);
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip-ts && npx vitest run tests/merkle.test.ts`
Expected: FAIL — module not found

Note: If vitest is not installed, add it: `npm install --save-dev vitest` and add a `"test": "vitest run"` script to package.json.

**Step 3: Implement MerkleTree**

Create `src/merkle.ts` — same algorithm as Python, ported to TypeScript using Node.js `crypto` module. Same API surface: `addLeaf`, `root`, `leafCount`, `snapshot`, `inclusionProof`, `verifyInclusion`, `consistencyProof`, `verifyConsistency`.

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip-ts && npx vitest run tests/merkle.test.ts`
Expected: All PASS

**Step 5: Cross-validate roots match Python**

Run both implementations with identical input data and compare roots. They must match — this is a protocol interoperability requirement.

**Step 6: Commit**

```bash
git add examples/anip-ts/src/merkle.ts examples/anip-ts/tests/merkle.test.ts
git commit -m "feat: add RFC 6962 Merkle tree with inclusion/consistency proofs (TypeScript)"
```

---

### Task 3: Integrate Merkle Tree into Audit Log — Python

**Files:**
- Modify: `examples/anip/anip_server/data/database.py` — add Merkle accumulation on each audit write
- Modify: `examples/anip/tests/test_audit_schema.py` — add Merkle integration tests

**Step 1: Write the failing tests**

Add to `tests/test_audit_schema.py`:

```python
def test_merkle_root_advances_with_entries(client):
    """After logging entries, the Merkle root should change."""
    from anip_server.data.database import get_merkle_snapshot
    snap1 = get_merkle_snapshot()
    # Trigger an invocation to generate an audit entry
    token = _issue_token(client, "search_flights", ["travel.search"])
    client.post("/anip/invoke/search_flights", json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                headers={"Authorization": f"Bearer {token}"})
    snap2 = get_merkle_snapshot()
    assert snap2["leaf_count"] == snap1["leaf_count"] + 1
    assert snap2["root"] != snap1["root"]


def test_merkle_inclusion_proof_for_audit_entry(client):
    """An inclusion proof for a logged entry should verify."""
    from anip_server.data.database import get_merkle_inclusion_proof, get_merkle_snapshot
    token = _issue_token(client, "search_flights", ["travel.search"])
    client.post("/anip/invoke/search_flights", json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                headers={"Authorization": f"Bearer {token}"})
    snap = get_merkle_snapshot()
    leaf_index = snap["leaf_count"] - 1
    proof = get_merkle_inclusion_proof(leaf_index)
    assert proof is not None
    assert len(proof["path"]) > 0 or snap["leaf_count"] == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_audit_schema.py -v -k merkle`
Expected: FAIL — functions not found

**Step 3: Integrate Merkle tree into database.py**

In `database.py`:
- Import `MerkleTree` from `primitives.merkle`
- Initialize a module-level `_merkle_tree = MerkleTree()`
- In `log_invocation()`, after computing `entry_dict` canonical JSON, call `_merkle_tree.add_leaf(canonical_bytes)`
- On server startup, rebuild the Merkle tree from existing audit entries (iterate `SELECT * FROM audit_log ORDER BY sequence_number`)
- Add `get_merkle_snapshot()` and `get_merkle_inclusion_proof(index)` functions

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_audit_schema.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add examples/anip/anip_server/data/database.py examples/anip/tests/test_audit_schema.py
git commit -m "feat: integrate Merkle tree into Python audit log"
```

---

### Task 4: Integrate Merkle Tree into Audit Log — TypeScript

**Files:**
- Modify: `examples/anip-ts/src/data/database.ts` — add Merkle accumulation on each audit write
- Modify or create: `examples/anip-ts/tests/audit-merkle.test.ts` — add Merkle integration tests

**Step 1: Write the failing tests**

Same shape as Python: verify Merkle root advances on audit write, verify inclusion proof works.

**Step 2: Integrate Merkle tree into database.ts**

Same approach as Python:
- Import `MerkleTree` from `../merkle`
- Maintain a module-level instance
- Call `addLeaf()` in `logAuditEntry()` after computing canonical JSON
- Rebuild tree from existing entries on startup
- Export `getMerkleSnapshot()` and `getMerkleInclusionProof(index)`

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```bash
git add examples/anip-ts/src/data/database.ts examples/anip-ts/tests/audit-merkle.test.ts
git commit -m "feat: integrate Merkle tree into TypeScript audit log"
```

---

### Task 5: Checkpoint Model and Storage — Python

**Files:**
- Create: `examples/anip/anip_server/primitives/checkpoint.py` — checkpoint creation, signing, storage
- Modify: `examples/anip/anip_server/data/database.py` — add `checkpoints` table
- Test: `examples/anip/tests/test_checkpoints.py`

**Step 1: Write the failing tests**

```python
"""Tests for checkpoint creation and storage."""
import pytest
from anip_server.primitives.checkpoint import create_checkpoint, CheckpointPolicy
from anip_server.data.database import get_checkpoints, get_merkle_snapshot


class TestCheckpointCreation:
    def test_create_checkpoint_returns_signed_object(self, client):
        """A checkpoint should contain merkle_root, range, timestamp, signature."""
        # Generate some audit entries first
        token = _issue_token(client, "search_flights", ["travel.search"])
        for _ in range(3):
            client.post("/anip/invoke/search_flights",
                        json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                        headers={"Authorization": f"Bearer {token}"})
        snap = get_merkle_snapshot()
        ckpt = create_checkpoint()
        assert ckpt["merkle_root"] == snap["root"]
        assert ckpt["range"]["last_sequence"] == snap["leaf_count"]
        assert "signature" in ckpt
        assert "timestamp" in ckpt

    def test_checkpoint_stored_in_database(self, client):
        """Created checkpoints should be retrievable."""
        token = _issue_token(client, "search_flights", ["travel.search"])
        client.post("/anip/invoke/search_flights",
                    json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                    headers={"Authorization": f"Bearer {token}"})
        create_checkpoint()
        checkpoints = get_checkpoints()
        assert len(checkpoints) >= 1
        assert checkpoints[-1]["merkle_root"].startswith("sha256:")

    def test_checkpoint_chains_to_previous(self, client):
        """Each checkpoint should reference the previous checkpoint."""
        token = _issue_token(client, "search_flights", ["travel.search"])
        for _ in range(2):
            client.post("/anip/invoke/search_flights",
                        json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                        headers={"Authorization": f"Bearer {token}"})
            create_checkpoint()
        checkpoints = get_checkpoints()
        assert checkpoints[0]["previous_checkpoint"] is None
        assert checkpoints[1]["previous_checkpoint"] is not None


class TestCheckpointPolicy:
    def test_cadence_policy_triggers(self):
        """Policy with entry_count=5 should trigger after 5 entries."""
        policy = CheckpointPolicy(entry_count=5)
        for i in range(4):
            assert not policy.should_checkpoint(entries_since_last=i + 1)
        assert policy.should_checkpoint(entries_since_last=5)

    def test_no_policy_never_triggers(self):
        """Without a policy, no automatic checkpointing."""
        policy = CheckpointPolicy()
        assert not policy.should_checkpoint(entries_since_last=1000)
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_checkpoints.py -v`
Expected: FAIL — module not found

**Step 3: Implement checkpoint module**

Create `primitives/checkpoint.py`:
- `CheckpointPolicy` dataclass: `entry_count: int | None`, `interval_seconds: int | None`
- `should_checkpoint(entries_since_last, seconds_since_last)` method
- `create_checkpoint()`: reads current Merkle snapshot, builds checkpoint object, signs with audit key (detached JWS), stores in `checkpoints` table, returns checkpoint dict
- Checkpoint object shape matches the proposal:

```python
{
    "version": "0.3",
    "service_id": str,
    "checkpoint_id": str,
    "range": {"first_sequence": int, "last_sequence": int},
    "merkle_root": str,
    "previous_checkpoint": str | None,
    "timestamp": str,
    "entry_count": int,
    "signature": str,
}
```

Add `checkpoints` table to `database.py`:

```sql
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id TEXT NOT NULL,
    first_sequence INTEGER NOT NULL,
    last_sequence INTEGER NOT NULL,
    merkle_root TEXT NOT NULL,
    previous_checkpoint TEXT,
    timestamp TEXT NOT NULL,
    entry_count INTEGER NOT NULL,
    signature TEXT NOT NULL
)
```

Add `get_checkpoints(limit=10)` and `store_checkpoint(ckpt)` functions.

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_checkpoints.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add examples/anip/anip_server/primitives/checkpoint.py examples/anip/anip_server/data/database.py examples/anip/tests/test_checkpoints.py
git commit -m "feat: add checkpoint model, policy, and storage (Python)"
```

---

### Task 6: Checkpoint Model and Storage — TypeScript

**Files:**
- Create: `examples/anip-ts/src/checkpoint.ts`
- Modify: `examples/anip-ts/src/data/database.ts` — add `checkpoints` table
- Create: `examples/anip-ts/tests/checkpoint.test.ts`

**Step 1–4:** Mirror Python implementation. Same checkpoint object shape, same policy logic, same table schema. Use `jose` for detached JWS signing.

**Step 5: Commit**

```bash
git add examples/anip-ts/src/checkpoint.ts examples/anip-ts/src/data/database.ts examples/anip-ts/tests/checkpoint.test.ts
git commit -m "feat: add checkpoint model, policy, and storage (TypeScript)"
```

---

### Task 7: Automatic Checkpointing on Audit Write — Python

**Files:**
- Modify: `examples/anip/anip_server/data/database.py` — trigger checkpoint based on policy after each audit write
- Modify: `examples/anip/anip_server/main.py` — configure checkpoint policy from config/env
- Test: `examples/anip/tests/test_checkpoints.py` — add auto-checkpoint tests

**Step 1: Write the failing test**

Add to `test_checkpoints.py`:

```python
def test_auto_checkpoint_after_n_entries(client):
    """With entry_count policy=3, a checkpoint should be created after every 3 entries."""
    from anip_server.data.database import set_checkpoint_policy, get_checkpoints
    from anip_server.primitives.checkpoint import CheckpointPolicy
    set_checkpoint_policy(CheckpointPolicy(entry_count=3))
    token = _issue_token(client, "search_flights", ["travel.search"])
    for _ in range(3):
        client.post("/anip/invoke/search_flights",
                    json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                    headers={"Authorization": f"Bearer {token}"})
    checkpoints = get_checkpoints()
    assert len(checkpoints) >= 1
```

**Step 2: Implement auto-checkpointing**

In `database.py`:
- Add `_checkpoint_policy: CheckpointPolicy | None` module state
- Add `_entries_since_checkpoint: int` counter
- In `log_invocation()`, after writing entry and updating Merkle tree, check `_checkpoint_policy.should_checkpoint()` and call `create_checkpoint()` if triggered
- Add `set_checkpoint_policy(policy)` function
- In `main.py`, read `ANIP_CHECKPOINT_CADENCE` env var (e.g., `"10"` for every 10 entries) and set policy on startup

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```bash
git add examples/anip/anip_server/data/database.py examples/anip/anip_server/main.py examples/anip/tests/test_checkpoints.py
git commit -m "feat: auto-checkpoint on audit write based on policy (Python)"
```

---

### Task 8: Automatic Checkpointing on Audit Write — TypeScript

**Files:**
- Modify: `examples/anip-ts/src/data/database.ts`
- Modify: `examples/anip-ts/src/server.ts`
- Test: `examples/anip-ts/tests/checkpoint.test.ts`

Mirror Python implementation from Task 7.

**Commit:**

```bash
git add examples/anip-ts/src/data/database.ts examples/anip-ts/src/server.ts examples/anip-ts/tests/checkpoint.test.ts
git commit -m "feat: auto-checkpoint on audit write based on policy (TypeScript)"
```

---

### Task 9: Trust Level Declaration in Discovery and Manifest — Python

**Files:**
- Modify: `examples/anip/anip_server/main.py` — add `trust_level` to discovery response
- Modify: `examples/anip/anip_server/primitives/models.py` — add trust posture to manifest model
- Modify: `examples/anip/anip_server/primitives/manifest.py` — populate trust posture
- Test: `examples/anip/tests/test_discovery.py` — add trust level tests

**Step 1: Write the failing tests**

Add to `tests/test_discovery.py`:

```python
def test_discovery_has_trust_level(client):
    """Discovery should include a trust_level field."""
    resp = client.get("/.well-known/anip")
    data = resp.json()["anip_discovery"]
    assert "trust_level" in data
    assert data["trust_level"] in ("signed", "anchored", "attested")


def test_manifest_has_trust_posture(client):
    """Manifest should include full trust posture declaration."""
    resp = client.get("/anip/manifest")
    manifest = resp.json()
    assert "trust" in manifest
    assert manifest["trust"]["level"] in ("signed", "anchored", "attested")
```

**Step 2: Implement trust declarations**

In `models.py`, add:

```python
class AnchoringPolicy(BaseModel):
    cadence: str | None = None     # e.g. "5m", "100 entries"
    max_lag: str | None = None     # e.g. "15m"
    sink: str | None = None        # URI-scheme identifier (witness:, https:, file:)
    sink_name: str | None = None   # human-readable sink label

class TrustPolicyTrigger(BaseModel):
    trigger: dict[str, Any]
    action: str  # e.g. "immediate_checkpoint"

class TrustPosture(BaseModel):
    level: str = "signed"  # "signed" | "anchored" | "attested"
    anchoring: AnchoringPolicy | None = None
    policies: list[TrustPolicyTrigger] | None = None
```

Add `trust: TrustPosture | None = None` to `ANIPManifest`.

In `main.py` discovery endpoint, add `"trust_level": manifest.trust.level` to the response.

In `manifest.py`, populate `trust` based on config:
- If `ANIP_TRUST_LEVEL` env var is set, use it
- Default: `"signed"` (existing v0.2 behavior)
- If `"anchored"`, also populate `anchoring` from env/config

**Step 3: Run tests, verify pass**

**Step 4: Update protocol version**

Change `protocol: "anip/0.2"` → `protocol: "anip/0.3"` in manifest and discovery.

**Step 5: Commit**

```bash
git add examples/anip/anip_server/main.py examples/anip/anip_server/primitives/models.py examples/anip/anip_server/primitives/manifest.py examples/anip/tests/test_discovery.py
git commit -m "feat: trust level declaration in discovery and manifest (Python)"
```

---

### Task 10: Trust Level Declaration in Discovery and Manifest — TypeScript

**Files:**
- Modify: `examples/anip-ts/src/server.ts`
- Modify: `examples/anip-ts/src/types.ts`
- Test: `examples/anip-ts/tests/discovery.test.ts`

Mirror Python implementation from Task 9.

**Commit:**

```bash
git add examples/anip-ts/src/server.ts examples/anip-ts/src/types.ts examples/anip-ts/tests/discovery.test.ts
git commit -m "feat: trust level declaration in discovery and manifest (TypeScript)"
```

---

### Task 11: GET /anip/checkpoints Endpoint — Python

**Files:**
- Modify: `examples/anip/anip_server/main.py` — add checkpoint list + individual checkpoint endpoints
- Test: `examples/anip/tests/test_checkpoints.py` — add endpoint tests

**Step 1: Write the failing tests**

Add to `test_checkpoints.py`:

```python
def test_checkpoints_endpoint_returns_list(client):
    """GET /anip/checkpoints should return checkpoint metadata."""
    token = _issue_token(client, "search_flights", ["travel.search"])
    client.post("/anip/invoke/search_flights",
                json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                headers={"Authorization": f"Bearer {token}"})
    create_checkpoint()
    resp = client.get("/anip/checkpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert "checkpoints" in data
    assert len(data["checkpoints"]) >= 1
    ckpt = data["checkpoints"][0]
    assert "merkle_root" in ckpt
    assert "range" in ckpt
    assert "signature" in ckpt
    assert "timestamp" in ckpt


def test_checkpoints_endpoint_with_limit(client):
    """GET /anip/checkpoints?limit=1 should return at most 1 checkpoint."""
    resp = client.get("/anip/checkpoints?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()["checkpoints"]) <= 1


def test_checkpoints_endpoint_empty_when_no_checkpoints(client):
    """GET /anip/checkpoints returns empty list when no checkpoints exist."""
    resp = client.get("/anip/checkpoints")
    assert resp.status_code == 200
    assert resp.json()["checkpoints"] == [] or isinstance(resp.json()["checkpoints"], list)


def test_individual_checkpoint_with_inclusion_proof(client):
    """GET /anip/checkpoints/{id}?include_proof=true&leaf_index=N should return inclusion proof."""
    token = _issue_token(client, "search_flights", ["travel.search"])
    for _ in range(3):
        client.post("/anip/invoke/search_flights",
                    json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                    headers={"Authorization": f"Bearer {token}"})
    create_checkpoint()
    checkpoints = get_checkpoints(limit=1)
    ckpt_id = checkpoints[0]["checkpoint_id"]
    resp = client.get(f"/anip/checkpoints/{ckpt_id}?include_proof=true&leaf_index=0")
    assert resp.status_code == 200
    data = resp.json()
    assert "checkpoint" in data
    assert "inclusion_proof" in data
    proof = data["inclusion_proof"]
    assert "leaf_index" in proof
    assert "path" in proof
    assert isinstance(proof["path"], list)
    assert "merkle_root" in proof


def test_individual_checkpoint_with_consistency_proof(client):
    """GET /anip/checkpoints/{id}?consistency_from={old_id} should return consistency proof."""
    token = _issue_token(client, "search_flights", ["travel.search"])
    for _ in range(3):
        client.post("/anip/invoke/search_flights",
                    json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                    headers={"Authorization": f"Bearer {token}"})
    create_checkpoint()
    for _ in range(3):
        client.post("/anip/invoke/search_flights",
                    json={"origin": "SEA", "destination": "SFO", "date": "2026-04-01"},
                    headers={"Authorization": f"Bearer {token}"})
    create_checkpoint()
    checkpoints = get_checkpoints(limit=10)
    old_id = checkpoints[0]["checkpoint_id"]
    new_id = checkpoints[1]["checkpoint_id"]
    resp = client.get(f"/anip/checkpoints/{new_id}?consistency_from={old_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "consistency_proof" in data
    proof = data["consistency_proof"]
    assert "old_size" in proof
    assert "new_size" in proof
    assert "path" in proof
```

**Step 2: Implement endpoints**

In `main.py`:

```python
@app.get("/anip/checkpoints")
def get_checkpoints_endpoint(limit: int = 10):
    """Checkpoint inspection surface — convenience/status, not the trust anchor."""
    checkpoints = get_checkpoints(limit=limit)
    return {"checkpoints": checkpoints}


@app.get("/anip/checkpoints/{checkpoint_id}")
def get_checkpoint_detail(
    checkpoint_id: str,
    include_proof: bool = False,
    leaf_index: int | None = None,
    consistency_from: str | None = None,
):
    """Individual checkpoint with optional Merkle proofs.

    Query params:
    - include_proof=true&leaf_index=N: returns inclusion proof for leaf N
    - consistency_from=<old_checkpoint_id>: returns consistency proof from old to this checkpoint
    """
    ckpt = get_checkpoint_by_id(checkpoint_id)
    if not ckpt:
        return JSONResponse(status_code=404, content={"error": "checkpoint_not_found"})

    result = {"checkpoint": ckpt}

    if include_proof and leaf_index is not None:
        proof = get_merkle_inclusion_proof(leaf_index)
        result["inclusion_proof"] = {
            "leaf_index": leaf_index,
            "path": proof["path"],
            "merkle_root": ckpt["merkle_root"],
        }

    if consistency_from:
        old_ckpt = get_checkpoint_by_id(consistency_from)
        if old_ckpt:
            proof = get_merkle_consistency_proof(old_ckpt["range"]["last_sequence"])
            result["consistency_proof"] = {
                "old_size": old_ckpt["range"]["last_sequence"],
                "new_size": ckpt["range"]["last_sequence"],
                "old_root": old_ckpt["merkle_root"],
                "new_root": ckpt["merkle_root"],
                "path": proof,
            }

    return result
```

Add to discovery endpoints:
- `"checkpoints": "/anip/checkpoints"`
- `"checkpoint_detail": "/anip/checkpoints/{checkpoint_id}"`

Add `get_checkpoint_by_id(id)` and `get_merkle_consistency_proof(old_size)` to `database.py`.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```bash
git add examples/anip/anip_server/main.py examples/anip/anip_server/data/database.py examples/anip/tests/test_checkpoints.py
git commit -m "feat: add GET /anip/checkpoints + /{id} with Merkle proofs (Python)"
```

---

### Task 12: GET /anip/checkpoints Endpoint — TypeScript

**Files:**
- Modify: `examples/anip-ts/src/server.ts`
- Modify: `examples/anip-ts/src/data/database.ts`
- Test: `examples/anip-ts/tests/checkpoint.test.ts`

Mirror Python implementation from Task 11 — both the list endpoint and the `/{checkpoint_id}` detail endpoint with inclusion and consistency proof support.

**Commit:**

```bash
git add examples/anip-ts/src/server.ts examples/anip-ts/src/data/database.ts examples/anip-ts/tests/checkpoint.test.ts
git commit -m "feat: add GET /anip/checkpoints + /{id} with Merkle proofs (TypeScript)"
```

---

### Task 13: Checkpoint Sink Interface + Local Filesystem Sink — Python

**Files:**
- Create: `examples/anip/anip_server/primitives/sinks.py` — sink interface + local FS implementation
- Modify: `examples/anip/anip_server/primitives/checkpoint.py` — publish to sink after creating checkpoint
- Test: `examples/anip/tests/test_sinks.py`

**Step 1: Write the failing tests**

```python
"""Tests for checkpoint sinks."""
import os
import json
import tempfile
import pytest
from anip_server.primitives.sinks import LocalFileSink


class TestLocalFileSink:
    def test_publish_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sink = LocalFileSink(tmpdir)
            ckpt = {
                "checkpoint_id": "ckpt-001",
                "merkle_root": "sha256:abc123",
                "timestamp": "2026-03-12T18:00:00Z",
            }
            sink.publish(ckpt)
            files = os.listdir(tmpdir)
            assert len(files) == 1
            with open(os.path.join(tmpdir, files[0])) as f:
                stored = json.load(f)
            assert stored["checkpoint_id"] == "ckpt-001"

    def test_publish_multiple_creates_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sink = LocalFileSink(tmpdir)
            for i in range(3):
                sink.publish({"checkpoint_id": f"ckpt-{i:03d}", "merkle_root": f"sha256:{i}"})
            assert len(os.listdir(tmpdir)) == 3
```

**Step 2: Implement sinks**

Create `primitives/sinks.py`:

```python
"""Checkpoint sink interface and implementations."""
import json
import os
from abc import ABC, abstractmethod
from typing import Any


class CheckpointSink(ABC):
    """Interface for publishing checkpoints to external storage."""

    @abstractmethod
    def publish(self, checkpoint: dict[str, Any]) -> None:
        """Publish a checkpoint. Should be idempotent."""
        ...


class LocalFileSink(CheckpointSink):
    """Writes checkpoints as JSON files to a local directory.

    Reference implementation — not a real external anchor.
    Production deployments should use an immutable store or witness service.
    """

    def __init__(self, directory: str) -> None:
        self._directory = directory
        os.makedirs(directory, exist_ok=True)

    def publish(self, checkpoint: dict[str, Any]) -> None:
        filename = f"{checkpoint['checkpoint_id']}.json"
        path = os.path.join(self._directory, filename)
        with open(path, "w") as f:
            json.dump(checkpoint, f, indent=2, sort_keys=True)
```

Wire into `checkpoint.py`: after storing checkpoint in DB, publish to sink if configured.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```bash
git add examples/anip/anip_server/primitives/sinks.py examples/anip/anip_server/primitives/checkpoint.py examples/anip/tests/test_sinks.py
git commit -m "feat: add checkpoint sink interface + local filesystem sink (Python)"
```

---

### Task 14: Checkpoint Sink Interface + Local Filesystem Sink — TypeScript

**Files:**
- Create: `examples/anip-ts/src/sinks.ts`
- Modify: `examples/anip-ts/src/checkpoint.ts`
- Create: `examples/anip-ts/tests/sinks.test.ts`

Mirror Python implementation from Task 13.

**Commit:**

```bash
git add examples/anip-ts/src/sinks.ts examples/anip-ts/src/checkpoint.ts examples/anip-ts/tests/sinks.test.ts
git commit -m "feat: add checkpoint sink interface + local filesystem sink (TypeScript)"
```

---

### Task 15: Update SPEC.md for v0.3

**Files:**
- Modify: `SPEC.md` — add trust levels section, checkpoint format, policy hooks, update protocol version and roadmap

**Step 1: Add trust levels to section 7 (Trust Model)**

After the existing v0.2 trust content, add a new subsection:

```markdown
### Trust Levels

ANIP defines three trust assurance levels:

| Level | Protocol Name | Description |
|-------|--------------|-------------|
| Bronze | `signed` | Signed tokens, manifests, and audit entries with local verification |
| Silver | `anchored` | Signed + Merkle tree accumulation + external checkpoint publication |
| Gold | `attested` | Anchored + independent third-party attestation (v0.4) |

A service declares its trust level in both discovery (`trust_level` field) and the manifest (full `trust` object with anchoring policy).
```

**Step 2: Add checkpoint format specification**

Add the checkpoint object schema, detached JWS signing requirement, and Merkle tree algorithm (SHA-256, RFC 6962). Include the full checkpoint JSON schema:

```json
{
  "version": "0.3",
  "service_id": "<string>",
  "checkpoint_id": "<string>",
  "range": { "first_sequence": "<int>", "last_sequence": "<int>" },
  "merkle_root": "sha256:<hex>",
  "previous_checkpoint": "sha256:<hex> | null",
  "timestamp": "<ISO 8601>",
  "entry_count": "<int>",
  "signature": "<detached JWS, signed by audit key>"
}
```

**Step 3: Add Merkle proof format specification**

Standardize the proof schemas so that any ANIP implementation produces interoperable proofs:

Inclusion proof schema:
```json
{
  "leaf_index": "<int>",
  "merkle_root": "sha256:<hex>",
  "path": [
    { "hash": "<hex>", "side": "left | right" }
  ]
}
```

Consistency proof schema:
```json
{
  "old_size": "<int>",
  "new_size": "<int>",
  "old_root": "sha256:<hex>",
  "new_root": "sha256:<hex>",
  "path": [
    { "hash": "<hex>", "type": "old | new" }
  ]
}
```

Document:
- Leaf hash: `SHA-256(0x00 || data)` per RFC 6962 §2.1
- Node hash: `SHA-256(0x01 || left || right)` per RFC 6962 §2.1
- Canonical entry serialization: all fields except `signature` and `id`, sorted keys, no whitespace
- Verification algorithm for both proof types

**Step 4: Add policy hooks specification**

Document the policy hook vocabulary: `cadence`, `max_lag`, `sink`, trigger/action pairs.

**Step 5: Add checkpoint location declaration vocabulary**

Standardize how a service declares where checkpoints are published. The `sink` field in the trust posture uses a URI-like scheme:

| Scheme | Example | Description |
|--------|---------|-------------|
| `witness:` | `witness:acme-audit` | Named witness service (deployment-defined) |
| `https:` | `https://audit.example.com/checkpoints` | HTTPS endpoint accepting checkpoint POST |
| `file:` | `file:///var/anip/checkpoints/` | Local filesystem (reference/dev only) |

The protocol standardizes the scheme vocabulary. Deployments define the actual endpoints. Callers can discover checkpoint locations from the manifest trust posture and independently verify published artifacts.

**Step 6: Update discovery endpoint schema**

Add `trust_level` field to the discovery response specification.

**Step 7: Add /anip/checkpoints endpoint specification**

Document both endpoints:
- `GET /anip/checkpoints` — list recent checkpoints (query: `limit`)
- `GET /anip/checkpoints/{checkpoint_id}` — individual checkpoint with optional proofs (query: `include_proof`, `leaf_index`, `consistency_from`)

Explicitly note: this is a convenience/inspection surface, not the authoritative trust anchor. Callers should verify checkpoint artifacts independently.

**Step 8: Update roadmap table**

Add v0.3 features to the roadmap table. Update protocol version references from `anip/0.2` to `anip/0.3`.

**Step 7: Commit**

```bash
git add SPEC.md
git commit -m "docs: add v0.3 trust levels, checkpointing, and policy hooks to SPEC"
```

---

### Task 16: Update trust-model-v0.2.md → trust-model.md

**Files:**
- Rename: `docs/trust-model-v0.2.md` → `docs/trust-model.md`
- Modify: `docs/trust-model.md` — add v0.3 sections on Merkle trees, checkpointing, and trust levels
- Modify: `README.md`, `SECURITY.md` — update links

**Step 1: Rename the file**

```bash
git mv docs/trust-model-v0.2.md docs/trust-model.md
```

**Step 2: Add v0.3 content**

Add sections covering:
- Trust levels (signed/anchored/attested)
- Merkle tree structure and how it relates to the existing hash chain
- Checkpoint format and signing
- External anchoring model
- Policy hooks

Keep all existing v0.2 content — it's still accurate and forms the foundation.

**Step 3: Update references**

Update all `docs/trust-model-v0.2.md` links in README.md, SECURITY.md, SPEC.md, and any other files that reference it.

**Step 4: Commit**

```bash
git add docs/trust-model.md docs/trust-model-v0.2.md README.md SECURITY.md SPEC.md
git commit -m "docs: rename trust-model-v0.2.md → trust-model.md and add v0.3 content"
```

---

### Task 17: Conformance Tests for v0.3

**Files:**
- Modify: `examples/anip/tests/test_conformance.py` — add v0.3 trust level conformance tests

**Step 1: Add conformance tests**

```python
class TestTrustLevel:
    def test_discovery_declares_trust_level(self):
        """Discovery MUST include trust_level."""
        resp = requests.get(f"{BASE}/. well-known/anip")
        data = resp.json()["anip_discovery"]
        assert "trust_level" in data
        assert data["trust_level"] in ("signed", "anchored", "attested")

    def test_manifest_declares_trust_posture(self):
        """Manifest MUST include trust object."""
        resp = requests.get(f"{BASE}/anip/manifest")
        manifest = resp.json()
        assert "trust" in manifest
        assert manifest["trust"]["level"] in ("signed", "anchored", "attested")

    def test_checkpoints_endpoint_exists(self):
        """GET /anip/checkpoints MUST return 200."""
        resp = requests.get(f"{BASE}/anip/checkpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert "checkpoints" in data
        assert isinstance(data["checkpoints"], list)


class TestAnchoredTrust:
    """Tests that only apply to services declaring trust_level: anchored."""

    def test_checkpoint_has_merkle_root(self):
        """Checkpoints MUST include a Merkle root."""
        resp = requests.get(f"{BASE}/anip/checkpoints?limit=1")
        checkpoints = resp.json()["checkpoints"]
        if not checkpoints:
            pytest.skip("No checkpoints available")
        assert checkpoints[0]["merkle_root"].startswith("sha256:")

    def test_checkpoint_has_signature(self):
        """Checkpoints MUST be signed."""
        resp = requests.get(f"{BASE}/anip/checkpoints?limit=1")
        checkpoints = resp.json()["checkpoints"]
        if not checkpoints:
            pytest.skip("No checkpoints available")
        assert "signature" in checkpoints[0]

    def test_inclusion_proof_format(self):
        """Inclusion proofs MUST follow standardized schema."""
        resp = requests.get(f"{BASE}/anip/checkpoints?limit=1")
        checkpoints = resp.json()["checkpoints"]
        if not checkpoints:
            pytest.skip("No checkpoints available")
        ckpt_id = checkpoints[0]["checkpoint_id"]
        resp = requests.get(f"{BASE}/anip/checkpoints/{ckpt_id}?include_proof=true&leaf_index=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "inclusion_proof" in data
        proof = data["inclusion_proof"]
        assert "leaf_index" in proof
        assert "merkle_root" in proof
        assert "path" in proof
        assert isinstance(proof["path"], list)
        for step in proof["path"]:
            assert "hash" in step
            assert step["side"] in ("left", "right")

    def test_checkpoint_detail_endpoint(self):
        """GET /anip/checkpoints/{id} MUST return the checkpoint."""
        resp = requests.get(f"{BASE}/anip/checkpoints?limit=1")
        checkpoints = resp.json()["checkpoints"]
        if not checkpoints:
            pytest.skip("No checkpoints available")
        ckpt_id = checkpoints[0]["checkpoint_id"]
        resp = requests.get(f"{BASE}/anip/checkpoints/{ckpt_id}")
        assert resp.status_code == 200
        assert resp.json()["checkpoint"]["checkpoint_id"] == ckpt_id
```

**Step 2: Run against both servers, verify pass**

**Step 3: Commit**

```bash
git add examples/anip/tests/test_conformance.py
git commit -m "test: add v0.3 trust level and checkpoint conformance tests"
```

---

### Task 18: Update README and Documentation

**Files:**
- Modify: `README.md` — update status section, version references, trust model link
- Modify: `SECURITY.md` — update trust model references

**Step 1: Update README.md**

- Update status section: v0.3 with anchored trust
- Update the v0.2 callout block to describe v0.3
- Update trust model link if renamed
- Add checkpoint endpoint to the "What exists today" list

**Step 2: Update SECURITY.md**

- Update trust model references and version

**Step 3: Commit**

```bash
git add README.md SECURITY.md
git commit -m "docs: update README and SECURITY.md for v0.3"
```
