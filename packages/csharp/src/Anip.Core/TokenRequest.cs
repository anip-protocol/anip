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

    /// <summary>Token ID string of the parent token (not a JWT). The service looks up the parent by ID in storage.</summary>
    [JsonPropertyName("parent_token")]
    public string? ParentToken { get; set; }

    [JsonPropertyName("ttl_hours")]
    public int TtlHours { get; set; }

    [JsonPropertyName("caller_class")]
    public string? CallerClass { get; set; }

    [JsonPropertyName("budget")]
    public Budget? Budget { get; set; }

    /// <summary>"allowed" or "exclusive"; defaults to "allowed" if null.</summary>
    [JsonPropertyName("concurrent_branches")]
    public string? ConcurrentBranches { get; set; }

    /// <summary>
    /// v0.23: bind a session identity to the issued token. Required for
    /// callers that intend to redeem session_bound ApprovalGrants. Only
    /// honored at root issuance — child tokens inherit parent.SessionId
    /// verbatim. SPEC §4.8.
    /// </summary>
    [JsonPropertyName("session_id")]
    public string? SessionId { get; set; }
}
