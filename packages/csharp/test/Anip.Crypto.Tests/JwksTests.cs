using Anip.Crypto;

namespace Anip.Crypto.Tests;

public class JwksTests
{
    [Fact]
    public void ToJwks_HasKeysArray()
    {
        var km = new KeyManager();
        var jwks = JwksSerializer.ToJwks(km);

        Assert.True(jwks.ContainsKey("keys"));
        var keys = jwks["keys"] as List<Dictionary<string, object>>;
        Assert.NotNull(keys);
        Assert.Equal(2, keys!.Count);
    }

    [Fact]
    public void ToJwks_KeysHaveRequiredFields()
    {
        var km = new KeyManager();
        var jwks = JwksSerializer.ToJwks(km);
        var keys = (List<Dictionary<string, object>>)jwks["keys"];

        foreach (var key in keys)
        {
            Assert.Equal("EC", key["kty"]);
            Assert.Equal("P-256", key["crv"]);
            Assert.True(key.ContainsKey("x"));
            Assert.True(key.ContainsKey("y"));
            Assert.True(key.ContainsKey("kid"));
            Assert.Equal("ES256", key["alg"]);
            Assert.True(key.ContainsKey("use"));
        }
    }

    [Fact]
    public void ToJwks_NoPrivateKeyMaterial()
    {
        var km = new KeyManager();
        var jwks = JwksSerializer.ToJwks(km);
        var keys = (List<Dictionary<string, object>>)jwks["keys"];

        foreach (var key in keys)
        {
            Assert.False(key.ContainsKey("d"), "JWKS should not contain private key parameter 'd'");
        }
    }

    [Fact]
    public void ToJwks_FirstKeyIsSig_SecondIsAudit()
    {
        var km = new KeyManager();
        var jwks = JwksSerializer.ToJwks(km);
        var keys = (List<Dictionary<string, object>>)jwks["keys"];

        Assert.Equal("sig", keys[0]["use"]);
        Assert.Equal("audit", keys[1]["use"]);
    }

    [Fact]
    public void ToJwks_KidsMatchKeyManager()
    {
        var km = new KeyManager();
        var jwks = JwksSerializer.ToJwks(km);
        var keys = (List<Dictionary<string, object>>)jwks["keys"];

        Assert.Equal(km.GetSigningKid(), keys[0]["kid"]);
        Assert.Equal(km.GetAuditKid(), keys[1]["kid"]);
    }

    [Fact]
    public void ToJwks_DifferentKeyManagers_DifferentKeys()
    {
        var km1 = new KeyManager();
        var km2 = new KeyManager();

        var jwks1 = JwksSerializer.ToJwks(km1);
        var jwks2 = JwksSerializer.ToJwks(km2);

        var keys1 = (List<Dictionary<string, object>>)jwks1["keys"];
        var keys2 = (List<Dictionary<string, object>>)jwks2["keys"];

        // Different key managers should produce different x,y values.
        Assert.NotEqual(keys1[0]["x"], keys2[0]["x"]);
    }
}
