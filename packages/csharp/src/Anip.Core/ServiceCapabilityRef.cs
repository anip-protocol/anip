using System.Text.Json.Serialization;

namespace Anip.Core;

public class ServiceCapabilityRef
{
    [JsonPropertyName("service")]
    public string Service { get; set; } = "";

    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";
}
