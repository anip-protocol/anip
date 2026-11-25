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
///   input schema are refused by the service, as on every other transport: see
///   <see cref="ArgumentsThatBreakTheDeclaredInputs_AreRefused_AndNoHandlerRuns"/>.
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
    /// Neither the MCP SDK nor the binding checks arguments against the tool's
    /// input schema for a custom <c>McpServerTool</c>. The service does
    /// (SPEC.md §6.3, Parameter Validation): arguments that do not match the
    /// capability's declared inputs are refused as a tool error carrying the
    /// <c>invalid_parameters</c> failure, and no handler runs.
    /// </summary>
    [Theory]
    [InlineData("missing required", """{}""", "echo is missing required input(s): message")]
    [InlineData("wrong type", """{"message":42}""", "echo has invalid input(s): 'message' must be string, got number")]
    [InlineData("null for a required string", """{"message":null}""", "echo is missing required input(s): message")]
    [InlineData("boolean where an integer is declared", """{"message":"hi","count":true}""", "echo has invalid input(s): 'count' must be integer, got boolean")]
    [InlineData("fraction where an integer is declared", """{"message":"hi","count":1.5}""", "echo has invalid input(s): 'count' must be integer, got number")]
    public async Task ArgumentsThatBreakTheDeclaredInputs_AreRefused_AndNoHandlerRuns(
        string what, string argumentsJson, string detail)
    {
        var client = await ConnectAsync(_app.Http);
        var arguments = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(argumentsJson)!;

        var reply = await client.CallToolAsync("echo", arguments, Authorization);

        Assert.True(reply.HasResult, $"{what}: {reply}");
        Assert.True(reply.IsToolError, $"{what}: {reply}");
        Assert.Equal(
            "FAILED: invalid_parameters\n" +
            $"Detail: {detail}\n" +
            "Resolution: retry_now\n" +
            "Requires: parameters that match the capability's declared inputs\n" +
            "Retryable: no",
            reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    /// <summary>
    /// Arguments that match the declared inputs reach the handler as they were
    /// sent: undeclared arguments are not checked, and an integral number is
    /// an integer however it is written.
    /// </summary>
    [Theory]
    [InlineData("undeclared argument", """{"message":"hi","surprise":"x"}""")]
    [InlineData("integral float where an integer is declared", """{"message":"hi","count":3.0}""")]
    [InlineData("null for an optional input", """{"message":"hi","count":null}""")]
    public async Task ArgumentsThatMatchTheDeclaredInputs_ReachTheHandlerUnchanged(string what, string argumentsJson)
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
            if (value.ValueKind == JsonValueKind.Number)
            {
                Assert.Equal(value.GetDouble(), Convert.ToDouble(call.Parameters[key]));
            }
            else
            {
                Assert.Equal(value.GetRawText(), JsonSerializer.Serialize(call.Parameters[key]));
            }
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
