using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Anip.Core;

namespace Anip.Crypto;

/// <summary>
/// Signs delegation tokens as ES256 JWTs.
/// </summary>
public static class JwtSigner
{
    /// <summary>
    /// Signs a DelegationToken as an ES256 JWT.
    /// </summary>
    /// <param name="privateKey">EC P-256 private key for signing.</param>
    /// <param name="keyId">Key ID to include in the JWT header.</param>
    /// <param name="token">The delegation token to sign.</param>
    /// <param name="issuer">The issuer claim value.</param>
    /// <returns>A compact JWT string.</returns>
    public static string SignToken(ECDsa privateKey, string keyId, DelegationToken token, string issuer)
    {
        // Build header.
        var header = new Dictionary<string, string>
        {
            ["alg"] = "ES256",
            ["typ"] = "JWT",
            ["kid"] = keyId
        };

        // Build claims.
        var claims = new Dictionary<string, object>
        {
            ["jti"] = token.TokenId,
            ["iss"] = issuer,
            ["sub"] = token.Subject,
            ["scope"] = token.Scope,
            ["capability"] = token.Purpose.Capability,
            ["purpose"] = token.Purpose,
            ["root_principal"] = token.RootPrincipal ?? "",
            ["caller_class"] = token.CallerClass ?? ""
        };

        // Parse the expiry time and set exp claim.
        if (DateTimeOffset.TryParse(token.Expires, out var expiresAt))
        {
            claims["exp"] = expiresAt.ToUnixTimeSeconds();
        }

        if (token.Parent != null)
        {
            claims["parent_token_id"] = token.Parent;
        }

        // v0.23 SPEC §4.8: bind session identity into the signed JWT so the
        // server can authoritatively resolve session_id from the bearer token
        // (never from caller-supplied invocation input).
        if (!string.IsNullOrEmpty(token.SessionId))
        {
            claims["anip:session_id"] = token.SessionId;
        }

        return SignRaw(privateKey, keyId, header, claims);
    }

    /// <summary>
    /// Signs arbitrary claims as an ES256 JWT. Used internally and for audit entry signing.
    /// </summary>
    internal static string SignRaw(ECDsa privateKey, string keyId, Dictionary<string, string> header, Dictionary<string, object> claims)
    {
        var options = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
        };

        var headerJson = JsonSerializer.Serialize(header, options);
        var claimsJson = JsonSerializer.Serialize(claims, options);

        var headerB64 = KeyManager.Base64UrlEncode(Encoding.UTF8.GetBytes(headerJson));
        var claimsB64 = KeyManager.Base64UrlEncode(Encoding.UTF8.GetBytes(claimsJson));

        var signingInput = $"{headerB64}.{claimsB64}";
        var signingInputBytes = Encoding.UTF8.GetBytes(signingInput);

        // ES256: sign with SHA-256.
        var signatureBytes = privateKey.SignData(signingInputBytes, HashAlgorithmName.SHA256, DSASignatureFormat.IeeeP1363FixedFieldConcatenation);

        var signatureB64 = KeyManager.Base64UrlEncode(signatureBytes);

        return $"{signingInput}.{signatureB64}";
    }
}
