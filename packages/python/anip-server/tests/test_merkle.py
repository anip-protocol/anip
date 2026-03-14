"""Tests for RFC 6962 Merkle tree."""
from anip_server.merkle import MerkleTree


def test_single_leaf():
    tree = MerkleTree()
    tree.add_leaf(b"hello")
    assert tree.leaf_count == 1
    assert tree.root.startswith("sha256:")


def test_root_changes_with_new_leaf():
    tree = MerkleTree()
    tree.add_leaf(b"a")
    root1 = tree.root
    tree.add_leaf(b"b")
    assert tree.root != root1


def test_inclusion_proof():
    tree = MerkleTree()
    for i in range(8):
        tree.add_leaf(f"leaf-{i}".encode())
    proof = tree.inclusion_proof(3)
    assert len(proof) > 0
    assert tree.verify_inclusion(3, b"leaf-3", proof, tree.root)


def test_inclusion_proof_wrong_data_fails():
    tree = MerkleTree()
    for i in range(4):
        tree.add_leaf(f"leaf-{i}".encode())
    proof = tree.inclusion_proof(0)
    assert not tree.verify_inclusion(0, b"wrong", proof, tree.root)


def test_consistency_proof():
    tree = MerkleTree()
    for i in range(4):
        tree.add_leaf(f"leaf-{i}".encode())
    old_root = tree.root
    old_size = tree.leaf_count
    for i in range(4, 8):
        tree.add_leaf(f"leaf-{i}".encode())
    proof = tree.consistency_proof(old_size)
    assert MerkleTree.verify_consistency_static(
        old_root, old_size, tree.root, tree.leaf_count, proof
    )


def test_snapshot():
    tree = MerkleTree()
    tree.add_leaf(b"data")
    snap = tree.snapshot()
    assert "root" in snap
    assert snap["leaf_count"] == 1
