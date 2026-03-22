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
}
