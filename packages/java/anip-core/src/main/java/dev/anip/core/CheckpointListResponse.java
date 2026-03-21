package dev.anip.core;

import java.util.List;

/**
 * Response from the checkpoint list endpoint.
 */
public class CheckpointListResponse {

    private final List<Checkpoint> checkpoints;
    private final String nextCursor;

    public CheckpointListResponse(List<Checkpoint> checkpoints, String nextCursor) {
        this.checkpoints = checkpoints;
        this.nextCursor = nextCursor;
    }

    public List<Checkpoint> getCheckpoints() {
        return checkpoints;
    }

    public String getNextCursor() {
        return nextCursor;
    }
}
