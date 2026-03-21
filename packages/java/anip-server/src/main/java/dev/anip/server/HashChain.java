package dev.anip.server;

import dev.anip.core.AuditEntry;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Map;
import java.util.TreeMap;

/**
 * Computes the canonical hash of an audit entry for hash-chain linking.
 * Matches the Go/Python implementation: excludes "signature" and "id" fields,
 * sorts keys, uses compact JSON.
 */
final class HashChain {

    private HashChain() {}

    /**
     * Computes the hash of an audit entry for hash chaining.
     * Returns "sha256:{hex}".
     */
    static String computeEntryHash(AuditEntry entry) {
        byte[] canonical = canonicalBytes(entry);
        return "sha256:" + sha256Hex(canonical);
    }

    /**
     * Returns the canonical JSON bytes of an audit entry for Merkle leaf hashing.
     * Excludes "signature" and "id" fields, sorts keys.
     */
    static byte[] canonicalBytes(AuditEntry entry) {
        Map<String, Object> map = JsonHelper.toMap(entry);
        // Remove signature and id fields.
        map.remove("signature");
        map.remove("id");
        TreeMap<String, Object> sorted = new TreeMap<>(map);
        String canonical = JsonHelper.canonicalJson(sorted);
        return canonical.getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Computes SHA-256 hex digest of the given bytes.
     */
    static String sha256Hex(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(data);
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b & 0xff));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }
}
