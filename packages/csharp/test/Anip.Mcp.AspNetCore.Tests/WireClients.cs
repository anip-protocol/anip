using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Anip.Mcp.AspNetCore.Tests;

/// <summary>What came back from one HTTP POST to the MCP endpoint.</summary>
internal sealed record WireReply(HttpStatusCode Status, JsonElement? Message, string RawBody, string? SessionId)
{
    /// <summary>True when the reply is a JSON-RPC error (the request never became a tool result).</summary>
    public bool IsProtocolError => Message is { } m && m.TryGetProperty("error", out _);

    public int? ProtocolErrorCode =>
        Message is { } m && m.TryGetProperty("error", out var e) && e.TryGetProperty("code", out var c)
            ? c.GetInt32()
            : null;

    public bool HasResult => Message is { } m && m.TryGetProperty("result", out _);

    public JsonElement Result => Message!.Value.GetProperty("result");

    /// <summary>True when the tool result is marked <c>isError</c>.</summary>
    public bool IsToolError =>
        HasResult && Result.TryGetProperty("isError", out var e) && e.ValueKind == JsonValueKind.True;

    /// <summary>The text of the first content block of a tool result.</summary>
    public string ToolText => Result.GetProperty("content")[0].GetProperty("text").GetString() ?? "";

    public override string ToString() => $"HTTP {(int)Status}: {RawBody}";
}

/// <summary>
/// A client written against the wire format, not against any SDK: plain HTTP
/// POSTs carrying JSON-RPC. It keeps working whichever SDK version the server
/// is built on, so the same tests can run before and after an SDK upgrade.
/// </summary>
internal interface IWireClient
{
    Task<WireReply> CallToolAsync(string name, object? arguments, string? authorization);

    Task<WireReply> ListToolsAsync(string? authorization);

    /// <summary>Sends a raw JSON body, for requests no well-behaved client would build.</summary>
    Task<WireReply> RequestRawAsync(string json, string? authorization, int id);
}

/// <summary>
/// Speaks the protocol the way clients did before the 2026-07-28 revision:
/// an <c>initialize</c> handshake first, then requests that carry the session
/// id if the server issued one.
/// </summary>
internal sealed class LegacyWireClient : IWireClient
{
    public const string ProtocolVersion = "2025-06-18";

    private readonly HttpClient _http;
    private readonly string _path;
    private int _nextId;

    public string? SessionId { get; private set; }

    private LegacyWireClient(HttpClient http, string path)
    {
        _http = http;
        _path = path;
    }

    /// <summary>
    /// A client that sends requests straight away, with no handshake before
    /// them, optionally presenting a session id or protocol version of its own.
    /// </summary>
    public static LegacyWireClient WithoutHandshake(
        HttpClient http, string? sessionId = null, string protocolVersion = ProtocolVersion, string path = "/mcp")
    {
        return new LegacyWireClient(http, path) { SessionId = sessionId, _protocolVersion = protocolVersion };
    }

    private string _protocolVersion = ProtocolVersion;

    /// <summary>Runs the initialize handshake and returns a ready client.</summary>
    public static async Task<LegacyWireClient> ConnectAsync(HttpClient http, string? authorization = null, string path = "/mcp")
    {
        var client = new LegacyWireClient(http, path);

        var init = await client.RequestAsync("initialize", new
        {
            protocolVersion = ProtocolVersion,
            capabilities = new { },
            clientInfo = new { name = "anip-wire-test", version = "1.0" },
        }, authorization, sendProtocolHeader: false);

        Assert.True(init.HasResult, $"initialize failed: {init}");
        client.SessionId = init.SessionId;

        var initialized = await client.SendAsync(
            new { jsonrpc = "2.0", method = "notifications/initialized" }, authorization, sendProtocolHeader: true);
        Assert.True((int)initialized.Status is >= 200 and < 300, $"initialized notification failed: {initialized}");

        return client;
    }

    public Task<WireReply> CallToolAsync(string name, object? arguments, string? authorization)
    {
        return RequestAsync("tools/call", new { name, arguments }, authorization);
    }

