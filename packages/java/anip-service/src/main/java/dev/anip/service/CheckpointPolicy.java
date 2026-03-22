package dev.anip.service;

/**
 * Configures automatic checkpoint creation.
 */
public class CheckpointPolicy {

    private int intervalSeconds = 60;
    private int minEntries = 1;

    public CheckpointPolicy() {}

    public CheckpointPolicy(int intervalSeconds, int minEntries) {
        this.intervalSeconds = intervalSeconds;
        this.minEntries = minEntries;
    }

    public int getIntervalSeconds() {
        return intervalSeconds;
    }

    public CheckpointPolicy setIntervalSeconds(int intervalSeconds) {
        this.intervalSeconds = intervalSeconds;
        return this;
    }

    public int getMinEntries() {
        return minEntries;
    }

    public CheckpointPolicy setMinEntries(int minEntries) {
        this.minEntries = minEntries;
        return this;
    }
}
