using System.Text.Json.Serialization;

namespace Anip.Core;

/// <summary>One ordered step in a composed capability. v0.23. See SPEC.md §4.6.</summary>
public class CompositionStep
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = "";

    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("empty_result_source")]
    public bool EmptyResultSource { get; set; } = false;

    [JsonPropertyName("empty_result_path")]
    public string? EmptyResultPath { get; set; }
}

/// <summary>Per-child-outcome failure handling for composed capabilities. v0.23. See SPEC.md §4.6.</summary>
public class FailurePolicy
{
    [JsonPropertyName("child_clarification")]
    public string ChildClarification { get; set; } = "propagate";

    [JsonPropertyName("child_denial")]
    public string ChildDenial { get; set; } = "propagate";

    [JsonPropertyName("child_approval_required")]
    public string ChildApprovalRequired { get; set; } = "propagate";

    [JsonPropertyName("child_error")]
    public string ChildError { get; set; } = "fail_parent";
}

/// <summary>Audit behavior for composed capabilities. v0.23. See SPEC.md §4.6.</summary>
public class AuditPolicy
{
    [JsonPropertyName("record_child_invocations")]
    public bool RecordChildInvocations { get; set; }

    [JsonPropertyName("parent_task_lineage")]
    public bool ParentTaskLineage { get; set; }
}

/// <summary>Declarative composition for kind=composed capabilities. v0.23. See SPEC.md §4.6.</summary>
public class Composition
{
    [JsonPropertyName("authority_boundary")]
    public string AuthorityBoundary { get; set; } = "same_service";

    [JsonPropertyName("steps")]
    public List<CompositionStep> Steps { get; set; } = new();

    [JsonPropertyName("input_mapping")]
    public Dictionary<string, Dictionary<string, string>> InputMapping { get; set; } = new();

    [JsonPropertyName("output_mapping")]
    public Dictionary<string, string> OutputMapping { get; set; } = new();

    [JsonPropertyName("empty_result_policy")]
    public string? EmptyResultPolicy { get; set; }

    [JsonPropertyName("empty_result_output")]
    public Dictionary<string, object>? EmptyResultOutput { get; set; }

    [JsonPropertyName("failure_policy")]
    public FailurePolicy FailurePolicy { get; set; } = new();

    [JsonPropertyName("audit_policy")]
    public AuditPolicy AuditPolicy { get; set; } = new();
}