    public Task<WireReply> ListToolsAsync(string? authorization)
    {
        return RequestAsync("tools/list", new { }, authorization);
    }

    public Task<WireReply> RequestAsync(string method, object? @params, string? authorization, bool sendProtocolHeader = true)
    {
        var id = Interlocked.Increment(ref _nextId);
        return SendAsync(new { jsonrpc = "2.0", id, method, @params }, authorization, sendProtocolHeader, id);
    }

    public Task<WireReply> RequestRawAsync(string json, string? authorization, int id)
    {
        return SendJsonAsync(json, authorization, sendProtocolHeader: true, id);
    }

    private Task<WireReply> SendAsync(object body, string? authorization, bool sendProtocolHeader, int? id = null)
    {
        return SendJsonAsync(JsonSerializer.Serialize(body), authorization, sendProtocolHeader, id);
    }

    private async Task<WireReply> SendJsonAsync(string json, string? authorization, bool sendProtocolHeader, int? id)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, _path)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json"),
        };
        request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream");
        if (authorization != null)
        {
            request.Headers.TryAddWithoutValidation("Authorization", authorization);
        }

        if (sendProtocolHeader)
        {
            request.Headers.TryAddWithoutValidation("MCP-Protocol-Version", _protocolVersion);
        }

        if (SessionId != null)
        {
            request.Headers.TryAddWithoutValidation("Mcp-Session-Id", SessionId);
        }

        using var response = await _http.SendAsync(request);
        var raw = await response.Content.ReadAsStringAsync();
        var sessionId = response.Headers.TryGetValues("Mcp-Session-Id", out var values) ? values.FirstOrDefault() : null;

        return new WireReply(response.StatusCode, WireBody.FindMessage(raw, id), raw, sessionId);
    }
}

/// <summary>
/// Speaks the 2026-07-28 protocol revision: no handshake and no session. Every
/// request names its protocol version, method and tool in HTTP headers and
/// describes the client in <c>_meta</c>.
/// </summary>
internal sealed class ModernWireClient : IWireClient
{
    public const string ProtocolVersion = "2026-07-28";

    private static readonly Dictionary<string, object?> Meta = new()
    {
        ["io.modelcontextprotocol/protocolVersion"] = ProtocolVersion,
        ["io.modelcontextprotocol/clientInfo"] = new { name = "anip-wire-test", version = "1.0" },
        ["io.modelcontextprotocol/clientCapabilities"] = new { },
    };

    private readonly HttpClient _http;
    private readonly string _path;
    private int _nextId;

    private ModernWireClient(HttpClient http, string path)
    {
        _http = http;
        _path = path;
    }

    /// <summary>Checks that the server serves this revision and returns a ready client.</summary>
    public static async Task<ModernWireClient> ConnectAsync(HttpClient http, string path = "/mcp")
    {
        var client = new ModernWireClient(http, path);

        var discover = await client.SendAsync(
            "server/discover", new Dictionary<string, object?> { ["_meta"] = Meta }, authorization: null, toolName: null);
        Assert.True(discover.HasResult, $"server/discover failed: {discover}");
        Assert.Contains(
            ProtocolVersion,
            discover.Result.GetProperty("supportedVersions").EnumerateArray().Select(v => v.GetString()));
        Assert.Null(discover.SessionId);

        return client;
    }

    public Task<WireReply> CallToolAsync(string name, object? arguments, string? authorization)
    {
        return SendAsync(
            "tools/call",
            new Dictionary<string, object?> { ["name"] = name, ["arguments"] = arguments, ["_meta"] = Meta },
            authorization,
            toolName: name);
    }

    /// <summary>A tool call whose <c>Mcp-Name</c> header names a different tool than its body.</summary>
    public Task<WireReply> CallToolWithHeaderNameAsync(string bodyName, string headerName, object? arguments, string? authorization)
    {
        return SendAsync(
            "tools/call",
            new Dictionary<string, object?> { ["name"] = bodyName, ["arguments"] = arguments, ["_meta"] = Meta },
            authorization,
            toolName: headerName);
    }

