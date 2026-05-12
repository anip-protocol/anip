using System.Text.Json.Serialization;

namespace Anip.Core;

public class InputMeaning
{
    [JsonPropertyName("label")] public string Label { get; set; } = "";
    [JsonPropertyName("value")] public string Value { get; set; } = "";
    [JsonPropertyName("description")] public string Description { get; set; } = "";
}
