using System.Text.Json.Serialization;

namespace Anip.Core;

public class TokenRequest
{
    [JsonPropertyName("subject")]
    public string Subject { get; set; } = "";

    [JsonPropertyName("scope")]
    public List<string> Scope { get; set; } = new();

    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("purpose_parameters")]
    public Dictionary<string, object>? PurposeParameters { get; set; }

    [JsonPropertyName("parent_token")]
    public string? ParentToken { get; set; }

    [JsonPropertyName("ttl_hours")]
    public int TtlHours { get; set; }

    [JsonPropertyName("caller_class")]
    public string? CallerClass { get; set; }
}