    public Task<WireReply> ListToolsAsync(string? authorization)
    {
        return SendAsync("tools/list", new Dictionary<string, object?> { ["_meta"] = Meta }, authorization, toolName: null);
    }

    /// <summary>
    /// Sends the given body as it is, apart from adding <c>_meta</c> when
    /// <c>params</c> is an object, and sets the headers a real client would
    /// derive from it, so that the request is judged on its own defect. When
    /// the body has no usable tool name, the <c>Mcp-Name</c> header names a
    /// tool that exists: the hardest case for the server, since the header on
    /// its own looks like a valid call.
    /// </summary>
    public Task<WireReply> RequestRawAsync(string json, string? authorization, int id)
    {
        var node = JsonNode.Parse(json)!.AsObject();
        var method = node["method"]?.GetValueKind() == JsonValueKind.String ? node["method"]!.GetValue<string>() : null;
        var toolName = "echo";
        if (node["params"] is JsonObject parameters)
        {
            parameters["_meta"] = JsonSerializer.SerializeToNode(Meta);
            if (parameters["name"]?.GetValueKind() == JsonValueKind.String)
            {
                toolName = parameters["name"]!.GetValue<string>();
            }
        }

        return PostAsync(node.ToJsonString(), authorization, method, toolName, id);
    }

    private Task<WireReply> SendAsync(string method, object @params, string? authorization, string? toolName)
    {
        var id = Interlocked.Increment(ref _nextId);
        var json = JsonSerializer.Serialize(new { jsonrpc = "2.0", id, method, @params });
        return PostAsync(json, authorization, method, toolName, id);
    }

    private async Task<WireReply> PostAsync(string json, string? authorization, string? method, string? toolName, int id)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, _path)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json"),
        };
        request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream");
        request.Headers.TryAddWithoutValidation("MCP-Protocol-Version", ProtocolVersion);
        if (method != null)
        {
            request.Headers.TryAddWithoutValidation("Mcp-Method", method);
        }

        if (toolName != null)
        {
            request.Headers.TryAddWithoutValidation("Mcp-Name", toolName);
        }

        if (authorization != null)
        {
            request.Headers.TryAddWithoutValidation("Authorization", authorization);
        }

        using var response = await _http.SendAsync(request);
        var raw = await response.Content.ReadAsStringAsync();
        var sessionId = response.Headers.TryGetValues("Mcp-Session-Id", out var values) ? values.FirstOrDefault() : null;

        return new WireReply(response.StatusCode, WireBody.FindMessage(raw, id), raw, sessionId);
    }
}

internal static class WireBody
{
    /// <summary>
    /// Finds the JSON-RPC reply in a response body that is either plain JSON
    /// or a server-sent event stream.
    /// </summary>
    public static JsonElement? FindMessage(string raw, int? id)
    {
        var candidates = new List<string>();
        var trimmed = raw.TrimStart();
        if (trimmed.StartsWith('{'))
        {
            candidates.Add(trimmed);
        }
        else
        {
            foreach (var line in raw.Split('\n'))
            {
                if (line.StartsWith("data:", StringComparison.Ordinal))
                {
                    var data = line["data:".Length..].Trim();
                    if (data.StartsWith('{'))
                    {
                        candidates.Add(data);
                    }
                }
            }
        }

        JsonElement? fallback = null;
        foreach (var candidate in candidates)
        {
            JsonElement element;
            try
            {
                element = JsonDocument.Parse(candidate).RootElement.Clone();
            }
            catch (JsonException)
            {
                continue;
            }

            var isReply = element.TryGetProperty("result", out _) || element.TryGetProperty("error", out _);
            if (!isReply)
            {
                continue;
            }

            if (id is { } wanted && element.TryGetProperty("id", out var gotId)
                && gotId.ValueKind == JsonValueKind.Number && gotId.GetInt32() == wanted)
            {
                return element;
            }

            fallback ??= element;
        }

        return fallback;
    }
}
