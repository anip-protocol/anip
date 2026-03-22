using System.Security.Cryptography;
using Anip.Crypto;

namespace Anip.Crypto.Tests;

public class KeyManagerTests
{
    [Fact]
    public void EphemeralKeys_AreGenerated()
    {
        var km = new KeyManager();

        Assert.NotNull(km.GetSigningKey());
        Assert.NotNull(km.GetAuditKey());
        Assert.False(string.IsNullOrEmpty(km.GetSigningKid()));
        Assert.False(string.IsNullOrEmpty(km.GetAuditKid()));
    }

    [Fact]
    public void EphemeralKeys_SigningAndAuditAreDifferent()
    {
        var km = new KeyManager();

        // The two key IDs should be different (distinct key pairs).
        Assert.NotEqual(km.GetSigningKid(), km.GetAuditKid());

        // Export parameters and compare — the keys themselves should differ.
        var signingParams = km.GetSigningKey().ExportParameters(false);
        var auditParams = km.GetAuditKey().ExportParameters(false);
        Assert.NotEqual(signingParams.Q.X, auditParams.Q.X);
    }

    [Fact]
    public void KeyId_HasCorrectLength()
    {
        var km = new KeyManager();

        // KID is first 16 chars of base64url-encoded SHA-256.
        Assert.Equal(16, km.GetSigningKid().Length);
        Assert.Equal(16, km.GetAuditKid().Length);
    }

    [Fact]
    public void KeyPersistence_RoundTrip()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"anip-test-{Guid.NewGuid():N}");

        try
        {
            // Create and save keys.
            var km1 = new KeyManager(tempDir);
            var signingKid1 = km1.GetSigningKid();
            var auditKid1 = km1.GetAuditKid();
            var signingParams1 = km1.GetSigningKey().ExportParameters(true);
            var auditParams1 = km1.GetAuditKey().ExportParameters(true);

            // Load keys from same path.
            var km2 = new KeyManager(tempDir);

            Assert.Equal(signingKid1, km2.GetSigningKid());
            Assert.Equal(auditKid1, km2.GetAuditKid());

            var signingParams2 = km2.GetSigningKey().ExportParameters(true);
            var auditParams2 = km2.GetAuditKey().ExportParameters(true);

            Assert.Equal(signingParams1.Q.X, signingParams2.Q.X);
            Assert.Equal(signingParams1.Q.Y, signingParams2.Q.Y);
            Assert.Equal(signingParams1.D, signingParams2.D);

            Assert.Equal(auditParams1.Q.X, auditParams2.Q.X);
            Assert.Equal(auditParams1.Q.Y, auditParams2.Q.Y);
            Assert.Equal(auditParams1.D, auditParams2.D);
        }
        finally
        {
            if (Directory.Exists(tempDir))
                Directory.Delete(tempDir, true);
        }
    }

    [Fact]
    public void KeyPersistence_FileExists()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"anip-test-{Guid.NewGuid():N}");

        try
        {
            var km = new KeyManager(tempDir);
            var keysFile = Path.Combine(tempDir, "anip-keys.json");
            Assert.True(File.Exists(keysFile));

            // File should contain JWK data.
            var content = File.ReadAllText(keysFile);
            Assert.Contains("DelegationJwk", content);
            Assert.Contains("AuditJwk", content);
            Assert.Contains("\"kty\"", content);
            Assert.Contains("\"crv\"", content);
            Assert.Contains("P-256", content);
        }
        finally
        {
            if (Directory.Exists(tempDir))
                Directory.Delete(tempDir, true);
        }
    }

    [Fact]
    public void ExportImport_PrivateKey_RoundTrip()
    {
        var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        var jwk = KeyManager.ExportPrivateKeyToJwk(key);

        Assert.Equal("EC", jwk["kty"]);
        Assert.Equal("P-256", jwk["crv"]);
        Assert.True(jwk.ContainsKey("x"));
        Assert.True(jwk.ContainsKey("y"));
        Assert.True(jwk.ContainsKey("d"));

        var imported = KeyManager.ImportPrivateKeyFromJwk(jwk);
        var originalParams = key.ExportParameters(true);
        var importedParams = imported.ExportParameters(true);

        Assert.Equal(originalParams.Q.X, importedParams.Q.X);
        Assert.Equal(originalParams.Q.Y, importedParams.Q.Y);
        Assert.Equal(originalParams.D, importedParams.D);
    }

    [Fact]
    public void ExportPublicKey_NoPrivateMaterial()
    {
        var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        var jwk = KeyManager.ExportPublicKeyToJwk(key);

        Assert.Equal("EC", jwk["kty"]);
        Assert.Equal("P-256", jwk["crv"]);
        Assert.True(jwk.ContainsKey("x"));
        Assert.True(jwk.ContainsKey("y"));
        Assert.False(jwk.ContainsKey("d"));
    }

    [Fact]
    public void ComputeKid_IsDeterministic()
    {
        var key = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        var kid1 = KeyManager.ComputeKid(key);
        var kid2 = KeyManager.ComputeKid(key);

        Assert.Equal(kid1, kid2);
    }

    [Fact]
    public void DifferentKeys_ProduceDifferentKids()
    {
        var key1 = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        var key2 = ECDsa.Create(ECCurve.NamedCurves.nistP256);

        Assert.NotEqual(KeyManager.ComputeKid(key1), KeyManager.ComputeKid(key2));
    }

    [Fact]
    public void NullKeyPath_CreatesEphemeralKeys()
    {
        var km = new KeyManager(null);
        Assert.NotNull(km.GetSigningKey());
        Assert.NotNull(km.GetAuditKey());
    }

    [Fact]
    public void EmptyKeyPath_CreatesEphemeralKeys()
    {
        var km = new KeyManager("");
        Assert.NotNull(km.GetSigningKey());
        Assert.NotNull(km.GetAuditKey());
    }
}
