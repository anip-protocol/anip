using System.Text.Json.Serialization;

namespace Anip.Core;

public class Cost
{
    [JsonPropertyName("certainty")]
    public string Certainty { get; set; } = "";

    [JsonPropertyName("financial")]
    public Dictionary<string, object>? Financial { get; set; }

    [JsonPropertyName("determined_by")]
    public string? DeterminedBy { get; set; }

    [JsonPropertyName("factors")]
    public List<string>? Factors { get; set; }

    [JsonPropertyName("compute")]
    public Dictionary<string, object>? Compute { get; set; }

    [JsonPropertyName("rate_limit")]
    public Dictionary<string, object>? RateLimit { get; set; }
}
