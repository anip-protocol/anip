using System.Text.Json;

using Anip.Core;
using Anip.Mcp;
using Anip.Service;

using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;

using ModelContextProtocol.Protocol;
using ModelContextProtocol.Server;

namespace Anip.Mcp.AspNetCore;

/// <summary>
/// Extension methods for wiring ANIP capabilities as MCP tools
/// over Streamable HTTP transport.
/// </summary>
public static class AnipMcpExtensions
{
    /// <summary>
    /// Registers MCP server with ANIP capabilities as tools.
    /// Each ANIP capability becomes an MCP tool that extracts auth from
    /// the HTTP Authorization header and invokes via the ANIP service.
    /// </summary>
    public static IServiceCollection AddAnipMcp(
        this IServiceCollection services,
        AnipService anipService,
        bool enrichDescriptions = true)
    {
        services.AddHttpContextAccessor();

        var tools = BuildTools(anipService, enrichDescriptions);

        services.AddMcpServer(options =>
        {
            options.ServerInfo = new Implementation
            {
                Name = "anip-mcp",
                Version = "0.11.0",
            };
        })
        .WithHttpTransport()
        .WithTools(tools);

        return services;
    }

    /// <summary>
    /// Maps the MCP Streamable HTTP endpoint at the specified route pattern.
    /// Defaults to "/mcp".
    /// </summary>
    public static IEndpointConventionBuilder MapAnipMcp(
        this IEndpointRouteBuilder endpoints,
        string pattern = "/mcp")
    {
        return endpoints.MapMcp(pattern);
    }

    /// <summary>
    /// Builds MCP tool instances for all ANIP capabilities.
    /// </summary>
    internal static List<McpServerTool> BuildTools(
        AnipService service, bool enrichDescriptions)
    {
        var manifest = service.GetManifest();
        var tools = new List<McpServerTool>();

        foreach (var (name, decl) in manifest.Capabilities)
        {
            var tool = CreateTool(name, decl, service, enrichDescriptions);
            tools.Add(tool);
        }

        return tools;
    }

    private static McpServerTool CreateTool(
        string capName,
        CapabilityDeclaration decl,
        AnipService service,
        bool enrichDescriptions)
    {
        var toolSpec = McpToolTranslator.BuildTool(capName, decl, enrichDescriptions);
        var inputSchema = BuildJsonElement(
            (Dictionary<string, object?>)toolSpec["inputSchema"]!);

        var readOnly = decl.SideEffect is { Type: "read" };
        var destructive = decl.SideEffect is { Type: "irreversible" };

        var protocolTool = new Tool
        {
            Name = capName,
            Description = (string?)toolSpec["description"],
            InputSchema = inputSchema,
            Annotations = new ToolAnnotations
            {
                ReadOnlyHint = readOnly,
                DestructiveHint = destructive,
            },
        };

        return new AnipMcpTool(protocolTool, capName, service);
    }

    private static JsonElement BuildJsonElement(Dictionary<string, object?> dict)
    {
        var json = JsonSerializer.Serialize(dict);
        return JsonDocument.Parse(json).RootElement.Clone();
    }
}

/// <summary>
/// Custom MCP tool implementation that dispatches to an ANIP capability.
/// Extracts the Authorization header from the HTTP context for per-request auth.
/// </summary>
internal sealed class AnipMcpTool : McpServerTool
{
    private readonly Tool _protocolTool;
    private readonly string _capabilityName;
    private readonly AnipService _service;

    public AnipMcpTool(Tool protocolTool, string capabilityName, AnipService service)
    {
        _protocolTool = protocolTool;
        _capabilityName = capabilityName;
        _service = service;
    }

    public override Tool ProtocolTool => _protocolTool;

    public override IReadOnlyList<object> Metadata => [];

    public override ValueTask<CallToolResult> InvokeAsync(
        RequestContext<CallToolRequestParams> request,
        CancellationToken cancellationToken = default)
    {
        // Extract arguments from the MCP request.
        var args = new Dictionary<string, object?>();
        if (request.Params?.Arguments != null)
        {
            foreach (var (key, value) in request.Params.Arguments)
            {
                args[key] = DeserializeJsonElement(value);
            }
        }

        // Extract the Authorization header from the HTTP context.
        // The SDK flows the HTTP context via IHttpContextAccessor when using
        // Streamable HTTP transport with ExecutionContext propagation.
        var httpContextAccessor = request.Server.Services?.GetService<IHttpContextAccessor>();
        var authHeader = httpContextAccessor?.HttpContext?.Request.Headers.Authorization
            .FirstOrDefault();
        var bearer = ExtractBearer(authHeader);

        if (string.IsNullOrEmpty(bearer))
        {
            return ValueTask.FromResult(new CallToolResult
            {
                Content = [new TextContentBlock
                {
                    Text = "FAILED: authentication_required\nDetail: No Authorization header provided\nRetryable: no",
                }],
                IsError = true,
            });
        }

        // Resolve auth: JWT-first, API-key fallback.
        DelegationToken token;
        try
        {
            token = McpAuthBridge.ResolveAuth(bearer, _service, _capabilityName);
        }
        catch (AnipError e)
        {
            return ValueTask.FromResult(new CallToolResult
            {
                Content = [new TextContentBlock
                {
                    Text = $"FAILED: {e.ErrorType}\nDetail: {e.Detail}\nRetryable: no",
                }],
                IsError = true,
            });
        }
        catch (Exception e)
        {
            return ValueTask.FromResult(new CallToolResult
            {
                Content = [new TextContentBlock
                {
                    Text = $"FAILED: authentication_failed\nDetail: {e.Message}\nRetryable: no",
                }],
                IsError = true,
            });
        }

        // Invoke with resolved token.
        var result = _service.Invoke(_capabilityName, token, args, new InvokeOpts());
        var mcpResult = McpToolTranslator.TranslateResponse(result);

        return ValueTask.FromResult(new CallToolResult
        {
            Content = [new TextContentBlock { Text = mcpResult.Text }],
            IsError = mcpResult.IsError ? true : null,
        });
    }

    private static string? ExtractBearer(string? authHeader)
    {
        if (authHeader != null && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authHeader["Bearer ".Length..].Trim();
        }

        return null;
    }

    private static object? DeserializeJsonElement(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Number when element.TryGetInt64(out var l) => l,
            JsonValueKind.Number => element.GetDouble(),
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            _ => JsonSerializer.Deserialize<object>(element),
        };
    }
}
