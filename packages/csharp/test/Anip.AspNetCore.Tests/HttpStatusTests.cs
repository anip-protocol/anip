using System.Net;
using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.AspNetCore.Tests;

/// <summary>
/// SPEC.md §6.3 "HTTP Status Codes": every HTTP binding answers a failure with
/// the status the table gives its type, and a request body that is not JSON
/// is <c>invalid_parameters</c> (400) once the credential has been checked.
/// </summary>
public class HttpStatusTests : IAsyncLifetime
{
    private HttpBindingsTestApp _app = null!;

    public async Task InitializeAsync() => _app = await HttpBindingsTestApp.StartAsync(new[]
    {
        // Fails with whatever failure type the caller names.
        new CapabilityDef(
            new CapabilityDeclaration
            {
                Name = "fail",
                Description = "Fails with the named type",
                ContractVersion = "1.0",
                SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                MinimumScope = new List<string> { "data" },
                Inputs = new List<CapabilityInput> { new() { Name = "type", Type = "string" } },
            },
            (ctx, parameters) => throw new AnipError(parameters["type"]!.ToString()!, "as asked")
                .WithResolution("contact_service_owner")),
        // Asks for approval but declares no grant_policy: the ApprovalRequest cannot be persisted.
        new CapabilityDef(
            new CapabilityDeclaration
            {
                Name = "unpersistable",
                Description = "Asks for approval without a grant policy",
                ContractVersion = "1.0",
                SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                MinimumScope = new List<string> { "data" },
            },
            (ctx, parameters) => throw new AnipError(Constants.FailureApprovalRequired, "approval needed")
                .WithResolution("request_approval")),
    });

    public async Task DisposeAsync() => await _app.DisposeAsync();

    public static IEnumerable<object[]> Table() => new (string Type, int Status)[]
    {
        ("invalid_parameters", 400), ("streaming_not_supported", 400), ("grant_not_found", 400),
        ("grant_capability_mismatch", 400), ("grant_scope_mismatch", 400), ("grant_param_drift", 400),
        ("grant_session_invalid", 400), ("grant_type_not_allowed_by_policy", 400),
        ("authentication_required", 401), ("invalid_token", 401), ("token_expired", 401),
        ("token_not_registered", 401),
        ("scope_insufficient", 403), ("insufficient_authority", 403), ("purpose_mismatch", 403),
        ("scope_escalation", 403), ("constraint_escalation", 403), ("broken_delegation_chain", 403),
        ("delegation_depth_exceeded", 403), ("parent_token_expired", 403), ("budget_exceeded", 403),
        ("budget_currency_mismatch", 403), ("budget_not_enforceable", 403), ("binding_missing", 403),
        ("binding_stale", 403), ("control_requirement_unsatisfied", 403), ("approver_not_authorized", 403),
        ("grant_requester_mismatch", 403),
        ("unknown_capability", 404), ("not_found", 404), ("approval_request_not_found", 404),
        ("grant_consumed", 409), ("grant_expired", 409), ("approval_request_already_decided", 409),
        ("approval_request_expired", 409), ("concurrent_lock", 409), ("concurrent_request_rejected", 409),
        ("unavailable", 409),
        ("internal_error", 500),
        ("service_unavailable", 503),
        ("a_type_a_handler_defines", 400),
    }.Select(row => new object[] { row.Type, row.Status });

