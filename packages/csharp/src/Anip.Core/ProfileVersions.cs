using System.Text.Json.Serialization;

namespace Anip.Core;

public class ProfileVersions
{
    [JsonPropertyName("core")]
    public string Core { get; set; } = "";

    [JsonPropertyName("cost")]
    public string? Cost { get; set; }

    [JsonPropertyName("capability_graph")]
    public string? CapabilityGraph { get; set; }

    [JsonPropertyName("state_session")]
    public string? StateSession { get; set; }

    [JsonPropertyName("observability")]
    public string? Observability { get; set; }
}
