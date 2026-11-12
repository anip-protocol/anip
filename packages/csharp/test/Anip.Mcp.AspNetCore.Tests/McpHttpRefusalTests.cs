using System.Net;

namespace Anip.Mcp.AspNetCore.Tests;

/// <summary>
/// Tool calls the MCP binding must refuse, sent as HTTP requests to the mounted
/// endpoint. Each test checks two things: the refusal reaches the caller, and
/// the capability handler did not run.
///
/// These cover the Streamable HTTP endpoint. They do not cover the legacy SSE
/// endpoints that MCP SDK 1.x also mapped, where credentials were taken from
/// the request that opened the stream; see <see cref="McpHttpTransportTests"/>
/// for the check that those endpoints are no longer served.
///
/// These tests use wire-level clients (see <see cref="IWireClient"/>) so they
/// do not depend on the MCP SDK version the binding is built on. Every test
/// runs once per way of speaking the protocol: see the classes at the end of
/// this file.
/// </summary>
public abstract class McpHttpRefusalTests : IAsyncLifetime
{
    private McpTestApp _app = null!;

    private protected abstract Task<IWireClient> ConnectAsync(
        HttpClient http, string path = "/mcp", IEnumerable<(string Name, string Value)>? extraHeaders = null);

    public async Task InitializeAsync() => _app = await McpTestApp.StartAsync();

    public async Task DisposeAsync()
    {
        // A refusal is an answer, not a crash.
        Assert.Empty(_app.UnhandledExceptions);
        await _app.DisposeAsync();
    }

    private static string Bearer(string credential) => $"Bearer {credential}";

    // --- Accepted calls (so that a refusal below is known to be a refusal) ---

