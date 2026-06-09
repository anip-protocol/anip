package dev.anip.generated.notion_governed_fronting_showcase;

import dev.anip.service.ANIPService;
import dev.anip.service.ServiceConfig;
import dev.anip.spring.AnipController;
import dev.anip.spring.AnipLifecycle;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@SpringBootApplication
public class Application {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }

    @Bean
    public BackendAdapter backendAdapter() {
        return BackendAdapter.defaultAdapter();
    }

    @Bean
    public ANIPService anipService(BackendAdapter backendAdapter) {
        Map<String, String> apiKeys = apiKeys();
        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "Notion Fronting Showcase 0.2.0");
        String serviceFilter = System.getenv().getOrDefault("ANIP_SERVICE_FILTER", serviceId);

        return new ANIPService(new ServiceConfig()
                .setServiceId(serviceId)
                .setCapabilities(GeneratedCapabilities.createAll(backendAdapter, serviceFilter))
                .setStorage(System.getenv().getOrDefault("ANIP_STORAGE", ":memory:"))
                .setTrust(System.getenv().getOrDefault("ANIP_TRUST_LEVEL", "signed"))
                .setKeyPath(System.getenv().getOrDefault("ANIP_KEY_PATH", "./anip-keys"))
                .setAuthenticate(bearer -> Optional.ofNullable(apiKeys.get(bearer))));
    }

    private static Map<String, String> apiKeys() {
        String raw = System.getenv("ANIP_API_KEYS_JSON");
        if (raw == null || raw.isBlank()) {
            return Map.of(
                    "demo-human-key", "human:generated",
                    "demo-agent-key", "agent:generated-service"
            );
        }
        try {
            Map<String, Object> decoded = MAPPER.readValue(raw, new TypeReference<Map<String, Object>>() {});
            Map<String, String> result = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : decoded.entrySet()) {
                if (entry.getKey() != null && entry.getValue() != null) {
                    result.put(entry.getKey(), String.valueOf(entry.getValue()));
                }
            }
            return result.isEmpty() ? Map.of("demo-agent-key", "agent:generated-service") : result;
        } catch (Exception ignored) {
            return Map.of("demo-agent-key", "agent:generated-service");
        }
    }

    @Bean
    public AnipController anipController(ANIPService service) {
        return new AnipController(service);
    }

    @Bean
    public AnipLifecycle anipLifecycle(ANIPService service) {
        return new AnipLifecycle(service);
    }
}
