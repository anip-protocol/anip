"""Tests for RFC 6962 Merkle tree implementation."""
import pytest
from anip_flight_demo.primitives.merkle import MerkleTree


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
        root_at_10 = tree.root
        count_at_10 = tree.leaf_count
        proof = tree.consistency_proof(count_at_5)
        assert isinstance(proof, list)
        assert all(isinstance(h, bytes) for h in proof)
        assert len(proof) > 0  # non-trivial proof
        assert MerkleTree.verify_consistency_static(
            root_at_5, count_at_5, root_at_10, count_at_10, proof
        )

    def test_consistency_proof_rejects_wrong_old_root(self):
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"entry-{i}".encode())
        count_at_5 = tree.leaf_count
        for i in range(5, 10):
            tree.add_leaf(f"entry-{i}".encode())
        proof = tree.consistency_proof(count_at_5)
        fake_root = "sha256:" + "00" * 32
        assert not MerkleTree.verify_consistency_static(
            fake_root, count_at_5, tree.root, tree.leaf_count, proof
        )

    def test_consistency_proof_rejects_wrong_new_root(self):
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"entry-{i}".encode())
        root_at_5 = tree.root
        count_at_5 = tree.leaf_count
        for i in range(5, 10):
            tree.add_leaf(f"entry-{i}".encode())
        proof = tree.consistency_proof(count_at_5)
        fake_root = "sha256:" + "ff" * 32
        assert not MerkleTree.verify_consistency_static(
            root_at_5, count_at_5, fake_root, tree.leaf_count, proof
        )

    def test_consistency_proof_multiple_sizes(self):
        """Verify consistency across many growth steps."""
        tree = MerkleTree()
        snapshots = []
        for i in range(20):
            tree.add_leaf(f"entry-{i}".encode())
            if (i + 1) % 4 == 0:
                snapshots.append((tree.root, tree.leaf_count))
        for j in range(len(snapshots)):
            for k in range(j + 1, len(snapshots)):
                old_root, old_size = snapshots[j]
                new_root, new_size = snapshots[k]
                proof_tree = MerkleTree()
                for i in range(new_size):
                    proof_tree.add_leaf(f"entry-{i}".encode())
                proof = proof_tree.consistency_proof(old_size)
                assert MerkleTree.verify_consistency_static(
                    old_root, old_size, new_root, new_size, proof
                ), f"Failed consistency {old_size} -> {new_size}"

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
