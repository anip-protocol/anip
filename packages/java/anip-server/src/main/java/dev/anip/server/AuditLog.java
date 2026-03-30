package dev.anip.server;

import dev.anip.core.AuditEntry;
import dev.anip.core.AuditFilters;
import dev.anip.core.AuditResponse;
import dev.anip.crypto.JwtSigner;
import dev.anip.crypto.KeyManager;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Manages audit log operations: append with hash chain and signature, query with filters.
 */
public final class AuditLog {

    private AuditLog() {}

    /**
     * Assigns a sequence number, computes prev_hash, signs the entry, and appends it.
     *
     * @param km      the key manager for signing
     * @param storage the storage backend
     * @param entry   the audit entry to append (modified in place)
     */
    public static void appendAudit(KeyManager km, Storage storage, AuditEntry entry) throws Exception {
        // Set timestamp if not already set.
        if (entry.getTimestamp() == null || entry.getTimestamp().isEmpty()) {
            entry.setTimestamp(DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
        }

        // 1. Append entry (storage assigns sequence_number and previous_hash).
        AuditEntry appended = storage.appendAuditEntry(entry);

        // Copy assigned fields back.
        entry.setSequenceNumber(appended.getSequenceNumber());
        entry.setPreviousHash(appended.getPreviousHash());

        // 2. Sign the entry.
        String signature = signAuditEntry(km, entry);

        // 3. Update the signature in storage.
        storage.updateAuditSignature(entry.getSequenceNumber(), signature);

        entry.setSignature(signature);
    }

    /**
     * Queries audit entries scoped to a root principal.
     *
     * @param storage       the storage backend
     * @param rootPrincipal the root principal to scope queries to
     * @param filters       the query filters
     * @return the audit response
     */
    public static AuditResponse queryAudit(Storage storage, String rootPrincipal,
                                            AuditFilters filters) throws Exception {
        // Always scope to root_principal.
        AuditFilters scopedFilters = new AuditFilters(
                filters.getCapability(),
                rootPrincipal,
                filters.getSince(),
                filters.getInvocationId(),
                filters.getClientReferenceId(),
                filters.getTaskId(),
                filters.getParentInvocationId(),
                filters.getLimit()
        );

        List<AuditEntry> entries = storage.queryAuditEntries(scopedFilters);

        return new AuditResponse(entries, entries.size(), rootPrincipal,
                filters.getCapability(), filters.getSince());
    }

    /**
     * Signs an audit entry using the audit key.
     * Computes SHA-256 of canonical JSON (excluding "signature" and "id"), then signs as JWT.
     */
    private static String signAuditEntry(KeyManager km, AuditEntry entry) throws Exception {
        Map<String, Object> map = JsonHelper.toMap(entry);
        // Remove signature and id fields.
        map.remove("signature");
        map.remove("id");
        TreeMap<String, Object> sorted = new TreeMap<>(map);
        String canonical = JsonHelper.canonicalJson(sorted);
        byte[] canonicalBytes = canonical.getBytes(StandardCharsets.UTF_8);

        // Compute hash.
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] hash = md.digest(canonicalBytes);
        StringBuilder hashHex = new StringBuilder();
        for (byte b : hash) {
            hashHex.append(String.format("%02x", b & 0xff));
        }

        // Sign using the audit key as a JWT containing the hash.
        Map<String, Object> claims = Map.of("audit_hash", hashHex.toString());
        return JwtSigner.signAuditJwt(km, claims);
    }
}
