package dev.anip.server;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class MerkleTreeTest {

    @Test
    void emptyTreeRoot() {
        MerkleTree tree = new MerkleTree();
        String root = tree.root();
        assertNotNull(root);
        assertTrue(root.startsWith("sha256:"));
    }

    @Test
    void singleLeafRoot() {
        MerkleTree tree = new MerkleTree();
        tree.addLeaf("hello".getBytes(StandardCharsets.UTF_8));
        String root = tree.root();
        assertNotNull(root);
        assertTrue(root.startsWith("sha256:"));
        assertEquals(1, tree.leafCount());
    }

    @Test
    void twoLeafRoot() {
        MerkleTree tree = new MerkleTree();
        tree.addLeaf("leaf1".getBytes(StandardCharsets.UTF_8));
        tree.addLeaf("leaf2".getBytes(StandardCharsets.UTF_8));
        String root = tree.root();
        assertNotNull(root);
        assertTrue(root.startsWith("sha256:"));
        assertEquals(2, tree.leafCount());
    }

    @Test
    void rootDeterministic() {
        MerkleTree t1 = new MerkleTree();
        MerkleTree t2 = new MerkleTree();
        for (int i = 0; i < 5; i++) {
            byte[] data = ("entry-" + i).getBytes(StandardCharsets.UTF_8);
            t1.addLeaf(data);
            t2.addLeaf(data);
        }
        assertEquals(t1.root(), t2.root());
    }

    @Test
    void rootDifferentForDifferentData() {
        MerkleTree t1 = new MerkleTree();
        MerkleTree t2 = new MerkleTree();
        t1.addLeaf("a".getBytes(StandardCharsets.UTF_8));
        t2.addLeaf("b".getBytes(StandardCharsets.UTF_8));
        assertNotEquals(t1.root(), t2.root());
    }

    @Test
    void inclusionProofSingleLeaf() {
        MerkleTree tree = new MerkleTree();
        tree.addLeaf("data".getBytes(StandardCharsets.UTF_8));

        List<MerkleTree.ProofStep> proof = tree.inclusionProof(0);
        assertNotNull(proof);
        assertEquals(0, proof.size()); // Single leaf has empty proof.
    }

    @Test
    void inclusionProofTwoLeaves() {
        MerkleTree tree = new MerkleTree();
        tree.addLeaf("leaf0".getBytes(StandardCharsets.UTF_8));
        tree.addLeaf("leaf1".getBytes(StandardCharsets.UTF_8));

        List<MerkleTree.ProofStep> proof0 = tree.inclusionProof(0);
        assertEquals(1, proof0.size());
        assertEquals("right", proof0.get(0).side());

        List<MerkleTree.ProofStep> proof1 = tree.inclusionProof(1);
        assertEquals(1, proof1.size());
        assertEquals("left", proof1.get(0).side());
    }

    @Test
    void inclusionProofVerification() {
        MerkleTree tree = new MerkleTree();
        for (int i = 0; i < 7; i++) {
            tree.addLeaf(("entry-" + i).getBytes(StandardCharsets.UTF_8));
        }

        String root = tree.root();

        // Verify each leaf.
        for (int i = 0; i < 7; i++) {
            byte[] data = ("entry-" + i).getBytes(StandardCharsets.UTF_8);
            List<MerkleTree.ProofStep> proof = tree.inclusionProof(i);
            assertTrue(MerkleTree.verifyInclusion(data, proof, root),
                    "Inclusion proof failed for leaf " + i);
        }
    }

    @Test
    void inclusionProofInvalidIndex() {
        MerkleTree tree = new MerkleTree();
        tree.addLeaf("data".getBytes(StandardCharsets.UTF_8));

        assertThrows(IllegalArgumentException.class, () -> tree.inclusionProof(-1));
        assertThrows(IllegalArgumentException.class, () -> tree.inclusionProof(1));
    }

    @Test
    void verifyInclusionWrongData() {
        MerkleTree tree = new MerkleTree();
        tree.addLeaf("correct".getBytes(StandardCharsets.UTF_8));
        tree.addLeaf("other".getBytes(StandardCharsets.UTF_8));

        String root = tree.root();
        List<MerkleTree.ProofStep> proof = tree.inclusionProof(0);

        // Wrong data should fail.
        assertFalse(MerkleTree.verifyInclusion(
                "wrong".getBytes(StandardCharsets.UTF_8), proof, root));
    }

    @Test
    void largestPowerOf2LessThan() {
        assertEquals(0, MerkleTree.largestPowerOf2LessThan(1));
        assertEquals(1, MerkleTree.largestPowerOf2LessThan(2));
        assertEquals(2, MerkleTree.largestPowerOf2LessThan(3));
        assertEquals(4, MerkleTree.largestPowerOf2LessThan(5));
        assertEquals(4, MerkleTree.largestPowerOf2LessThan(7));
        assertEquals(8, MerkleTree.largestPowerOf2LessThan(9));
    }

    @Test
    void proofForLargerTree() {
        MerkleTree tree = new MerkleTree();
        for (int i = 0; i < 16; i++) {
            tree.addLeaf(("item-" + i).getBytes(StandardCharsets.UTF_8));
        }

        // Power-of-2 tree: each proof should have log2(16) = 4 steps.
        for (int i = 0; i < 16; i++) {
            List<MerkleTree.ProofStep> proof = tree.inclusionProof(i);
            assertEquals(4, proof.size(), "Proof for leaf " + i + " should have 4 steps");
            assertTrue(MerkleTree.verifyInclusion(
                    ("item-" + i).getBytes(StandardCharsets.UTF_8),
                    proof, tree.root()));
        }
    }
}
