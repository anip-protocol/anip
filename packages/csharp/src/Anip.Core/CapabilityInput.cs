using System.Text.Json.Serialization;

namespace Anip.Core;

public class CapabilityInput
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("required")]
    public bool Required { get; set; }

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
