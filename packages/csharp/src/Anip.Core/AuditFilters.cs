using System.Text.Json.Serialization;

namespace Anip.Core;

public class AuditFilters
{
    [JsonPropertyName("capability")]
    public string? Capability { get; set; }

    [JsonPropertyName("root_principal")]
    public string? RootPrincipal { get; set; }

    [JsonPropertyName("since")]
    public string? Since { get; set; }

    [JsonPropertyName("invocation_id")]
    public string? InvocationId { get; set; }

    [JsonPropertyName("client_reference_id")]
    public string? ClientReferenceId { get; set; }

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("parent_invocation_id")]
    public string? ParentInvocationId { get; set; }

    [JsonPropertyName("limit")]
    public int Limit { get; set; }
}
