using System.Text.Json.Serialization;

namespace Anip.Core;

public class RestrictedCapability
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("grantable_by")]
    public string? GrantableBy { get; set; }
}
