using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

namespace Anip.Mcp.AspNetCore.Tests;

/// <summary>
/// The mounted endpoint as seen by the MCP SDK's own client, both when it
/// negotiates the newest protocol revision and when it is held to the last
/// revision that used the <c>initialize</c> handshake.
/// </summary>
public class McpSdkClientTests : IAsyncLifetime
{
    private const string NewestRevision = "2026-07-28";
    private const string LastHandshakeRevision = "2025-11-25";

    private McpTestApp _app = null!;

    public async Task InitializeAsync() => _app = await McpTestApp.StartAsync();

    public async Task DisposeAsync() => await _app.DisposeAsync();

    private async Task<McpClient> ConnectAsync(string? pinnedRevision, string? bearer)
    {
        var transportOptions = new HttpClientTransportOptions
        {
            Endpoint = new Uri(_app.Http.BaseAddress!, "/mcp"),
            TransportMode = HttpTransportMode.StreamableHttp,
        };
        if (bearer != null)
        {
            transportOptions.AdditionalHeaders = new Dictionary<string, string> { ["Authorization"] = $"Bearer {bearer}" };
        }

        var client = await McpClient.CreateAsync(
            new HttpClientTransport(transportOptions, _app.Http, ownsHttpClient: false),
            new McpClientOptions { ProtocolVersion = pinnedRevision });

        Assert.Equal(pinnedRevision ?? NewestRevision, client.NegotiatedProtocolVersion);
        return client;
    }

    private static string Text(CallToolResult result) =>
        string.Join("", result.Content.OfType<TextContentBlock>().Select(block => block.Text));

    [Theory]
    [InlineData(null)]
    [InlineData(LastHandshakeRevision)]
    public async Task ListsTools(string? pinnedRevision)
    {
        await using var client = await ConnectAsync(pinnedRevision, bearer: null);

        var tools = await client.ListToolsAsync();

        Assert.Equal(new[] { "delete_record", "echo", "explode" }, tools.Select(t => t.Name).OrderBy(n => n, StringComparer.Ordinal));
        Assert.Null(client.SessionId);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(LastHandshakeRevision)]
    public async Task CallsAToolWithAnApiKey(string? pinnedRevision)
    {
        await using var client = await ConnectAsync(pinnedRevision, McpTestApp.ApiKey);

        var result = await client.CallToolAsync("echo", new Dictionary<string, object?> { ["message"] = "hi", ["count"] = 2 });

        Assert.NotEqual(true, result.IsError);
        Assert.Contains("\"echoed\": \"hi\"", Text(result));
        var call = Assert.Single(_app.Calls);
        Assert.Equal("adapter:anip-mcp", call.Subject);
        Assert.Equal(2L, call.Parameters["count"]);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(LastHandshakeRevision)]
    public async Task ACallWithoutCredentials_ComesBackAsAToolError(string? pinnedRevision)
    {
        await using var client = await ConnectAsync(pinnedRevision, bearer: null);

        var result = await client.CallToolAsync("echo", new Dictionary<string, object?> { ["message"] = "hi" });

        Assert.True(result.IsError);
        Assert.StartsWith("FAILED: authentication_required", Text(result));
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(LastHandshakeRevision)]
    public async Task ACallWithAWrongKey_ComesBackAsAToolError(string? pinnedRevision)
    {
        await using var client = await ConnectAsync(pinnedRevision, "not-a-known-key");

        var result = await client.CallToolAsync("echo", new Dictionary<string, object?> { ["message"] = "hi" });

        Assert.True(result.IsError);
        Assert.StartsWith("FAILED: invalid_token", Text(result));
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(LastHandshakeRevision)]
    public async Task ATokenForAnotherCapability_ComesBackAsAToolError(string? pinnedRevision)
    {
        // The scope covers delete_record, so only the binding to "echo" can refuse this call.
        var jwtForEcho = _app.IssueJwt("agent:alice", "echo", "data.read", "admin.write");
        await using var client = await ConnectAsync(pinnedRevision, jwtForEcho);

        var result = await client.CallToolAsync("delete_record", new Dictionary<string, object?> { ["id"] = "r1" });

        Assert.True(result.IsError);
        Assert.StartsWith("FAILED: purpose_mismatch", Text(result));
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(LastHandshakeRevision)]
    public async Task AnUnknownTool_IsAProtocolError(string? pinnedRevision)
    {
        await using var client = await ConnectAsync(pinnedRevision, McpTestApp.ApiKey);

        var error = await Assert.ThrowsAnyAsync<ModelContextProtocol.McpException>(
            async () => await client.CallToolAsync("no_such_tool", new Dictionary<string, object?>()));

        Assert.Contains("no_such_tool", error.Message);
        Assert.Empty(_app.Calls);
    }
}
