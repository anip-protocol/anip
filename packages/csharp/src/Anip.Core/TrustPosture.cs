using System.Text.Json.Serialization;

namespace Anip.Core;

public class TrustPosture
{
    [JsonPropertyName("level")]
    public string Level { get; set; } = "";

    [JsonPropertyName("anchoring")]
    public Dictionary<string, object>? Anchoring { get; set; }

    [JsonPropertyName("policies")]
    public List<object>? Policies { get; set; }
}
