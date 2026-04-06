using System.Text.Json.Serialization;

namespace Anip.Core;

/// <summary>
/// Structured recovery step for failure handling (v0.21).
/// </summary>
public class RecoveryTarget
{
    [JsonPropertyName("kind")]
    public string Kind { get; set; } = "";

    [JsonPropertyName("target")]
    public ServiceCapabilityRef? Target { get; set; }

    [JsonPropertyName("continuity")]
    public string Continuity { get; set; } = "same_task";

    [JsonPropertyName("retry_after_target")]
    public bool RetryAfterTarget { get; set; }
}
