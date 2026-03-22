using System.Text.Json.Serialization;

namespace Anip.Core;

public class CapabilityComposition
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("optional")]
    public bool Optional { get; set; }
}
