using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Anip.AspNetCore;
using Anip.Core;
using Anip.Server;
using Anip.Service;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace Anip.AspNetCore.Tests;

/// <summary>
/// v0.23 — POST /anip/approval_grants HTTP integration: validation order,
/// state-check-before-approver-auth, schema rejections, end-to-end continuation.
/// </summary>
public class V023ApprovalGrantsEndpointTests : IAsyncLifetime
{
    private IHost _host = null!;
    private HttpClient _client = null!;
    private AnipService _service = null!;

    public async Task InitializeAsync()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "svc-v023",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "send_notice",
                        Description = "approval-required cap",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "write" },
                        MinimumScope = new List<string> { "data.write" },
                        GrantPolicy = new GrantPolicy
                        {
                            AllowedGrantTypes = new() { "one_time", "session_bound" },
                            DefaultGrantType = "one_time",
                            ExpiresInSeconds = 600,
                            MaxUses = 3,
                        },
                    },
                    (ctx, p) => new Dictionary<string, object?> { ["sent"] = true }),
            },
            Authenticate = bearer => bearer == "valid-api-key" ? "boss@test.com" : null,
        });

        _host = new HostBuilder()
            .ConfigureWebHost(webHost =>
            {
                webHost.UseTestServer();
                webHost.ConfigureServices(s => s.AddAnip(_service));
                webHost.Configure(app =>
                {
                    app.UseRouting();
                    app.UseEndpoints(e => e.MapControllers());
                });
            })
            .Build();
        await _host.StartAsync();
        _client = _host.GetTestClient();
    }

    public async Task DisposeAsync()
    {
        _client.Dispose();
        await _host.StopAsync();
        _host.Dispose();
    }

    private async Task<JsonElement> ParseJson(HttpResponseMessage r)
    {
        var s = await r.Content.ReadAsStringAsync();
        return JsonDocument.Parse(s).RootElement.Clone();
    }

    private async Task<string> IssueApproverJwt()
    {
        // Get a JWT with approver:* scope.
        var body = JsonSerializer.Serialize(new
        {
            subject = "approver@test.com",
            scope = new[] { "approver:*" },
            capability = "send_notice",
        });
        var req = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "valid-api-key");
        var resp = await _client.SendAsync(req);
        var json = await ParseJson(resp);
        return json.GetProperty("token").GetString()!;
    }

    private string SeedPendingRequest(string id)
    {
        var req = new ApprovalRequest
        {
            ApprovalRequestId = id,
            Capability = "send_notice",
            Scope = new List<string> { "data.write" },
            Requester = new Dictionary<string, object> { ["subject"] = "alice" },
            Preview = new Dictionary<string, object>(),
            PreviewDigest = V023.Sha256Digest(new Dictionary<string, object>()),
            RequestedParameters = new Dictionary<string, object> { ["msg"] = "hi" },
            RequestedParametersDigest = V023.Sha256Digest(new Dictionary<string, object> { ["msg"] = "hi" }),
            GrantPolicy = new GrantPolicy
            {
                AllowedGrantTypes = new() { "one_time", "session_bound" },
                DefaultGrantType = "one_time",
                ExpiresInSeconds = 600,
                MaxUses = 3,
            },
            Status = ApprovalRequest.StatusPending,
            CreatedAt = V023.UtcNowIso(),
            ExpiresAt = V023.UtcInIso(900),
        };
        _service.GetStorage().StoreApprovalRequest(req);
        return id;
    }

    private HttpRequestMessage Post(string path, object? body, string? bearer)
    {
        var req = new HttpRequestMessage(HttpMethod.Post, path);
        if (body != null)
        {
            var json = JsonSerializer.Serialize(body);
            req.Content = new StringContent(json, Encoding.UTF8, "application/json");
        }
        if (!string.IsNullOrEmpty(bearer))
        {
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearer);
        }
        return req;
    }

    [Fact]
    public async Task ApprovalGrants_Unauthorized_When_NoBearer()
    {
        var resp = await _client.SendAsync(Post("/anip/approval_grants", new { }, null));
        Assert.Equal(HttpStatusCode.Unauthorized, resp.StatusCode);
    }

    [Fact]
    public async Task ApprovalGrants_NotFound_When_RequestMissing()
    {
        var jwt = await IssueApproverJwt();
        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = "apr_nope",
            grant_type = "one_time",
        }, jwt));
        Assert.Equal(HttpStatusCode.NotFound, resp.StatusCode);
        var j = await ParseJson(resp);
        Assert.Equal(Constants.FailureApprovalRequestNotFound,
            j.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task ApprovalGrants_StateCheck_BeforeApproverAuth()
    {
        // Seed a request that is already approved, request from a token with no
        // approver scope. Spec demands 409 (state) BEFORE 403 (approver auth).
        var id = SeedPendingRequest("apr_state");
        // Decide it directly via SPI.
        _service.IssueApprovalGrant(id, ApprovalGrant.TypeOneTime,
            new Dictionary<string, object?> { ["subject"] = "boss" }, null, null, null);

        // Now use a JWT with NO approver scope.
        var bodyTok = JsonSerializer.Serialize(new
        {
            subject = "user@test.com",
            scope = new[] { "data" },
            capability = "send_notice",
        });
        var tokReq = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(bodyTok, Encoding.UTF8, "application/json"),
        };
        tokReq.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "valid-api-key");
        var tokRespJson = await ParseJson(await _client.SendAsync(tokReq));
        var nonApproverJwt = tokRespJson.GetProperty("token").GetString()!;

        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = id,
            grant_type = "one_time",
        }, nonApproverJwt));
        Assert.Equal(HttpStatusCode.Conflict, resp.StatusCode);
        var j = await ParseJson(resp);
        Assert.Equal(Constants.FailureApprovalRequestAlreadyDecided,
            j.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task ApprovalGrants_Forbidden_When_NoApproverScope()
    {
        var id = SeedPendingRequest("apr_unauth");
        var bodyTok = JsonSerializer.Serialize(new
        {
            subject = "user@test.com",
            scope = new[] { "data" }, // not approver
            capability = "send_notice",
        });
        var tokReq = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(bodyTok, Encoding.UTF8, "application/json"),
        };
        tokReq.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "valid-api-key");
        var tokJson = await ParseJson(await _client.SendAsync(tokReq));
        var nonApproverJwt = tokJson.GetProperty("token").GetString()!;

        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = id,
            grant_type = "one_time",
        }, nonApproverJwt));
        Assert.Equal(HttpStatusCode.Forbidden, resp.StatusCode);
        var j = await ParseJson(resp);
        Assert.Equal(Constants.FailureApproverNotAuthorized,
            j.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task ApprovalGrants_Schema_RejectsZeroMaxUses()
    {
        var id = SeedPendingRequest("apr_zero_max");
        var jwt = await IssueApproverJwt();
        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = id,
            grant_type = "one_time",
            max_uses = 0,
        }, jwt));
        Assert.Equal(HttpStatusCode.BadRequest, resp.StatusCode);
        var j = await ParseJson(resp);
        Assert.Equal(Constants.FailureInvalidParameters,
            j.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task ApprovalGrants_Schema_RejectsZeroExpiresIn()
    {
        var id = SeedPendingRequest("apr_zero_exp");
        var jwt = await IssueApproverJwt();
        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = id,
            grant_type = "one_time",
            expires_in_seconds = 0,
        }, jwt));
        Assert.Equal(HttpStatusCode.BadRequest, resp.StatusCode);
    }

    [Fact]
    public async Task ApprovalGrants_Schema_RejectsEmptySessionId()
    {
        var id = SeedPendingRequest("apr_empty_sid");
        var jwt = await IssueApproverJwt();
        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = id,
            grant_type = "session_bound",
            session_id = "",
        }, jwt));
        Assert.Equal(HttpStatusCode.BadRequest, resp.StatusCode);
    }

    [Fact]
    public async Task ApprovalGrants_HappyPath_ReturnsBareGrant()
    {
        var id = SeedPendingRequest("apr_happy_http");
        var jwt = await IssueApproverJwt();
        var resp = await _client.SendAsync(Post("/anip/approval_grants", new
        {
            approval_request_id = id,
            grant_type = "one_time",
        }, jwt));
        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
        var j = await ParseJson(resp);
        // Body IS the bare grant — no wrapper.
        Assert.Equal(id, j.GetProperty("approval_request_id").GetString());
        Assert.Equal("one_time", j.GetProperty("grant_type").GetString());
        Assert.False(string.IsNullOrEmpty(j.GetProperty("signature").GetString()));
    }

    [Fact]
    public async Task Discovery_Advertises_ApprovalGrants_Endpoint()
    {
        var resp = await _client.GetAsync("/.well-known/anip");
        Assert.Equal(HttpStatusCode.OK, resp.StatusCode);
        var j = await ParseJson(resp);
        var endpoints = j.GetProperty("anip_discovery").GetProperty("endpoints");
        Assert.Equal("/anip/approval_grants",
            endpoints.GetProperty("approval_grants").GetString());
    }

    [Fact]
    public async Task ApprovalGrants_MalformedJson_Returns400()
    {
        var jwt = await IssueApproverJwt();
        var req = new HttpRequestMessage(HttpMethod.Post, "/anip/approval_grants")
        {
            Content = new StringContent("{not-json", Encoding.UTF8, "application/json"),
        };
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt);
        var resp = await _client.SendAsync(req);
        Assert.Equal(HttpStatusCode.BadRequest, resp.StatusCode);
    }
}
