using System.Text.Json.Serialization;

namespace Anip.Core;

public class DeniedCapability
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("reason_type")]
    public string ReasonType { get; set; } = "";
}
