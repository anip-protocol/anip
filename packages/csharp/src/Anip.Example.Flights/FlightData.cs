namespace Anip.Example.Flights;

/// <summary>
/// In-memory flight inventory used by both capabilities.
/// </summary>
internal static class FlightData
{
    private record Flight(
        string FlightNumber, string Origin, string Destination, string Date,
        string DepartureTime, string ArrivalTime, double Price,
        string Currency, int Stops);

    private static readonly List<Flight> Inventory = new()
    {
        new("AA100", "SEA", "SFO", "2026-03-10", "08:00", "10:15", 420.00, "USD", 0),
        new("UA205", "SEA", "SFO", "2026-03-10", "11:30", "13:45", 380.00, "USD", 0),
        new("DL310", "SEA", "SFO", "2026-03-10", "14:00", "18:30", 280.00, "USD", 1),
        new("AA101", "SEA", "SFO", "2026-03-11", "08:00", "10:15", 310.00, "USD", 0),
        new("UA450", "SEA", "LAX", "2026-03-10", "09:00", "11:30", 350.00, "USD", 0),
        new("DL520", "SFO", "JFK", "2026-03-12", "06:00", "14:30", 580.00, "USD", 0),
    };

    public static List<Dictionary<string, object?>> SearchFlights(string origin, string destination, string date)
    {
        var results = new List<Dictionary<string, object?>>();
        foreach (var f in Inventory)
        {
            if (f.Origin == origin && f.Destination == destination && f.Date == date)
            {
                results.Add(new Dictionary<string, object?>
                {
                    ["flight_number"] = f.FlightNumber,
                    ["departure_time"] = f.DepartureTime,
                    ["arrival_time"] = f.ArrivalTime,
                    ["price"] = f.Price,
                    ["currency"] = f.Currency,
                    ["stops"] = f.Stops,
                });
            }
        }
        return results;
    }

    public static Dictionary<string, object?>? FindFlight(string flightNumber, string date)
    {
        foreach (var f in Inventory)
        {
            if (f.FlightNumber == flightNumber && f.Date == date)
            {
                return new Dictionary<string, object?>
                {
                    ["flight_number"] = f.FlightNumber,
                    ["departure_time"] = f.DepartureTime,
                    ["arrival_time"] = f.ArrivalTime,
                    ["price"] = f.Price,
                    ["currency"] = f.Currency,
                    ["stops"] = f.Stops,
                };
            }
        }
        return null;
    }
}
