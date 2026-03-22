using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Anip.Core;
using Anip.Crypto;

namespace Anip.Server;

/// <summary>
/// Creates and manages audit log checkpoints with Merkle tree integrity.
/// </summary>
public static class CheckpointManager
{
    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    /// <summary>
    /// Builds a checkpoint from all audit entries and stores it.
    /// Returns null if there are no new entries since the last checkpoint.
    /// </summary>
    public static Checkpoint? CreateCheckpoint(KeyManager keys, IStorage storage, string serviceId)
    {
        // Get max sequence.
        var maxSeq = storage.GetMaxAuditSequence();
        if (maxSeq == 0)
            return null; // No entries.

        // Get the last checkpoint to determine the range.
        var checkpoints = storage.ListCheckpoints(100);

        Checkpoint? lastCp = null;
        int lastCovered = 0;
        if (checkpoints.Count > 0)
        {
            lastCp = checkpoints[^1];
            if (lastCp.Range.TryGetValue("last_sequence", out var ls))
                lastCovered = ls;
        }

        if (maxSeq <= lastCovered)
            return null; // No new entries.

        // Full reconstruction from entry 1 (cumulative tree).
        var entries = storage.GetAuditEntriesRange(1, maxSeq);

        // Build Merkle tree.
        var tree = new MerkleTree();
        foreach (var entry in entries)
        {
            tree.AddLeaf(HashChain.CanonicalBytes(entry));
        }

        // Compute checkpoint number.
        var cpNumber = 1;
        string? prevCheckpointHash = null;

        if (lastCp != null)
        {
            // Parse number from last checkpoint ID.
            if (lastCp.CheckpointId.StartsWith("ckpt-") &&
                int.TryParse(lastCp.CheckpointId.AsSpan(5), out var n))
            {
                cpNumber = n + 1;
            }

            // Compute hash of previous checkpoint.
            var prevBody = JsonSerializer.Serialize(lastCp, s_serializerOptions);
            var prevMap = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(prevBody)!;
            var canonicalPrev = JsonSerializer.Serialize(prevMap);
            var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonicalPrev));
            prevCheckpointHash = $"sha256:{Convert.ToHexString(hash).ToLowerInvariant()}";
        }

        var cp = new Checkpoint
        {
            Version = "0.3",
            ServiceId = serviceId,
            CheckpointId = $"ckpt-{cpNumber}",
            Range = new Dictionary<string, int>
            {
                ["first_sequence"] = 1,
                ["last_sequence"] = maxSeq
            },
            MerkleRoot = tree.Root(),
            PreviousCheckpoint = prevCheckpointHash,
            Timestamp = DateTime.UtcNow.ToString("o"),
            EntryCount = entries.Count
        };

        // Sign the checkpoint.
        var cpJson = JsonSerializer.Serialize(cp, s_serializerOptions);
        var signature = JwsSigner.SignDetached(keys.GetAuditKey(), keys.GetAuditKid(),
            Encoding.UTF8.GetBytes(cpJson));

        // Store the checkpoint.
        storage.StoreCheckpoint(cp, signature);

        return cp;
    }

    /// <summary>
    /// Generates an inclusion proof for a leaf at the given index within the checkpoint's range.
    /// Returns the proof steps and an optional unavailability reason.
    /// If entries have been deleted (expired), returns (null, "audit_entries_expired").
    /// </summary>
    public static (List<ProofStep>? Proof, string? UnavailableReason) GenerateInclusionProof(
        IStorage storage,
        Checkpoint cp,
        int leafIndex)
    {
        var firstSeq = cp.Range["first_sequence"];
        var lastSeq = cp.Range["last_sequence"];

        // Get entries in the checkpoint range.
        var entries = storage.GetAuditEntriesRange(firstSeq, lastSeq);

        var expectedCount = lastSeq - firstSeq + 1;
        if (entries.Count < expectedCount)
        {
            // Entries have been deleted/expired.
            return (null, "audit_entries_expired");
        }

        // Rebuild Merkle tree.
        var tree = new MerkleTree();
        foreach (var entry in entries)
        {
            tree.AddLeaf(HashChain.CanonicalBytes(entry));
        }

        // Validate leaf index.
        if (leafIndex < 0 || leafIndex >= tree.LeafCount)
        {
            throw new ArgumentOutOfRangeException(nameof(leafIndex),
                $"leaf index {leafIndex} out of range [0, {tree.LeafCount})");
        }

        var proof = tree.InclusionProof(leafIndex);
        return (proof, null);
    }
}