    [Theory]
    [MemberData(nameof(Table))]
    public async Task ProtocolBinding_AnswersTheTableStatus(string failureType, int status)
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/fail", _app.Jwt("fail"),
            JsonSerializer.Serialize(new { parameters = new { type = failureType } }));

        Assert.Equal(failureType, body.GetProperty("failure").GetProperty("type").GetString());
        Assert.Equal(status, (int)response.StatusCode);
    }

    [Theory]
    [MemberData(nameof(Table))]
    public async Task RestBinding_AnswersTheTableStatus(string failureType, int status)
    {
        var (response, body) = await _app.SendAsync(
            HttpMethod.Get, $"/api/fail?type={failureType}", HttpBindingsTestApp.ApiKey);

        Assert.Equal(failureType, body.GetProperty("failure").GetProperty("type").GetString());
        Assert.Equal(status, (int)response.StatusCode);
    }

    // --- a request body that is not JSON ---

    private static void AssertInvalidBody(HttpResponseMessage response, JsonElement body)
    {
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.False(body.GetProperty("success").GetBoolean());
        var failure = body.GetProperty("failure");
        Assert.Equal(Constants.FailureInvalidParameters, failure.GetProperty("type").GetString());
        Assert.False(string.IsNullOrEmpty(failure.GetProperty("detail").GetString()));
        Assert.False(failure.GetProperty("retry").GetBoolean());
        Assert.Equal("retry_now", failure.GetProperty("resolution").GetProperty("action").GetString());
        Assert.Equal("retry_now", failure.GetProperty("resolution").GetProperty("recovery_class").GetString());
    }

    [Theory]
    [InlineData("""{"parameters": """)]
    [InlineData("not json")]
    [InlineData("")]
    [InlineData("[1, 2]")]
    [InlineData("\"text\"")]
    [InlineData("42")]
    public async Task Invoke_BodyThatIsNotAJsonObject_Is400InvalidParameters(string content)
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"), content);

        AssertInvalidBody(response, body);
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Invoke_BodyThatIsNotJson_WithoutACredential_Is401()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", null, """{"parameters": """);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(Constants.FailureAuthRequired, body.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task Invoke_BodyThatIsNotJson_WithAnInvalidToken_Is401()
    {
        var (response, body) = await _app.SendAsync(
            HttpMethod.Post, "/anip/invoke/book", "not-a-token", """{"parameters": """);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(Constants.FailureInvalidToken, body.GetProperty("failure").GetProperty("type").GetString());
    }

    [Theory]
    [InlineData("""{"scope": """)]
    [InlineData("not json")]
    [InlineData("")]
    [InlineData("[1, 2]")]
    [InlineData("null")]
    [InlineData("""{"scope": "not-a-list", "capability": "book"}""")]
    public async Task Tokens_BodyThatIsNotATokenRequest_Is400InvalidParameters(string content)
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/tokens", HttpBindingsTestApp.ApiKey, content);

        AssertInvalidBody(response, body);
    }

    [Fact]
    public async Task Tokens_BodyThatIsNotJson_WithoutACredential_Is401()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/tokens", null, """{"scope": """);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(Constants.FailureAuthRequired, body.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task Tokens_BodyThatIsNotJson_WithAnUnknownCredential_Is401()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/tokens", "unknown-key", """{"scope": """);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        // SPEC.md §6.3 Token Issuance: an unrecognised credential is authentication_required.
        Assert.Equal(Constants.FailureAuthRequired, body.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task Tokens_ValidRequest_StillIssues()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/tokens", HttpBindingsTestApp.ApiKey,
            """{"subject": "agent@test.com", "scope": ["data"], "capability": "book", "ttl_hours": 1}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(body.GetProperty("issued").GetBoolean());
    }

    [Theory]
    [InlineData("""{"flight_number": """)]
    [InlineData("not json")]
    [InlineData("[1, 2]")]
    public async Task Rest_BodyThatIsNotAJsonObject_Is400InvalidParameters(string content)
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/api/book", HttpBindingsTestApp.ApiKey, content);

        AssertInvalidBody(response, body);
        Assert.Empty(_app.HandlerRuns);
    }

    [Fact]
    public async Task Rest_BodyThatIsNotJson_WithoutACredential_Is401()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/api/book", null, """{"flight_number": """);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(Constants.FailureAuthRequired, body.GetProperty("failure").GetProperty("type").GetString());
    }

    // --- the ApprovalRequest cannot be persisted (SPEC.md §4.7) ---

    [Fact]
    public async Task ProtocolBinding_ApprovalRequestNotPersisted_Is503ServiceUnavailable()
    {
        var (response, body) = await _app.SendAsync(
            HttpMethod.Post, "/anip/invoke/unpersistable", _app.Jwt("unpersistable"), """{"parameters": {}}""");

        Assert.Equal("service_unavailable", body.GetProperty("failure").GetProperty("type").GetString());
        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        Assert.Equal("wait_and_retry", body.GetProperty("failure").GetProperty("resolution").GetProperty("action").GetString());
        Assert.False(body.GetProperty("failure").TryGetProperty("approval_required", out _));
    }

    [Fact]
    public async Task RestBinding_ApprovalRequestNotPersisted_Is503ServiceUnavailable()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Get, "/api/unpersistable", HttpBindingsTestApp.ApiKey);

        Assert.Equal("service_unavailable", body.GetProperty("failure").GetProperty("type").GetString());
        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
    }

    // --- failures the bindings raise themselves ---

    [Fact]
    public async Task StreamingRequestedFromAUnaryCapability_IsAJson400()
    {
        var (response, body) = await _app.SendAsync(HttpMethod.Post, "/anip/invoke/book", _app.Jwt("book"),
            """{"parameters": {"flight_number": "AA100"}, "stream": true}""");

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("application/json", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal(Constants.FailureStreamingNotSupported, body.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task Rest_UnknownCapability_Is404_AndWithoutACredential401()
    {
        var (unknown, unknownBody) = await _app.SendAsync(HttpMethod.Get, "/api/nope", HttpBindingsTestApp.ApiKey);
        var (anonymous, anonymousBody) = await _app.SendAsync(HttpMethod.Get, "/api/search?origin=SEA", null);
        var (badKey, badKeyBody) = await _app.SendAsync(HttpMethod.Get, "/api/search?origin=SEA", "unknown-key");

        Assert.Equal(HttpStatusCode.NotFound, unknown.StatusCode);
        Assert.Equal(Constants.FailureUnknownCapability, unknownBody.GetProperty("failure").GetProperty("type").GetString());
        Assert.Equal(HttpStatusCode.Unauthorized, anonymous.StatusCode);
        Assert.Equal(Constants.FailureAuthRequired, anonymousBody.GetProperty("failure").GetProperty("type").GetString());
        Assert.Equal(Constants.FailureStatusCode(badKeyBody.GetProperty("failure").GetProperty("type").GetString()),
            (int)badKey.StatusCode);
    }
}
