package dev.anip.core;

/**
 * Describes a single input parameter for a capability.
 */
public class CapabilityInput {

    private final String name;
    private final String type;
    private final boolean required;
    private final Object defaultValue;
    private final String description;

    public CapabilityInput(String name, String type, boolean required, Object defaultValue, String description) {
        this.name = name;
        this.type = type;
        this.required = required;
        this.defaultValue = defaultValue;
        this.description = description;
    }

    public CapabilityInput(String name, String type, boolean required, String description) {
        this(name, type, required, null, description);
    }

    public String getName() {
        return name;
    }

    public String getType() {
        return type;
    }

    public boolean isRequired() {
        return required;
    }

    public Object getDefaultValue() {
        return defaultValue;
    }

    public String getDescription() {
        return description;
    }
}
