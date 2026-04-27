using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Anip.Core;

namespace Anip.Crypto;

/// <summary>
/// Verifies ES256 JWTs and extracts DelegationToken data.
/// </summary>
public static class JwtVerifier
{
    /// <summary>
    /// Verifies an ES256 JWT and extracts the DelegationToken from its claims.
    /// </summary>
    /// <param name="jwt">The compact JWT string.</param>
    /// <param name="publicKey">EC P-256 public key for verification.</param>
    /// <param name="expectedIssuer">Expected issuer claim value.</param>
    /// <returns>The extracted DelegationToken.</returns>
    /// <exception cref="AnipError">Thrown when the token is invalid, expired, or has wrong issuer.</exception>
    public static DelegationToken VerifyAndExtract(string jwt, ECDsa publicKey, string expectedIssuer)
    {
        var parts = jwt.Split('.', 4);
        if (parts.Length != 3)
        {
            throw new AnipError(Constants.FailureInvalidToken, "Invalid JWT format: expected 3 parts");
        }

        var headerB64 = parts[0];
        var claimsB64 = parts[1];
        var signatureB64 = parts[2];

        // Decode and validate header.
        var headerJson = Encoding.UTF8.GetString(KeyManager.Base64UrlDecode(headerB64));
        var header = JsonSerializer.Deserialize<Dictionary<string, string>>(headerJson);
        if (header == null || !header.TryGetValue("alg", out var alg) || alg != "ES256")
        {
            throw new AnipError(Constants.FailureInvalidToken, $"Unsupported algorithm: {header?["alg"] ?? "none"}");
        }

        // Verify signature.
        var signingInput = Encoding.UTF8.GetBytes($"{headerB64}.{claimsB64}");
        var signatureBytes = KeyManager.Base64UrlDecode(signatureB64);

        bool valid;
        try
        {
            valid = publicKey.VerifyData(signingInput, signatureBytes, HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation);
        }
        catch
        {
            valid = false;
        }

        if (!valid)
        {
            throw new AnipError(Constants.FailureInvalidToken, "Invalid signature");
        }

        // Decode claims.
        var claimsJson = Encoding.UTF8.GetString(KeyManager.Base64UrlDecode(claimsB64));
        var claims = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(claimsJson)
            ?? throw new AnipError(Constants.FailureInvalidToken, "Failed to decode claims");

        // Check expiration.
        if (claims.TryGetValue("exp", out var expElement))
        {
            var exp = expElement.GetInt64();
            if (DateTimeOffset.UtcNow.ToUnixTimeSeconds() > exp)
            {
                throw new AnipError(Constants.FailureTokenExpired, "Token has expired");
            }
        }

        // Check issuer.
        if (!string.IsNullOrEmpty(expectedIssuer) && claims.TryGetValue("iss", out var issElement))
        {
            var iss = issElement.GetString();
            if (iss != expectedIssuer)
            {
                throw new AnipError(Constants.FailureInvalidToken, $"Issuer mismatch: expected \"{expectedIssuer}\", got \"{iss}\"");
            }
        }

        // Extract DelegationToken fields.
        var token = new DelegationToken();

        if (claims.TryGetValue("jti", out var jti))
            token.TokenId = jti.GetString() ?? "";

        if (claims.TryGetValue("iss", out var issuer))
            token.Issuer = issuer.GetString() ?? "";

        if (claims.TryGetValue("sub", out var sub))
            token.Subject = sub.GetString() ?? "";

        if (claims.TryGetValue("scope", out var scope) && scope.ValueKind == JsonValueKind.Array)
        {
            token.Scope = scope.EnumerateArray()
                .Select(e => e.GetString() ?? "")
                .ToList();
        }

        if (claims.TryGetValue("purpose", out var purpose))
        {
            token.Purpose = JsonSerializer.Deserialize<Purpose>(purpose.GetRawText()) ?? new Purpose();
        }

        if (claims.TryGetValue("capability", out var capability))
        {
            // capability is a top-level claim that mirrors purpose.capability.
            // The purpose object already has it, so we only set it if purpose didn't.
            if (string.IsNullOrEmpty(token.Purpose.Capability))
            {
                token.Purpose.Capability = capability.GetString() ?? "";
            }
        }

        if (claims.TryGetValue("root_principal", out var rootPrincipal))
        {
            var rp = rootPrincipal.GetString();
            token.RootPrincipal = string.IsNullOrEmpty(rp) ? null : rp;
        }

        if (claims.TryGetValue("caller_class", out var callerClass))
        {
            var cc = callerClass.GetString();
            token.CallerClass = string.IsNullOrEmpty(cc) ? null : cc;
        }

        if (claims.TryGetValue("exp", out var expClaim))
        {
            var expUnix = expClaim.GetInt64();
            token.Expires = DateTimeOffset.FromUnixTimeSeconds(expUnix).ToString("o");
        }

        if (claims.TryGetValue("parent_token_id", out var parent))
            token.Parent = parent.GetString();

        // v0.23 SPEC §4.8: extract session_id claim if present.
        if (claims.TryGetValue("anip:session_id", out var sid))
        {
            var sidStr = sid.GetString();
            token.SessionId = string.IsNullOrEmpty(sidStr) ? null : sidStr;
        }

        return token;
    }
}
