using System.Net;

namespace Anip.Mcp.AspNetCore.Tests;

/// <summary>
/// How the endpoint is exposed over HTTP. These pin down the choices made when
/// the binding moved to the 2.x MCP SDK: no sessions, no legacy SSE endpoints,
/// and both old and new protocol revisions served from the same path.
/// </summary>
public class McpHttpTransportTests : IAsyncLifetime
{
    private const string Authorization = "Bearer " + McpTestApp.ApiKey;

    private McpTestApp _app = null!;

    public async Task InitializeAsync() => _app = await McpTestApp.StartAsync();

    public async Task DisposeAsync() => await _app.DisposeAsync();

    [Fact]
    public async Task InitializeHandshake_IsAnswered_WithoutIssuingASession()
    {
        var client = await LegacyWireClient.ConnectAsync(_app.Http);

        Assert.Null(client.SessionId);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Authorization);
        Assert.False(reply.IsToolError, reply.ToString());
        Assert.Null(reply.SessionId);
    }

    /// <summary>
    /// With no session there is nothing to "join": a tool call can arrive
    /// without a handshake before it. It is still authenticated like any other.
    /// </summary>
    [Fact]
    public async Task ToolCallWithoutAHandshake_StillNeedsCredentials()
    {
        var client = LegacyWireClient.WithoutHandshake(_app.Http);

        var refused = await client.CallToolAsync("echo", new { message = "hi" }, authorization: null);
        Assert.True(refused.IsToolError, refused.ToString());
        Assert.StartsWith("FAILED: authentication_required", refused.ToolText);
        Assert.Empty(_app.Calls);

        var accepted = await client.CallToolAsync("echo", new { message = "hi" }, Authorization);
        Assert.False(accepted.IsToolError, accepted.ToString());
        Assert.Single(_app.Calls);
    }

    [Fact]
    public async Task RequestCarryingASessionId_IsRejected()
    {
        var client = LegacyWireClient.WithoutHandshake(_app.Http, sessionId: "left-over-from-an-older-server");

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Authorization);

        Assert.Equal(HttpStatusCode.BadRequest, reply.Status);
        Assert.False(reply.HasResult, reply.ToString());
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData("GET", "/mcp/sse")]
    [InlineData("POST", "/mcp/message")]
    [InlineData("POST", "/mcp/message?sessionId=anything")]
    public async Task LegacySseEndpoints_AreNotServed(string method, string path)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        request.Headers.TryAddWithoutValidation("Accept", "text/event-stream");
        request.Headers.TryAddWithoutValidation("Authorization", Authorization);
        if (method == "POST")
        {
            request.Content = new StringContent(
                """{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"echo","arguments":{"message":"hi"}}}""",
                System.Text.Encoding.UTF8,
                "application/json");
        }

        using var response = await _app.Http.SendAsync(request);

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData("GET")]
    [InlineData("DELETE")]
    public async Task SessionOnlyHttpMethods_AreNotAllowed(string method)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), "/mcp");
        request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream");

        using var response = await _app.Http.SendAsync(request);

        Assert.Equal(HttpStatusCode.MethodNotAllowed, response.StatusCode);
    }

    /// <summary>
    /// In the 2026-07-28 revision the tool is named twice, in the body and in
    /// the <c>Mcp-Name</c> header. A request where the two disagree must not
    /// run either tool: here the token is valid for the tool in the header and
    /// not for the tool in the body.
    /// </summary>
    [Fact]
    public async Task Protocol20260728_HeaderNamingADifferentToolThanTheBody_RunsNeither()
    {
        var jwtForEcho = _app.IssueJwt("agent:alice", "echo", "data.read");
        var client = await ModernWireClient.ConnectAsync(_app.Http);

        var reply = await client.CallToolWithHeaderNameAsync(
            bodyName: "delete_record", headerName: "echo", new { id = "r1", message = "hi" }, $"Bearer {jwtForEcho}");

        Assert.False(reply.HasResult && !reply.IsToolError, $"expected a refusal, got: {reply}");
        Assert.Empty(_app.Calls);
    }

    [Fact]
    public async Task UnsupportedProtocolVersionHeader_IsRejected()
    {
        var client = LegacyWireClient.WithoutHandshake(_app.Http, protocolVersion: "1999-01-01");

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Authorization);

        Assert.Equal(HttpStatusCode.BadRequest, reply.Status);
        Assert.Empty(_app.Calls);
    }
}
