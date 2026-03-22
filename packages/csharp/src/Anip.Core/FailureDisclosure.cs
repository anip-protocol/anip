using System.Text.Json.Serialization;

namespace Anip.Core;

public class FailureDisclosure
{
    [JsonPropertyName("detail_level")]
    public string DetailLevel { get; set; } = "";

    [JsonPropertyName("caller_classes")]
    public List<string>? CallerClasses { get; set; }
}
