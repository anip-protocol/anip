package dev.anip.spring;

import dev.anip.service.ANIPService;
import org.springframework.context.SmartLifecycle;

/**
 * Manages ANIPService lifecycle within the Spring application context.
 * Calls {@code service.start()} when Spring starts and {@code service.shutdown()}
 * when Spring stops.
 */
public class AnipLifecycle implements SmartLifecycle {

    private final ANIPService service;
    private volatile boolean running = false;

    public AnipLifecycle(ANIPService service) {
        this.service = service;
    }

    @Override
    public void start() {
        try {
            service.start();
        } catch (Exception e) {
            throw new RuntimeException("Failed to start ANIPService", e);
        }
        running = true;
    }

    @Override
    public void stop() {
        service.shutdown();
        running = false;
    }

    @Override
    public boolean isRunning() {
        return running;
    }

    @Override
    public int getPhase() {
        return 0; // start early, stop late
    }
}
