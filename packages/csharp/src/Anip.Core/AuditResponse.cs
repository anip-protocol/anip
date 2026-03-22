using System.Text.Json.Serialization;

namespace Anip.Core;

public class AuditResponse
{
    [JsonPropertyName("entries")]
    public List<AuditEntry> Entries { get; set; } = new();

    [JsonPropertyName("count")]
    public int Count { get; set; }

    [JsonPropertyName("root_principal")]
    public string? RootPrincipal { get; set; }

    [JsonPropertyName("capability_filter")]
    public string? CapabilityFilter { get; set; }

    [JsonPropertyName("since_filter")]
    public string? SinceFilter { get; set; }
}
