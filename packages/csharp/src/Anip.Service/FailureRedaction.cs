namespace Anip.Service;

/// <summary>
/// Applies disclosure-level redaction to failure responses.
/// Rules: type, retry, resolution.action are never redacted.
/// "full": everything as-is.
/// "reduced": detail truncated to 200 chars, resolution.grantable_by nulled.
/// "redacted": detail replaced with generic message, resolution fields nulled except action.
/// </summary>
public static class FailureRedaction
{
    private static readonly Dictionary<string, string> GenericMessages = new()
    {
        ["scope_insufficient"] = "Insufficient scope for this capability",
        ["invalid_token"] = "Authentication failed",
        ["token_expired"] = "Token has expired",
        ["purpose_mismatch"] = "Token purpose does not match this capability",
        ["insufficient_authority"] = "Insufficient authority for this action",
        ["unknown_capability"] = "Capability not found",
        ["not_found"] = "Resource not found",
        ["unavailable"] = "Service temporarily unavailable",
        ["concurrent_lock"] = "Operation conflict",
        ["internal_error"] = "Internal error",
        ["streaming_not_supported"] = "Streaming not supported for this capability",
        ["scope_escalation"] = "Scope escalation not permitted",
    };

    /// <summary>
    /// Applies disclosure-level redaction to a failure response.
    /// The input is NOT mutated; a new dictionary is returned.
    /// </summary>
    public static Dictionary<string, object?> Redact(Dictionary<string, object?> failure, string level)
    {
        if (level == "full")
        {
            return CopyMap(failure);
        }

        var result = CopyMap(failure);

        if (level == "reduced")
        {
            if (result.TryGetValue("detail", out var detailObj) && detailObj is string detail && detail.Length > 200)
            {
                result["detail"] = detail[..200];
            }

            if (result.TryGetValue("resolution", out var resObj) && resObj is Dictionary<string, object?> res)
            {
                var resCopy = CopyMap(res);
                resCopy["grantable_by"] = null;
                result["resolution"] = resCopy;
            }

            return result;
        }

        // "redacted" mode
        var failType = result.TryGetValue("type", out var typeObj) ? typeObj as string : null;
        if (failType != null && GenericMessages.TryGetValue(failType, out var msg))
        {
            result["detail"] = msg;
        }
        else
        {
            result["detail"] = "Request failed";
        }

        if (result.TryGetValue("resolution", out var resObj2) && resObj2 is Dictionary<string, object?> res2)
        {
            var resCopy = new Dictionary<string, object?>
            {
                ["action"] = res2.TryGetValue("action", out var action) ? action : null,
                ["requires"] = null,
                ["grantable_by"] = null,
                ["estimated_availability"] = null,
            };
            result["resolution"] = resCopy;
        }

        return result;
    }

    private static Dictionary<string, object?> CopyMap(Dictionary<string, object?> source)
    {
        return new Dictionary<string, object?>(source);
    }
}
