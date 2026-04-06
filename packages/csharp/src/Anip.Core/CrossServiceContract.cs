using System.Text.Json.Serialization;

namespace Anip.Core;

/// <summary>
/// Declares bounded cross-service step meaning for a capability (v0.21).
/// </summary>
public class CrossServiceContract
{
    [JsonPropertyName("handoff")]
    public List<CrossServiceContractEntry> Handoff { get; set; } = new();

    [JsonPropertyName("followup")]
    public List<CrossServiceContractEntry> Followup { get; set; } = new();

    [JsonPropertyName("verification")]
    public List<CrossServiceContractEntry> Verification { get; set; } = new();
}
