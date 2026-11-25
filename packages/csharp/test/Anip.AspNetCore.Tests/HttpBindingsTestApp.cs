using System.Collections.Concurrent;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Anip.AspNetCore;
using Anip.Core;
using Anip.GraphQL.AspNetCore;
using Anip.Rest.AspNetCore;
using Anip.Service;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace Anip.AspNetCore.Tests;

/// <summary>
/// One service behind the three HTTP bindings (protocol endpoints, REST
/// adapter, GraphQL adapter), mounted the way the flight example mounts them.
/// </summary>
internal sealed class HttpBindingsTestApp : IAsyncDisposable
{
    public const string ApiKey = "valid-api-key";

    private readonly IHost _host;

    public AnipService Service { get; }
    public HttpClient Http { get; }
    public ConcurrentQueue<string> HandlerRuns { get; } = new();

    private HttpBindingsTestApp(AnipService service, IHost host, ConcurrentQueue<string> runs)
    {
        Service = service;
        _host = host;
        Http = host.GetTestClient();
        HandlerRuns = runs;
    }

    public static async Task<HttpBindingsTestApp> StartAsync(IEnumerable<CapabilityDef>? extra = null)
    {
        var runs = new ConcurrentQueue<string>();

        Dictionary<string, object?> Ran(string capability, Dictionary<string, object?> parameters)
        {
            runs.Enqueue(capability);
            return new Dictionary<string, object?> { ["capability"] = capability, ["count"] = parameters.Count };
        }

        var capabilities = new List<CapabilityDef>
        {
            new(
                new CapabilityDeclaration
                {
                    Name = "search",
                    Description = "Searches",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                    MinimumScope = new List<string> { "data" },
                    Inputs = new List<CapabilityInput>
                    {
                        new() { Name = "origin", Type = "string" },
                        new() { Name = "limit", Type = "integer", Required = false },
                        new() { Name = "filters", Type = "object", Required = false },
                    },
                },
                (ctx, parameters) => Ran("search", parameters)),
            new(
                new CapabilityDeclaration
                {
                    Name = "book",
                    Description = "Books",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "irreversible", RollbackWindow = "none" },
                    MinimumScope = new List<string> { "data" },
                    Inputs = new List<CapabilityInput>
                    {
                        new() { Name = "flight_number", Type = "string" },
                        new() { Name = "passengers", Type = "integer", Required = false, Default = 1 },
                    },
                },
                (ctx, parameters) => Ran("book", parameters)),
            new(
                new CapabilityDeclaration
                {
                    Name = "watch",
                    Description = "Streams",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                    MinimumScope = new List<string> { "data" },
                    ResponseModes = new List<string> { "unary", "streaming" },
                    Inputs = new List<CapabilityInput>
                    {
                        new() { Name = "topic", Type = "string" },
                    },
                },
                (ctx, parameters) => Ran("watch", parameters)),
        };
        if (extra != null) capabilities.AddRange(extra);

        var service = new AnipService(new ServiceConfig
        {
            ServiceId = "test-http-bindings-svc",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = capabilities,
            Authenticate = bearer => bearer == ApiKey ? "user@test.com" : null,
        });

        var host = new HostBuilder()
            .ConfigureWebHost(webHost =>
            {
                webHost.UseTestServer();
                webHost.ConfigureServices(services =>
                {
                    services.AddAnip(service);
                    services.AddControllers()
                        .AddApplicationPart(typeof(AnipRestController).Assembly)
                        .AddApplicationPart(typeof(AnipGraphQLController).Assembly);
                });
                webHost.Configure(app =>
                {
                    app.UseRouting();
                    app.UseEndpoints(endpoints => endpoints.MapControllers());
                });
            })
            .Build();

        await host.StartAsync();
        return new HttpBindingsTestApp(service, host, runs);
    }

    /// <summary>A delegation token for one capability, issued the way a caller obtains one.</summary>
    public string Jwt(string capability, params string[] scope) =>
        Service.IssueToken("user@test.com", new TokenRequest
        {
            Subject = "agent@test.com",
            Scope = scope.Length > 0 ? scope.ToList() : new List<string> { "data" },
            Capability = capability,
            PurposeParameters = new Dictionary<string, object>(),
            TtlHours = 1,
        }).Token;

    public async Task<(HttpResponseMessage Response, JsonElement Body)> SendAsync(
        HttpMethod method, string path, string? bearer, string? body = null,
        params (string Name, string Value)[] headers)
    {
        var request = new HttpRequestMessage(method, path);
        if (body != null)
        {
            request.Content = new StringContent(body, Encoding.UTF8, "application/json");
        }
        if (bearer != null)
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearer);
        }
        foreach (var (name, value) in headers)
        {
            request.Headers.TryAddWithoutValidation(name, value);
        }

        var response = await Http.SendAsync(request);
        var text = await response.Content.ReadAsStringAsync();
        JsonElement json = default;
        try
        {
            json = JsonSerializer.Deserialize<JsonElement>(text);
        }
        catch (JsonException)
        {
            // Not JSON (an SSE stream, an empty body): the caller looks at the response.
        }
        return (response, json);
    }

    public async Task<JsonElement> AuditEntryAsync(string bearer, string invocationId)
    {
        var (response, body) = await SendAsync(HttpMethod.Post, $"/anip/audit?invocation_id={invocationId}", bearer, "{}");
        Assert.Equal(System.Net.HttpStatusCode.OK, response.StatusCode);
        return Assert.Single(body.GetProperty("entries").EnumerateArray().ToList());
    }

    public async ValueTask DisposeAsync()
    {
        Http.Dispose();
        await _host.StopAsync();
        _host.Dispose();
    }
}
