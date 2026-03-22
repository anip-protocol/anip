using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Anip.Crypto;

/// <summary>
/// Creates detached JWS signatures for payload integrity verification.
/// Used for the X-ANIP-Signature header on manifest responses.
/// </summary>
public static class JwsSigner
{
    /// <summary>
    /// Creates a detached JWS signature for the given payload.
    /// The result is a compact JWS with an empty payload section: "header..signature".
    /// </summary>
    /// <param name="privateKey">EC P-256 private key for signing.</param>
    /// <param name="keyId">Key ID to include in the JWS header.</param>
    /// <param name="payload">The payload bytes to sign.</param>
    /// <returns>A detached JWS string in the format "header..signature".</returns>
    public static string SignDetached(ECDsa privateKey, string keyId, byte[] payload)
    {
        var header = new Dictionary<string, string>
        {
            ["alg"] = "ES256",
            ["kid"] = keyId
        };

        var headerJson = JsonSerializer.Serialize(header);
        var headerB64 = KeyManager.Base64UrlEncode(Encoding.UTF8.GetBytes(headerJson));
        var payloadB64 = KeyManager.Base64UrlEncode(payload);

        // The signing input includes the payload, but the output omits it.
        var signingInput = $"{headerB64}.{payloadB64}";
        var signingInputBytes = Encoding.UTF8.GetBytes(signingInput);

        var signatureBytes = privateKey.SignData(signingInputBytes, HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation);

        var signatureB64 = KeyManager.Base64UrlEncode(signatureBytes);

        // Detached: omit the payload part.
        return $"{headerB64}..{signatureB64}";
    }

    /// <summary>
    /// Verifies a detached JWS signature against the given payload.
    /// </summary>
    /// <param name="publicKey">EC P-256 public key for verification.</param>
    /// <param name="payload">The original payload bytes.</param>
    /// <param name="signature">The detached JWS string ("header..signature").</param>
    /// <returns>True if the signature is valid.</returns>
    public static bool VerifyDetached(ECDsa publicKey, byte[] payload, string signature)
    {
        var parts = signature.Split('.', 4);
        if (parts.Length != 3 || parts[1] != "")
        {
            return false;
        }

        var headerB64 = parts[0];
        var sigB64 = parts[2];

        // Decode and validate header.
        try
        {
            var headerJson = Encoding.UTF8.GetString(KeyManager.Base64UrlDecode(headerB64));
            var header = JsonSerializer.Deserialize<Dictionary<string, string>>(headerJson);
            if (header == null || !header.TryGetValue("alg", out var alg) || alg != "ES256")
            {
                return false;
            }
        }
        catch
        {
            return false;
        }

        // Reconstruct signing input with the payload.
        var payloadB64 = KeyManager.Base64UrlEncode(payload);
        var signingInput = $"{headerB64}.{payloadB64}";
        var signingInputBytes = Encoding.UTF8.GetBytes(signingInput);

        try
        {
            var signatureBytes = KeyManager.Base64UrlDecode(sigB64);
            return publicKey.VerifyData(signingInputBytes, signatureBytes, HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation);
        }
        catch
        {
            return false;
        }
    }
}
