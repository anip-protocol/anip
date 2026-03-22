package dev.anip.example.flights;

import dev.anip.graphql.AnipGraphQLController;
import dev.anip.mcp.AnipMcpHttp;
import dev.anip.rest.AnipRestController;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;
import dev.anip.service.ANIPService;
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

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }

    @Bean
    public ANIPService anipService() {
        // API key bootstrap auth.
        Map<String, String> apiKeys = Map.of(
                "demo-human-key", "human:samir@example.com",
                "demo-agent-key", "agent:demo-agent"
        );

        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "anip-flight-service");

        // Optional OIDC authentication.
        OidcValidator oidcValidator = null;
        String issuerUrl = System.getenv("OIDC_ISSUER_URL");
        if (issuerUrl != null && !issuerUrl.isEmpty()) {
            String audience = System.getenv().getOrDefault("OIDC_AUDIENCE", serviceId);
            String jwksUrl = System.getenv("OIDC_JWKS_URL");
            oidcValidator = new OidcValidator(issuerUrl, audience, jwksUrl);
        }
        final OidcValidator oidc = oidcValidator;

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
                    // 1. API key map.
                    String principal = apiKeys.get(bearer);
                    if (principal != null) {
                        return Optional.of(principal);
                    }
                    // 2. OIDC (if configured).
                    if (oidc != null) {
                        return oidc.validate(bearer);
                    }
                    return Optional.empty();
                })
        );
    }

    @Bean
    public AnipController anipController(ANIPService service) {
        return new AnipController(service);
    }

    @Bean
    public AnipLifecycle anipLifecycle(ANIPService service) {
        return new AnipLifecycle(service);
    }

    @Bean
    public AnipRestController restController(ANIPService service) {
        return new AnipRestController(service);
    }

    @Bean
    public AnipGraphQLController graphqlController(ANIPService service) {
        return new AnipGraphQLController(service);
    }

    @Bean
    public RouterFunction<ServerResponse> mcpRoutes(ANIPService service) {
        try {
            return AnipMcpHttp.mount(service);
        } catch (Throwable t) {
            // MCP SDK may require additional SPI providers at runtime.
            // If unavailable, skip MCP HTTP and log the issue.
            System.err.println("MCP HTTP transport not available: " + t.getMessage());
            return request -> Optional.empty();
        }
    }
}
