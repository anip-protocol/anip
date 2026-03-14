import { describe, it, expect } from "vitest";
import { MerkleTree } from "../src/merkle.js";

describe("MerkleTree", () => {
  it("computes root for single leaf", () => {
    const tree = new MerkleTree();
    tree.addLeaf(Buffer.from("hello"));
    expect(tree.leafCount).toBe(1);
    expect(tree.root).toMatch(/^sha256:/);
  });

  it("root changes with new leaf", () => {
    const tree = new MerkleTree();
    tree.addLeaf(Buffer.from("a"));
    const root1 = tree.root;
    tree.addLeaf(Buffer.from("b"));
    expect(tree.root).not.toBe(root1);
  });

  it("produces valid inclusion proof", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 8; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const proof = tree.inclusionProof(3);
    expect(proof.length).toBeGreaterThan(0);
    expect(tree.verifyInclusion(3, Buffer.from("leaf-3"), proof)).toBe(true);
  });

  it("rejects wrong data in inclusion proof", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 4; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const proof = tree.inclusionProof(0);
    expect(tree.verifyInclusion(0, Buffer.from("wrong"), proof)).toBe(false);
  });

  it("produces valid consistency proof", () => {
    const tree = new MerkleTree();
    for (let i = 0; i < 4; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const oldRoot = tree.root;
    const oldSize = tree.leafCount;
    for (let i = 4; i < 8; i++) tree.addLeaf(Buffer.from(`leaf-${i}`));
    const proof = tree.consistencyProof(oldSize);
    expect(
      MerkleTree.verifyConsistencyStatic(oldRoot, oldSize, tree.root, tree.leafCount, proof)
    ).toBe(true);
  });
});
