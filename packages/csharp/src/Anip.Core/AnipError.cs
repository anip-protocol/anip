using System.Text.Json.Serialization;

namespace Anip.Core;

public class AnipError : Exception
{
    [JsonPropertyName("type")]
    public string ErrorType { get; }

    [JsonPropertyName("detail")]
    public string Detail { get; }

    [JsonPropertyName("resolution")]
    public Resolution? Resolution { get; set; }

    [JsonPropertyName("retry")]
    public bool Retry { get; set; }

    // v0.23: present iff ErrorType == "approval_required"
    [JsonPropertyName("approval_required")]
    public ApprovalRequiredMetadata? ApprovalRequired { get; set; }

    public AnipError(string errorType, string detail, Resolution? resolution = null, bool retry = false)
        : base(detail)
    {
        ErrorType = errorType;
        Detail = detail;
        Resolution = resolution;
        Retry = retry;
    }

    public AnipError WithResolution(string action)
    {
        Resolution = new Resolution { Action = action, RecoveryClass = Constants.RecoveryClassForAction(action) };
        return this;
    }

    public AnipError WithRetry()
    {
        Retry = true;
        return this;
    }

    /// <summary>v0.23: attach approval-required metadata.</summary>
    public AnipError WithApprovalRequired(ApprovalRequiredMetadata metadata)
    {
        ApprovalRequired = metadata;
        return this;
    }
}

public class Resolution
{
    [JsonPropertyName("action")]
    public string Action { get; set; } = "";

    [JsonPropertyName("recovery_class")]
    public string RecoveryClass { get; set; } = "";

    [JsonPropertyName("requires")]
    public string? Requires { get; set; }

    [JsonPropertyName("grantable_by")]
    public string? GrantableBy { get; set; }

    [JsonPropertyName("estimated_availability")]
    public string? EstimatedAvailability { get; set; }

    [JsonPropertyName("recovery_target")]
    public RecoveryTarget? RecoveryTarget { get; set; }
}
