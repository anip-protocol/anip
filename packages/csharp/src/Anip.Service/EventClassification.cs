namespace Anip.Service;

/// <summary>
/// Assigns event classes to audit entries based on side-effect type, success, and failure type.
/// Implements SPEC section 6.8 event classification.
/// </summary>
public static class EventClassification
{
    /// <summary>
    /// Classifies an event into one of the standard event classes.
    /// </summary>
    public static string Classify(string? sideEffectType, bool success, string? failureType)
    {
        if (string.IsNullOrEmpty(sideEffectType))
        {
            return "malformed_or_spam";
        }

        if (success)
        {
            if (IsHighRiskSideEffect(sideEffectType))
            {
                return "high_risk_success";
            }
            return "low_risk_success";
        }

        if (IsMalformedFailureType(failureType))
        {
            return "malformed_or_spam";
        }

        return "high_risk_denial";
    }

    private static bool IsHighRiskSideEffect(string sideEffectType)
    {
        return sideEffectType is "write" or "irreversible" or "transactional";
    }

    private static bool IsMalformedFailureType(string? failureType)
    {
        return failureType is "unknown_capability" or "streaming_not_supported" or "internal_error";
    }
}
