using System.Text.Json.Serialization;

namespace Anip.Core;

public class CapabilityRequirement
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("reason")]
    public string? Reason { get; set; }
}
