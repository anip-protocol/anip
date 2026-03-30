package dev.anip.studio;

import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Serves the ANIP Studio SPA from classpath resources.
 * Static assets are expected at classpath:studio/
 */
@RestController
public class AnipStudioController {

    private final String serviceId;
    private final String prefix;

    public AnipStudioController(String serviceId) {
        this(serviceId, "/studio");
    }

    public AnipStudioController(String serviceId, String prefix) {
        this.serviceId = serviceId;
        this.prefix = prefix;
    }

    @GetMapping("${anip.studio.prefix:/studio}/config.json")
    public ResponseEntity<Map<String, Object>> config() {
        return ResponseEntity.ok(Map.of(
                "service_id", serviceId,
                "embedded", true
        ));
    }

    @GetMapping("${anip.studio.prefix:/studio}/assets/{file}")
    public ResponseEntity<Resource> asset(@PathVariable String file) {
        Resource resource = new ClassPathResource("studio/assets/" + file);
        if (!resource.exists()) {
            return ResponseEntity.notFound().build();
        }
        String contentType = guessContentType(file);
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(365, TimeUnit.DAYS).cachePublic())
                .header("Content-Type", contentType)
                .body(resource);
    }

    @GetMapping(value = {"${anip.studio.prefix:/studio}", "${anip.studio.prefix:/studio}/", "${anip.studio.prefix:/studio}/**"})
    public ResponseEntity<String> index() throws IOException {
        Resource index = new ClassPathResource("studio/index.html");
        if (!index.exists()) {
            return ResponseEntity.status(503).body("Studio assets not available");
        }
        String html = index.getContentAsString(StandardCharsets.UTF_8);
        return ResponseEntity.ok()
                .cacheControl(CacheControl.noCache())
                .contentType(MediaType.TEXT_HTML)
                .body(html);
    }

    private String guessContentType(String file) {
        if (file.endsWith(".js")) return "application/javascript";
        if (file.endsWith(".css")) return "text/css";
        if (file.endsWith(".json")) return "application/json";
        if (file.endsWith(".png")) return "image/png";
        if (file.endsWith(".svg")) return "image/svg+xml";
        return "application/octet-stream";
    }
}
