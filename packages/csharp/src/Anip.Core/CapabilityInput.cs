using System.Text.Json.Serialization;

namespace Anip.Core;

public class CapabilityInput
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    /// <summary>
    /// Whether the caller must supply this input. SPEC.md §4.1: an input whose
    /// declaration does not state <c>required</c> is required, in code and when
    /// a declaration is decoded; an optional input says <c>Required = false</c>.
    /// Always serialised.
    /// </summary>
    [JsonPropertyName("required")]
    [JsonIgnore(Condition = JsonIgnoreCondition.Never)]
    public bool Required { get; set; } = true;

    [JsonPropertyName("default")]
    public object? Default { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("semantic_type")] public string? SemanticType { get; set; }
    [JsonPropertyName("entity_reference")] public bool EntityReference { get; set; }
    [JsonPropertyName("allowed_values")] public List<string>? AllowedValues { get; set; }
    [JsonPropertyName("catalog_ref")] public string? CatalogRef { get; set; }
    [JsonPropertyName("input_meanings")] public List<InputMeaning>? InputMeanings { get; set; }
    [JsonPropertyName("resolution")] public InputResolution? Resolution { get; set; }

    /// <summary>
    /// Whether the caller must supply this input (SPEC.md §6.3, Parameter
    /// Validation). A required input whose resolution sets <c>on_missing</c>
    /// (§4.10) is not: its declaration says what happens when the value is
    /// absent, and the service answers through that path. Schema front doors
    /// (MCP, GraphQL, OpenAPI) use the same rule so that they do not refuse
    /// such an input before the service does.
    /// </summary>
    public bool MustBeSupplied() => Required && Resolution?.OnMissing == null;

    public static void Validate(CapabilityInput inp)
    {
        if (inp.Resolution == null) return;
        if (inp.Resolution.Mode == null)
        {
            throw new ArgumentException("resolution.mode is required");
        }
        if (inp.Resolution.Mode == ResolutionMode.ClosedValues
            && (inp.AllowedValues == null || inp.AllowedValues.Count == 0))
        {
            throw new ArgumentException("closed_values requires non-empty allowed_values");
        }
        if (inp.Resolution.OnMissing == ResolutionBehavior.UseDefault && inp.Default == null)
        {
            throw new ArgumentException("on_missing=use_default requires a non-null default");
        }
    }
}
