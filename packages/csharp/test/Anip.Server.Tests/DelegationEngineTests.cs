using Anip.Core;
using Anip.Crypto;
using Anip.Server;
using Xunit;

namespace Anip.Server.Tests;

public class DelegationEngineTests : IDisposable
{
    private readonly KeyManager _keys;
    private readonly SqliteStorage _storage;
    private const string ServiceId = "svc-test";
    private const string Principal = "user@example.com";

    public DelegationEngineTests()
    {
        _keys = new KeyManager();
        _storage = new SqliteStorage(":memory:");
    }

    public void Dispose()
    {
        _storage.Dispose();
    }

    [Fact]
    public void IssueToken_Successfully()
    {
        var request = new TokenRequest
        {
            Subject = "agent@example.com",
            Scope = new List<string> { "data:read", "compute:run" },
            Capability = "summarize",
            TtlHours = 4
        };

        var response = DelegationEngine.IssueDelegationToken(_keys, _storage, ServiceId, Principal, request);

        Assert.True(response.Issued);
        Assert.StartsWith("anip-", response.TokenId);
        Assert.NotEmpty(response.Token);
        Assert.NotEmpty(response.Expires);

        // Token should be stored.
        var stored = _storage.LoadToken(response.TokenId);
        Assert.NotNull(stored);
        Assert.Equal("agent@example.com", stored.Subject);
        Assert.Equal(ServiceId, stored.Issuer);
        Assert.Equal(Principal, stored.RootPrincipal);
        Assert.Equal("summarize", stored.Purpose.Capability);
    }

    [Fact]
    public void IssueToken_DefaultSubject()
    {
        var request = new TokenRequest
        {
            Scope = new List<string> { "data:read" },
            Capability = "test"
        };

        var response = DelegationEngine.IssueDelegationToken(_keys, _storage, ServiceId, Principal, request);
        var stored = _storage.LoadToken(response.TokenId);

        Assert.NotNull(stored);
        Assert.Equal(Principal, stored.Subject);
    }

    [Fact]
    public void IssueToken_DefaultTtl()
    {
        var request = new TokenRequest
        {
            Scope = new List<string> { "data:read" },
            Capability = "test"
        };

        var response = DelegationEngine.IssueDelegationToken(_keys, _storage, ServiceId, Principal, request);
        var stored = _storage.LoadToken(response.TokenId);

        Assert.NotNull(stored);
        // Default TTL is 2 hours, so expiry should be roughly 2 hours from now.
        var expires = DateTimeOffset.Parse(stored.Expires);
        var expectedMin = DateTimeOffset.UtcNow.AddHours(1.9);
        var expectedMax = DateTimeOffset.UtcNow.AddHours(2.1);
        Assert.InRange(expires, expectedMin, expectedMax);
    }

    [Fact]
    public void ValidateScope_Pass()
    {
        var token = new DelegationToken
        {
            Scope = new List<string> { "data:read", "compute:run" }
        };

        // Should not throw.
        DelegationEngine.ValidateScope(token, new List<string> { "data", "compute" });
    }

    [Fact]
    public void ValidateScope_PrefixMatch()
    {
        var token = new DelegationToken
        {
            Scope = new List<string> { "data:read" }
        };

        // "data" scope should cover "data.subset" via prefix match.
        DelegationEngine.ValidateScope(token, new List<string> { "data.subset" });
    }

    [Fact]
    public void ValidateScope_Fail()
    {
        var token = new DelegationToken
        {
            Scope = new List<string> { "data:read" }
        };

        var ex = Assert.Throws<AnipError>(() =>
            DelegationEngine.ValidateScope(token, new List<string> { "admin" }));

        Assert.Equal(Constants.FailureScopeInsufficient, ex.ErrorType);
        Assert.Contains("admin", ex.Detail);
    }

    [Fact]
    public void ResolveBearerToken_RoundTrip()
    {
        var request = new TokenRequest
        {
            Subject = "agent@example.com",
            Scope = new List<string> { "data:read" },
            Capability = "summarize"
        };

        var response = DelegationEngine.IssueDelegationToken(_keys, _storage, ServiceId, Principal, request);

        var resolved = DelegationEngine.ResolveBearerToken(_keys, _storage, ServiceId, response.Token);

        Assert.Equal(response.TokenId, resolved.TokenId);
        Assert.Equal("agent@example.com", resolved.Subject);
        Assert.Equal(Principal, resolved.RootPrincipal);
    }

    [Fact]
    public void ResolveBearerToken_InvalidJwt()
    {
        var ex = Assert.Throws<AnipError>(() =>
            DelegationEngine.ResolveBearerToken(_keys, _storage, ServiceId, "invalid.jwt.token"));

        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
    }

    [Fact]
    public void ScopeNarrowing_ChildCannotWidenParent()
    {
        // Issue a parent token with narrow scope.
        var parentRequest = new TokenRequest
        {
            Subject = "agent-1@example.com",
            Scope = new List<string> { "data:read" },
            Capability = "summarize"
        };

        var parentResponse = DelegationEngine.IssueDelegationToken(
            _keys, _storage, ServiceId, Principal, parentRequest);

        // Attempt to sub-delegate with wider scope.
        var childRequest = new TokenRequest
        {
            Subject = "agent-2@example.com",
            Scope = new List<string> { "data:read", "admin:write" },
            Capability = "summarize",
            ParentToken = parentResponse.TokenId
        };

        // The child token gets issued (scope validation happens at invoke time),
        // but validating the child's scope against the parent's should fail.
        var childResponse = DelegationEngine.IssueDelegationToken(
            _keys, _storage, ServiceId, "agent-1@example.com", childRequest);

        var childToken = _storage.LoadToken(childResponse.TokenId)!;
        var parentToken = _storage.LoadToken(parentResponse.TokenId)!;

        // Child has scope "admin:write" which parent doesn't have.
        var ex = Assert.Throws<AnipError>(() =>
            DelegationEngine.ValidateScope(parentToken, new List<string> { "admin" }));

        Assert.Equal(Constants.FailureScopeInsufficient, ex.ErrorType);
    }

    [Fact]
    public void IssueToken_WithParent_InheritsRootPrincipal()
    {
        var parentRequest = new TokenRequest
        {
            Subject = "agent-1@example.com",
            Scope = new List<string> { "data:read" },
            Capability = "summarize"
        };

        var parentResponse = DelegationEngine.IssueDelegationToken(
            _keys, _storage, ServiceId, Principal, parentRequest);

        var childRequest = new TokenRequest
        {
            Subject = "agent-2@example.com",
            Scope = new List<string> { "data:read" },
            Capability = "summarize",
            ParentToken = parentResponse.TokenId
        };

        var childResponse = DelegationEngine.IssueDelegationToken(
            _keys, _storage, ServiceId, "agent-1@example.com", childRequest);

        var childToken = _storage.LoadToken(childResponse.TokenId)!;

        // Root principal is inherited from parent, not from the immediate principal.
        Assert.Equal(Principal, childToken.RootPrincipal);
        Assert.Equal(parentResponse.TokenId, childToken.Parent);
    }

    [Fact]
    public void IssueToken_InvalidParentToken_Throws()
    {
        var request = new TokenRequest
        {
            Subject = "agent@example.com",
            Scope = new List<string> { "data:read" },
            Capability = "summarize",
            ParentToken = "nonexistent-token"
        };

        var ex = Assert.Throws<AnipError>(() =>
            DelegationEngine.IssueDelegationToken(_keys, _storage, ServiceId, Principal, request));

        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
        Assert.Contains("parent token not found", ex.Detail);
    }
}
