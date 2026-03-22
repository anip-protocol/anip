package dev.anip.core;

/**
 * Storage health status.
 */
public class StorageHealth {

    private final boolean connected;
    private final String type;

    public StorageHealth(boolean connected, String type) {
        this.connected = connected;
        this.type = type;
    }

    public boolean isConnected() {
        return connected;
    }

    public String getType() {
        return type;
    }
}
