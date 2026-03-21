package dev.anip.core;

/**
 * Health report for the ANIP service.
 */
public class HealthReport {

    private final String status;
    private final StorageHealth storage;
    private final String uptime;
    private final String version;

    public HealthReport(String status, StorageHealth storage, String uptime, String version) {
        this.status = status;
        this.storage = storage;
        this.uptime = uptime;
        this.version = version;
    }

    public String getStatus() {
        return status;
    }

    public StorageHealth getStorage() {
        return storage;
    }

    public String getUptime() {
        return uptime;
    }

    public String getVersion() {
        return version;
    }
}
