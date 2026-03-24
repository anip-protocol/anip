using System.Text.Json;
using Anip.Core;
using Anip.Service;
using Anip.Stdio;

namespace Anip.Stdio.Tests;

public class AnipStdioServerTests : IDisposable
{
    private readonly AnipService _service;
    private readonly AnipStdioServer _server;
    private readonly string _principal = "test-user";

    public AnipStdioServerTests()
    {
        var config = new ServiceConfig
        {
            ServiceId = "stdio-test-service",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1, // Disable retention to avoid background task issues.
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
        _server = new AnipStdioServer(_service);
    }

    public void Dispose()
    {
        _service.Dispose();
    }

    // --- Helper to build JSON-RPC request dicts ---

    private static Dictionary<string, object?> MakeRequest(string method, object? id = null, Dictionary<string, object?>? parameters = null)
    {
        return new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id ?? 1,
            ["method"] = method,
            ["params"] = parameters ?? new Dictionary<string, object?>(),
        };
    }

    private static Dictionary<string, object?> WithAuth(Dictionary<string, object?> parameters, string bearer)
    {
        parameters["auth"] = new Dictionary<string, object?> { ["bearer"] = bearer };
        return parameters;
    }

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

    private static Dictionary<string, object?> AsDict(object response)
    {
        return (Dictionary<string, object?>)response;
    }

    private static Dictionary<string, object?> GetResult(object response)
    {
        var dict = AsDict(response);
        return (Dictionary<string, object?>)dict["result"]!;
    }

    private static Dictionary<string, object?> GetError(object response)
    {
        var dict = AsDict(response);
        return (Dictionary<string, object?>)dict["error"]!;
    }

    // --- Validation tests ---

