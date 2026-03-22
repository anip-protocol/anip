using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Anip.Core;
using Anip.Crypto;

namespace Anip.Server;

/// <summary>
/// Audit log operations: append entries with hash-chain and signature, query entries.
/// </summary>
public static class AuditLog
{
    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    /// <summary>
    /// Assigns a sequence number, computes previous_hash, signs the entry, and appends it.
    /// </summary>
    public static AuditEntry AppendAudit(KeyManager keys, IStorage storage, AuditEntry entry)
    {
        // Set timestamp if not already set.
        if (string.IsNullOrEmpty(entry.Timestamp))
        {
            entry.Timestamp = DateTime.UtcNow.ToString("o");
        }

        // 1. Append entry (storage assigns sequence_number and previous_hash).
        var appended = storage.AppendAuditEntry(entry);

        // 2. Sign the entry.
        var signature = SignAuditEntry(keys, appended);

        // 3. Update the signature in storage.
        storage.UpdateAuditSignature(appended.SequenceNumber, signature);

        appended.Signature = signature;
        return appended;
    }

    /// <summary>
    /// Queries audit entries scoped to a root principal.
    /// </summary>
    public static AuditResponse QueryAudit(IStorage storage, string rootPrincipal, AuditFilters filters)
    {
        // Always scope to root_principal.
        filters.RootPrincipal = rootPrincipal;

        var entries = storage.QueryAuditEntries(filters);

        return new AuditResponse { Entries = entries };
    }

    /// <summary>
    /// Signs an audit entry's canonical JSON (excluding "signature" and "id" fields).
    /// Returns a compact JWS containing the SHA-256 hash of the canonical entry.
    /// </summary>
    internal static string SignAuditEntry(KeyManager keys, AuditEntry entry)
    {
        // Get canonical JSON (excluding "signature" and "id", sorted keys).
        var json = JsonSerializer.Serialize(entry, s_serializerOptions);
        var dict = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(json)!;

        dict.Remove("signature");
        dict.Remove("id");

        var sorted = new SortedDictionary<string, JsonElement>(dict);
        var canonical = JsonSerializer.Serialize(sorted);
        var canonicalBytes = Encoding.UTF8.GetBytes(canonical);

        var hash = SHA256.HashData(canonicalBytes);
        var hashHex = Convert.ToHexString(hash).ToLowerInvariant();

        // Sign as JWT with the audit key.
        var header = new Dictionary<string, string>
        {
            ["alg"] = "ES256",
            ["typ"] = "JWT",
            ["kid"] = keys.GetAuditKid()
        };

        var claims = new Dictionary<string, object>
        {
            ["audit_hash"] = hashHex
        };

        return JwtSigner.SignRaw(keys.GetAuditKey(), keys.GetAuditKid(), header, claims);
    }
}
