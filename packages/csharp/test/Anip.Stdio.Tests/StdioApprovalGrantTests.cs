using System.Text.Json;
using Anip.Core;
using Anip.Service;
using Anip.Stdio;

namespace Anip.Stdio.Tests;

/// <summary>SPEC.md §4.8: stdio carries approval_grant on anip.invoke, validated as over HTTP.</summary>
public class StdioApprovalGrantTests : IDisposable
{
    private readonly AnipService _service;
    private readonly AnipStdioServer _server;
    private readonly string _token;

    public StdioApprovalGrantTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "stdio-approvals",
            Storage = ":memory:",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(new CapabilityDeclaration
                {
                    Name = "transfer",
                    Description = "Transfer funds",
                    ContractVersion = "1.0",
                    Inputs = new List<CapabilityInput> { new() { Name = "amount", Type = "number", Required = true } },
                    SideEffect = new SideEffect { Type = "irreversible", RollbackWindow = "none" },
                    MinimumScope = new List<string> { "finance.write" },
                    ResponseModes = new List<string> { "unary", "streaming" },
                    GrantPolicy = new GrantPolicy
                    {
                        AllowedGrantTypes = new() { "one_time" },
                        DefaultGrantType = "one_time",
                        ExpiresInSeconds = 900,
                        MaxUses = 1,
                    },
                }, (ctx, p) =>
                {
                    if (Convert.ToDouble(p["amount"] is JsonElement e ? e.GetDouble() : p["amount"]) > 1000
                        && ctx.ApprovalGrant == null)
                    {
                        throw new AnipError(Constants.FailureApprovalRequired, "transfers above 1000 need approval");
                    }
                    return new Dictionary<string, object?> { ["transferred"] = true };
                }),
            },
        });
        _service.Start();
        _server = new AnipStdioServer(_service);
        _token = _service.IssueToken("alice", new TokenRequest
        {
            Scope = new List<string> { "finance.write" },
            Capability = "transfer",
        }).Token;
    }

    public void Dispose() => _service.Dispose();

    private Dictionary<string, object?>? _lastFailure;

    /// <summary>The failure type of the call, or null when it succeeded.</summary>
    private async Task<string?> Invoke(Dictionary<string, object?> extra)
    {
        var parameters = new Dictionary<string, object?>
        {
            ["auth"] = new Dictionary<string, object?> { ["bearer"] = _token },
            ["capability"] = "transfer",
            ["parameters"] = new Dictionary<string, object?> { ["amount"] = 5000 },
        };
        foreach (var (key, value) in extra) parameters[key] = value;
        // The params a stdio client sends arrive as JSON.
        var decoded = JsonSerializer.Deserialize<Dictionary<string, object?>>(JsonSerializer.Serialize(parameters))!;
        var raw = await _server.HandleRequestAsync(new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0", ["id"] = 1, ["method"] = "anip.invoke", ["params"] = decoded,
        });
        var response = raw is List<Dictionary<string, object?>> list ? list[^1] : (Dictionary<string, object?>)raw;
        if (response.TryGetValue("error", out var error) && error is Dictionary<string, object?> err)
        {
            return (string?)((Dictionary<string, object?>)err["data"]!)["type"];
        }
        var result = (Dictionary<string, object?>)response["result"]!;
        if (result["success"] is true) return null;
        _lastFailure = (Dictionary<string, object?>)result["failure"]!;
        return (string?)_lastFailure["type"];
    }

    [Fact]
    public async Task ContinuationRunsWithTheGrant()
    {
        Assert.Equal("approval_required", await Invoke(new()));
        var meta = _lastFailure!["approval_required"];
        var requestId = meta switch
        {
            ApprovalRequiredMetadata m => m.ApprovalRequestId,
            Dictionary<string, object?> d => (string)d["approval_request_id"]!,
            _ => throw new Xunit.Sdk.XunitException($"unexpected metadata {meta}"),
        };
        var grant = _service.IssueApprovalGrant(requestId!, ApprovalGrant.TypeOneTime,
            new Dictionary<string, object?> { ["subject"] = "approver" }, null, null, null);

        Assert.Null(await Invoke(new() { ["approval_grant"] = grant.GrantId }));
        Assert.Equal("grant_consumed", await Invoke(new() { ["approval_grant"] = grant.GrantId }));
    }

    [Theory]
    [InlineData(false, "\"\"")]
    [InlineData(false, "\"   \"")]
    [InlineData(false, "7")]
    [InlineData(true, "\"\"")]
    [InlineData(true, "\"   \"")]
    [InlineData(true, "7")]
    public async Task BlankGrantIsNotFound(bool stream, string grantJson)
    {
        var grant = JsonSerializer.Deserialize<JsonElement>(grantJson);
        Assert.Equal("grant_not_found", await Invoke(new() { ["approval_grant"] = grant, ["stream"] = stream }));
    }

    [Fact]
    public async Task NullGrantIsNoGrant()
    {
        Assert.Equal("approval_required", await Invoke(new() { ["approval_grant"] = null }));
    }
}
