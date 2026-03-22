using System.Text.Json.Serialization;

namespace Anip.Core;

public class HealthReport
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = "";

    [JsonPropertyName("storage")]
    public StorageHealth Storage { get; set; } = new();

    [JsonPropertyName("uptime")]
    public string Uptime { get; set; } = "";

    [JsonPropertyName("version")]
    public string Version { get; set; } = "";
}
