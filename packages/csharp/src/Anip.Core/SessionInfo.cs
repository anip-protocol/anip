using System.Text.Json.Serialization;

namespace Anip.Core;

public class SessionInfo
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";
}
