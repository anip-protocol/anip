using System.Text.Json;

namespace Anip.Mcp.AspNetCore.Tests;

/// <summary>
/// Requests that are malformed, sent through real HTTP.
///
/// Two layers are involved and they behave differently:
///
/// - A <c>tools/call</c> request whose own shape is wrong (no tool name,
///   arguments that are not an object) must be refused before a handler runs.
/// - Arguments that are well-formed JSON but break the capability's declared
///   input schema are a different matter: see
///   <see cref="ArgumentsThatBreakTheDeclaredSchema_ReachTheHandlerUnchanged"/>.
///
/// Every test runs once per way of speaking the protocol: see the classes at
/// the end of this file.
/// </summary>
public abstract class McpHttpMalformedRequestTests : IAsyncLifetime
{
    private const string Authorization = "Bearer " + McpTestApp.ApiKey;

    private McpTestApp _app = null!;

    private protected abstract Task<IWireClient> ConnectAsync(HttpClient http);

    public async Task InitializeAsync() => _app = await McpTestApp.StartAsync();

    public async Task DisposeAsync() => await _app.DisposeAsync();

    [Theory]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"arguments":{"message":"hi"}}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"name":42,"arguments":{"message":"hi"}}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"name":true,"arguments":{"message":"hi"}}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"name":["echo"],"arguments":{"message":"hi"}}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"name":{"tool":"echo"},"arguments":{"message":"hi"}}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"name":"echo","arguments":"message=hi"}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":{"name":"echo","arguments":["hi"]}}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call","params":"echo"}""")]
    [InlineData("""{"jsonrpc":"2.0","id":900,"method":"tools/call"}""")]
    public async Task MalformedToolCall_IsRefused_AndNoHandlerRuns(string body)
    {
        // How each is refused differs by SDK version and protocol revision: a
        // JSON-RPC error, an HTTP 400, or an HTTP 500. The 500s are a defect
        // in MCP SDK 2.4.0, which throws while comparing the Mcp-Name header
        // of a 2026-07-28 request with a tool name that is not a string. They
        // are accepted here because what this test is about is that none of
        // these requests runs a handler.
        var client = await ConnectAsync(_app.Http);

        var reply = await client.RequestRawAsync(body, Authorization, id: 900);

        Assert.False(reply.HasResult && !reply.IsToolError, $"expected a refusal, got: {reply}");
        Assert.Empty(_app.Calls);
    }

    /// <summary>
    /// The C# binding has never checked arguments against the tool's input
    /// schema: neither the 1.x nor the 2.x MCP SDK does it for a custom
    /// <c>McpServerTool</c>, and the binding does not do it itself. Capability
    /// handlers validate their own parameters. This test records that, so a
    /// change in either direction is noticed rather than silent.
    /// </summary>
    [Theory]
    [InlineData("missing required", """{}""")]
    [InlineData("wrong type", """{"message":42}""")]
    [InlineData("null for a required string", """{"message":null}""")]
    [InlineData("boolean where an integer is declared", """{"message":"hi","count":true}""")]
    [InlineData("fraction where an integer is declared", """{"message":"hi","count":1.5}""")]
    [InlineData("undeclared argument", """{"message":"hi","surprise":"x"}""")]
    public async Task ArgumentsThatBreakTheDeclaredSchema_ReachTheHandlerUnchanged(string what, string argumentsJson)
    {
        var client = await ConnectAsync(_app.Http);
        var arguments = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(argumentsJson)!;

        var reply = await client.CallToolAsync("echo", arguments, Authorization);

        Assert.True(reply.HasResult, $"{what}: {reply}");
        Assert.False(reply.IsToolError, $"{what}: {reply}");
        var call = Assert.Single(_app.Calls);
        Assert.Equal(arguments.Keys.OrderBy(k => k), call.Parameters.Keys.OrderBy(k => k));
        foreach (var (key, value) in arguments)
        {
            Assert.Equal(value.GetRawText(), JsonSerializer.Serialize(call.Parameters[key]));
        }
    }

    [Fact]
    public async Task ArgumentsKeepTheirJsonTypes()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync(
            "echo", new { message = "hi", count = 3, flag = true }, Authorization);

        Assert.False(reply.IsToolError, reply.ToString());
        var call = Assert.Single(_app.Calls);
        Assert.Equal("hi", call.Parameters["message"]);
        Assert.Equal(3L, call.Parameters["count"]);
        Assert.Equal(true, call.Parameters["flag"]);
    }
}

/// <summary>Malformed requests, from a client that opens with the <c>initialize</c> handshake.</summary>
public sealed class McpHttpMalformedRequestTests_InitializeHandshake : McpHttpMalformedRequestTests
{
    private protected override async Task<IWireClient> ConnectAsync(HttpClient http) =>
        await LegacyWireClient.ConnectAsync(http);
}

/// <summary>Malformed requests, from a client that speaks the 2026-07-28 protocol revision.</summary>
public sealed class McpHttpMalformedRequestTests_Protocol20260728 : McpHttpMalformedRequestTests
{
    private protected override async Task<IWireClient> ConnectAsync(HttpClient http) =>
        await ModernWireClient.ConnectAsync(http);
}
