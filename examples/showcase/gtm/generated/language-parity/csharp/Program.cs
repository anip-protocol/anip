using Anip.AspNetCore;
using Anip.GraphQL.AspNetCore;
using Anip.Mcp.AspNetCore;
using Anip.Rest.AspNetCore;
using Anip.Service;
using System.Text.Json;
using GTMOperatorContract20260512235040;

var builder = WebApplication.CreateBuilder(args);
var bindUrl = Environment.GetEnvironmentVariable("ASPNETCORE_URLS")
    ?? Environment.GetEnvironmentVariable("ANIP_HTTP_URL")
    ?? builder.Configuration["Urls"]
    ?? "http://0.0.0.0:4100";
builder.WebHost.UseUrls(bindUrl);

var apiKeys = ApiKeys();
var serviceId = Environment.GetEnvironmentVariable("ANIP_SERVICE_ID") ?? "GTM Operator Contract 20260512235040";
var serviceFilter = Environment.GetEnvironmentVariable("ANIP_SERVICE_FILTER") ?? serviceId;

var service = new AnipService(new ServiceConfig
{
    ServiceId = serviceId,
    Capabilities = GeneratedCapabilities.CreateAll(BackendAdapter.Default, serviceFilter),
    Storage = Environment.GetEnvironmentVariable("ANIP_STORAGE") ?? ":memory:",
    Trust = Environment.GetEnvironmentVariable("ANIP_TRUST_LEVEL") ?? "signed",
    KeyPath = Environment.GetEnvironmentVariable("ANIP_KEY_PATH") ?? "./anip-keys",
    Authenticate = bearer => apiKeys.TryGetValue(bearer, out var principal) ? principal : null,
});

builder.Services.AddAnip(service);
builder.Services.AddAnipMcp(service);
builder.Services.AddControllers()
    .AddApplicationPart(typeof(AnipRestController).Assembly)
    .AddApplicationPart(typeof(AnipGraphQLController).Assembly);

var app = builder.Build();
app.MapControllers();
app.MapAnipMcp();
app.Run();

static Dictionary<string, string> ApiKeys()
{
    var raw = Environment.GetEnvironmentVariable("ANIP_API_KEYS_JSON");
    if (string.IsNullOrWhiteSpace(raw))
    {
        return new Dictionary<string, string>
        {
            ["demo-human-key"] = "human:generated",
            ["demo-agent-key"] = "agent:generated-service",
        };
    }
    try
    {
        var decoded = JsonSerializer.Deserialize<Dictionary<string, object?>>(raw) ?? [];
        var result = new Dictionary<string, string>();
        foreach (var entry in decoded)
        {
            if (!string.IsNullOrWhiteSpace(entry.Key) && entry.Value is not null)
            {
                result[entry.Key] = entry.Value.ToString() ?? string.Empty;
            }
        }
        return result.Count == 0 ? new Dictionary<string, string> { ["demo-agent-key"] = "agent:generated-service" } : result;
    }
    catch
    {
        return new Dictionary<string, string> { ["demo-agent-key"] = "agent:generated-service" };
    }
}
