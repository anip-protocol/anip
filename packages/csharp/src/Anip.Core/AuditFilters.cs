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

    [JsonPropertyName("limit")]
    public int Limit { get; set; }
}
