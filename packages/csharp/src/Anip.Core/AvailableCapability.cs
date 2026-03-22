using System.Text.Json.Serialization;

namespace Anip.Core;

public class AvailableCapability
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("scope_match")]
    public string ScopeMatch { get; set; } = "";

    [JsonPropertyName("constraints")]
    public Dictionary<string, object>? Constraints { get; set; }
}
