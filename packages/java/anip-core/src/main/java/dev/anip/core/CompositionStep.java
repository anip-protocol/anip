package dev.anip.core;

/** A single step in a composed capability. v0.23. See SPEC.md §4.6. */
public class CompositionStep {
    private final String id;
    private final String capability;
    private boolean emptyResultSource = false;
    private String emptyResultPath;

    public CompositionStep(String id, String capability) {
        this.id = id;
        this.capability = capability;
    }

    public String getId() {
        return id;
    }

    public String getCapability() {
        return capability;
    }

    public boolean isEmptyResultSource() {
        return emptyResultSource;
    }

    public CompositionStep setEmptyResultSource(boolean emptyResultSource) {
        this.emptyResultSource = emptyResultSource;
        return this;
    }

    public String getEmptyResultPath() {
        return emptyResultPath;
    }

    public CompositionStep setEmptyResultPath(String emptyResultPath) {
        this.emptyResultPath = emptyResultPath;
        return this;
    }
}
