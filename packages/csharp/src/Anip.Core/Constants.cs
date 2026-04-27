namespace Anip.Core;

public static class Constants
{
    public const string ProtocolVersion = "anip/0.23";
    public const string ManifestVersion = "0.10.0";

    // Failure types
    public const string FailureAuthRequired = "authentication_required";
    public const string FailureInvalidToken = "invalid_token";
    public const string FailureTokenExpired = "token_expired";
    public const string FailureScopeInsufficient = "scope_insufficient";
    public const string FailureUnknownCapability = "unknown_capability";
    public const string FailureBudgetExceeded = "budget_exceeded";
    public const string FailureBudgetCurrencyMismatch = "budget_currency_mismatch";
    public const string FailureBudgetNotEnforceable = "budget_not_enforceable";
    public const string FailureBindingMissing = "binding_missing";
    public const string FailureBindingStale = "binding_stale";
    public const string FailureControlRequirementUnsatisfied = "control_requirement_unsatisfied";
    public const string FailurePurposeMismatch = "purpose_mismatch";
    public const string FailureNotFound = "not_found";
    public const string FailureUnavailable = "unavailable";
    public const string FailureConcurrentLock = "concurrent_lock";
    public const string FailureInternalError = "internal_error";
    public const string FailureStreamingNotSupported = "streaming_not_supported";
    public const string FailureInvalidParameters = "invalid_parameters";
    public const string FailureNonDelegableAction = "non_delegable_action";

    // v0.23 — composition + approval grants. SPEC.md §4.6, §4.7, §4.8, §4.9.
    public const string FailureApprovalRequired = "approval_required";
    public const string FailureGrantNotFound = "grant_not_found";
    public const string FailureGrantExpired = "grant_expired";
    public const string FailureGrantConsumed = "grant_consumed";
    public const string FailureGrantCapabilityMismatch = "grant_capability_mismatch";
    public const string FailureGrantScopeMismatch = "grant_scope_mismatch";
    public const string FailureGrantParamDrift = "grant_param_drift";
    public const string FailureGrantSessionInvalid = "grant_session_invalid";
    public const string FailureApprovalRequestNotFound = "approval_request_not_found";
    public const string FailureApprovalRequestAlreadyDecided = "approval_request_already_decided";
    public const string FailureApprovalRequestExpired = "approval_request_expired";
    public const string FailureApproverNotAuthorized = "approver_not_authorized";
    public const string FailureGrantTypeNotAllowed = "grant_type_not_allowed_by_policy";
    public const string FailureCompositionChildFailed = "composition_child_failed";

    // Maps each canonical resolution action to its recovery class.
    public static readonly Dictionary<string, string> RecoveryClassMap = new()
    {
        ["retry_now"] = "retry_now",
        ["wait_and_retry"] = "wait_then_retry",
        ["obtain_binding"] = "refresh_then_retry",
        ["refresh_binding"] = "refresh_then_retry",
        ["obtain_quote_first"] = "refresh_then_retry",
        ["revalidate_state"] = "revalidate_then_retry",
        ["request_broader_scope"] = "redelegation_then_retry",
        ["request_budget_increase"] = "redelegation_then_retry",
        ["request_budget_bound_delegation"] = "redelegation_then_retry",
        ["request_matching_currency_delegation"] = "redelegation_then_retry",
        ["request_new_delegation"] = "redelegation_then_retry",
        ["request_capability_binding"] = "redelegation_then_retry",
        ["request_deeper_delegation"] = "redelegation_then_retry",
        ["escalate_to_root_principal"] = "terminal",
        ["provide_credentials"] = "retry_now",
        ["check_manifest"] = "revalidate_then_retry",
        ["contact_service_owner"] = "terminal",
    };

    /// <summary>Returns the recovery class for a given action. Throws if unmapped.</summary>
    public static string RecoveryClassForAction(string action)
    {
        if (RecoveryClassMap.TryGetValue(action, out var cls))
            return cls;
        throw new ArgumentException($"No recovery class mapped for action: \"{action}\"");
    }

    // Merkle hash prefixes (RFC 6962)
    public const byte LeafHashPrefix = 0x00;
    public const byte NodeHashPrefix = 0x01;

    public static readonly Dictionary<string, string> DefaultProfile = new()
    {
        ["core"] = "1.0",
        ["cost"] = "1.0",
        ["capability_graph"] = "1.0",
        ["state_session"] = "1.0",
        ["observability"] = "1.0"
    };

    public static int FailureStatusCode(string? failureType) => failureType switch
    {
        FailureAuthRequired or FailureInvalidToken or FailureTokenExpired => 401,
        FailureScopeInsufficient or FailureBudgetExceeded or FailureBudgetCurrencyMismatch
            or FailureBudgetNotEnforceable or FailureBindingMissing or FailureBindingStale
            or FailureControlRequirementUnsatisfied or FailurePurposeMismatch
            or FailureApproverNotAuthorized => 403,
        FailureUnknownCapability or FailureNotFound
            or FailureApprovalRequestNotFound => 404,
        FailureUnavailable or FailureConcurrentLock
            or FailureApprovalRequestAlreadyDecided or FailureApprovalRequestExpired
            or FailureGrantConsumed or FailureGrantExpired => 409,
        FailureInternalError => 500,
        FailureInvalidParameters => 400,
        _ => 400
    };

    public static string GenerateInvocationId()
    {
        var bytes = new byte[6];
        System.Security.Cryptography.RandomNumberGenerator.Fill(bytes);
        return "inv-" + Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
