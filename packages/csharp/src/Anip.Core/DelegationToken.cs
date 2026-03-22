using System.Text.Json.Serialization;

namespace Anip.Core;

public class DelegationToken
{
    [JsonPropertyName("token_id")]
    public string TokenId { get; set; } = "";

    [JsonPropertyName("issuer")]
    public string Issuer { get; set; } = "";

    [JsonPropertyName("subject")]
    public string Subject { get; set; } = "";

    [JsonPropertyName("scope")]
    public List<string> Scope { get; set; } = new();

    [JsonPropertyName("purpose")]
    public Purpose Purpose { get; set; } = new();

    [JsonPropertyName("parent")]
    public string? Parent { get; set; }

    [JsonPropertyName("expires")]
    public string Expires { get; set; } = "";

    [JsonPropertyName("constraints")]
    public DelegationConstraints Constraints { get; set; } = new();

    [JsonPropertyName("root_principal")]
    public string? RootPrincipal { get; set; }

    [JsonPropertyName("caller_class")]
    public string? CallerClass { get; set; }
}
