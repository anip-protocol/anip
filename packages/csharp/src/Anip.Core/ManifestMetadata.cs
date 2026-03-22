using System.Text.Json.Serialization;

namespace Anip.Core;

public class ManifestMetadata
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("sha256")]
    public string Sha256 { get; set; } = "";

    [JsonPropertyName("issued_at")]
    public string IssuedAt { get; set; } = "";

    [JsonPropertyName("expires_at")]
    public string ExpiresAt { get; set; } = "";
}
