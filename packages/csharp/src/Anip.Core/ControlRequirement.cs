using System.Text.Json.Serialization;

namespace Anip.Core;

public class ControlRequirement
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("enforcement")]
    public string Enforcement { get; set; } = "reject";

}
