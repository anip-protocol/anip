using System.Text;
using Anip.Crypto;

namespace Anip.Crypto.Tests;

public class JwsTests
{
    [Fact]
    public void SignDetached_ProducesValidFormat()
    {
        var km = new KeyManager();
        var payload = Encoding.UTF8.GetBytes("{\"test\":\"data\"}");

        var jws = JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload);

        // Should be 3 dot-separated parts with empty middle.
        var parts = jws.Split('.');
        Assert.Equal(3, parts.Length);
        Assert.Equal("", parts[1]); // Detached: empty payload.
        Assert.False(string.IsNullOrEmpty(parts[0])); // Header present.
        Assert.False(string.IsNullOrEmpty(parts[2])); // Signature present.
    }

    [Fact]
    public void SignDetached_DifferentPayloads_DifferentSignatures()
    {
        var km = new KeyManager();
        var payload1 = Encoding.UTF8.GetBytes("{\"data\":\"one\"}");
        var payload2 = Encoding.UTF8.GetBytes("{\"data\":\"two\"}");

        var jws1 = JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload1);
        var jws2 = JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload2);

        // Signatures should differ for different payloads.
        var sig1 = jws1.Split('.')[2];
        var sig2 = jws2.Split('.')[2];
        Assert.NotEqual(sig1, sig2);
    }

    [Fact]
    public void SignDetached_VerifyDetached_RoundTrip()
    {
        var km = new KeyManager();
        var payload = Encoding.UTF8.GetBytes("{\"manifest\":\"test\"}");

        var jws = JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload);

        Assert.True(JwsSigner.VerifyDetached(km.GetSigningKey(), payload, jws));
    }

    [Fact]
    public void VerifyDetached_WrongPayload_ReturnsFalse()
    {
        var km = new KeyManager();
        var payload = Encoding.UTF8.GetBytes("{\"manifest\":\"test\"}");
        var wrongPayload = Encoding.UTF8.GetBytes("{\"manifest\":\"wrong\"}");

        var jws = JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload);

        Assert.False(JwsSigner.VerifyDetached(km.GetSigningKey(), wrongPayload, jws));
    }

    [Fact]
    public void VerifyDetached_WrongKey_ReturnsFalse()
    {
        var km1 = new KeyManager();
        var km2 = new KeyManager();
        var payload = Encoding.UTF8.GetBytes("{\"test\":\"data\"}");

        var jws = JwsSigner.SignDetached(km1.GetSigningKey(), km1.GetSigningKid(), payload);

        Assert.False(JwsSigner.VerifyDetached(km2.GetSigningKey(), payload, jws));
    }

    [Fact]
    public void VerifyDetached_InvalidFormat_ReturnsFalse()
    {
        var km = new KeyManager();
        var payload = Encoding.UTF8.GetBytes("test");

        Assert.False(JwsSigner.VerifyDetached(km.GetSigningKey(), payload, "not-a-jws"));
        Assert.False(JwsSigner.VerifyDetached(km.GetSigningKey(), payload, "header.non-empty.sig"));
    }

    [Fact]
    public void SignDetached_HeaderContainsAlgAndKid()
    {
        var km = new KeyManager();
        var payload = Encoding.UTF8.GetBytes("test");

        var jws = JwsSigner.SignDetached(km.GetSigningKey(), km.GetSigningKid(), payload);

        var headerB64 = jws.Split('.')[0];
        var headerJson = Encoding.UTF8.GetString(KeyManager.Base64UrlDecode(headerB64));

        Assert.Contains("\"alg\":\"ES256\"", headerJson);
        Assert.Contains($"\"kid\":\"{km.GetSigningKid()}\"", headerJson);
    }
}
