package dev.anip.rest.quarkustest;

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
                .setServiceId("test-rest-quarkus-svc")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search_flights", "Search for flights", "1.0",
                                        List.of(
                                                new CapabilityInput("q", "string", true, "Search query")
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
                                        "create_item", "Create an item", "1.0",
                                        List.of(
                                                new CapabilityInput("name", "string", true, "Item name")
                                        ),
                                        new CapabilityOutput("object", List.of("item_id")),
                                        new SideEffect("irreversible", "none"),
                                        List.of("inventory"), null, null,
                                        List.of("sync")
                                ),
                                (ctx, params) -> Map.of("item_id", "ITEM-001", "status", "created")
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
