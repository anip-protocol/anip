using Anip.AspNetCore;
using Anip.Core;
using Anip.Service;

// Your business logic. Nothing here knows about ANIP.
List<Dictionary<string, object?>> DoSearch(string origin, string destination) =>
[
    new() { ["flight_number"] = "AA100", ["origin"] = origin, ["destination"] = destination, ["price"] = 420 },
    new() { ["flight_number"] = "DL310", ["origin"] = origin, ["destination"] = destination, ["price"] = 280 },
];

Dictionary<string, object?> DoBook(string flightNumber) =>
    new() { ["booking_id"] = "BK-0001", ["flight_number"] = flightNumber };

// A capability that only reads.
var searchFlights = new CapabilityDef(
    new CapabilityDeclaration
    {
        Name = "search_flights",
        Description = "Search available flights between two airports",
        ContractVersion = "1.0",
        Inputs =
        [
            new() { Name = "origin", Type = "string", Required = true, Description = "Departure airport" },
            new() { Name = "destination", Type = "string", Required = true, Description = "Arrival airport" },
        ],
        Output = new() { Type = "object", Fields = ["flights"] },
        SideEffect = new() { Type = "read", RollbackWindow = "not_applicable" },
        MinimumScope = ["travel.search"],
    },
    (ctx, p) => new() { ["flights"] = DoSearch($"{p["origin"]}", $"{p["destination"]}") });

// A capability that cannot be undone, and needs a different scope.
var bookFlight = new CapabilityDef(
    new CapabilityDeclaration
    {
        Name = "book_flight",
        Description = "Book a flight",
        ContractVersion = "1.0",
        Inputs =
        [
            new() { Name = "flight_number", Type = "string", Required = true, Description = "Flight to book" },
        ],
        Output = new() { Type = "object", Fields = ["booking_id", "flight_number"] },
        SideEffect = new() { Type = "irreversible", RollbackWindow = "none" },
        MinimumScope = ["travel.book"],
    },
    (ctx, p) => DoBook($"{p["flight_number"]}"));

var service = new AnipService(new ServiceConfig
{
    ServiceId = "quickstart-flights",
    Capabilities = [searchFlights, bookFlight],
    Storage = ":memory:",
    Trust = "signed",
    // Who is calling? Map your own API keys or sessions to a principal.
    Authenticate = bearer => bearer == "demo-key" ? "human:demo@example.com" : null,
});

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddAnip(service);

var app = builder.Build();
app.MapControllers();
app.Run($"http://localhost:{Environment.GetEnvironmentVariable("PORT") ?? "9100"}");
