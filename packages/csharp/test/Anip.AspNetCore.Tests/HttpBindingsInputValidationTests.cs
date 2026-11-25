using System.Net;
using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.AspNetCore.Tests;

/// <summary>
/// SPEC.md §6.3 "Parameter Validation" through every HTTP binding: the
/// protocol endpoint (unary and streaming), the REST adapter and the GraphQL
/// adapter. A missing required input is the <c>invalid_parameters</c> failure
/// with its resolution, and the handler does not run.
/// </summary>
public class HttpBindingsInputValidationTests : IAsyncLifetime
{
    private HttpBindingsTestApp _app = null!;

    public async Task InitializeAsync() => _app = await HttpBindingsTestApp.StartAsync();

    public async Task DisposeAsync() => await _app.DisposeAsync();

    private static void AssertInvalidParameters(JsonElement failure, string detail)
    {
        Assert.Equal(Constants.FailureInvalidParameters, failure.GetProperty("type").GetString());
        Assert.Equal(detail, failure.GetProperty("detail").GetString());
        Assert.False(failure.GetProperty("retry").GetBoolean());
        var resolution = failure.GetProperty("resolution");
        Assert.Equal("retry_now", resolution.GetProperty("action").GetString());
        Assert.Equal("retry_now", resolution.GetProperty("recovery_class").GetString());
        Assert.Equal("parameters that match the capability's declared inputs",
            resolution.GetProperty("requires").GetString());
    }

    // --- protocol endpoint, unary ---

    [Fact]
    public async Task Invoke_MissingRequiredInput_Is400InvalidParameters()
    {
        var jwt = _app.Jwt("book");

        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", jwt,
            """{"parameters": {"passengers": 2}, "client_reference_id": "ref-1"}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.False(body.GetProperty("success").GetBoolean());
        AssertInvalidParameters(body.GetProperty("failure"), "book is missing required input(s): flight_number");
        Assert.False(body.TryGetProperty("result", out _));
        Assert.Equal("ref-1", body.GetProperty("client_reference_id").GetString());
        Assert.Empty(_app.HandlerRuns);

        var entry = await _app.AuditEntryAsync(jwt, body.GetProperty("invocation_id").GetString()!);
        Assert.False(entry.GetProperty("success").GetBoolean());
        Assert.Equal(Constants.FailureInvalidParameters, entry.GetProperty("failure_type").GetString());
    }

    [Theory]
    [InlineData("""{"flight_number": 12345}""", "book has invalid input(s): 'flight_number' must be string, got number")]
    [InlineData("""{"flight_number": "AA100", "passengers": "two"}""", "book has invalid input(s): 'passengers' must be integer, got string")]
    [InlineData("""{"flight_number": "AA100", "passengers": true}""", "book has invalid input(s): 'passengers' must be integer, got boolean")]
    [InlineData("""{"flight_number": "AA100", "passengers": 1.5}""", "book has invalid input(s): 'passengers' must be integer, got number")]
    [InlineData("""{"flight_number": null}""", "book is missing required input(s): flight_number")]
    [InlineData("""{}""", "book is missing required input(s): flight_number")]
    public async Task Invoke_ParametersThatDoNotMatch_Are400InvalidParameters(string parameters, string detail)
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"),
            $$"""{"parameters": {{parameters}}}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        AssertInvalidParameters(body.GetProperty("failure"), detail);
        Assert.Empty(_app.HandlerRuns);
    }

