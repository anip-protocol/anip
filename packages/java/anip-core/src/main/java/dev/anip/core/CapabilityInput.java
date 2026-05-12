package dev.anip.core;

import java.util.List;

/**
 * Describes a single input parameter for a capability.
 *
 * <p>This class is JSON-stack-agnostic. Snake_case wire names are mapped by the
 * downstream transport/service module's ObjectMapper (typically via
 * {@code PropertyNamingStrategies.SNAKE_CASE}). v0.24 adds optional resolution
 * metadata and adjacent hint fields; see SPEC.md §4.10.
 */
public class CapabilityInput {
    private final String name;
    private final String type;
    private final boolean required;
    private final Object defaultValue;
    private final String description;
    private final String semanticType;
    private final boolean entityReference;
    private final List<String> allowedValues;
    private final String catalogRef;
    private final List<InputMeaning> inputMeanings;
    private final InputResolution resolution;

    public CapabilityInput(
            String name,
            String type,
            boolean required,
            Object defaultValue,
            String description,
            String semanticType,
            boolean entityReference,
            List<String> allowedValues,
            String catalogRef,
            List<InputMeaning> inputMeanings,
            InputResolution resolution
    ) {
        this.name = name;
        this.type = type;
        this.required = required;
        this.defaultValue = defaultValue;
        this.description = description;
        this.semanticType = semanticType;
        this.entityReference = entityReference;
        this.allowedValues = allowedValues;
        this.catalogRef = catalogRef;
        this.inputMeanings = inputMeanings;
        this.resolution = resolution;
    }

    public CapabilityInput(String name, String type, boolean required, Object defaultValue, String description) {
        this(name, type, required, defaultValue, description, null, false, null, null, null, null);
    }

    public CapabilityInput(String name, String type, boolean required, String description) {
        this(name, type, required, null, description, null, false, null, null, null, null);
    }

    public String getName() { return name; }
    public String getType() { return type; }
    public boolean isRequired() { return required; }
    public Object getDefaultValue() { return defaultValue; }
    public String getDescription() { return description; }
    public String getSemanticType() { return semanticType; }
    public boolean isEntityReference() { return entityReference; }
    public List<String> getAllowedValues() { return allowedValues; }
    public String getCatalogRef() { return catalogRef; }
    public List<InputMeaning> getInputMeanings() { return inputMeanings; }
    public InputResolution getResolution() { return resolution; }

    public static void validate(CapabilityInput inp) {
        if (inp.resolution == null) return;
        if (inp.resolution.mode() == ResolutionMode.CLOSED_VALUES
                && (inp.allowedValues == null || inp.allowedValues.isEmpty())) {
            throw new IllegalArgumentException("closed_values requires non-empty allowed_values");
        }
        if (inp.resolution.onMissing() == ResolutionBehavior.USE_DEFAULT && inp.defaultValue == null) {
            throw new IllegalArgumentException("on_missing=use_default requires a non-null default");
        }
    }
}
