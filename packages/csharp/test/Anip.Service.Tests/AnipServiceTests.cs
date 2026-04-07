using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

public class AnipServiceTests : IDisposable
{
    private readonly AnipService _service;
    private readonly string _principal = "test-user";

    public AnipServiceTests()
    {
        var config = new ServiceConfig
        {
            ServiceId = "test-service",
            Storage = ":memory:",
            Trust = "signed",
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "echo",
                        Description = "Echoes input back",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "none" },
                        MinimumScope = new List<string> { "data" },
                    },
                    (ctx, parameters) =>
                    {
                        return new Dictionary<string, object?>
                        {
                            ["echoed"] = parameters.TryGetValue("message", out var msg) ? msg : "no message",
                        };
                    }
                ),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "write_data",
                        Description = "Writes data with side effects",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "write" },
                        MinimumScope = new List<string> { "data", "data.write" },
                    },
                    (ctx, parameters) =>
                    {
                        return new Dictionary<string, object?>
                        {
                            ["written"] = true,
                        };
                    }
                ),
            },
            Authenticate = bearer =>
            {
                if (bearer == "valid-key")
                    return _principal;
                return null;
            },
        };

        _service = new AnipService(config);
        _service.Start();
    }

    public void Dispose()
    {
        _service.Dispose();
    }

    // --- Lifecycle ---

    [Fact]
    public void ServiceId_ReturnsConfiguredId()
    {
        Assert.Equal("test-service", _service.ServiceId);
    }

    [Fact]
    public void Start_Shutdown_Lifecycle()
    {
        // If we get here from constructor without exceptions, Start() works.
        // Shutdown is called in Dispose.
        var health = _service.GetHealth();
        Assert.Equal("healthy", health.Status);
    }

    // --- Authentication ---

    [Fact]
    public void AuthenticateBearer_ValidKey()
    {
        var principal = _service.AuthenticateBearer("valid-key");
        Assert.Equal(_principal, principal);
    }

    [Fact]
    public void AuthenticateBearer_InvalidKey()
    {
        var principal = _service.AuthenticateBearer("bad-key");
        Assert.Null(principal);
    }

    // --- Token issuance and resolution ---

    [Fact]
    public void IssueAndResolveToken_RoundTrip()
    {
        var req = new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { "data" },
            Capability = "echo",
            TtlHours = 1,
        };

        var resp = _service.IssueToken(_principal, req);

        Assert.True(resp.Issued);
        Assert.NotEmpty(resp.TokenId);
        Assert.NotEmpty(resp.Token);
        Assert.NotEmpty(resp.Expires);

        // Now resolve the JWT.
        var resolved = _service.ResolveBearerToken(resp.Token);
        Assert.Equal(resp.TokenId, resolved.TokenId);
        Assert.Equal("agent-1", resolved.Subject);
    }

    [Fact]
    public void ResolveBearerToken_InvalidJwt_Throws()
    {
        var ex = Assert.Throws<AnipError>(() => _service.ResolveBearerToken("not.a.jwt"));
        Assert.Equal(Constants.FailureInvalidToken, ex.ErrorType);
    }

    // --- Invoke ---

    [Fact]
    public void Invoke_Success_ReturnsResult()
    {
        var token = IssueTestToken("data");
        var resolved = _service.ResolveBearerToken(token);

        var result = _service.Invoke("echo", resolved,
            new Dictionary<string, object?> { ["message"] = "hello" },
            new InvokeOpts());

        Assert.Equal(true, result["success"]);
        Assert.NotNull(result["invocation_id"]);
        var innerResult = (Dictionary<string, object?>)result["result"]!;
        Assert.Equal("hello", innerResult["echoed"]);
    }

    [Fact]
    public void Invoke_UnknownCapability_Returns404Failure()
    {
        var token = IssueTestToken("data");
        var resolved = _service.ResolveBearerToken(token);

        var result = _service.Invoke("nonexistent", resolved,
            new Dictionary<string, object?>(),
            new InvokeOpts());

        Assert.Equal(false, result["success"]);
        var failure = (Dictionary<string, object?>)result["failure"]!;
        Assert.Equal(Constants.FailureUnknownCapability, failure["type"]);
    }

    [Fact]
    public void Invoke_ScopeInsufficient_ReturnsFailure()
    {
        // Token only has "billing" scope, but echo requires "data".
        var token = IssueTestToken("billing");
        var resolved = _service.ResolveBearerToken(token);

        var result = _service.Invoke("echo", resolved,
            new Dictionary<string, object?>(),
            new InvokeOpts());

        Assert.Equal(false, result["success"]);
        var failure = (Dictionary<string, object?>)result["failure"]!;
        Assert.Equal(Constants.FailureScopeInsufficient, failure["type"]);
    }

    [Fact]
    public void Invoke_HasInvocationId()
    {
        var token = IssueTestToken("data");
        var resolved = _service.ResolveBearerToken(token);

        var result = _service.Invoke("echo", resolved,
            new Dictionary<string, object?>(),
            new InvokeOpts());

        var invocationId = (string)result["invocation_id"]!;
        Assert.StartsWith("inv-", invocationId);
    }

    // --- Permissions ---

    [Fact]
    public void DiscoverPermissions_Available()
    {
        var token = IssueTestToken("data", "data.write");
        var resolved = _service.ResolveBearerToken(token);

        var perms = _service.DiscoverPermissions(resolved);

        Assert.Contains(perms.Available, a => a.Capability == "echo");
        Assert.Contains(perms.Available, a => a.Capability == "write_data");
        Assert.Empty(perms.Restricted);
        Assert.Empty(perms.Denied);
    }

    [Fact]
    public void DiscoverPermissions_Restricted()
    {
        // Token only has "billing" scope, which doesn't cover "data" or "data.write".
        var token = IssueTestToken("billing");
        var resolved = _service.ResolveBearerToken(token);

        var perms = _service.DiscoverPermissions(resolved);

        // Both capabilities require "data" scope which "billing" doesn't cover.
        Assert.Empty(perms.Available);
        Assert.Contains(perms.Restricted, r => r.Capability == "echo");
        Assert.Contains(perms.Restricted, r => r.Capability == "write_data");
    }

    // --- Audit ---

    [Fact]
    public void QueryAudit_ReturnsInvocationEntries()
    {
        var token = IssueTestToken("data");
        var resolved = _service.ResolveBearerToken(token);

        // Invoke to create audit entries.
        _service.Invoke("echo", resolved,
            new Dictionary<string, object?> { ["message"] = "test" },
            new InvokeOpts());

        // Query audit.
        var response = _service.QueryAudit(resolved, new AuditFilters());

        Assert.True(response.Count > 0);
        Assert.True(response.Entries.Count > 0);
        Assert.Contains(response.Entries, e => e.Capability == "echo");
    }

    // --- Health ---

    [Fact]
    public void GetHealth_ReturnsHealthyReport()
    {
        var health = _service.GetHealth();

        Assert.Equal("healthy", health.Status);
        Assert.True(health.Storage.Connected);
        Assert.Equal("sqlite", health.Storage.Type);
        Assert.Equal(Constants.ProtocolVersion, health.Version);
        Assert.NotEmpty(health.Uptime);
    }

    // --- Discovery ---

    [Fact]
    public void GetDiscovery_HasCorrectShape()
    {
        var doc = _service.GetDiscovery("https://example.com");

        Assert.True(doc.ContainsKey("anip_discovery"));
        var inner = (Dictionary<string, object?>)doc["anip_discovery"]!;

        Assert.Equal(Constants.ProtocolVersion, inner["protocol"]);
        Assert.Equal("anip-compliant", inner["compliance"]);
        Assert.Equal("signed", inner["trust_level"]);
        Assert.Equal("https://example.com", inner["base_url"]);

        // Capabilities.
        var caps = (Dictionary<string, object?>)inner["capabilities"]!;
        Assert.True(caps.ContainsKey("echo"));
        Assert.True(caps.ContainsKey("write_data"));

        // Endpoints.
        var endpoints = (Dictionary<string, object?>)inner["endpoints"]!;
        Assert.Equal("/anip/manifest", endpoints["manifest"]);
        Assert.Equal("/.well-known/jwks.json", endpoints["jwks"]);
    }

    [Fact]
    public void GetDiscovery_NullBaseUrl_NoBaseUrlField()
    {
        var doc = _service.GetDiscovery(null);
        var inner = (Dictionary<string, object?>)doc["anip_discovery"]!;
        Assert.False(inner.ContainsKey("base_url"));
    }

    // --- Manifest ---

    [Fact]
    public void GetManifest_HasCapabilities()
    {
        var manifest = _service.GetManifest();

        Assert.Equal(Constants.ProtocolVersion, manifest.Protocol);
        Assert.True(manifest.Capabilities.ContainsKey("echo"));
        Assert.True(manifest.Capabilities.ContainsKey("write_data"));
        Assert.Equal("test-service", manifest.ServiceIdentity!.Id);
    }

    [Fact]
    public void GetSignedManifest_HasSignature()
    {
        var signed = _service.GetSignedManifest();

        Assert.NotEmpty(signed.ManifestJson);
        Assert.NotEmpty(signed.Signature);
        Assert.Contains("..", signed.Signature); // Detached JWS format.
    }

    // --- JWKS ---

    [Fact]
    public void GetJwks_HasKeys()
    {
        var jwks = _service.GetJwks();

        Assert.True(jwks.ContainsKey("keys"));
    }

    // --- Capability declaration ---

    [Fact]
    public void GetCapabilityDeclaration_Found()
    {
        var decl = _service.GetCapabilityDeclaration("echo");
        Assert.NotNull(decl);
        Assert.Equal("echo", decl.Name);
    }

    [Fact]
    public void GetCapabilityDeclaration_NotFound()
    {
        var decl = _service.GetCapabilityDeclaration("nonexistent");
        Assert.Null(decl);
    }

    // --- IssueCapabilityToken ---

    [Fact]
    public void IssueCapabilityToken_IssuesRootToken()
    {
        var resp = _service.IssueCapabilityToken(
            _principal, "echo", new List<string> { "data" });

        Assert.True(resp.Issued);
        Assert.NotEmpty(resp.TokenId);
        Assert.NotEmpty(resp.Token);
        Assert.NotEmpty(resp.Expires);

        // Resolve and verify capability binding.
        var resolved = _service.ResolveBearerToken(resp.Token);
        Assert.Equal(_principal, resolved.Subject);
        Assert.Equal("echo", resolved.Purpose?.Capability);
    }

    [Fact]
    public void IssueCapabilityToken_WithOptionalParams()
    {
        var resp = _service.IssueCapabilityToken(
            _principal, "echo", new List<string> { "data" },
            purposeParameters: new Dictionary<string, object> { ["task_id"] = "task-123" },
            ttlHours: 4,
            budget: new Budget { Currency = "USD", MaxAmount = 100 });

        Assert.True(resp.Issued);
        Assert.NotEmpty(resp.TokenId);
    }

    [Fact]
    public void IssueCapabilityToken_ScopeIsExplicit()
    {
        // Scope that differs from capability name should still work.
        var resp = _service.IssueCapabilityToken(
            _principal, "echo", new List<string> { "custom.scope" });

        Assert.True(resp.Issued);
    }

    // --- IssueDelegatedCapabilityToken ---

    [Fact]
    public void IssueDelegatedCapabilityToken_IssuesDelegatedToken()
    {
        // Issue root token first.
        var rootResp = _service.IssueCapabilityToken(
            _principal, "echo", new List<string> { "data" });
        Assert.True(rootResp.Issued);

        // Delegate.
        var resp = _service.IssueDelegatedCapabilityToken(
            _principal, rootResp.TokenId, "echo",
            new List<string> { "data" }, "agent:helper");

        Assert.True(resp.Issued);
        Assert.NotEmpty(resp.TokenId);
        Assert.NotEmpty(resp.Token);

        // Resolve and verify delegation.
        var resolved = _service.ResolveBearerToken(resp.Token);
        Assert.Equal("agent:helper", resolved.Subject);
        Assert.Equal("echo", resolved.Purpose?.Capability);
        Assert.Equal(rootResp.TokenId, resolved.Parent);
    }

    [Fact]
    public void IssueDelegatedCapabilityToken_ScopeIsExplicit()
    {
        // Root token with broader scope.
        var rootResp = _service.IssueCapabilityToken(
            _principal, "echo", new List<string> { "data", "data.read" });

        // Delegate with a subset scope — scope is explicit, not derived from capability.
        var resp = _service.IssueDelegatedCapabilityToken(
            _principal, rootResp.TokenId, "echo",
            new List<string> { "data" }, "agent:worker");

        Assert.True(resp.Issued);
    }

    [Fact]
    public void IssueDelegatedCapabilityToken_WithOptionalParams()
    {
        var rootResp = _service.IssueCapabilityToken(
            _principal, "echo", new List<string> { "data" });

        var resp = _service.IssueDelegatedCapabilityToken(
            _principal, rootResp.TokenId, "echo",
            new List<string> { "data" }, "agent:delegate",
            callerClass: "automated",
            purposeParameters: new Dictionary<string, object> { ["task_id"] = "task-456" },
            ttlHours: 1,
            budget: new Budget { Currency = "USD", MaxAmount = 50 });

        Assert.True(resp.Issued);
        Assert.NotEmpty(resp.TokenId);
    }

    // --- Helpers ---

    private string IssueTestToken(params string[] scopes)
    {
        var req = new TokenRequest
        {
            Subject = "agent-1",
            Scope = scopes.ToList(),
            Capability = "echo",
            TtlHours = 1,
        };

        var resp = _service.IssueToken(_principal, req);
        return resp.Token;
    }
}
