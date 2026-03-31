package dev.anip.core;

/**
 * Declares a control that must be satisfied before invocation.
 */
public class ControlRequirement {

    private final String type;
    private final String enforcement;
    private final String field;
    private final String maxAge;

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
}
