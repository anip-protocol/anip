using System.Security.Cryptography;
using Anip.Core;
using Anip.Service;

namespace Anip.Example.Flights;

/// <summary>
/// Book a confirmed flight reservation.
/// </summary>
public static class BookFlightCapability
{
    /// <summary>Bookings for this many passengers or more need an approval grant (SPEC.md §4.7).</summary>
    public const int GroupBookingApprovalThreshold = 5;

    public static CapabilityDef Create()
    {
        var declaration = new CapabilityDeclaration
        {
            Name = "book_flight",
            Description = "Book a confirmed flight reservation",
            ContractVersion = "1.0",
            Inputs = new List<CapabilityInput>
            {
                new() { Name = "flight_number", Type = "string", Required = true, Description = "Flight to book" },
                new() { Name = "date", Type = "date", Required = true, Description = "Travel date (YYYY-MM-DD)" },
                new() { Name = "passengers", Type = "integer", Required = false, Default = 1, Description = $"Number of passengers. Bookings for {GroupBookingApprovalThreshold} or more require approval" },
                // Optional as an input: the binding requirement below is what demands it.
                new() { Name = "quote_id", Type = "object", Required = false, Description = "Priced quote from search_flights" },
            },
            Output = new CapabilityOutput
            {
                Type = "booking_confirmation",
                Fields = new List<string> { "booking_id", "flight_number", "departure_time", "total_cost" },
            },
            SideEffect = new SideEffect
            {
                Type = "irreversible",
                RollbackWindow = "none",
            },
            MinimumScope = new List<string> { "travel.book" },
            Cost = new Cost
            {
                Certainty = "estimated",
                Financial = new FinancialCost
                {
                    Currency = "USD",
                    RangeMin = 280,
                    RangeMax = 500,
                },
                DeterminedBy = "search_flights",
            },
            Requires = new List<CapabilityRequirement>
            {
                new()
                {
                    Capability = "search_flights",
                    Reason = "must select from available flights before booking",
                },
            },
            RequiresBinding = new List<BindingRequirement>
            {
                new()
                {
                    Type = "quote",
                    Field = "quote_id",
                    SourceCapability = "search_flights",
                    MaxAge = "PT15M",
                },
            },
            ControlRequirements = new List<ControlRequirement>(),
            RefreshVia = new List<string> { "search_flights" },
            VerifyVia = new List<string>(),
            ResponseModes = new List<string> { "unary" },
            // Cross-service hints (illustrative — this is a single-service showcase)
            CrossService = new CrossServiceHints
            {
                RefreshVia = new List<ServiceCapabilityRef>
                {
                    new() { Service = "travel-search", Capability = "search_flights" },
                },
            },
            // What an approver may issue for a group booking (SPEC.md §4.7).
            GrantPolicy = new GrantPolicy
            {
                AllowedGrantTypes = new List<string> { "one_time", "session_bound" },
                DefaultGrantType = "one_time",
                ExpiresInSeconds = 900,
                MaxUses = 2,
            },
        };

        return new CapabilityDef(declaration, Handle);
    }

    private static Dictionary<string, object?> Handle(InvocationContext ctx, Dictionary<string, object?> parameters)
    {
        var flightNumber = GetString(parameters, "flight_number");
        var date = GetString(parameters, "date");
        var passengers = GetInt(parameters, "passengers", 1);
        parameters.TryGetValue("quote_id", out var quoteId);

        if (string.IsNullOrEmpty(flightNumber) || string.IsNullOrEmpty(date))
        {
            throw new AnipError(Constants.FailureInvalidParameters,
                "flight_number and date must not be empty");
        }

        // Group bookings need an approver's grant. On the continuation invocation
        // the runtime has already validated and reserved the grant.
        if (passengers >= GroupBookingApprovalThreshold && string.IsNullOrWhiteSpace(ctx.ApprovalGrant))
        {
            throw new AnipError(Constants.FailureApprovalRequired,
                $"bookings for {GroupBookingApprovalThreshold} or more passengers require approval")
                .WithResolution("request_approval");
        }

        var flight = FlightData.FindFlight(flightNumber, date);
        if (flight == null)
        {
            throw new AnipError(Constants.FailureUnavailable,
                $"flight {flightNumber} on {date} not found");
        }

        var price = Convert.ToDouble(flight["price"]);
        var totalCost = price * passengers;
        var currency = (string)flight["currency"]!;

        // Generate booking ID.
        var bytes = new byte[4];
        RandomNumberGenerator.Fill(bytes);
        var bookingId = $"BK-{Convert.ToHexString(bytes)}";

        // Track actual cost.
        ctx.CostActual = new CostActual
        {
            Financial = new FinancialCost
            {
                Amount = totalCost,
                Currency = currency,
            },
        };

        return new Dictionary<string, object?>
        {
            ["booking_id"] = bookingId,
            ["flight_number"] = flight["flight_number"],
            ["departure_time"] = flight["departure_time"],
            ["total_cost"] = totalCost,
            ["currency"] = currency,
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

    /// <summary>
    /// Reads an integer input. An integral number is an integer however it is
    /// written (<c>5</c>, <c>5.0</c>, <c>5e0</c>): SPEC.md §6.3.
    /// </summary>
    private static int GetInt(Dictionary<string, object?> parameters, string key, int defaultValue)
    {
        if (!parameters.TryGetValue(key, out var value))
            return defaultValue;

        double? number = value switch
        {
            System.Text.Json.JsonElement { ValueKind: System.Text.Json.JsonValueKind.Number } el
                when el.TryGetDouble(out var parsed) => parsed,
            int i => i,
            long l => l,
            double d => d,
            float f => f,
            decimal m => (double)m,
            _ => null,
        };

        if (number is { } n && Math.Floor(n) == n && n >= int.MinValue && n <= int.MaxValue)
            return (int)n;

        return defaultValue;
    }
}
