using System.Text.Json.Serialization;

namespace Anip.Core;

public class Purpose
{
    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("parameters")]
    public Dictionary<string, object>? Parameters { get; set; }

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }
}
