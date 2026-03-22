namespace Anip.Service;

/// <summary>
/// Strips parameters from low-value audit entries before persistence.
/// Implements SPEC section 6.10.
/// Returns a shallow copy -- does not mutate the input.
/// </summary>
public static class StorageRedaction
{
    /// <summary>
    /// Redacts storage entries by stripping parameters from low-value events.
    /// </summary>
    public static Dictionary<string, object?> RedactEntry(Dictionary<string, object?> entry)
    {
        var result = new Dictionary<string, object?>(entry);

        var ec = result.TryGetValue("event_class", out var ecObj) ? ecObj as string : null;

        if (IsLowValueClass(ec))
        {
            result["parameters"] = null;
            result["storage_redacted"] = true;
        }
        else
        {
            result["storage_redacted"] = false;
        }

        return result;
    }

    private static bool IsLowValueClass(string? ec)
    {
        return ec is "low_risk_success" or "malformed_or_spam" or "repeated_low_value_denial";
    }
}
