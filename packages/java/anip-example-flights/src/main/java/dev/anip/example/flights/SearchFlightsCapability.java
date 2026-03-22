package dev.anip.example.flights;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.Constants;
import dev.anip.core.SideEffect;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Search available flights by origin, destination, and date.
 */
public final class SearchFlightsCapability {

    private SearchFlightsCapability() {}

    public static CapabilityDef create() {
        CapabilityDeclaration decl = new CapabilityDeclaration(
                "search_flights",
                "Search available flights by origin, destination, and date",
                "1.0",
                List.of(
                        new CapabilityInput("origin", "airport_code", true, "Departure airport"),
                        new CapabilityInput("destination", "airport_code", true, "Arrival airport"),
                        new CapabilityInput("date", "date", true, "Travel date (YYYY-MM-DD)")
                ),
                new CapabilityOutput("flight_list",
                        List.of("flight_number", "departure_time", "arrival_time", "price", "stops")),
                new SideEffect("read", "not_applicable"),
                List.of("travel.search"),
                null, // no cost
                null, // no requires
                List.of("unary")
        );

        return new CapabilityDef(decl, SearchFlightsCapability::handle);
    }

    private static Map<String, Object> handle(InvocationContext ctx, Map<String, Object> params) {
        String origin = (String) params.get("origin");
        String destination = (String) params.get("destination");
        String date = (String) params.get("date");

        if (origin == null || origin.isEmpty()
                || destination == null || destination.isEmpty()
                || date == null || date.isEmpty()) {
            throw new ANIPError(Constants.FAILURE_INVALID_PARAMETERS,
                    "origin, destination, and date are all required");
        }

        List<Map<String, Object>> flights = FlightData.searchFlights(origin, destination, date);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("flights", flights);
        result.put("count", flights.size());
        return result;
    }
}
