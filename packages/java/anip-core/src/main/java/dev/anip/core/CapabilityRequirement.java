package dev.anip.core;

/**
 * Describes a capability that must be invoked first.
 */
public class CapabilityRequirement {

    private final String capability;
    private final String reason;

    public CapabilityRequirement(String capability, String reason) {
        this.capability = capability;
        this.reason = reason;
    }

    public String getCapability() {
        return capability;
    }

    public String getReason() {
        return reason;
    }
}
