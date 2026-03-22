using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Anip.Core;

namespace Anip.Server;

/// <summary>
/// Computes canonical hashes for audit entry hash-chain linking.
/// </summary>
public static class HashChain
{
    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    /// <summary>
    /// Computes the canonical SHA-256 hash of an audit entry for hash-chain linking.
    /// Excludes "signature" and "id" fields, sorts keys, uses compact JSON.
    /// </summary>
    public static string ComputeEntryHash(AuditEntry entry)
    {
        var canonical = CanonicalBytes(entry);
        var hash = SHA256.HashData(canonical);
        return $"sha256:{Convert.ToHexString(hash).ToLowerInvariant()}";
    }

    /// <summary>
    /// Returns the canonical JSON bytes of an audit entry (excluding "signature" and "id", sorted keys).
    /// Used for both hash-chain and Merkle leaf hashing.
    /// </summary>
    internal static byte[] CanonicalBytes(AuditEntry entry)
    {
        var json = JsonSerializer.Serialize(entry, s_serializerOptions);
        var dict = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(json)!;

        // Remove signature and id fields.
        dict.Remove("signature");
        dict.Remove("id");

        // Sort keys and build ordered dictionary.
        var sorted = new SortedDictionary<string, JsonElement>(dict);

        // Serialize with sorted keys.
        var canonical = JsonSerializer.Serialize(sorted);
        return Encoding.UTF8.GetBytes(canonical);
    }
}
