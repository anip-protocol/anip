package quickstart;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.SideEffect;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;
import dev.anip.spring.AnipController;
import dev.anip.spring.AnipLifecycle;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@SpringBootApplication
public class Application {

    // Your business logic. Nothing here knows about ANIP.
    static List<Map<String, Object>> doSearch(String origin, String destination) {
        return List.of(
                Map.of("flight_number", "AA100", "origin", origin, "destination", destination, "price", 420),
                Map.of("flight_number", "DL310", "origin", origin, "destination", destination, "price", 280));
    }

    static Map<String, Object> doBook(String flightNumber) {
        return Map.of("booking_id", "BK-0001", "flight_number", flightNumber);
    }

    // A capability that only reads.
    static final CapabilityDef SEARCH_FLIGHTS = new CapabilityDef(
            new CapabilityDeclaration(
                    "search_flights",
                    "Search available flights between two airports",
                    "1.0",
                    List.of(
                            new CapabilityInput("origin", "string", true, "Departure airport"),
                            new CapabilityInput("destination", "string", true, "Arrival airport")),
                    new CapabilityOutput("object", List.of("flights")),
                    new SideEffect("read", "not_applicable"),
                    List.of("travel.search"),
                    null, // cost
                    null, // requires
                    List.of("unary")),
            (ctx, params) -> Map.of("flights",
                    doSearch((String) params.get("origin"), (String) params.get("destination"))));

    // A capability that cannot be undone, and needs a different scope.
    static final CapabilityDef BOOK_FLIGHT = new CapabilityDef(
            new CapabilityDeclaration(
                    "book_flight",
                    "Book a flight",
                    "1.0",
                    List.of(
                            new CapabilityInput("flight_number", "string", true, "Flight to book")),
                    new CapabilityOutput("object", List.of("booking_id", "flight_number")),
                    new SideEffect("irreversible", "none"),
                    List.of("travel.book"),
                    null, // cost
                    null, // requires
                    List.of("unary")),
            (ctx, params) -> doBook((String) params.get("flight_number")));

    @Bean
    ANIPService anipService() {
        return new ANIPService(new ServiceConfig()
                .setServiceId("quickstart-flights")
                .setCapabilities(List.of(SEARCH_FLIGHTS, BOOK_FLIGHT))
                .setStorage(":memory:")
                .setTrust("signed")
                // Who is calling? Map your own API keys or sessions to a principal.
                .setAuthenticate(bearer -> Optional.ofNullable(
                        Map.of("demo-key", "human:demo@example.com").get(bearer))));
    }

    // Mount the ANIP routes, and start and stop the service with the application.
    @Bean
    AnipController anipController(ANIPService service) {
        return new AnipController(service);
    }

    @Bean
    AnipLifecycle anipLifecycle(ANIPService service) {
        return new AnipLifecycle(service);
    }

    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(Application.class);
        app.setDefaultProperties(Map.of("server.port", System.getenv().getOrDefault("PORT", "9100")));
        app.run(args);
    }
}
