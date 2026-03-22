using System.Text.Json.Serialization;

namespace Anip.Core;

public class ServiceIdentity
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("jwks_uri")]
    public string JwksUri { get; set; } = "";

    [JsonPropertyName("issuer_mode")]
    public string IssuerMode { get; set; } = "";
}
