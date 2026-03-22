package dev.anip.graphql.quarkustest;

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
        ANIPService svc = new ANIPService(new ServiceConfig()
                .setServiceId("test-graphql-quarkus-svc")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search_flights", "Search for flights", "1.0",
                                        List.of(
                                                new CapabilityInput("origin", "string", true, "Origin airport"),
                                                new CapabilityInput("destination", "string", true, "Destination airport")
                                        ),
                                        new CapabilityOutput("object", List.of("flights")),
                                        new SideEffect("read", "not_applicable"),
                                        List.of("travel"), null, null,
                                        List.of("sync")
                                ),
                                (ctx, params) -> Map.of("flights", List.of(
                                        Map.of("id", "FL-001", "price", 199.99)
                                ))
                        ),
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
                .setAuthenticate(bearer -> "valid-api-key".equals(bearer)
                        ? Optional.of("user@test.com")
                        : Optional.empty())
                .setRetentionIntervalSeconds(-1)
        );
        try {
            svc.start();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        return svc;
    }
}
