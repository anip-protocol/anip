using System.Text.Json.Serialization;

namespace Anip.Core;

public class FinancialCost
{
    [JsonPropertyName("currency")]
    public string Currency { get; set; } = "";

    [JsonPropertyName("amount")]
    public double? Amount { get; set; }

    [JsonPropertyName("range_min")]
    public double? RangeMin { get; set; }

    [JsonPropertyName("range_max")]
    public double? RangeMax { get; set; }

    [JsonPropertyName("typical")]
    public double? Typical { get; set; }

    [JsonPropertyName("upper_bound")]
    public double? UpperBound { get; set; }
}
