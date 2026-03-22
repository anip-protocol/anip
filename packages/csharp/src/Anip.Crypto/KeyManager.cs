using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Anip.Crypto;

/// <summary>
/// Manages two EC P-256 key pairs: one for delegation token signing, one for audit entries.
/// </summary>
public class KeyManager
{
    private ECDsa _signingKey = null!;
    private ECDsa _auditKey = null!;
    private string _signingKid = null!;
    private string _auditKid = null!;

    /// <summary>
    /// Creates a KeyManager by loading keys from keyPath or generating new ones.
    /// If keyPath is null or empty, keys are generated in memory only (ephemeral).
    /// </summary>
    public KeyManager(string? keyPath = null)
    {
        if (!string.IsNullOrEmpty(keyPath))
        {
            var keysFile = keyPath;

            if (Directory.Exists(keyPath))
            {
                keysFile = Path.Combine(keyPath, "anip-keys.json");
            }
            else if (!File.Exists(keyPath))
            {
                // Determine if it looks like a directory (ends with / or no extension).
                if (keyPath.EndsWith('/') || keyPath.EndsWith(Path.DirectorySeparatorChar) || Path.GetExtension(keyPath) == "")
                {
                    Directory.CreateDirectory(keyPath);
                    keysFile = Path.Combine(keyPath, "anip-keys.json");
                }
            }

            if (File.Exists(keysFile))
            {
                LoadFromFile(keysFile);
                return;
            }

            Generate();
            SaveToFile(keysFile);
            return;
        }

        // In-memory only.
        Generate();
    }

    // Internal constructor for testing — takes pre-built keys directly.
    internal KeyManager(ECDsa signingKey, ECDsa auditKey)
    {
        _signingKey = signingKey;
        _auditKey = auditKey;
        _signingKid = ComputeKid(signingKey);
        _auditKid = ComputeKid(auditKey);
    }

    /// <summary>Returns the delegation/signing private key.</summary>
    public ECDsa GetSigningKey() => _signingKey;

    /// <summary>Returns the audit private key.</summary>
    public ECDsa GetAuditKey() => _auditKey;

    /// <summary>Returns the key ID (JWK thumbprint) for the signing key.</summary>
    public string GetSigningKid() => _signingKid;

    /// <summary>Returns the key ID (JWK thumbprint) for the audit key.</summary>
    public string GetAuditKid() => _auditKid;

    private void Generate()
    {
        _signingKey = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        _auditKey = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        _signingKid = ComputeKid(_signingKey);
        _auditKid = ComputeKid(_auditKey);
    }

    /// <summary>
    /// Computes a JWK thumbprint (RFC 7638) for an EC P-256 public key,
    /// returning the first 16 characters of the base64url-encoded SHA-256 hash.
    /// </summary>
    internal static string ComputeKid(ECDsa key)
    {
        var parameters = key.ExportParameters(false);
        var x = Base64UrlEncode(PadToFieldSize(parameters.Q.X!, 32));
        var y = Base64UrlEncode(PadToFieldSize(parameters.Q.Y!, 32));

        // RFC 7638: members in lexicographic order.
        var thumbprintInput = $"{{\"crv\":\"P-256\",\"kty\":\"EC\",\"x\":\"{x}\",\"y\":\"{y}\"}}";
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(thumbprintInput));
        var thumbprint = Base64UrlEncode(hash);

        return thumbprint.Length > 16 ? thumbprint[..16] : thumbprint;
    }

    private void LoadFromFile(string path)
    {
        var json = File.ReadAllText(path);
        var persisted = JsonSerializer.Deserialize<PersistedKeys>(json)
            ?? throw new InvalidOperationException($"Failed to deserialize keys from {path}");

        _signingKey = ImportPrivateKeyFromJwk(persisted.DelegationJwk);
        _signingKid = persisted.DelegationKid;
        _auditKey = ImportPrivateKeyFromJwk(persisted.AuditJwk);
        _auditKid = persisted.AuditKid;
    }

    private void SaveToFile(string path)
    {
        var dir = Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
        }

        var persisted = new PersistedKeys
        {
            DelegationJwk = ExportPrivateKeyToJwk(_signingKey),
            DelegationKid = _signingKid,
            AuditJwk = ExportPrivateKeyToJwk(_auditKey),
            AuditKid = _auditKid
        };

        var json = JsonSerializer.Serialize(persisted, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(path, json);

        // Restrict file permissions on Unix.
        if (!OperatingSystem.IsWindows())
        {
            File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite);
        }
    }

    internal static Dictionary<string, string> ExportPrivateKeyToJwk(ECDsa key)
    {
        var parameters = key.ExportParameters(true);
        return new Dictionary<string, string>
        {
            ["kty"] = "EC",
            ["crv"] = "P-256",
            ["x"] = Base64UrlEncode(PadToFieldSize(parameters.Q.X!, 32)),
            ["y"] = Base64UrlEncode(PadToFieldSize(parameters.Q.Y!, 32)),
            ["d"] = Base64UrlEncode(PadToFieldSize(parameters.D!, 32))
        };
    }

    internal static Dictionary<string, string> ExportPublicKeyToJwk(ECDsa key)
    {
        var parameters = key.ExportParameters(false);
        return new Dictionary<string, string>
        {
            ["kty"] = "EC",
            ["crv"] = "P-256",
            ["x"] = Base64UrlEncode(PadToFieldSize(parameters.Q.X!, 32)),
            ["y"] = Base64UrlEncode(PadToFieldSize(parameters.Q.Y!, 32))
        };
    }

    internal static ECDsa ImportPrivateKeyFromJwk(Dictionary<string, string> jwk)
    {
        var x = Base64UrlDecode(jwk["x"]);
        var y = Base64UrlDecode(jwk["y"]);
        var d = Base64UrlDecode(jwk["d"]);

        var parameters = new ECParameters
        {
            Curve = ECCurve.NamedCurves.nistP256,
            Q = new ECPoint { X = x, Y = y },
            D = d
        };

        var key = ECDsa.Create(parameters);
        return key;
    }

    internal static ECDsa ImportPublicKeyFromJwk(Dictionary<string, string> jwk)
    {
        var x = Base64UrlDecode(jwk["x"]);
        var y = Base64UrlDecode(jwk["y"]);

        var parameters = new ECParameters
        {
            Curve = ECCurve.NamedCurves.nistP256,
            Q = new ECPoint { X = x, Y = y }
        };

        var key = ECDsa.Create(parameters);
        return key;
    }

    internal static string Base64UrlEncode(byte[] data)
    {
        return Convert.ToBase64String(data)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');
    }

    internal static byte[] Base64UrlDecode(string input)
    {
        var s = input.Replace('-', '+').Replace('_', '/');
        switch (s.Length % 4)
        {
            case 2: s += "=="; break;
            case 3: s += "="; break;
        }
        return Convert.FromBase64String(s);
    }

    private static byte[] PadToFieldSize(byte[] data, int fieldSize)
    {
        if (data.Length >= fieldSize)
            return data;

        var padded = new byte[fieldSize];
        Buffer.BlockCopy(data, 0, padded, fieldSize - data.Length, data.Length);
        return padded;
    }
}

internal class PersistedKeys
{
    public Dictionary<string, string> DelegationJwk { get; set; } = new();
    public string DelegationKid { get; set; } = "";
    public Dictionary<string, string> AuditJwk { get; set; } = new();
    public string AuditKid { get; set; } = "";
}
