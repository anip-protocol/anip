package dev.anip.service;

import java.util.Map;

/**
 * A single event in a streaming invocation.
 */
public class StreamEvent {

    private final String type;    // "progress", "completed", "failed"
    private final Map<String, Object> payload;

    public StreamEvent(String type, Map<String, Object> payload) {
        this.type = type;
        this.payload = payload;
    }

    public String getType() {
        return type;
    }

    public Map<String, Object> getPayload() {
        return payload;
    }
}
