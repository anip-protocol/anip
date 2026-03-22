using System.Text.Json.Serialization;

namespace Anip.Core;

public class InvokeRequest
{
    [JsonPropertyName("token")]
    public string Token { get; set; } = "";

    [JsonPropertyName("parameters")]
    public Dictionary<string, object> Parameters { get; set; } = new();

    [JsonPropertyName("budget")]
    public Dictionary<string, object>? Budget { get; set; }

    [JsonPropertyName("client_reference_id")]
    public string? ClientReferenceId { get; set; }

    [JsonPropertyName("stream")]
    public bool Stream { get; set; }
}
