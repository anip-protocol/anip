package dev.anip.core;

import java.util.List;

/**
 * Describes the output of a capability.
 */
public class CapabilityOutput {

    private final String type;
    private final List<String> fields;

    public CapabilityOutput(String type, List<String> fields) {
        this.type = type;
        this.fields = fields;
    }

    public String getType() {
        return type;
    }

    public List<String> getFields() {
        return fields;
    }
}
