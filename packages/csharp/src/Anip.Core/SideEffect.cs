using System.Text.Json.Serialization;

namespace Anip.Core;

public class SideEffect
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("rollback_window")]
    public string? RollbackWindow { get; set; }
}
