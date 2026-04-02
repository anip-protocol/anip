using System.Text.Json.Serialization;

namespace Anip.Core;

public class CrossServiceHints
{
    [JsonPropertyName("handoff_to")]
    public List<ServiceCapabilityRef> HandoffTo { get; set; } = new();

    [JsonPropertyName("refresh_via")]
    public List<ServiceCapabilityRef> RefreshVia { get; set; } = new();

    [JsonPropertyName("verify_via")]
    public List<ServiceCapabilityRef> VerifyVia { get; set; } = new();

    [JsonPropertyName("followup_via")]
    public List<ServiceCapabilityRef> FollowupVia { get; set; } = new();
}
