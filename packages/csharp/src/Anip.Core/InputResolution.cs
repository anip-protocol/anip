using System.Text.Json.Serialization;

namespace Anip.Core;

public class InputResolution
{
    // Mode is required, but typed as nullable to distinguish "missing" from
    // "default enum value". Validate() rejects null mode at the cross-field check.
    [JsonPropertyName("mode")] public ResolutionMode? Mode { get; set; }
    [JsonPropertyName("resolver_ref")] public string? ResolverRef { get; set; }
    [JsonPropertyName("on_missing")] public ResolutionBehavior? OnMissing { get; set; }
    [JsonPropertyName("on_ambiguous")] public ResolutionBehavior? OnAmbiguous { get; set; }
    [JsonPropertyName("on_unresolved")] public ResolutionBehavior? OnUnresolved { get; set; }
}
