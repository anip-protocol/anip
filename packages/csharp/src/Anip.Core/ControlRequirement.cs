using System.Text.Json.Serialization;

namespace Anip.Core;

public class ControlRequirement
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("enforcement")]
    public string Enforcement { get; set; } = "reject";

    [JsonPropertyName("field")]
    public string? Field { get; set; }

    [JsonPropertyName("max_age")]
    public string? MaxAge { get; set; }
}