    [Theory]
    [InlineData("""{"flight_number": "AA100"}""")]
    [InlineData("""{"flight_number": "AA100", "passengers": 5.0}""")]
    [InlineData("""{"flight_number": "AA100", "passengers": null, "seat": [1, 2]}""")]
    public async Task Invoke_ParametersThatMatch_Run(string parameters)
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"),
            $$"""{"parameters": {{parameters}}}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(body.GetProperty("success").GetBoolean());
        Assert.Equal(new[] { "book" }, _app.HandlerRuns);
    }

    // --- protocol endpoint, streaming ---

    [Theory]
    [InlineData("""["AA100"]""", "array")]
    [InlineData("\"AA100\"", "string")]
    [InlineData("1.5", "number")]
    [InlineData("true", "boolean")]
    public async Task Invoke_ParametersThatAreNotAnObject_Are400InvalidParameters(string parameters, string received)
    {
        // SPEC.md §6.3: the value does not match the request schema.
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"),
            $$"""{"parameters": {{parameters}}}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        AssertInvalidParameters(body.GetProperty("failure"), $"book parameters must be an object, got {received}");
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Invoke_NullParameters_AreTheEmptyObject()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"),
            """{"parameters": null}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        AssertInvalidParameters(body.GetProperty("failure"), "book is missing required input(s): flight_number");
    }

    [Fact]
    public async Task StreamRequestedFromAUnaryCapability_CarriesTheCheckManifestResolution()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"),
            """{"parameters": {"flight_number": "AA100"}, "stream": true}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        var failure = body.GetProperty("failure");
        Assert.Equal(Constants.FailureStreamingNotSupported, failure.GetProperty("type").GetString());
        var resolution = failure.GetProperty("resolution");
        Assert.Equal("check_manifest", resolution.GetProperty("action").GetString());
        Assert.Equal("revalidate_then_retry", resolution.GetProperty("recovery_class").GetString());
    }

    [Fact]
    public async Task StreamingInvoke_MissingRequiredInput_IsAJson400_AndNoStreamOpens()
    {
        var jwt = _app.Jwt("watch");

        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/watch", jwt,
            """{"parameters": {}, "stream": true, "client_reference_id": "ref-s"}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("application/json", response.Content.Headers.ContentType?.MediaType);
        Assert.False(body.GetProperty("success").GetBoolean());
        AssertInvalidParameters(body.GetProperty("failure"), "watch is missing required input(s): topic");
        Assert.Equal("ref-s", body.GetProperty("client_reference_id").GetString());
        Assert.Empty(_app.HandlerRuns);

        var entry = await _app.AuditEntryAsync(jwt, body.GetProperty("invocation_id").GetString()!);
        Assert.False(entry.GetProperty("success").GetBoolean());
        Assert.Equal(Constants.FailureInvalidParameters, entry.GetProperty("failure_type").GetString());
    }

    [Fact]
    public async Task StreamingInvoke_BindingMissing_IsAJsonRefusal_AndNoStreamOpens()
    {
        // SPEC.md §6.3: a streaming invocation runs the unary pre-handler checks.
        await using var app = await HttpBindingsTestApp.StartAsync(new[]
        {
            new CapabilityDef(
                new CapabilityDeclaration
                {
                    Name = "watch_quote",
                    Description = "needs a quote binding",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "read" },
                    MinimumScope = new List<string> { "data" },
                    ResponseModes = new List<string> { "unary", "streaming" },
                    Inputs = new List<CapabilityInput> { new() { Name = "quote", Type = "object", Required = false } },
                    RequiresBinding = new List<BindingRequirement>
                    {
                        new() { Type = "quote", Field = "quote", SourceCapability = "search" },
                    },
                },
                (ctx, p) => throw new InvalidOperationException("the handler must not run")),
        });

        var (response, body) = await app.SendAsync(HttpMethod.Post, "/anip/invoke/watch_quote",
            app.Jwt("watch_quote"), """{"parameters": {}, "stream": true}""");

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
        Assert.Equal("application/json", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal(Constants.FailureBindingMissing, body.GetProperty("failure").GetProperty("type").GetString());
        Assert.StartsWith("inv-", body.GetProperty("invocation_id").GetString());
    }

    [Fact]
    public async Task StreamingInvoke_ValidParameters_Stream()
    {
        var (response, _) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/watch", _app.Jwt("watch"),
            """{"parameters": {"topic": "gates"}, "stream": true}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("text/event-stream", response.Content.Headers.ContentType?.MediaType);
        Assert.Contains("event: completed", await response.Content.ReadAsStringAsync());
        Assert.Equal(new[] { "watch" }, _app.HandlerRuns);
    }

    // --- REST adapter ---

    [Fact]
    public async Task Rest_Post_MissingRequiredInput_Is400InvalidParameters()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/api/book", HttpBindingsTestApp.ApiKey,
            """{"passengers": 2}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.False(body.GetProperty("success").GetBoolean());
        AssertInvalidParameters(body.GetProperty("failure"), "book is missing required input(s): flight_number");
        Assert.StartsWith("inv-", body.GetProperty("invocation_id").GetString());
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Rest_Post_WrongType_Is400InvalidParameters()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/api/book", HttpBindingsTestApp.ApiKey,
            """{"flight_number": "AA100", "passengers": "two"}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        AssertInvalidParameters(body.GetProperty("failure"),
            "book has invalid input(s): 'passengers' must be integer, got string");
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Rest_Get_MissingRequiredInput_Is400InvalidParameters()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Get, "/api/search?limit=3", HttpBindingsTestApp.ApiKey);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        AssertInvalidParameters(body.GetProperty("failure"), "search is missing required input(s): origin");
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Rest_Get_QueryValueOfTheWrongType_Is400InvalidParameters()
    {
        var (response, body) = await _app.SendAsync(
            HttpMethod.Get, "/api/search?origin=SEA&limit=many", HttpBindingsTestApp.ApiKey);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        AssertInvalidParameters(body.GetProperty("failure"),
            "search has invalid input(s): 'limit' must be integer, got string");
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Rest_ValidCalls_Run()
    {
        var (get, _) = await _app.SendAsync(HttpMethod.Get, "/api/search?origin=SEA&limit=3", HttpBindingsTestApp.ApiKey);
        var (post, _) = await _app.SendAsync(HttpMethod.Post, "/api/book", HttpBindingsTestApp.ApiKey,
            """{"flight_number": "AA100", "passengers": 2.0}""");

        Assert.Equal(HttpStatusCode.OK, get.StatusCode);
        Assert.Equal(HttpStatusCode.OK, post.StatusCode);
        Assert.Equal(new[] { "search", "book" }, _app.HandlerRuns);
    }

    // --- GraphQL adapter ---

    [Fact]
    public async Task GraphQL_InputOfTheWrongJsonType_IsTheFailureInTheData()
    {
        var query = JsonSerializer.Serialize(new
        {
            query = "query($f: JSON) { search(origin: \"SEA\", filters: $f) { success failure { type detail retry resolution { action recoveryClass requires } } } }",
            variables = new { f = "not-an-object" },
        });

        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/graphql", HttpBindingsTestApp.ApiKey, query);

        // GraphQL convention: 200, with the failure in the response body.
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var search = body.GetProperty("data").GetProperty("search");
        Assert.False(search.GetProperty("success").GetBoolean());
        var failure = search.GetProperty("failure");
        Assert.Equal(Constants.FailureInvalidParameters, failure.GetProperty("type").GetString());
        Assert.Equal("search has invalid input(s): 'filters' must be object, got string",
            failure.GetProperty("detail").GetString());
        Assert.False(failure.GetProperty("retry").GetBoolean());
        Assert.Equal("retry_now", failure.GetProperty("resolution").GetProperty("action").GetString());
        Assert.Equal("retry_now", failure.GetProperty("resolution").GetProperty("recoveryClass").GetString());
        Assert.Equal("parameters that match the capability's declared inputs",
            failure.GetProperty("resolution").GetProperty("requires").GetString());
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task GraphQL_MissingRequiredArgument_IsRefusedAndNoHandlerRuns()
    {
        var query = JsonSerializer.Serialize(new { query = "{ search(limit: 3) { success failure { type } } }" });

        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/graphql", HttpBindingsTestApp.ApiKey, query);

        // A required input is a non-null argument: GraphQL's own validation refuses the document.
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(body.TryGetProperty("errors", out var errors) && errors.GetArrayLength() > 0, body.ToString());
        Assert.Contains("origin", errors[0].GetProperty("message").GetString());
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task GraphQL_ValidCall_Runs()
    {
        var query = JsonSerializer.Serialize(new
        {
            query = "query($f: JSON) { search(origin: \"SEA\", limit: 3, filters: $f) { success failure { type detail } } }",
            variables = new { f = new { stops = 0 } },
        });

        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/graphql", HttpBindingsTestApp.ApiKey, query);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(body.GetProperty("data").GetProperty("search").GetProperty("success").GetBoolean(), body.ToString());
        Assert.Equal(new[] { "search" }, _app.HandlerRuns);
    }
}
