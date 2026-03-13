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

  // Cross-validation: roots must match the Python implementation exactly
  describe("cross-validation with Python implementation", () => {
    it("empty tree matches Python root", () => {
      const tree = new MerkleTree();
      expect(tree.root).toBe(
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      );
    });

    it("single leaf 'hello' matches Python root", () => {
      const tree = new MerkleTree();
      tree.addLeaf(Buffer.from("hello"));
      expect(tree.root).toBe(
        "sha256:8a2a5c9b768827de5a9552c38a044c66959c68f6d2f21b5260af54d2f87db827"
      );
    });

    it("three leaves 'a','b','c' matches Python root", () => {
      const tree = new MerkleTree();
      for (const x of ["a", "b", "c"]) tree.addLeaf(Buffer.from(x));
      expect(tree.root).toBe(
        "sha256:36642e73c2540ab121e3a6bf9545b0a24982cd830eb13d3cd19de3ce6c021ec1"
      );
    });

    it("8 entries matches Python root", () => {
      const tree = new MerkleTree();
      for (let i = 0; i < 8; i++) tree.addLeaf(Buffer.from(`entry-${i}`));
      expect(tree.root).toBe(
        "sha256:dfcc13b9b0ca932c68de3d59eaaa8fe266a9c8091c0300e8405ebfeb0d0e5832"
      );
    });
  });
});
