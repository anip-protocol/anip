package dev.anip.example.quartzflights;

import dev.anip.example.flights.SearchFlightsCapability;
import dev.anip.example.flights.BookFlightCapability;
import dev.anip.service.ANIPService;
import dev.anip.service.ServiceConfig;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@ApplicationScoped
public class QuarkusFlightsApp {

    @Produces
    @ApplicationScoped
    public ANIPService anipService() {
        Map<String, String> apiKeys = Map.of(
                "demo-human-key", "human:samir@example.com",
                "demo-agent-key", "agent:demo-agent"
        );

        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "anip-flight-service");

        return new ANIPService(new ServiceConfig()
                .setServiceId(serviceId)
                .setCapabilities(List.of(
                        SearchFlightsCapability.create(),
                        BookFlightCapability.create()
                ))
                .setStorage(System.getenv().getOrDefault("ANIP_STORAGE", ":memory:"))
                .setTrust(System.getenv().getOrDefault("ANIP_TRUST_LEVEL", "signed"))
                .setKeyPath(System.getenv().getOrDefault("ANIP_KEY_PATH", "./anip-keys"))
                .setAuthenticate(bearer -> {
                    String principal = apiKeys.get(bearer);
                    if (principal != null) {
                        return Optional.of(principal);
                    }
                    return Optional.empty();
                })
        );
    }
}
