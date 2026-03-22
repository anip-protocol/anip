using Anip.Core;
using Anip.Mcp;
using Anip.Service;

namespace Anip.Mcp.Tests;

public class McpAuthBridgeTests : IDisposable
{
    private readonly AnipService _service;
    private readonly string _validJwt;

    public McpAuthBridgeTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "test-auth-bridge-svc",
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "search_flights",
                        Description = "Search for flights",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                        MinimumScope = new List<string> { "travel" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "origin", Type = "string", Required = true, Description = "Origin airport" },
                        },
                    },
                    (ctx, parameters) => new Dictionary<string, object?> { ["flights"] = new List<object>() }
                ),
            },
            Storage = ":memory:",
            Authenticate = bearer =>
            {
                if (bearer == "valid-api-key") return "user@test.com";
                return null;
            },
            RetentionIntervalSeconds = -1,
        });
        _service.Start();

        // Issue a valid JWT for tests.
        var resp = _service.IssueToken("user@test.com", new TokenRequest
        {
            Subject = "agent@test.com",
            Scope = new List<string> { "travel" },
            Capability = "search_flights",
            TtlHours = 2,
        });
        _validJwt = resp.Token;
    }

    public void Dispose()
    {
        _service.Dispose();
    }

    [Fact]
    public void JwtSuccess()
    {
        var token = McpAuthBridge.ResolveAuth(_validJwt, _service, "search_flights");

        Assert.NotNull(token);
        Assert.Equal("agent@test.com", token.Subject);
    }

    [Fact]
    public void ApiKeyFallback()
    {
        var token = McpAuthBridge.ResolveAuth("valid-api-key", _service, "search_flights");

        Assert.NotNull(token);
        Assert.Equal("adapter:anip-mcp", token.Subject);
    }

    [Fact]
    public void InvalidBearerThrows()
    {
        Assert.Throws<AnipError>(() =>
            McpAuthBridge.ResolveAuth("bad-key", _service, "search_flights"));
    }
}
