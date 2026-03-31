package dev.anip.core;

/**
 * Declares a control that must be satisfied before invocation.
 */
public class ControlRequirement {

    private String type;
    private String enforcement;
    private String field;
    private String maxAge;

    /** No-arg constructor for Jackson deserialization. */
    public ControlRequirement() {}

    public ControlRequirement(String type, String enforcement, String field, String maxAge) {
        this.type = type;
        this.enforcement = enforcement;
        this.field = field;
        this.maxAge = maxAge;
    }

    public String getType() {
        return type;
    }

    /** "reject" in v0.13. */
    public String getEnforcement() {
        return enforcement;
    }

    public String getField() {
        return field;
    }

    public String getMaxAge() {
        return maxAge;
    }

    public void setType(String type) {
        this.type = type;
    }

    public void setEnforcement(String enforcement) {
        this.enforcement = enforcement;
    }

    public void setField(String field) {
        this.field = field;
    }

    public void setMaxAge(String maxAge) {
        this.maxAge = maxAge;
    }
}
