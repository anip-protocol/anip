package dev.anip.service;

import dev.anip.core.CapabilityDeclaration;

import java.util.List;
import java.util.Optional;
import java.util.function.Function;

/**
 * Configuration for an ANIP service instance.
 */
public class ServiceConfig {

    private String serviceId;
    private List<CapabilityDef> capabilities;
    private String storage;   // "sqlite:///path", ":memory:", "postgres://..."
    private String trust;     // "signed" or "anchored"
    private String keyPath;
    private Function<String, Optional<String>> authenticate;
    private ObservabilityHooks hooks;
    private CheckpointPolicy checkpointPolicy;
    private int retentionIntervalSeconds = 60; // default 60, -1 to disable

    public ServiceConfig() {}

    public String getServiceId() {
        return serviceId;
    }

    public ServiceConfig setServiceId(String serviceId) {
        this.serviceId = serviceId;
        return this;
    }

    public List<CapabilityDef> getCapabilities() {
        return capabilities;
    }

    public ServiceConfig setCapabilities(List<CapabilityDef> capabilities) {
        this.capabilities = capabilities;
        return this;
    }

    public String getStorage() {
        return storage;
    }

    public ServiceConfig setStorage(String storage) {
        this.storage = storage;
        return this;
    }

    public String getTrust() {
        return trust;
    }

    public ServiceConfig setTrust(String trust) {
        this.trust = trust;
        return this;
    }

    public String getKeyPath() {
        return keyPath;
    }

    public ServiceConfig setKeyPath(String keyPath) {
        this.keyPath = keyPath;
        return this;
    }

    public Function<String, Optional<String>> getAuthenticate() {
        return authenticate;
    }

    public ServiceConfig setAuthenticate(Function<String, Optional<String>> authenticate) {
        this.authenticate = authenticate;
        return this;
    }

    public ObservabilityHooks getHooks() {
        return hooks;
    }

    public ServiceConfig setHooks(ObservabilityHooks hooks) {
        this.hooks = hooks;
        return this;
    }

    public CheckpointPolicy getCheckpointPolicy() {
        return checkpointPolicy;
    }

    public ServiceConfig setCheckpointPolicy(CheckpointPolicy checkpointPolicy) {
        this.checkpointPolicy = checkpointPolicy;
        return this;
    }

    public int getRetentionIntervalSeconds() {
        return retentionIntervalSeconds;
    }

    public ServiceConfig setRetentionIntervalSeconds(int retentionIntervalSeconds) {
        this.retentionIntervalSeconds = retentionIntervalSeconds;
        return this;
    }
}
