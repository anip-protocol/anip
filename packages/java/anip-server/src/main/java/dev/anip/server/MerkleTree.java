package dev.anip.server;

import dev.anip.core.Constants;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;

/**
 * RFC 6962 Merkle hash tree implementation.
 * Leaf: SHA256(0x00 || data), Node: SHA256(0x01 || left || right).
 */
public class MerkleTree {

    private final List<byte[]> leaves = new ArrayList<>();

    /**
     * Adds a data element to the tree.
     */
    public void addLeaf(byte[] data) {
        leaves.add(leafHash(data));
    }

    /**
     * Returns the number of leaves.
     */
    public int leafCount() {
        return leaves.size();
    }

    /**
     * Returns the Merkle root as "sha256:{hex}".
     */
    public String root() {
        if (leaves.isEmpty()) {
            byte[] h = sha256(new byte[0]);
            return "sha256:" + hexEncode(h);
        }
        byte[] rootBytes = computeRoot(0, leaves.size());
        return "sha256:" + hexEncode(rootBytes);
    }

    /**
     * Generates the inclusion proof path for the leaf at the given index.
     */
    public List<ProofStep> inclusionProof(int index) {
        if (index < 0 || index >= leaves.size()) {
            throw new IllegalArgumentException(
                    "leaf index " + index + " out of range [0, " + leaves.size() + ")");
        }
        List<ProofStep> path = new ArrayList<>();
        buildInclusionPath(index, 0, leaves.size(), path);
        return path;
    }

    /**
     * Verifies that data at the given index is included in the tree with the expected root.
     */
    public static boolean verifyInclusion(byte[] data, List<ProofStep> proof, String expectedRoot) {
        byte[] current = leafHash(data);
        for (ProofStep step : proof) {
            byte[] sibling = hexDecode(step.hash());
            if ("left".equals(step.side())) {
                current = nodeHash(sibling, current);
            } else {
                current = nodeHash(current, sibling);
            }
        }
        return ("sha256:" + hexEncode(current)).equals(expectedRoot);
    }

    // --- Internal ---

    private byte[] computeRoot(int lo, int hi) {
        int n = hi - lo;
        if (n == 1) {
            return leaves.get(lo);
        }
        int split = largestPowerOf2LessThan(n);
        byte[] left = computeRoot(lo, lo + split);
        byte[] right = computeRoot(lo + split, hi);
        return nodeHash(left, right);
    }

    private void buildInclusionPath(int index, int lo, int hi, List<ProofStep> path) {
        int n = hi - lo;
        if (n == 1) {
            return;
        }
        int split = largestPowerOf2LessThan(n);
        if (index - lo < split) {
            buildInclusionPath(index, lo, lo + split, path);
            byte[] right = computeRoot(lo + split, hi);
            path.add(new ProofStep(hexEncode(right), "right"));
        } else {
            buildInclusionPath(index, lo + split, hi, path);
            byte[] left = computeRoot(lo, lo + split);
            path.add(new ProofStep(hexEncode(left), "left"));
        }
    }

    static int largestPowerOf2LessThan(int n) {
        if (n <= 1) {
            return 0;
        }
        int k = 1;
        while (k * 2 < n) {
            k *= 2;
        }
        return k;
    }

    static byte[] leafHash(byte[] data) {
        byte[] input = new byte[1 + data.length];
        input[0] = Constants.LEAF_HASH_PREFIX;
        System.arraycopy(data, 0, input, 1, data.length);
        return sha256(input);
    }

    static byte[] nodeHash(byte[] left, byte[] right) {
        byte[] input = new byte[1 + left.length + right.length];
        input[0] = Constants.NODE_HASH_PREFIX;
        System.arraycopy(left, 0, input, 1, left.length);
        System.arraycopy(right, 0, input, 1 + left.length, right.length);
        return sha256(input);
    }

    private static byte[] sha256(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            return md.digest(data);
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }

    static String hexEncode(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }

    static byte[] hexDecode(String hex) {
        byte[] b = new byte[hex.length() / 2];
        for (int i = 0; i < b.length; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }

    /**
     * A single step in a Merkle inclusion proof.
     *
     * @param hash the sibling hash (hex-encoded, no prefix)
     * @param side "left" or "right" — which side the sibling is on
     */
    public record ProofStep(String hash, String side) {}
}
