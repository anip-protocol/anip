package dev.anip.core;

/**
 * Describes a capability that can be composed with another capability.
 */
public class CapabilityComposition {

    private final String capability;
    private final boolean optional;

    public CapabilityComposition(String capability, boolean optional) {
        this.capability = capability;
        this.optional = optional;
    }

    public String getCapability() {
        return capability;
    }

    public boolean isOptional() {
        return optional;
    }
}
