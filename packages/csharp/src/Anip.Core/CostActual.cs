using System.Text.Json.Serialization;

namespace Anip.Core;

public class CostActual
{
    [JsonPropertyName("financial")]
    public Dictionary<string, object>? Financial { get; set; }

    [JsonPropertyName("variance_from_estimate")]
    public string? VarianceFromEstimate { get; set; }
}
