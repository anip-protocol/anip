package dev.anip.core;

import java.util.Map;

/**
 * A Merkle checkpoint over a range of audit entries.
 */
public class Checkpoint {

    private final String version;
    private final String serviceId;
    private final String checkpointId;
    private final Map<String, Integer> range;
    private final String merkleRoot;
    private final String previousCheckpoint;
    private final String timestamp;
    private final int entryCount;
    private final String signature;

    public Checkpoint(String version, String serviceId, String checkpointId,
                      Map<String, Integer> range, String merkleRoot,
                      String previousCheckpoint, String timestamp,
                      int entryCount, String signature) {
        this.version = version;
        this.serviceId = serviceId;
        this.checkpointId = checkpointId;
        this.range = range;
        this.merkleRoot = merkleRoot;
        this.previousCheckpoint = previousCheckpoint;
        this.timestamp = timestamp;
        this.entryCount = entryCount;
        this.signature = signature;
    }

    public String getVersion() {
        return version;
    }

    public String getServiceId() {
        return serviceId;
    }

    public String getCheckpointId() {
        return checkpointId;
    }

    /** Contains "first_sequence" and "last_sequence". */
    public Map<String, Integer> getRange() {
        return range;
    }

    public String getMerkleRoot() {
        return merkleRoot;
    }

    public String getPreviousCheckpoint() {
        return previousCheckpoint;
    }

    public String getTimestamp() {
        return timestamp;
    }

    public int getEntryCount() {
        return entryCount;
    }

    public String getSignature() {
        return signature;
    }
}
