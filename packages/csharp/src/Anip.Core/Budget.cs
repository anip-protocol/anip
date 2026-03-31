using System.Text.Json.Serialization;

namespace Anip.Core;

public class Budget
{
    [JsonPropertyName("currency")]
    public string Currency { get; set; } = "";

    [JsonPropertyName("max_amount")]
    public double MaxAmount { get; set; }
}
