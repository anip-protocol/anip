package dev.anip.core;

/**
 * Declares that a capability requires a bound value.
 */
public class BindingRequirement {

    private final String type;
    private final String field;
    private final String sourceCapability;
    private final String maxAge;

    public BindingRequirement(String type, String field, String sourceCapability, String maxAge) {
        this.type = type;
        this.field = field;
        this.sourceCapability = sourceCapability;
        this.maxAge = maxAge;
    }

    public String getType() {
        return type;
    }

    public String getField() {
        return field;
    }

    public String getSourceCapability() {
        return sourceCapability;
    }

    public String getMaxAge() {
        return maxAge;
    }
}