    [Fact]
    public async Task ApiKey_IsAccepted_AndRunsAsTheAdapterSubjectWithMinimumScope()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Bearer(McpTestApp.ApiKey));

        Assert.True(reply.HasResult, reply.ToString());
        Assert.False(reply.IsToolError, reply.ToString());
        Assert.Contains("\"echoed\": \"hi\"", reply.ToolText);

        var call = Assert.Single(_app.Calls);
        Assert.Equal("echo", call.Capability);
        Assert.Equal("adapter:anip-mcp", call.Subject);
        Assert.Equal(McpTestApp.ApiKeyPrincipal, call.RootPrincipal);
        Assert.Equal(new[] { "data.read" }, call.Scopes);
    }

    [Fact]
    public async Task Jwt_IsAccepted_AndRunsAsTheTokenSubject()
    {
        var jwt = _app.IssueJwt("agent:alice", "echo", "data.read");
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Bearer(jwt));

        Assert.False(reply.IsToolError, reply.ToString());
        var call = Assert.Single(_app.Calls);
        Assert.Equal("agent:alice", call.Subject);
        Assert.Equal(McpTestApp.ApiKeyPrincipal, call.RootPrincipal);
    }

    [Fact]
    public async Task BearerScheme_IsMatchedCaseInsensitively()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, $"bearer {McpTestApp.ApiKey}");

        Assert.False(reply.IsToolError, reply.ToString());
        Assert.Single(_app.Calls);
    }

    // --- Authentication refusals ---

    [Fact]
    public async Task NoCredentials_IsRefused()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, authorization: null);

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: authentication_required", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData("Basic dmFsaWQtYXBpLWtleTo=")]
    [InlineData("valid-api-key")]
    [InlineData("Bearer")]
    [InlineData("Bearer ")]
    [InlineData("Bearervalid-api-key")]
    [InlineData("Token valid-api-key")]
    [InlineData("ApiKey valid-api-key")]
    public async Task CredentialsThatAreNotABearerToken_AreRefused(string authorization)
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, authorization);

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: authentication_required", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData("not-a-known-key")]
    [InlineData("eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl")]
    public async Task InvalidCredentials_AreRefused(string credential)
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Bearer(credential));

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: invalid_token", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Fact]
    public async Task TamperedJwt_IsRefused()
    {
        var jwt = _app.IssueJwt("agent:alice", "echo", "data.read");
        var tampered = jwt[..^4] + (jwt.EndsWith("AAAA", StringComparison.Ordinal) ? "BBBB" : "AAAA");
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Bearer(tampered));

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: invalid_token", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    // --- Credentials come from the Authorization header and nowhere else ---

    [Fact]
    public async Task CredentialsInTheQueryString_AreNotAccepted()
    {
        var client = await ConnectAsync(
            _app.Http,
            path: $"/mcp?access_token={McpTestApp.ApiKey}&api_key={McpTestApp.ApiKey}&authorization=Bearer%20{McpTestApp.ApiKey}");

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, authorization: null);

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: authentication_required", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Theory]
    [InlineData("X-Api-Key", "valid-api-key")]
    [InlineData("X-Authorization", "Bearer valid-api-key")]
    [InlineData("Proxy-Authorization", "Bearer valid-api-key")]
    [InlineData("Cookie", "Authorization=Bearer valid-api-key; access_token=valid-api-key")]
    public async Task CredentialsInAnotherHeader_AreNotAccepted(string header, string value)
    {
        var client = await ConnectAsync(_app.Http, extraHeaders: [(header, value)]);

        var reply = await client.CallToolAsync("echo", new { message = "hi" }, authorization: null);

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: authentication_required", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Fact]
    public async Task CredentialsInTheArguments_AreNotAccepted()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync(
            "echo",
            new Dictionary<string, object?>
            {
                ["message"] = "hi",
                ["__bearer"] = McpTestApp.ApiKey,
                ["authorization"] = Bearer(McpTestApp.ApiKey),
                ["api_key"] = McpTestApp.ApiKey,
            },
            authorization: null);

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: authentication_required", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Fact]
    public async Task ASecondAuthorizationHeader_DoesNotRescueAnInvalidFirstOne()
    {
        var client = await ConnectAsync(_app.Http, extraHeaders: [("Authorization", Bearer(McpTestApp.ApiKey))]);

        // Sent first; the valid one above is added after it.
        var reply = await client.CallToolAsync("echo", new { message = "hi" }, Bearer("not-a-known-key"));

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: invalid_token", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    // --- Authorization refusals ---

    [Fact]
    public async Task TokenIssuedForAnotherCapability_IsRefused()
    {
        // The scope covers delete_record, so only the binding to "echo" can
        // refuse this call. With a narrower scope the scope check would refuse
        // it first and the purpose check would never be reached.
        var jwtForEcho = _app.IssueJwt("agent:alice", "echo", "data.read", "admin.write");
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("delete_record", new { id = "r1" }, Bearer(jwtForEcho));

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: purpose_mismatch", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Fact]
    public async Task TokenWithInsufficientScope_IsRefused()
    {
        // Bound to the right capability, but without the scope it requires.
        var jwt = _app.IssueJwt("agent:alice", "delete_record", "data.read");
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("delete_record", new { id = "r1" }, Bearer(jwt));

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: scope_insufficient", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    // --- Requests for things that do not exist ---

    [Fact]
    public async Task UnknownTool_IsRefusedAsAProtocolError()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("no_such_tool", new { }, Bearer(McpTestApp.ApiKey));

        Assert.True(reply.IsProtocolError, reply.ToString());
        Assert.Equal(-32602, reply.ProtocolErrorCode);
        Assert.Empty(_app.Calls);
    }

    // --- Credentials are per request, never remembered ---

    [Fact]
    public async Task CredentialsAreCheckedOnEveryRequest_NotRememberedFromAnEarlierOne()
    {
        // Same client, and the same session if the server keeps one.
        var client = await ConnectAsync(_app.Http);

        var first = await client.CallToolAsync("echo", new { message = "one" }, Bearer(McpTestApp.ApiKey));
        Assert.False(first.IsToolError, first.ToString());
        Assert.Single(_app.Calls);

        var second = await client.CallToolAsync("echo", new { message = "two" }, authorization: null);
        Assert.True(second.IsToolError, second.ToString());
        Assert.StartsWith("FAILED: authentication_required", second.ToolText);

        var third = await client.CallToolAsync("echo", new { message = "three" }, Bearer("not-a-known-key"));
        Assert.True(third.IsToolError, third.ToString());

        Assert.Single(_app.Calls);
    }

    [Fact]
    public async Task EachRequestRunsUnderItsOwnCredentials_WhenRequestsOverlap()
    {
        var alice = _app.IssueJwt("agent:alice", "echo", "data.read");
        var bob = _app.IssueJwt("agent:bob", "echo", "data.read");
        var client = await ConnectAsync(_app.Http);

        var tasks = Enumerable.Range(0, 24).Select(async i =>
        {
            (string? jwt, string? subject) = (i % 3) switch
            {
                0 => (alice, "agent:alice"),
                1 => (bob, "agent:bob"),
                _ => ((string?)null, (string?)null),
            };

            var reply = await client.CallToolAsync(
                "echo", new { message = $"m{i}" }, jwt == null ? null : Bearer(jwt));

            if (subject == null)
            {
                Assert.True(reply.IsToolError, reply.ToString());
            }
            else
            {
                Assert.False(reply.IsToolError, reply.ToString());
                Assert.Contains($"\"subject\": \"{subject}\"", reply.ToolText);
                Assert.Contains($"\"echoed\": \"m{i}\"", reply.ToolText);
            }
        });

        await Task.WhenAll(tasks);

        Assert.Equal(16, _app.Calls.Count);
        foreach (var call in _app.Calls)
        {
            var index = int.Parse(((string)call.Parameters["message"]!)[1..]);
            Assert.Equal(index % 3 == 0 ? "agent:alice" : "agent:bob", call.Subject);
        }
    }

    // --- What needs no credentials ---

    [Fact]
    public async Task ListingTools_NeedsNoCredentials_AndShowsSchemasAndHints()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.ListToolsAsync(authorization: null);

        Assert.True(reply.HasResult, reply.ToString());
        var tools = reply.Result.GetProperty("tools").EnumerateArray().ToDictionary(t => t.GetProperty("name").GetString()!);
        Assert.Equal(new[] { "delete_record", "echo", "explode" }, tools.Keys.OrderBy(k => k, StringComparer.Ordinal));

        var echo = tools["echo"];
        Assert.Equal("object", echo.GetProperty("inputSchema").GetProperty("type").GetString());
        Assert.Equal("integer", echo.GetProperty("inputSchema").GetProperty("properties").GetProperty("count").GetProperty("type").GetString());
        Assert.Equal(new[] { "message" }, echo.GetProperty("inputSchema").GetProperty("required").EnumerateArray().Select(e => e.GetString()));
        Assert.True(echo.GetProperty("annotations").GetProperty("readOnlyHint").GetBoolean());
        Assert.False(echo.GetProperty("annotations").GetProperty("destructiveHint").GetBoolean());
        Assert.Contains("Delegation scope: data.read.", echo.GetProperty("description").GetString());

        var delete = tools["delete_record"];
        Assert.False(delete.GetProperty("annotations").GetProperty("readOnlyHint").GetBoolean());
        Assert.True(delete.GetProperty("annotations").GetProperty("destructiveHint").GetBoolean());

        Assert.Empty(_app.Calls);
    }

    // --- Failures inside a capability ---

    [Fact]
    public async Task HandlerException_BecomesAToolError_WithoutLeakingTheExceptionText()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync("explode", new { }, Bearer(McpTestApp.ApiKey));

        Assert.Equal(HttpStatusCode.OK, reply.Status);
        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: internal_error", reply.ToolText);
        Assert.DoesNotContain("secret-internal-detail", reply.RawBody);
    }

    // --- The approval grant rides on a reserved argument ---

    [Fact]
    public async Task UnknownApprovalGrant_IsRefused()
    {
        var client = await ConnectAsync(_app.Http);

        var reply = await client.CallToolAsync(
            "echo",
            new Dictionary<string, object?> { ["message"] = "hi", ["__approval_grant"] = "grant-that-does-not-exist" },
            Bearer(McpTestApp.ApiKey));

        Assert.True(reply.IsToolError, reply.ToString());
        Assert.StartsWith("FAILED: grant_not_found", reply.ToolText);
        Assert.Empty(_app.Calls);
    }

    [Fact]
    public async Task ReservedApprovalGrantKey_IsStrippedFromTheParametersTheHandlerSees()
    {
        var client = await ConnectAsync(_app.Http);

        // Not a string, so it is not a usable grant: the call proceeds without
        // one, and the reserved key must still not reach the handler.
        var reply = await client.CallToolAsync(
            "echo",
            new Dictionary<string, object?> { ["message"] = "hi", ["__approval_grant"] = 5 },
            Bearer(McpTestApp.ApiKey));

        Assert.False(reply.IsToolError, reply.ToString());
        var call = Assert.Single(_app.Calls);
        Assert.Equal(new[] { "message" }, call.Parameters.Keys);
        Assert.Null(call.ApprovalGrant);
    }
}

/// <summary>The refusals, for a client that opens with the <c>initialize</c> handshake.</summary>
public sealed class McpHttpRefusalTests_InitializeHandshake : McpHttpRefusalTests
{
    private protected override async Task<IWireClient> ConnectAsync(
        HttpClient http, string path = "/mcp", IEnumerable<(string Name, string Value)>? extraHeaders = null) =>
        await LegacyWireClient.ConnectAsync(http, authorization: null, path, extraHeaders);
}

/// <summary>The refusals, for a client that speaks the 2026-07-28 protocol revision.</summary>
public sealed class McpHttpRefusalTests_Protocol20260728 : McpHttpRefusalTests
{
    private protected override async Task<IWireClient> ConnectAsync(
        HttpClient http, string path = "/mcp", IEnumerable<(string Name, string Value)>? extraHeaders = null) =>
        await ModernWireClient.ConnectAsync(http, path, extraHeaders);
}
