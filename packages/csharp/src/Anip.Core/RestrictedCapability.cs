using System.Text.Json.Serialization;

namespace Anip.Core;

public class RestrictedCapability
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("reason_type")]
    public string ReasonType { get; set; } = "";

    [JsonPropertyName("grantable_by")]
    public string? GrantableBy { get; set; }

    [JsonPropertyName("unmet_token_requirements")]
    public List<string>? UnmetTokenRequirements { get; set; }

    [JsonPropertyName("resolution_hint")]
    public string? ResolutionHint { get; set; }
}
