package dev.anip.service;

import java.util.concurrent.BlockingQueue;

/**
 * Holds the result of a streaming invocation.
 * The events queue emits progress events followed by exactly one terminal event
 * (completed or failed), then a poison pill (type="__done__") to signal completion.
 * Call cancel to signal the handler that the client has disconnected.
 */
public class StreamResult {

    /** Poison pill event type to signal end of stream. */
    public static final String DONE_TYPE = "__done__";

    private final BlockingQueue<StreamEvent> events;
    private final Runnable cancel;

    public StreamResult(BlockingQueue<StreamEvent> events, Runnable cancel) {
        this.events = events;
        this.cancel = cancel;
    }

    public BlockingQueue<StreamEvent> getEvents() {
        return events;
    }

    public Runnable getCancel() {
        return cancel;
    }
}