    [Fact]
    public async Task InvalidRequest_MissingJsonrpc()
    {
        var msg = new Dictionary<string, object?>
        {
            ["id"] = 1,
            ["method"] = "anip.discovery",
        };

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32600, error["code"]);
        Assert.Contains("jsonrpc", (string)error["message"]!);
    }

    [Fact]
    public async Task InvalidRequest_MissingMethod()
    {
        var msg = new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["id"] = 1,
        };

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32600, error["code"]);
        Assert.Contains("method", (string)error["message"]!);
    }

    [Fact]
    public async Task InvalidRequest_MissingId()
    {
        var msg = new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["method"] = "anip.discovery",
        };

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32600, error["code"]);
        Assert.Contains("id", (string)error["message"]!);
    }

    [Fact]
    public async Task UnknownMethod_ReturnsMethodNotFound()
    {
        var msg = MakeRequest("anip.nonexistent");

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32601, error["code"]);
        Assert.Contains("Unknown method", (string)error["message"]!);
    }

    // --- anip.discovery ---

    [Fact]
    public async Task Discovery_ReturnsDiscoveryDocument()
    {
        var msg = MakeRequest("anip.discovery");
        var response = await _server.HandleRequestAsync(msg);

        var dict = AsDict(response);
        Assert.Equal("2.0", dict["jsonrpc"]);
        Assert.Equal(1, dict["id"]);

        var result = GetResult(response);
        Assert.True(result.ContainsKey("anip_discovery"));
    }

    // --- anip.manifest ---

    [Fact]
    public async Task Manifest_ReturnsManifestAndSignature()
    {
        var msg = MakeRequest("anip.manifest");
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True(result.ContainsKey("manifest"));
        Assert.True(result.ContainsKey("signature"));
        Assert.IsType<string>(result["signature"]);
    }

    // --- anip.jwks ---

    [Fact]
    public async Task Jwks_ReturnsKeysDocument()
    {
        var msg = MakeRequest("anip.jwks");
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True(result.ContainsKey("keys"));
    }

    // --- anip.tokens.issue ---

    [Fact]
    public async Task TokensIssue_WithValidAuth_ReturnsToken()
    {
        var parameters = WithAuth(new Dictionary<string, object?>
        {
            ["subject"] = "agent-1",
            ["scope"] = new List<object?> { "data" },
            ["capability"] = "echo",
            ["ttl_hours"] = 1,
        }, "valid-key");

        var msg = MakeRequest("anip.tokens.issue", 1, parameters);
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True((bool)result["issued"]!);
        Assert.NotNull(result["token_id"]);
        Assert.NotNull(result["token"]);
    }

    [Fact]
    public async Task TokensIssue_WithoutAuth_ReturnsAuthError()
    {
        var msg = MakeRequest("anip.tokens.issue", 1, new Dictionary<string, object?>
        {
            ["subject"] = "agent-1",
            ["scope"] = new List<object?> { "data" },
            ["capability"] = "echo",
        });

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32001, error["code"]);
    }

    [Fact]
    public async Task TokensIssue_WithInvalidAuth_ReturnsAuthError()
    {
        var parameters = WithAuth(new Dictionary<string, object?>
        {
            ["subject"] = "agent-1",
            ["scope"] = new List<object?> { "data" },
            ["capability"] = "echo",
        }, "bad-key");

        var msg = MakeRequest("anip.tokens.issue", 1, parameters);
        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32001, error["code"]);
    }

    // --- anip.permissions ---

    [Fact]
    public async Task Permissions_ReturnsPermissionDoc()
    {
        var jwt = IssueTestToken("data");

        var msg = MakeRequest("anip.permissions", 1,
            WithAuth(new Dictionary<string, object?>(), jwt));
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True(result.ContainsKey("available"));
        Assert.True(result.ContainsKey("restricted"));
        Assert.True(result.ContainsKey("denied"));
    }

    [Fact]
    public async Task Permissions_WithoutAuth_ReturnsAuthError()
    {
        var msg = MakeRequest("anip.permissions");
        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32001, error["code"]);
    }

    // --- anip.invoke ---

    [Fact]
    public async Task Invoke_Success()
    {
        var jwt = IssueTestToken("data");

        var parameters = WithAuth(new Dictionary<string, object?>
        {
            ["capability"] = "echo",
            ["parameters"] = new Dictionary<string, object?>
            {
                ["message"] = "hello",
            },
        }, jwt);

        var msg = MakeRequest("anip.invoke", 1, parameters);
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True((bool)result["success"]!);
        var innerResult = (Dictionary<string, object?>)result["result"]!;
        Assert.Equal("hello", innerResult["echoed"]);
    }

    [Fact]
    public async Task Invoke_MissingCapability_ReturnsError()
    {
        var jwt = IssueTestToken("data");

        var parameters = WithAuth(new Dictionary<string, object?>
        {
            ["parameters"] = new Dictionary<string, object?> { ["message"] = "hello" },
        }, jwt);

        var msg = MakeRequest("anip.invoke", 1, parameters);
        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32004, error["code"]); // not_found / unknown_capability
    }

    [Fact]
    public async Task Invoke_WithoutAuth_ReturnsAuthError()
    {
        var msg = MakeRequest("anip.invoke", 1, new Dictionary<string, object?>
        {
            ["capability"] = "echo",
        });

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32001, error["code"]);
    }

    [Fact]
    public async Task Invoke_ScopeInsufficient_ReturnsInvokeFailure()
    {
        // Issue token with wrong scope
        var jwt = IssueTestToken("billing");

        var parameters = WithAuth(new Dictionary<string, object?>
        {
            ["capability"] = "echo",
            ["parameters"] = new Dictionary<string, object?> { ["message"] = "hello" },
        }, jwt);

        var msg = MakeRequest("anip.invoke", 1, parameters);
        var response = await _server.HandleRequestAsync(msg);

        // Invoke returns a result envelope with success=false rather than a JSON-RPC error
        var result = GetResult(response);
        Assert.False((bool)result["success"]!);
    }

    // --- anip.audit.query ---

    [Fact]
    public async Task AuditQuery_ReturnsAuditEntries()
    {
        var jwt = IssueTestToken("data");

        // Invoke to create audit entries
        var invokeParams = WithAuth(new Dictionary<string, object?>
        {
            ["capability"] = "echo",
            ["parameters"] = new Dictionary<string, object?> { ["message"] = "audit-test" },
        }, jwt);
        await _server.HandleRequestAsync(MakeRequest("anip.invoke", 1, invokeParams));

        // Now query audit
        var queryParams = WithAuth(new Dictionary<string, object?>(), jwt);
        var msg = MakeRequest("anip.audit.query", 2, queryParams);
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True(result.ContainsKey("entries"));
        Assert.True(result.ContainsKey("count"));
    }

    [Fact]
    public async Task AuditQuery_WithoutAuth_ReturnsAuthError()
    {
        var msg = MakeRequest("anip.audit.query");
        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32001, error["code"]);
    }

    // --- anip.checkpoints.list ---

    [Fact]
    public async Task CheckpointsList_ReturnsList()
    {
        var msg = MakeRequest("anip.checkpoints.list");
        var response = await _server.HandleRequestAsync(msg);

        var result = GetResult(response);
        Assert.True(result.ContainsKey("checkpoints"));
    }

    // --- anip.checkpoints.get ---

    [Fact]
    public async Task CheckpointsGet_MissingId_ReturnsNotFoundError()
    {
        var msg = MakeRequest("anip.checkpoints.get");
        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32004, error["code"]);
    }

    [Fact]
    public async Task CheckpointsGet_NonexistentId_ReturnsNotFoundError()
    {
        var msg = MakeRequest("anip.checkpoints.get", 1, new Dictionary<string, object?>
        {
            ["id"] = "nonexistent-checkpoint",
        });

        var response = await _server.HandleRequestAsync(msg);
        var error = GetError(response);

        Assert.Equal(-32004, error["code"]);
    }

    // --- Serve loop integration test ---

    [Fact]
    public async Task ServeAsync_ProcessesMultipleRequests()
    {
        var input = string.Join("\n", new[]
        {
            JsonSerializer.Serialize(MakeRequest("anip.discovery", 1)),
            JsonSerializer.Serialize(MakeRequest("anip.jwks", 2)),
        }) + "\n";

        using var reader = new StringReader(input);
        using var writer = new StringWriter();

        await _server.ServeAsync(reader, writer);

        var output = writer.ToString();
        var lines = output.Split('\n', StringSplitOptions.RemoveEmptyEntries);

        Assert.Equal(2, lines.Length);

        // Both should be valid JSON-RPC responses
        using var doc1 = JsonDocument.Parse(lines[0]);
        Assert.Equal("2.0", doc1.RootElement.GetProperty("jsonrpc").GetString());

        using var doc2 = JsonDocument.Parse(lines[1]);
        Assert.Equal("2.0", doc2.RootElement.GetProperty("jsonrpc").GetString());
    }

    [Fact]
    public async Task ServeAsync_HandlesMalformedJson()
    {
        var input = "not valid json\n";

        using var reader = new StringReader(input);
        using var writer = new StringWriter();

        await _server.ServeAsync(reader, writer);

        var output = writer.ToString();
        var lines = output.Split('\n', StringSplitOptions.RemoveEmptyEntries);

        Assert.Single(lines);
        using var doc = JsonDocument.Parse(lines[0]);
        var error = doc.RootElement.GetProperty("error");
        Assert.Equal(-32700, error.GetProperty("code").GetInt32());
    }

    // --- Request ID preservation ---

    [Fact]
    public async Task RequestId_IsPreservedInResponse()
    {
        var msg = MakeRequest("anip.discovery", 42);
        var response = AsDict(await _server.HandleRequestAsync(msg));

        Assert.Equal(42, response["id"]);
    }

    [Fact]
    public async Task RequestId_StringIsPreserved()
    {
        var msg = MakeRequest("anip.discovery", "my-req-id");
        var response = AsDict(await _server.HandleRequestAsync(msg));

        Assert.Equal("my-req-id", response["id"]);
    }
}
