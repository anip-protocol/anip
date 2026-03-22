package dev.anip.quarkus;

import dev.anip.service.ANIPService;
import io.quarkus.runtime.ShutdownEvent;
import io.quarkus.runtime.StartupEvent;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

/**
 * Bridges Quarkus lifecycle to ANIPService start/shutdown.
 */
@ApplicationScoped
public class AnipLifecycle {

    @Inject
    ANIPService service;

    void onStart(@Observes StartupEvent ev) {
        try {
            service.start();
        } catch (Exception e) {
            throw new RuntimeException("Failed to start ANIPService", e);
        }
    }

    void onStop(@Observes ShutdownEvent ev) {
        try {
            service.shutdown();
        } catch (Exception e) {
            // Best effort shutdown.
        }
    }
}
