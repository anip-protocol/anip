package dev.anip.example.flights;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * In-memory flight inventory used by both capabilities.
 */
final class FlightData {

    private FlightData() {}

    private record Flight(String flightNumber, String origin, String destination, String date,
                           String departureTime, String arrivalTime, double price,
                           String currency, int stops) {}

    private static final List<Flight> INVENTORY = List.of(
            new Flight("AA100", "SEA", "SFO", "2026-03-10", "08:00", "10:15", 420.00, "USD", 0),
            new Flight("UA205", "SEA", "SFO", "2026-03-10", "11:30", "13:45", 380.00, "USD", 0),
            new Flight("DL310", "SEA", "SFO", "2026-03-10", "14:00", "18:30", 280.00, "USD", 1),
            new Flight("AA101", "SEA", "SFO", "2026-03-11", "08:00", "10:15", 310.00, "USD", 0),
            new Flight("UA450", "SEA", "LAX", "2026-03-10", "09:00", "11:30", 350.00, "USD", 0),
            new Flight("DL520", "SFO", "JFK", "2026-03-12", "06:00", "14:30", 580.00, "USD", 0)
    );

    static List<Map<String, Object>> searchFlights(String origin, String destination, String date) {
        List<Map<String, Object>> results = new ArrayList<>();
        for (Flight f : INVENTORY) {
            if (f.origin().equals(origin)
                    && f.destination().equals(destination)
                    && f.date().equals(date)) {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("flight_number", f.flightNumber());
                m.put("departure_time", f.departureTime());
                m.put("arrival_time", f.arrivalTime());
                m.put("price", f.price());
                m.put("currency", f.currency());
                m.put("stops", f.stops());
                results.add(m);
            }
        }
        return results;
    }

    static Map<String, Object> findFlight(String flightNumber, String date) {
        for (Flight f : INVENTORY) {
            if (f.flightNumber().equals(flightNumber) && f.date().equals(date)) {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("flight_number", f.flightNumber());
                m.put("departure_time", f.departureTime());
                m.put("arrival_time", f.arrivalTime());
                m.put("price", f.price());
                m.put("currency", f.currency());
                m.put("stops", f.stops());
                return m;
            }
        }
        return null;
    }
}
