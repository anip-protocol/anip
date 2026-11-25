using Anip.Core;
using Anip.Service;
using Anip.Stdio;

namespace Anip.Stdio.Tests;

/// <summary>
/// SPEC.md §6.3 "Parameter Validation" over the stdio transport: the
/// <c>invalid_parameters</c> failure is in the response message, unary and streaming.
/// </summary>
public class StdioInputValidationTests : IDisposable
{
    private readonly AnipService _service;
    private readonly AnipStdioServer _server;
    private int _handlerRuns;

    public StdioInputValidationTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "stdio-validation-service",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "greet",
                        Description = "Greets someone",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "read" },
                        MinimumScope = new List<string> { "data" },
                        ResponseModes = new List<string> { "unary", "streaming" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "name", Type = "string" },
                            new() { Name = "times", Type = "integer", Required = false },
                        },
                    },
                    (ctx, parameters) =>
                    {
                        Interlocked.Increment(ref _handlerRuns);
                        return new Dictionary<string, object?> { ["greeting"] = "hello " + parameters["name"] };
                    }),
            },
            Authenticate = bearer => bearer == "valid-key" ? "test-user" : null,
        });
        _service.Start();
        _server = new AnipStdioServer(_service);
    }

    public void Dispose() => _service.Dispose();

    private Dictionary<string, object?> InvokeRequest(Dictionary<string, object?> parameters, bool stream)
    {
        var jwt = _service.IssueToken("test-user", new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { "data" },
            Capability = "greet",
            TtlHours = 1,
        }).Token;

        return new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["id"] = 7,
            ["method"] = "anip.invoke",
            ["params"] = new Dictionary<string, object?>
            {
                ["auth"] = new Dictionary<string, object?> { ["bearer"] = jwt },
                ["capability"] = "greet",
                ["stream"] = stream,
                ["parameters"] = parameters,
            },
        };
    }

    private static void AssertInvalidParameters(Dictionary<string, object?> failure, string detail)
    {
        Assert.Equal(Constants.FailureInvalidParameters, failure["type"]);
        Assert.Equal(detail, failure["detail"]);
        Assert.Equal(false, failure["retry"]);
        var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
        Assert.Equal("retry_now", resolution["action"]);
        Assert.Equal("retry_now", resolution["recovery_class"]);
        Assert.Equal("parameters that match the capability's declared inputs", resolution["requires"]);
    }

    [Fact]
    public async Task Unary_MissingRequiredInput_IsAFailureInTheResult()
    {
        var response = (Dictionary<string, object?>)await _server.HandleRequestAsync(
            InvokeRequest(new Dictionary<string, object?>(), stream: false));

        var result = Assert.IsType<Dictionary<string, object?>>(response["result"]);
        Assert.Equal(false, result["success"]);
        AssertInvalidParameters(
            Assert.IsType<Dictionary<string, object?>>(result["failure"]),
            "greet is missing required input(s): name");
        Assert.StartsWith("inv-", Assert.IsType<string>(result["invocation_id"]));
        Assert.Equal(0, _handlerRuns);
    }

    [Fact]
    public async Task Unary_WrongType_IsAFailureInTheResult()
    {
        var response = (Dictionary<string, object?>)await _server.HandleRequestAsync(
            InvokeRequest(new Dictionary<string, object?> { ["name"] = "Ada", ["times"] = 1.5 }, stream: false));

        var result = Assert.IsType<Dictionary<string, object?>>(response["result"]);
        AssertInvalidParameters(
            Assert.IsType<Dictionary<string, object?>>(result["failure"]),
            "greet has invalid input(s): 'times' must be integer, got number");
        Assert.Equal(0, _handlerRuns);
    }

    [Fact]
    public async Task Unary_ThroughTheWire_MissingRequiredInput_IsRefused()
    {
        var request = InvokeRequest(new Dictionary<string, object?>(), stream: false);
        var reader = new StringReader(System.Text.Json.JsonSerializer.Serialize(request) + "\n");
        var writer = new StringWriter();

        await _server.ServeAsync(reader, writer);

        using var reply = System.Text.Json.JsonDocument.Parse(writer.ToString());
        var failure = reply.RootElement.GetProperty("result").GetProperty("failure");
        Assert.Equal(Constants.FailureInvalidParameters, failure.GetProperty("type").GetString());
        Assert.Equal("retry_now", failure.GetProperty("resolution").GetProperty("action").GetString());
        Assert.False(failure.GetProperty("retry").GetBoolean());
        Assert.Equal(0, _handlerRuns);
    }

    [Fact]
    public async Task Streaming_MissingRequiredInput_IsAnErrorCarryingTheFailure()
    {
        var response = await _server.HandleRequestAsync(
            InvokeRequest(new Dictionary<string, object?>(), stream: true));

        // No stream opens: one message, the JSON-RPC error, with the failure as its data.
        var message = Assert.IsType<Dictionary<string, object?>>(response);
        Assert.Equal(7, message["id"]);
        var error = Assert.IsType<Dictionary<string, object?>>(message["error"]);
        AssertInvalidParameters(
            Assert.IsType<Dictionary<string, object?>>(error["data"]),
            "greet is missing required input(s): name");
        Assert.Equal(0, _handlerRuns);
    }

    [Fact]
    public async Task ValidCall_Runs_UnaryAndStreaming()
    {
        var unary = (Dictionary<string, object?>)await _server.HandleRequestAsync(
            InvokeRequest(new Dictionary<string, object?> { ["name"] = "Ada", ["times"] = 2.0 }, stream: false));
        Assert.Equal(true, ((Dictionary<string, object?>)unary["result"]!)["success"]);

        var streamed = Assert.IsType<List<Dictionary<string, object?>>>(await _server.HandleRequestAsync(
            InvokeRequest(new Dictionary<string, object?> { ["name"] = "Ada" }, stream: true)));
        Assert.Equal(true, ((Dictionary<string, object?>)streamed[^1]["result"]!)["success"]);
        Assert.Equal(2, _handlerRuns);
    }
}
