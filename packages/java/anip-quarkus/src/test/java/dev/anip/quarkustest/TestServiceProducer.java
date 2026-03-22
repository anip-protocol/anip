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
                                        List.of("travel"), null, null, null
                                ),
                                (ctx, params) -> Map.of("flights", List.of(Map.of("id", "FL-001", "price", 199.99)))
                        )
                ))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> "valid-api-key".equals(bearer) ? Optional.of("user@test.com") : Optional.empty())
        );
    }
}
