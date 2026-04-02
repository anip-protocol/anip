using Anip.Core;
using Anip.Service;

namespace Anip.Example.Flights;

/// <summary>
/// Search available flights by origin, destination, and date.
/// </summary>
public static class SearchFlightsCapability
{
    public static CapabilityDef Create()
    {
        var declaration = new CapabilityDeclaration
        {
            Name = "search_flights",
            Description = "Search available flights by origin, destination, and date",
            ContractVersion = "1.0",
            Inputs = new List<CapabilityInput>
            {
                new() { Name = "origin", Type = "airport_code", Required = true, Description = "Departure airport" },
                new() { Name = "destination", Type = "airport_code", Required = true, Description = "Arrival airport" },
                new() { Name = "date", Type = "date", Required = true, Description = "Travel date (YYYY-MM-DD)" },
            },
            Output = new CapabilityOutput
            {
                Type = "flight_list",
                Fields = new List<string> { "flight_number", "departure_time", "arrival_time", "price", "stops", "quote_id" },
            },
            SideEffect = new SideEffect
            {
                Type = "read",
                RollbackWindow = "not_applicable",
            },
            MinimumScope = new List<string> { "travel.search" },
            ResponseModes = new List<string> { "unary" },
            RefreshVia = new List<string>(),
            VerifyVia = new List<string>(),
        };

        return new CapabilityDef(declaration, Handle);
    }

    private static Dictionary<string, object?> Handle(InvocationContext ctx, Dictionary<string, object?> parameters)
    {
        var origin = GetString(parameters, "origin");
        var destination = GetString(parameters, "destination");
        var date = GetString(parameters, "date");

        if (string.IsNullOrEmpty(origin) || string.IsNullOrEmpty(destination) || string.IsNullOrEmpty(date))
        {
            throw new AnipError(Constants.FailureInvalidParameters,
                "origin, destination, and date are all required");
        }

        var flights = FlightData.SearchFlights(origin, destination, date);
        var epoch = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

        foreach (var flight in flights)
        {
            var bytes = new byte[4];
            System.Security.Cryptography.RandomNumberGenerator.Fill(bytes);
            flight["quote_id"] = new Dictionary<string, object>
            {
                ["id"] = $"qt-{Convert.ToHexString(bytes).ToLowerInvariant()}",
                ["price"] = flight["price"]!,
                ["issued_at"] = epoch,
            };
        }

        return new Dictionary<string, object?>
        {
            ["flights"] = flights,
            ["count"] = flights.Count,
        };
    }

    private static string? GetString(Dictionary<string, object?> parameters, string key)
    {
        if (!parameters.TryGetValue(key, out var value))
            return null;

        if (value is System.Text.Json.JsonElement el &&
            el.ValueKind == System.Text.Json.JsonValueKind.String)
        {
            return el.GetString();
        }

        return value as string;
    }
}
