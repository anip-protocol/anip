using System.Text.Json.Serialization;

namespace Anip.Core;

public class StorageHealth
{
    [JsonPropertyName("connected")]
    public bool Connected { get; set; }

    [JsonPropertyName("type")]
    public string Type { get; set; } = "";
}
