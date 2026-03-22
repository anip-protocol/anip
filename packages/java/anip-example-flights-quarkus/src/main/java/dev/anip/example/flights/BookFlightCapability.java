package dev.anip.example.flights;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.CapabilityRequirement;
import dev.anip.core.Constants;
import dev.anip.core.Cost;
import dev.anip.core.CostActual;
import dev.anip.core.SideEffect;
import dev.anip.service.CapabilityDef;
import dev.anip.service.InvocationContext;

import java.security.SecureRandom;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Book a confirmed flight reservation.
 */
public final class BookFlightCapability {

    private BookFlightCapability() {}

    private static final SecureRandom RANDOM = new SecureRandom();

    public static CapabilityDef create() {
        CapabilityDeclaration decl = new CapabilityDeclaration(
                "book_flight",
                "Book a confirmed flight reservation",
                "1.0",
                List.of(
                        new CapabilityInput("flight_number", "string", true, "Flight to book"),
                        new CapabilityInput("date", "date", true, "Travel date (YYYY-MM-DD)"),
                        new CapabilityInput("passengers", "integer", false, 1, "Number of passengers")
                ),
                new CapabilityOutput("booking_confirmation",
                        List.of("booking_id", "flight_number", "departure_time", "total_cost")),
                new SideEffect("irreversible", "none"),
                List.of("travel.book"),
                new Cost(
                        "estimated",
                        Map.of(
                                "currency", "USD",
                                "estimated_range", Map.of("min", 280, "max", 500)
                        ),
                        "search_flights",
                        null, null, null
                ),
                List.of(new CapabilityRequirement("search_flights",
                        "must select from available flights before booking")),
                List.of("unary")
        );

        return new CapabilityDef(decl, BookFlightCapability::handle);
    }

    private static Map<String, Object> handle(InvocationContext ctx, Map<String, Object> params) {
        String flightNumber = (String) params.get("flight_number");
        String date = (String) params.get("date");
        int passengers = 1;
        if (params.get("passengers") instanceof Number p) {
            passengers = p.intValue();
        }

        if (flightNumber == null || flightNumber.isEmpty()
                || date == null || date.isEmpty()) {
            throw new ANIPError(Constants.FAILURE_INVALID_PARAMETERS,
                    "flight_number and date are required");
        }

        Map<String, Object> flight = FlightData.findFlight(flightNumber, date);
        if (flight == null) {
            throw new ANIPError(Constants.FAILURE_UNAVAILABLE,
                    "flight " + flightNumber + " on " + date + " not found");
        }

        double price = ((Number) flight.get("price")).doubleValue();
        double totalCost = price * passengers;
        String currency = (String) flight.get("currency");

        // Generate booking ID.
        byte[] b = new byte[4];
        RANDOM.nextBytes(b);
        String bookingId = String.format("BK-%02X%02X%02X%02X", b[0], b[1], b[2], b[3]);

        // Track actual cost.
        ctx.setCostActual(new CostActual(
                Map.of("amount", totalCost, "currency", currency),
                null
        ));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("booking_id", bookingId);
        result.put("flight_number", flight.get("flight_number"));
        result.put("departure_time", flight.get("departure_time"));
        result.put("total_cost", totalCost);
        result.put("currency", currency);
        return result;
    }
}
