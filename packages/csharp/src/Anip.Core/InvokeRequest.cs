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

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("parent_invocation_id")]
    public string? ParentInvocationId { get; set; }

    [JsonPropertyName("upstream_service")]
    public string? UpstreamService { get; set; }

    [JsonPropertyName("stream")]
    public bool Stream { get; set; }

    // v0.23: grant_id supplied on continuation invocations
    [JsonPropertyName("approval_grant")]
    public string? ApprovalGrant { get; set; }
}
