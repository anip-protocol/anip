using Anip.AspNetCore;
using Anip.Example.Flights;
using Anip.Mcp.AspNetCore;
using Anip.Service;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls("http://0.0.0.0:8080");

var apiKeys = new Dictionary<string, string>
{
    ["demo-human-key"] = "human:samir@example.com",
    ["demo-agent-key"] = "agent:demo-agent",
};

var service = new AnipService(new ServiceConfig
{
    ServiceId = Environment.GetEnvironmentVariable("ANIP_SERVICE_ID") ?? "anip-flight-service",
    Capabilities = new List<CapabilityDef>
    {
        SearchFlightsCapability.Create(),
        BookFlightCapability.Create(),
    },
    Storage = Environment.GetEnvironmentVariable("ANIP_STORAGE") ?? ":memory:",
    Trust = Environment.GetEnvironmentVariable("ANIP_TRUST_LEVEL") ?? "signed",
    KeyPath = Environment.GetEnvironmentVariable("ANIP_KEY_PATH") ?? "./anip-keys",
    Authenticate = bearer => apiKeys.TryGetValue(bearer, out var principal) ? principal : null,
});

builder.Services.AddAnip(service);
builder.Services.AddAnipMcp(service);

var app = builder.Build();
app.MapControllers();
app.MapAnipMcp();
app.Run();
