package dev.anip.generated.notion_governed_fronting_showcase;

import dev.anip.service.ANIPService;
import dev.anip.service.ServiceConfig;
import dev.anip.stdio.AnipStdioServer;

import java.util.Map;
import java.util.Optional;

public class StdioMain {
    public static void main(String[] args) throws Exception {
        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "Notion Fronting Showcase 0.2.0");
        String serviceFilter = System.getenv().getOrDefault("ANIP_SERVICE_FILTER", serviceId);
        Map<String, String> apiKeys = Map.of(
                "demo-human-key", "human:generated",
                "demo-agent-key", "agent:generated-service",
                "dev-admin-key", "human:local-developer"
        );
        ANIPService service = new ANIPService(new ServiceConfig()
                .setServiceId(serviceId)
                .setCapabilities(GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter(), serviceFilter))
                .setStorage(System.getenv().getOrDefault("ANIP_STORAGE", ":memory:"))
                .setTrust(System.getenv().getOrDefault("ANIP_TRUST_LEVEL", "signed"))
                .setKeyPath(System.getenv().getOrDefault("ANIP_KEY_PATH", "./anip-keys"))
                .setAuthenticate(bearer -> Optional.ofNullable(apiKeys.get(bearer))));
        service.start();
        try {
            new AnipStdioServer(service).serve();
        } finally {
            service.shutdown();
        }
    }
}
