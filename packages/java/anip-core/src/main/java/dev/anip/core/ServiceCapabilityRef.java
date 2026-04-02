package dev.anip.core;

/**
 * Identifies a capability on another service for cross-service coordination.
 */
public class ServiceCapabilityRef {

    private String service;
    private String capability;

    /** No-arg constructor for Jackson deserialization. */
    public ServiceCapabilityRef() {}

    public ServiceCapabilityRef(String service, String capability) {
        this.service = service;
        this.capability = capability;
    }

    public String getService() {
        return service;
    }

    public String getCapability() {
        return capability;
    }

    public void setService(String service) {
        this.service = service;
    }

    public void setCapability(String capability) {
        this.capability = capability;
    }
}
