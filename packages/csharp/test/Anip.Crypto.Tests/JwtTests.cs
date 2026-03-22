using System.Security.Cryptography;
using Anip.Core;
using Anip.Crypto;

namespace Anip.Crypto.Tests;

public class JwtTests
{
    private static DelegationToken CreateTestToken()
    {
        return new DelegationToken
        {
            TokenId = "test-token-123",
            Subject = "agent:test-agent",
            Scope = new List<string> { "read", "write" },
            Purpose = new Purpose
            {
                Capability = "data.query",
                TaskId = "task-456"
            },
            RootPrincipal = "user:alice",
            CallerClass = "orchestrator",
            Expires = DateTimeOffset.UtcNow.AddHours(1).ToString("o"),
            Parent = "parent-token-789"
        };
    }

    [Fact]
    public void SignAndVerify_RoundTrip()
    {
        var km = new KeyManager();
        var token = CreateTestToken();
        var issuer = "test-issuer";

        var jwt = JwtSigner.SignToken(km.GetSigningKey(), km.GetSigningKid(), token, issuer);
        Assert.False(string.IsNullOrEmpty(jwt));

        // JWT should have 3 dot-separated parts.
        var parts = jwt.Split('.');
        Assert.Equal(3, parts.Length);

        // Verify and extract.
        var extracted = JwtVerifier.VerifyAndExtract(jwt, km.GetSigningKey(), issuer);

        Assert.Equal(token.TokenId, extracted.TokenId);
        Assert.Equal(issuer, extracted.Issuer);
        Assert.Equal(token.Subject, extracted.Subject);
        Assert.Equal(token.Scope, extracted.Scope);
        Assert.Equal(token.Purpose.Capability, extracted.Purpose.Capability);
        Assert.Equal(token.Purpose.TaskId, extracted.Purpose.TaskId);
        Assert.Equal(token.RootPrincipal, extracted.RootPrincipal);
        Assert.Equal(token.CallerClass, extracted.CallerClass);
        Assert.Equal(token.Parent, extracted.Parent);
    }

    [Fact]
    public void ExpiredToken_ThrowsTokenExpired()
    {
        var km = new KeyManager();
        var token = CreateTestToken();
        token.Expires = DateTimeOffset.UtcNow.AddHours(-1).ToString("o"); // Expired 1 hour ago.

        var jwt = JwtSigner.SignToken(km.GetSigningKey(), km.GetSigningKid(), token, "issuer");

        var ex = Assert.Throws<AnipError>(() =>
            JwtVerifier.VerifyAndExtract(jwt, km.GetSigningKey(), "issuer"));

        Assert.Equal(Constants.FailureTokenExpired, ex.ErrorType);
    }

    [Fact]
    public void WrongIssuer_ThrowsInvalidToken()
    {
        var km = new KeyManager();
        var token = CreateTestToken();

        var jwt = JwtSigner.SignToken(km.GetSigningKey(), km.GetSigningKid(), token, "real-issuer");

        var ex = Assert.Throws<AnipError>(() =>
            JwtVerifier.VerifyAndExtract(jwt, km.GetSigningKey(), "wrong-issuer"));

        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
        Assert.Contains("Issuer mismatch", ex.Detail);
    }

    [Fact]
    public void TamperedJwt_ThrowsInvalidToken()
    {
        var km = new KeyManager();
        var token = CreateTestToken();

        var jwt = JwtSigner.SignToken(km.GetSigningKey(), km.GetSigningKid(), token, "issuer");

        // Tamper with the payload.
        var parts = jwt.Split('.');
        var tamperedPayload = parts[1] + "XX";
        var tampered = $"{parts[0]}.{tamperedPayload}.{parts[2]}";

        var ex = Assert.Throws<AnipError>(() =>
            JwtVerifier.VerifyAndExtract(tampered, km.GetSigningKey(), "issuer"));

        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
    }

    [Fact]
    public void WrongKey_ThrowsInvalidToken()
    {
        var km1 = new KeyManager();
        var km2 = new KeyManager();
        var token = CreateTestToken();

        var jwt = JwtSigner.SignToken(km1.GetSigningKey(), km1.GetSigningKid(), token, "issuer");

        // Verify with a different key.
        var ex = Assert.Throws<AnipError>(() =>
            JwtVerifier.VerifyAndExtract(jwt, km2.GetSigningKey(), "issuer"));

        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
    }

    [Fact]
    public void InvalidFormat_ThrowsInvalidToken()
    {
        var km = new KeyManager();

        var ex = Assert.Throws<AnipError>(() =>
            JwtVerifier.VerifyAndExtract("not.a.valid.jwt.string", km.GetSigningKey(), "issuer"));

        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
    }

    [Fact]
    public void TokenWithNoParent_ParentIsNull()
    {
        var km = new KeyManager();
        var token = CreateTestToken();
        token.Parent = null;

        var jwt = JwtSigner.SignToken(km.GetSigningKey(), km.GetSigningKid(), token, "issuer");
        var extracted = JwtVerifier.VerifyAndExtract(jwt, km.GetSigningKey(), "issuer");

        Assert.Null(extracted.Parent);
    }

    [Fact]
    public void EmptyIssuer_SkipsIssuerCheck()
    {
        var km = new KeyManager();
        var token = CreateTestToken();

        var jwt = JwtSigner.SignToken(km.GetSigningKey(), km.GetSigningKid(), token, "any-issuer");

        // Passing empty expectedIssuer should skip issuer validation.
        var extracted = JwtVerifier.VerifyAndExtract(jwt, km.GetSigningKey(), "");

        Assert.Equal("any-issuer", extracted.Issuer);
    }
}
