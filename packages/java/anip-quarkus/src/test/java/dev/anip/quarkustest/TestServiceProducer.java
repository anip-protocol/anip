package dev.anip.quarkustest;

import dev.anip.core.*;
import dev.anip.service.*;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@ApplicationScoped
public class TestServiceProducer {

    @Produces
    @ApplicationScoped
    public ANIPService anipService() {
        return new ANIPService(new ServiceConfig()
                .setServiceId("test-quarkus-svc")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search_flights", "Search for flights", "1.0",
                                        List.of(
                                                new CapabilityInput("origin", "string", true, "Origin"),
                                                new CapabilityInput("destination", "string", true, "Dest")
                                        ),
                                        new CapabilityOutput("object", List.of("flights")),
                                        new SideEffect("read", "not_applicable"),
                                        List.of("travel"), null, null,
                                        List.of("sync", "streaming")
                                ),
                                (ctx, params) -> Map.of("flights", List.of(Map.of("id", "FL-001", "price", 199.99)))
                        ),
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "hold_seat", "Hold a seat at a quoted price", "1.0",
                                        List.of(
                                                new CapabilityInput("quote_id", "object", false, "Priced quote")
                                        ),
                                        new CapabilityOutput("object", List.of("held")),
                                        new SideEffect("write", "none"),
                                        List.of("travel"), null, null,
                                        List.of("sync", "streaming"),
                                        List.of(new dev.anip.core.BindingRequirement(
                                                "quote", "quote_id", "search_flights", null)),
                                        List.of()
                                ),
                                (ctx, params) -> Map.of("held", true)
                        ),
                        // Unary only, like the Spring binding's test service.
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "book_flight", "Book a flight", "1.0",
                                        List.of(
                                                new CapabilityInput("flight_id", "string", true, "Flight ID")
                                        ),
                                        new CapabilityOutput("object", List.of("booking_id")),
                                        new SideEffect("irreversible", "none"),
                                        List.of("travel", "finance"), null, null,
                                        List.of("sync")
                                ),
                                (ctx, params) -> Map.of("booking_id", "BK-001", "status", "confirmed")
                        )
                ))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> "valid-api-key".equals(bearer) ? Optional.of("user@test.com") : Optional.empty())
        );
    }
}
