using System.Text.Json.Serialization;

namespace Anip.Core;

public class TokenResponse
{
    [JsonPropertyName("issued")]
    public bool Issued { get; set; }

    [JsonPropertyName("token_id")]
    public string TokenId { get; set; } = "";

    [JsonPropertyName("token")]
    public string Token { get; set; } = "";

    [JsonPropertyName("expires")]
    public string Expires { get; set; } = "";

    /// <summary>Echoed when the issued token has a resolved purpose.task_id.</summary>
    [JsonPropertyName("task_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? TaskId { get; set; }
}
