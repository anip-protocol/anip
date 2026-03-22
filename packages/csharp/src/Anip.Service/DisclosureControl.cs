namespace Anip.Service;

/// <summary>
/// Resolves the effective disclosure level for failure responses.
/// Fixed modes ("full", "reduced", "redacted") pass through.
/// "policy" mode resolves caller class from token claims and applies the policy map.
/// Implements SPEC section 6.9 caller-class-aware disclosure.
/// </summary>
public static class DisclosureControl
{
    /// <summary>
    /// Resolves the effective disclosure level.
    /// </summary>
    public static string Resolve(string level, Dictionary<string, object?>? tokenClaims, Dictionary<string, string>? policy)
    {
        if (level != "policy")
        {
            return level;
        }

        var callerClass = ResolveCallerClass(tokenClaims);

        if (policy == null)
        {
            return "redacted";
        }

        if (policy.TryGetValue(callerClass, out var mapped))
        {
            return mapped;
        }

        if (policy.TryGetValue("default", out var def))
        {
            return def;
        }

        return "redacted";
    }

    /// <summary>
    /// Determines the caller class from token claims.
    /// Priority: 1) explicit anip:caller_class claim, 2) scope-derived, 3) "default".
    /// </summary>
    internal static string ResolveCallerClass(Dictionary<string, object?>? claims)
    {
        if (claims == null)
        {
            return "default";
        }

        if (claims.TryGetValue("anip:caller_class", out var ccObj) && ccObj is string cc && !string.IsNullOrEmpty(cc))
        {
            return cc;
        }

        // Check for scope-derived class.
        if (claims.TryGetValue("scope", out var scopeObj))
        {
            if (scopeObj is List<string> scopes)
            {
                if (scopes.Contains("audit:full"))
                    return "audit_full";
            }
            else if (scopeObj is IEnumerable<object?> scopeList)
            {
                foreach (var item in scopeList)
                {
                    if (item is string str && str == "audit:full")
                        return "audit_full";
                }
            }
        }

        return "default";
    }
}
