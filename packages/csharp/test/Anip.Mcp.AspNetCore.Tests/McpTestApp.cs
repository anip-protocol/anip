using System.Collections.Concurrent;

using Anip.Core;
using Anip.Mcp.AspNetCore;
using Anip.Service;

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace Anip.Mcp.AspNetCore.Tests;

/// <summary>One run of a capability handler, as the handler saw it.</summary>
internal sealed record HandlerCall(
    string Capability,
    Dictionary<string, object?> Parameters,
    string Subject,
    string RootPrincipal,
    List<string> Scopes,
    string? ApprovalGrant);

/// <summary>
/// An ANIP service mounted through <c>AddAnipMcp</c> / <c>MapAnipMcp</c> on an
/// in-memory ASP.NET Core server (<c>TestServer</c>). Tests send it HTTP
/// requests, which run through the full ASP.NET Core and MCP SDK pipeline but
/// not through sockets or Kestrel, and read <see cref="Calls"/> to learn
/// whether a handler ran.
/// </summary>
internal sealed class McpTestApp : IAsyncDisposable
{
    public const string ApiKey = "valid-api-key";
    public const string ApiKeyPrincipal = "human:owner@test.com";

    private readonly IHost _host;

    public AnipService Service { get; }

    public HttpClient Http { get; }

    /// <summary>Every handler run so far, in order.</summary>
    public ConcurrentQueue<HandlerCall> Calls { get; }

    /// <summary>Exceptions that escaped the request pipeline and were answered with a 500.</summary>
    public ConcurrentQueue<Exception> UnhandledExceptions { get; } = new();

    private McpTestApp(AnipService service, IHost host, ConcurrentQueue<HandlerCall> calls)
    {
        Service = service;
        _host = host;
        Calls = calls;
        Http = host.GetTestClient();
    }

    public static async Task<McpTestApp> StartAsync()
    {
        var calls = new ConcurrentQueue<HandlerCall>();
        McpTestApp? self = null;

        Dictionary<string, object?> Record(string capability, InvocationContext ctx, Dictionary<string, object?> parameters)
        {
            calls.Enqueue(new HandlerCall(
                capability,
                new Dictionary<string, object?>(parameters),
                ctx.Subject,
                ctx.RootPrincipal,
                new List<string>(ctx.Scopes),
                ctx.ApprovalGrant));

            return new Dictionary<string, object?>
            {
                ["capability"] = capability,
                ["subject"] = ctx.Subject,
                ["echoed"] = parameters.TryGetValue("message", out var message) ? message : null,
            };
        }

        var service = new AnipService(new ServiceConfig
        {
            ServiceId = "test-mcp-aspnetcore-svc",
            Storage = ":memory:",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "echo",
                        Description = "Echoes a message back",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                        MinimumScope = new List<string> { "data.read" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "message", Type = "string", Required = true, Description = "Text to echo" },
                            new() { Name = "count", Type = "integer", Required = false, Description = "Repeat count" },
                            new() { Name = "flag", Type = "boolean", Required = false, Description = "A switch" },
                        },
                    },
                    (ctx, parameters) => Record("echo", ctx, parameters)),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "delete_record",
                        Description = "Deletes a record for good",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "irreversible", RollbackWindow = "none" },
                        MinimumScope = new List<string> { "admin.write" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "id", Type = "string", Required = true, Description = "Record id" },
                        },
                    },
                    (ctx, parameters) => Record("delete_record", ctx, parameters)),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "explode",
                        Description = "Always throws",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
                        MinimumScope = new List<string> { "data.read" },
                    },
                    (ctx, parameters) =>
                    {
                        Record("explode", ctx, parameters);
                        throw new InvalidOperationException("secret-internal-detail");
                    }),
            },
            Authenticate = bearer => bearer == ApiKey ? ApiKeyPrincipal : null,
        });
        service.Start();

        var host = new HostBuilder()
            .ConfigureWebHost(webHost =>
            {
                webHost.UseTestServer();
                webHost.ConfigureServices(services =>
                {
                    services.AddRouting();
                    services.AddAnipMcp(service);
                });
                webHost.Configure(app =>
                {
                    // A real server answers 500 when a request handler throws.
                    // The in-memory test server would instead rethrow into the
                    // test's HttpClient call, so do what a real server does,
                    // and keep the exception so a test can say none is expected.
                    app.Use(async (context, next) =>
                    {
                        try
                        {
                            await next();
                        }
                        catch (Exception e) when (!context.Response.HasStarted)
                        {
                            self?.UnhandledExceptions.Enqueue(e);
                            context.Response.StatusCode = StatusCodes.Status500InternalServerError;
                        }
                    });
                    app.UseRouting();
                    app.UseEndpoints(endpoints => endpoints.MapAnipMcp());
                });
            })
            .Build();

        await host.StartAsync();

        self = new McpTestApp(service, host, calls);
        return self;
    }

    /// <summary>Issues a delegation token (a JWT) the way a caller obtains one.</summary>
    public string IssueJwt(string subject, string capability, params string[] scope)
    {
        return Service.IssueToken(ApiKeyPrincipal, new TokenRequest
        {
            Subject = subject,
            Scope = scope.ToList(),
            Capability = capability,
            TtlHours = 1,
        }).Token;
    }

    public async ValueTask DisposeAsync()
    {
        Http.Dispose();
        await _host.StopAsync();
        _host.Dispose();
        Service.Dispose();
    }
}
