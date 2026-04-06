using System.Text.Json.Serialization;

namespace Anip.Core;

/// <summary>
/// A single cross-service step with stronger semantics than advisory hints (v0.21).
/// </summary>
public class CrossServiceContractEntry
{
    [JsonPropertyName("target")]
    public ServiceCapabilityRef Target { get; set; } = new();

    [JsonPropertyName("required_for_task_completion")]
    public bool RequiredForTaskCompletion { get; set; }

    [JsonPropertyName("continuity")]
    public string Continuity { get; set; } = "same_task";

    [JsonPropertyName("completion_mode")]
    public string CompletionMode { get; set; } = "";
}
