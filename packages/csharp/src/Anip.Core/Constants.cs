namespace Anip.Core;

public static class Constants
{
    public const string ProtocolVersion = "anip/0.14";
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
            or FailureControlRequirementUnsatisfied or FailurePurposeMismatch => 403,
        FailureUnknownCapability or FailureNotFound => 404,
        FailureUnavailable or FailureConcurrentLock => 409,
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
