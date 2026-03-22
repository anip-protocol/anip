using System.Text.Json.Serialization;

namespace Anip.Core;

public class CapabilityOutput
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("fields")]
    public List<string> Fields { get; set; } = new();
}
