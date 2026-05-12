package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/**
 * Describes a single input parameter for a capability.
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

    @JsonCreator
    public CapabilityInput(
            @JsonProperty("name") String name,
            @JsonProperty("type") String type,
            @JsonProperty("required") Boolean required,
            @JsonProperty("default") Object defaultValue,
            @JsonProperty("description") String description,
            @JsonProperty("semantic_type") String semanticType,
            @JsonProperty("entity_reference") Boolean entityReference,
            @JsonProperty("allowed_values") List<String> allowedValues,
            @JsonProperty("catalog_ref") String catalogRef,
            @JsonProperty("input_meanings") List<InputMeaning> inputMeanings,
            @JsonProperty("resolution") InputResolution resolution
    ) {
        this.name = name;
        this.type = type;
        this.required = required == null ? true : required;
        this.defaultValue = defaultValue;
        this.description = description == null ? "" : description;
        this.semanticType = semanticType;
        this.entityReference = entityReference != null && entityReference;
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

    @JsonProperty("name") public String getName() { return name; }
    @JsonProperty("type") public String getType() { return type; }
    @JsonProperty("required") public boolean isRequired() { return required; }
    @JsonProperty("default") public Object getDefaultValue() { return defaultValue; }
    @JsonProperty("description") public String getDescription() { return description; }
    @JsonProperty("semantic_type") public String getSemanticType() { return semanticType; }
    @JsonProperty("entity_reference") public boolean isEntityReference() { return entityReference; }
    @JsonProperty("allowed_values") public List<String> getAllowedValues() { return allowedValues; }
    @JsonProperty("catalog_ref") public String getCatalogRef() { return catalogRef; }
    @JsonProperty("input_meanings") public List<InputMeaning> getInputMeanings() { return inputMeanings; }
    @JsonProperty("resolution") public InputResolution getResolution() { return resolution; }

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
