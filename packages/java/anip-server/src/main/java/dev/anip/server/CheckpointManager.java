package dev.anip.server;

import dev.anip.core.AuditEntry;
import dev.anip.core.Checkpoint;
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
 * Manages Merkle checkpoints over audit log entries.
 * Uses RFC 6962 Merkle tree construction.
 */
public final class CheckpointManager {

    private CheckpointManager() {}

    /**
     * Creates a checkpoint from audit entries and stores it.
     * Returns null if there are no new entries to checkpoint.
     *
     * @param km        the key manager for signing
     * @param storage   the storage backend
     * @param serviceId the service identifier
     * @return the created checkpoint, or null if no new entries
     */
    public static Checkpoint createCheckpoint(KeyManager km, Storage storage,
                                               String serviceId) throws Exception {
        // Get max sequence.
        int maxSeq = storage.getMaxAuditSequence();
        if (maxSeq == 0) {
            return null; // No entries.
        }

        // Get the last checkpoint to determine the range.
        List<Checkpoint> checkpoints = storage.listCheckpoints(100);

        Checkpoint lastCP = null;
        int lastCovered = 0;
        if (!checkpoints.isEmpty()) {
            lastCP = checkpoints.get(checkpoints.size() - 1);
            Integer ls = lastCP.getRange().get("last_sequence");
            if (ls != null) {
                lastCovered = ls;
            }
        }

        if (maxSeq <= lastCovered) {
            return null; // No new entries.
        }

        // Full reconstruction from entry 1 (cumulative tree).
        List<AuditEntry> entries = storage.getAuditEntriesRange(1, maxSeq);

        // Build Merkle tree.
        MerkleTree tree = new MerkleTree();
        for (AuditEntry entry : entries) {
            tree.addLeaf(HashChain.canonicalBytes(entry));
        }

        // Compute checkpoint number.
        int cpNumber = 1;
        String prevCheckpointHash = null;
        if (lastCP != null) {
            // Parse number from last checkpoint ID.
            String lastId = lastCP.getCheckpointId();
            if (lastId.startsWith("ckpt-")) {
                try {
                    cpNumber = Integer.parseInt(lastId.substring(5)) + 1;
                } catch (NumberFormatException ignored) {
                }
            }

            // Compute hash of previous checkpoint.
            String prevBody = JsonHelper.toJson(lastCP);
            @SuppressWarnings("unchecked")
            Map<String, Object> prevMap = JsonHelper.MAPPER.readValue(prevBody, Map.class);
            TreeMap<String, Object> sortedPrev = new TreeMap<>(prevMap);
            String canonicalPrev = JsonHelper.canonicalJson(sortedPrev);
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(canonicalPrev.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder("sha256:");
            for (byte b : hash) {
                sb.append(String.format("%02x", b & 0xff));
            }
            prevCheckpointHash = sb.toString();
        }

        String checkpointId = "ckpt-" + cpNumber;
        Map<String, Integer> range = Map.of("first_sequence", 1, "last_sequence", maxSeq);
        String merkleRoot = tree.root();
        String timestamp = DateTimeFormatter.ISO_INSTANT.format(Instant.now());

        Checkpoint cp = new Checkpoint(
                "0.3", serviceId, checkpointId, range,
                merkleRoot, prevCheckpointHash, timestamp,
                entries.size(), null
        );

        // Sign the checkpoint.
        String cpJson = JsonHelper.toJson(cp);
        String signature = JwtSigner.signDetachedJwsAudit(km, cpJson.getBytes(StandardCharsets.UTF_8));

        // Store the checkpoint.
        storage.storeCheckpoint(cp, signature);

        return cp;
    }

    /**
     * Generates an inclusion proof for a leaf at the given index within the checkpoint's range.
     * Returns the result containing proof steps and the Merkle root.
     * If entries have been deleted (expired), returns a result with proofUnavailable set.
     *
     * @param storage   the storage backend
     * @param cp        the checkpoint
     * @param leafIndex the 0-based leaf index
     * @return the inclusion proof result
     */
    public static InclusionProofResult generateInclusionProof(
            Storage storage, Checkpoint cp, int leafIndex) throws Exception {

        Integer firstSeq = cp.getRange().get("first_sequence");
        Integer lastSeq = cp.getRange().get("last_sequence");
        if (firstSeq == null || lastSeq == null) {
            throw new IllegalArgumentException("Checkpoint missing range");
        }

        // Get entries in the checkpoint range.
        List<AuditEntry> entries = storage.getAuditEntriesRange(firstSeq, lastSeq);

        int expectedCount = lastSeq - firstSeq + 1;
        if (entries.size() < expectedCount) {
            // Entries have been deleted/expired.
            return new InclusionProofResult(null, "audit_entries_expired");
        }

        // Rebuild Merkle tree.
        MerkleTree tree = new MerkleTree();
        for (AuditEntry entry : entries) {
            tree.addLeaf(HashChain.canonicalBytes(entry));
        }

        // Validate leaf index.
        if (leafIndex < 0 || leafIndex >= tree.leafCount()) {
            throw new IllegalArgumentException(
                    "leaf index " + leafIndex + " out of range [0, " + tree.leafCount() + ")");
        }

        List<MerkleTree.ProofStep> proof = tree.inclusionProof(leafIndex);
        return new InclusionProofResult(proof, null);
    }

    /**
     * Result of an inclusion proof generation.
     *
     * @param proofSteps       the proof steps (null if unavailable)
     * @param proofUnavailable the reason the proof is unavailable (null if available)
     */
    public record InclusionProofResult(
            List<MerkleTree.ProofStep> proofSteps,
            String proofUnavailable
    ) {}
}
