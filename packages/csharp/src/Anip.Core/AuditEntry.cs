using System.Text.Json.Serialization;

namespace Anip.Core;

public class AuditEntry
{
    [JsonPropertyName("sequence_number")]
    public int SequenceNumber { get; set; }

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("token_id")]
    public string? TokenId { get; set; }

    [JsonPropertyName("issuer")]
    public string? Issuer { get; set; }

    [JsonPropertyName("subject")]
    public string? Subject { get; set; }

    [JsonPropertyName("root_principal")]
    public string? RootPrincipal { get; set; }

    [JsonPropertyName("parameters")]
    public Dictionary<string, object>? Parameters { get; set; }

    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("result_summary")]
    public Dictionary<string, object>? ResultSummary { get; set; }

    [JsonPropertyName("failure_type")]
    public string? FailureType { get; set; }

    [JsonPropertyName("cost_actual")]
    public CostActual? CostActual { get; set; }

    [JsonPropertyName("delegation_chain")]
    public List<string>? DelegationChain { get; set; }

    [JsonPropertyName("invocation_id")]
    public string? InvocationId { get; set; }

    [JsonPropertyName("client_reference_id")]
    public string? ClientReferenceId { get; set; }

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("parent_invocation_id")]
    public string? ParentInvocationId { get; set; }

    [JsonPropertyName("upstream_service")]
    public string? UpstreamService { get; set; }

    [JsonPropertyName("previous_hash")]
    public string? PreviousHash { get; set; }

    [JsonPropertyName("signature")]
    public string? Signature { get; set; }

    [JsonPropertyName("event_class")]
    public string? EventClass { get; set; }

    [JsonPropertyName("retention_tier")]
    public string? RetentionTier { get; set; }

    [JsonPropertyName("expires_at")]
    public string? ExpiresAt { get; set; }

    [JsonPropertyName("storage_redacted")]
    public bool StorageRedacted { get; set; }

    [JsonPropertyName("entry_type")]
    public string? EntryType { get; set; }

    [JsonPropertyName("grouping_key")]
    public Dictionary<string, string>? GroupingKey { get; set; }

    [JsonPropertyName("aggregation_window")]
    public Dictionary<string, string>? AggregationWindow { get; set; }

    [JsonPropertyName("aggregation_count")]
    public int AggregationCount { get; set; }

    [JsonPropertyName("first_seen")]
    public string? FirstSeen { get; set; }

    [JsonPropertyName("last_seen")]
    public string? LastSeen { get; set; }

    [JsonPropertyName("representative_detail")]
    public string? RepresentativeDetail { get; set; }

    [JsonPropertyName("stream_summary")]
    public Dictionary<string, object>? StreamSummary { get; set; }
}
