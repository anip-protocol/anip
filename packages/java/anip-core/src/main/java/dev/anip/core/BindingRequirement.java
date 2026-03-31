package dev.anip.core;

/**
 * Declares that a capability requires a bound value.
 */
public class BindingRequirement {

    private String type;
    private String field;
    private String sourceCapability;
    private String maxAge;

    /** No-arg constructor for Jackson deserialization. */
    public BindingRequirement() {}

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

    public void setType(String type) {
        this.type = type;
    }

    public void setField(String field) {
        this.field = field;
    }

    public void setSourceCapability(String sourceCapability) {
        this.sourceCapability = sourceCapability;
    }

    public void setMaxAge(String maxAge) {
        this.maxAge = maxAge;
    }
}
