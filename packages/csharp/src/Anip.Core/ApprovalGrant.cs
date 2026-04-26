using System.Text.Json.Serialization;

namespace Anip.Core;

/// <summary>Constrains what an approver MAY issue for a given approval request. v0.23. See SPEC.md §4.7.</summary>
public class GrantPolicy
{
    [JsonPropertyName("allowed_grant_types")]
    public List<string> AllowedGrantTypes { get; set; } = new();

    [JsonPropertyName("default_grant_type")]
    public string DefaultGrantType { get; set; } = "one_time";

    [JsonPropertyName("expires_in_seconds")]
    public int ExpiresInSeconds { get; set; }

    [JsonPropertyName("max_uses")]
    public int MaxUses { get; set; }

    /// <summary>
    /// Enforces SPEC.md §4.7 invariants. Throws ArgumentException when malformed.
    /// Callers (issuance helpers, schema validators) MUST invoke this before trusting the policy.
    /// </summary>
    public void Validate()
    {
        if (AllowedGrantTypes == null || AllowedGrantTypes.Count == 0)
        {
            throw new ArgumentException("GrantPolicy.AllowedGrantTypes must be non-empty");
        }
        if (string.IsNullOrEmpty(DefaultGrantType))
        {
            throw new ArgumentException("GrantPolicy.DefaultGrantType must be set");
        }
        if (!AllowedGrantTypes.Contains(DefaultGrantType))
        {
            throw new ArgumentException(
                $"GrantPolicy.DefaultGrantType='{DefaultGrantType}' must appear in AllowedGrantTypes=[{string.Join(",", AllowedGrantTypes)}]");
        }
    }
}

/// <summary>Metadata attached to an approval_required failure response. v0.23. See SPEC.md §4.7.</summary>
public class ApprovalRequiredMetadata
{
    [JsonPropertyName("approval_request_id")]
    public string ApprovalRequestId { get; set; } = "";

    [JsonPropertyName("preview_digest")]
    public string PreviewDigest { get; set; } = "";

    [JsonPropertyName("requested_parameters_digest")]
    public string RequestedParametersDigest { get; set; } = "";

    [JsonPropertyName("grant_policy")]
    public GrantPolicy GrantPolicy { get; set; } = new();
}

/// <summary>Persistent record of a request for human/principal approval. v0.23. See SPEC.md §4.7.</summary>
public class ApprovalRequest
{
    public const string StatusPending = "pending";
    public const string StatusApproved = "approved";
    public const string StatusDenied = "denied";
    public const string StatusExpired = "expired";

    [JsonPropertyName("approval_request_id")]
    public string ApprovalRequestId { get; set; } = "";

    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("scope")]
    public List<string> Scope { get; set; } = new();

    [JsonPropertyName("requester")]
    public Dictionary<string, object> Requester { get; set; } = new();

    [JsonPropertyName("parent_invocation_id")]
    public string? ParentInvocationId { get; set; }

    [JsonPropertyName("preview")]
    public Dictionary<string, object> Preview { get; set; } = new();

    [JsonPropertyName("preview_digest")]
    public string PreviewDigest { get; set; } = "";

    [JsonPropertyName("requested_parameters")]
    public Dictionary<string, object> RequestedParameters { get; set; } = new();

    [JsonPropertyName("requested_parameters_digest")]
    public string RequestedParametersDigest { get; set; } = "";

    [JsonPropertyName("grant_policy")]
    public GrantPolicy GrantPolicy { get; set; } = new();

    [JsonPropertyName("status")]
    public string Status { get; set; } = StatusPending;

    [JsonPropertyName("approver")]
    public Dictionary<string, object>? Approver { get; set; }

    [JsonPropertyName("decided_at")]
    public string? DecidedAt { get; set; }

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = "";

    [JsonPropertyName("expires_at")]
    public string ExpiresAt { get; set; } = "";
}

/// <summary>Signed authorization object issued after approval. v0.23. See SPEC.md §4.8.</summary>
public class ApprovalGrant
{
    public const string TypeOneTime = "one_time";
    public const string TypeSessionBound = "session_bound";

    [JsonPropertyName("grant_id")]
    public string GrantId { get; set; } = "";

    [JsonPropertyName("approval_request_id")]
    public string ApprovalRequestId { get; set; } = "";

    [JsonPropertyName("grant_type")]
    public string GrantType { get; set; } = "";

    [JsonPropertyName("capability")]
    public string Capability { get; set; } = "";

    [JsonPropertyName("scope")]
    public List<string> Scope { get; set; } = new();

    [JsonPropertyName("approved_parameters_digest")]
    public string ApprovedParametersDigest { get; set; } = "";

    [JsonPropertyName("preview_digest")]
    public string PreviewDigest { get; set; } = "";

    [JsonPropertyName("requester")]
    public Dictionary<string, object> Requester { get; set; } = new();

    [JsonPropertyName("approver")]
    public Dictionary<string, object> Approver { get; set; } = new();

    [JsonPropertyName("issued_at")]
    public string IssuedAt { get; set; } = "";

    [JsonPropertyName("expires_at")]
    public string ExpiresAt { get; set; } = "";

    [JsonPropertyName("max_uses")]
    public int MaxUses { get; set; }

    [JsonPropertyName("use_count")]
    public int UseCount { get; set; } = 0;

    [JsonPropertyName("session_id")]
    public string? SessionId { get; set; }

    [JsonPropertyName("signature")]
    public string Signature { get; set; } = "";
}

/// <summary>Request body for POST {approval_grants}. v0.23. See SPEC.md §4.9.</summary>
public class IssueApprovalGrantRequest
{
    [JsonPropertyName("approval_request_id")]
    public string ApprovalRequestId { get; set; } = "";

    [JsonPropertyName("grant_type")]
    public string GrantType { get; set; } = "";

    [JsonPropertyName("session_id")]
    public string? SessionId { get; set; }

    [JsonPropertyName("expires_in_seconds")]
    public int? ExpiresInSeconds { get; set; }

    [JsonPropertyName("max_uses")]
    public int? MaxUses { get; set; }
}

/// <summary>Response body for POST {approval_grants}. v0.23. See SPEC.md §4.9.</summary>
public class IssueApprovalGrantResponse
{
    [JsonPropertyName("grant")]
    public ApprovalGrant Grant { get; set; } = new();
}
