package dev.anip.core;

import java.util.List;

/**
 * Describes a single input parameter for a capability.
 *
 * <p>This class is JSON-stack-agnostic. Snake_case wire names are mapped by the
 * downstream transport/service module's ObjectMapper (typically via
 * {@code PropertyNamingStrategies.SNAKE_CASE}). v0.24 adds optional resolution
 * metadata and adjacent hint fields; see SPEC.md §4.10.
 *
 * <p>{@code required} defaults to {@code true} (SPEC.md §4.1): the constructor
 * without it declares a required input, and decoding a declaration that does
 * not state it ({@code dev.anip.server.AnipJacksonModule}) yields a required
 * input. Serialisation always writes {@code required}.
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

    /**
     * An input that does not state {@code required} is required (SPEC.md §4.1).
     * An optional input states {@code required = false} through one of the
     * other constructors.
     */
    public CapabilityInput(String name, String type) {
        this(name, type, true, null, null, null, false, null, null, null, null);
    }

    public String getName() { return name; }
    public String getType() { return type; }
    public boolean isRequired() { return required; }

    /**
     * Whether the caller has to supply this input (SPEC.md §6.3, Parameter
     * Validation): it is required, and its declaration does not carry a
     * {@code resolution} block that sets {@code on_missing} (§4.10). When
     * {@code on_missing} is set the declaration already says what happens
     * when the value is absent, and the service answers through that path.
     * Everything that demands inputs of a caller (the parameter check, the
     * MCP tool schema, the GraphQL schema, the OpenAPI document) asks this.
     */
    public boolean mustBeSupplied() {
        return required && !(resolution != null && resolution.onMissing() != null);
    }
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
