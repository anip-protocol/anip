package dev.anip.core;

/**
 * Declares a control that must be satisfied before invocation.
 */
public class ControlRequirement {

    private String type;
    private String enforcement;

    /** No-arg constructor for Jackson deserialization. */
    public ControlRequirement() {}

    public ControlRequirement(String type, String enforcement) {
        this.type = type;
        this.enforcement = enforcement;
    }

    public String getType() {
        return type;
    }

    /** "reject" in v0.14. */
    public String getEnforcement() {
        return enforcement;
    }

    public void setType(String type) {
        this.type = type;
    }

    public void setEnforcement(String enforcement) {
        this.enforcement = enforcement;
    }
}
