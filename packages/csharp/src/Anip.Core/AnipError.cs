using System.Text.Json.Serialization;

namespace Anip.Core;

/// <summary>
/// Represents a canonical ANIP invocation failure returned by service runtimes.
/// </summary>
public class AnipError : Exception
{
    /// <summary>
    /// Canonical ANIP failure type, such as <c>clarification_required</c>,
    /// <c>approval_required</c>, or <c>denied</c>.
    /// </summary>
    [JsonPropertyName("type")]
    public string ErrorType { get; }

    /// <summary>
    /// Human-readable failure detail suitable for diagnostics or user-facing recovery guidance.
    /// </summary>
    [JsonPropertyName("detail")]
    public string Detail { get; }

    /// <summary>
    /// Optional recovery instruction that tells the caller how the failure may be resolved.
    /// </summary>
    [JsonPropertyName("resolution")]
    public Resolution? Resolution { get; set; }

    /// <summary>
    /// Indicates whether the caller may retry the invocation without changing inputs or authority.
    /// </summary>
    [JsonPropertyName("retry")]
    public bool Retry { get; set; }

    /// <summary>
    /// Approval metadata supplied when <see cref="ErrorType"/> is <c>approval_required</c>.
    /// </summary>
    [JsonPropertyName("approval_required")]
    public ApprovalRequiredMetadata? ApprovalRequired { get; set; }

    /// <summary>
    /// Creates a canonical ANIP error.
    /// </summary>
    /// <param name="errorType">Canonical failure type.</param>
    /// <param name="detail">Human-readable failure detail.</param>
    /// <param name="resolution">Optional recovery instruction.</param>
    /// <param name="retry">Whether the caller may retry without changing request context.</param>
    public AnipError(string errorType, string detail, Resolution? resolution = null, bool retry = false)
        : base(detail)
    {
        ErrorType = errorType;
        Detail = detail;
        Resolution = resolution;
        Retry = retry;
    }

    /// <summary>
    /// Attaches a canonical recovery action to this error.
    /// </summary>
    /// <param name="action">Canonical recovery action.</param>
    /// <returns>The same error instance for fluent construction.</returns>
    public AnipError WithResolution(string action)
    {
        Resolution = new Resolution { Action = action, RecoveryClass = Constants.RecoveryClassForAction(action) };
        return this;
    }

    /// <summary>
    /// Marks this error as retryable.
    /// </summary>
    /// <returns>The same error instance for fluent construction.</returns>
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

/// <summary>
/// Describes the recovery action and recovery class for an ANIP failure.
/// </summary>
public class Resolution
{
    /// <summary>
    /// Canonical recovery action, such as <c>obtain_binding</c> or <c>request_approval</c>.
    /// </summary>
    [JsonPropertyName("action")]
    public string Action { get; set; } = "";

    /// <summary>
    /// Canonical recovery class derived from <see cref="Action"/> when not explicitly supplied.
    /// </summary>
    [JsonPropertyName("recovery_class")]
    public string RecoveryClass { get; set; } = "";

    /// <summary>
    /// Optional missing requirement that must be supplied before retrying.
    /// </summary>
    [JsonPropertyName("requires")]
    public string? Requires { get; set; }

    /// <summary>
    /// Optional actor or role that can grant the missing authority.
    /// </summary>
    [JsonPropertyName("grantable_by")]
    public string? GrantableBy { get; set; }

    /// <summary>
    /// Optional service-estimated availability for retryable or temporarily unavailable work.
    /// </summary>
    [JsonPropertyName("estimated_availability")]
    public string? EstimatedAvailability { get; set; }

    /// <summary>
    /// Optional structured target that should receive the recovery action.
    /// </summary>
    [JsonPropertyName("recovery_target")]
    public RecoveryTarget? RecoveryTarget { get; set; }
}
