using System.Security.Cryptography;

namespace Anip.Crypto;

/// <summary>
/// Serializes public keys as a JWKS (JSON Web Key Set).
/// </summary>
public static class JwksSerializer
{
    /// <summary>
    /// Serializes both public keys from the KeyManager as a JWKS.
    /// Returns a dictionary suitable for JSON serialization as {"keys": [...]}.
    /// Only includes public key parameters (no private key material).
    /// </summary>
    public static Dictionary<string, object> ToJwks(KeyManager keyManager)
    {
        return new Dictionary<string, object>
        {
            ["keys"] = new List<Dictionary<string, object>>
            {
                PublicKeyToJwkMap(keyManager.GetSigningKey(), keyManager.GetSigningKid(), "sig"),
                PublicKeyToJwkMap(keyManager.GetAuditKey(), keyManager.GetAuditKid(), "audit")
            }
        };
    }

    private static Dictionary<string, object> PublicKeyToJwkMap(ECDsa key, string kid, string use)
    {
        var jwk = KeyManager.ExportPublicKeyToJwk(key);
        return new Dictionary<string, object>
        {
            ["kty"] = jwk["kty"],
            ["crv"] = jwk["crv"],
            ["x"] = jwk["x"],
            ["y"] = jwk["y"],
            ["kid"] = kid,
            ["alg"] = "ES256",
            ["use"] = use
        };
    }
}
