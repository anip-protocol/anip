using System.Text.Json.Serialization;

namespace Anip.Core;

public class BindingRequirement
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("field")]
    public string Field { get; set; } = "";

    [JsonPropertyName("source_capability")]
    public string? SourceCapability { get; set; }

    [JsonPropertyName("max_age")]
    public string? MaxAge { get; set; }
}
