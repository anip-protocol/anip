using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Anip.AspNetCore;
using Anip.Core;
using Anip.Service;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace Anip.AspNetCore.Tests;

public class AnipControllerTests : IAsyncLifetime
{
    private IHost _host = null!;
    private HttpClient _client = null!;

    public async Task InitializeAsync()
    {
        var anipService = new AnipService(new ServiceConfig
        {
            ServiceId = "test-aspnetcore-svc",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
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
                if (bearer == "valid-api-key")
                    return "user@test.com";
                return null;
            },
        });

        _host = new HostBuilder()
            .ConfigureWebHost(webHost =>
            {
                webHost.UseTestServer();
                webHost.ConfigureServices(services =>
                {
                    services.AddAnip(anipService);
                });
                webHost.Configure(app =>
                {
                    app.UseRouting();
                    app.UseEndpoints(endpoints =>
                    {
                        endpoints.MapControllers();
                    });
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

    // --- Discovery ---

    [Fact]
    public async Task Discovery_Returns200WithProtocolVersion()
    {
        var response = await _client.GetAsync("/.well-known/anip");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        var discovery = json.GetProperty("anip_discovery");
        Assert.Equal("anip/0.13", discovery.GetProperty("protocol").GetString());
        Assert.Equal("anip-compliant", discovery.GetProperty("compliance").GetString());
        Assert.True(discovery.TryGetProperty("base_url", out _));
        Assert.True(discovery.TryGetProperty("capabilities", out _));
    }

    // --- JWKS ---

    [Fact]
    public async Task Jwks_ReturnsKeys()
    {
        var response = await _client.GetAsync("/.well-known/jwks.json");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.True(json.TryGetProperty("keys", out var keys));
        Assert.Equal(JsonValueKind.Array, keys.ValueKind);
        Assert.True(keys.GetArrayLength() > 0);
    }

    // --- Manifest ---

    [Fact]
    public async Task Manifest_HasSignatureHeader()
    {
        var response = await _client.GetAsync("/anip/manifest");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        Assert.True(response.Headers.Contains("X-ANIP-Signature"));
        var signature = response.Headers.GetValues("X-ANIP-Signature").First();
        Assert.False(string.IsNullOrEmpty(signature));

        var json = await ParseJson(response);
        Assert.Equal("anip/0.13", json.GetProperty("protocol").GetString());
        Assert.True(json.TryGetProperty("capabilities", out _));
    }

    // --- Token Issuance ---

    [Fact]
    public async Task TokenIssuance_WithValidApiKey_Returns200()
    {
        var body = JsonSerializer.Serialize(new
        {
            subject = "agent@test.com",
            scope = new[] { "data" },
            capability = "echo",
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "valid-api-key");

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.True(json.GetProperty("issued").GetBoolean());
        Assert.True(json.TryGetProperty("token_id", out _));
        Assert.True(json.TryGetProperty("token", out _));
    }

    [Fact]
    public async Task TokenIssuance_WithoutAuth_Returns401()
    {
        var body = JsonSerializer.Serialize(new
        {
            subject = "agent@test.com",
            scope = new[] { "data" },
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);

        var json = await ParseJson(response);
        Assert.False(json.GetProperty("success").GetBoolean());
        Assert.Equal("authentication_required",
            json.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task TokenIssuance_WithInvalidKey_Returns401()
    {
        var body = JsonSerializer.Serialize(new
        {
            subject = "agent@test.com",
            scope = new[] { "data" },
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "bad-key");

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);

        var json = await ParseJson(response);
        Assert.False(json.GetProperty("success").GetBoolean());
        Assert.Equal("invalid_token",
            json.GetProperty("failure").GetProperty("type").GetString());
    }

    // --- Invoke ---

    [Fact]
    public async Task Invoke_WithJwt_ReturnsSuccess()
    {
        var jwt = await ObtainJwt();

        var body = JsonSerializer.Serialize(new
        {
            parameters = new { message = "hello" },
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/invoke/echo")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt);

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.True(json.GetProperty("success").GetBoolean());
        Assert.True(json.TryGetProperty("invocation_id", out _));
    }

    [Fact]
    public async Task Invoke_WithoutAuth_Returns401()
    {
        var body = JsonSerializer.Serialize(new
        {
            parameters = new { message = "hello" },
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/invoke/echo")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);

        var json = await ParseJson(response);
        Assert.False(json.GetProperty("success").GetBoolean());
        Assert.Equal("authentication_required",
            json.GetProperty("failure").GetProperty("type").GetString());
    }

    [Fact]
    public async Task Invoke_WithInvalidJwt_Returns401()
    {
        var body = JsonSerializer.Serialize(new
        {
            parameters = new { message = "hello" },
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/invoke/echo")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "not-a-real-jwt");

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);

        var json = await ParseJson(response);
        Assert.False(json.GetProperty("success").GetBoolean());
    }

    [Fact]
    public async Task Invoke_UnknownCapability_Returns404()
    {
        var jwt = await ObtainJwt();

        var body = JsonSerializer.Serialize(new
        {
            parameters = new { },
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/invoke/nonexistent")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt);

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);

        var json = await ParseJson(response);
        Assert.False(json.GetProperty("success").GetBoolean());
        Assert.Equal("unknown_capability",
            json.GetProperty("failure").GetProperty("type").GetString());
    }

    // --- Permissions ---

    [Fact]
    public async Task Permissions_WithJwt_ReturnsAvailable()
    {
        var jwt = await ObtainJwt();

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/permissions")
        {
            Content = new StringContent("{}", Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt);

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.True(json.TryGetProperty("available", out var available));
        Assert.Equal(JsonValueKind.Array, available.ValueKind);
    }

    [Fact]
    public async Task Permissions_WithoutAuth_Returns401()
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/permissions")
        {
            Content = new StringContent("{}", Encoding.UTF8, "application/json"),
        };

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    // --- Audit ---

    [Fact]
    public async Task Audit_WithJwt_ReturnsEntries()
    {
        var jwt = await ObtainJwt();

        // Make an invocation first so there's audit data.
        var invokeReq = new HttpRequestMessage(HttpMethod.Post, "/anip/invoke/echo")
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new { parameters = new { message = "test" } }),
                Encoding.UTF8, "application/json"),
        };
        invokeReq.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt);
        await _client.SendAsync(invokeReq);

        // Query audit.
        var auditReq = new HttpRequestMessage(HttpMethod.Post, "/anip/audit")
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new { limit = 10 }),
                Encoding.UTF8, "application/json"),
        };
        auditReq.Headers.Authorization = new AuthenticationHeaderValue("Bearer", jwt);

        var response = await _client.SendAsync(auditReq);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.True(json.TryGetProperty("count", out var count));
        Assert.True(count.GetInt32() >= 0);
    }

    // --- Checkpoints ---

    [Fact]
    public async Task Checkpoints_Returns200WithArray()
    {
        var response = await _client.GetAsync("/anip/checkpoints");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.True(json.TryGetProperty("checkpoints", out var checkpoints));
        Assert.Equal(JsonValueKind.Array, checkpoints.ValueKind);
    }

    // --- Health ---

    [Fact]
    public async Task Health_ReturnsStatus()
    {
        var response = await _client.GetAsync("/-/health");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        Assert.Equal("healthy", json.GetProperty("status").GetString());
        Assert.True(json.TryGetProperty("storage", out _));
        Assert.True(json.TryGetProperty("version", out _));
    }

    // --- Helpers ---

    private async Task<string> ObtainJwt()
    {
        var body = JsonSerializer.Serialize(new
        {
            subject = "agent@test.com",
            scope = new[] { "data" },
            capability = "echo",
        });

        var request = new HttpRequestMessage(HttpMethod.Post, "/anip/tokens")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", "valid-api-key");

        var response = await _client.SendAsync(request);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var json = await ParseJson(response);
        return json.GetProperty("token").GetString()!;
    }

    private static async Task<JsonElement> ParseJson(HttpResponseMessage response)
    {
        var content = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<JsonElement>(content);
    }
}
