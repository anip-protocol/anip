using System.Text.RegularExpressions;

namespace Anip.Service;

/// <summary>
/// Implements the two-layer retention model from SPEC section 6.8.
/// Maps event classes to tiers, and tiers to ISO 8601 durations.
/// </summary>
public partial class RetentionPolicy
{
    private static readonly Dictionary<string, string> DefaultClassToTier = new()
    {
        ["high_risk_success"] = "long",
        ["high_risk_denial"] = "medium",
        ["low_risk_success"] = "short",
        ["repeated_low_value_denial"] = "aggregate_only",
        ["malformed_or_spam"] = "short",
    };

    private static readonly Dictionary<string, string> DefaultTierToDuration = new()
    {
        ["long"] = "P365D",
        ["medium"] = "P90D",
        ["short"] = "P7D",
        ["aggregate_only"] = "P1D",
    };

    [GeneratedRegex(@"^P(\d+)D$")]
    private static partial Regex DurationRegex();

    private readonly Dictionary<string, string> _classToTier;
    private readonly Dictionary<string, string> _tierToDuration;

    /// <summary>
    /// Creates a retention policy with optional overrides. Null maps use defaults.
    /// </summary>
    public RetentionPolicy(
        Dictionary<string, string>? classOverrides = null,
        Dictionary<string, string>? tierOverrides = null)
    {
        _classToTier = new Dictionary<string, string>(DefaultClassToTier);
        if (classOverrides != null)
        {
            foreach (var kv in classOverrides)
                _classToTier[kv.Key] = kv.Value;
        }

        _tierToDuration = new Dictionary<string, string>(DefaultTierToDuration);
        if (tierOverrides != null)
        {
            foreach (var kv in tierOverrides)
                _tierToDuration[kv.Key] = kv.Value;
        }
    }

    /// <summary>
    /// Maps an event class to its retention tier.
    /// </summary>
    public string ResolveTier(string eventClass)
    {
        return _classToTier.TryGetValue(eventClass, out var tier) ? tier : "short";
    }

    /// <summary>
    /// Returns an RFC3339 timestamp for when the entry expires.
    /// </summary>
    public string ComputeExpiresAt(string tier, DateTime now)
    {
        if (!_tierToDuration.TryGetValue(tier, out var duration) || string.IsNullOrEmpty(duration))
            return "";

        var days = ParseIsoDurationDays(duration);
        if (days < 0)
            return "";

        return now.AddDays(days).ToString("o");
    }

    /// <summary>
    /// Returns the medium-tier duration string for discovery.
    /// </summary>
    public string DefaultRetention()
    {
        return _tierToDuration.TryGetValue("medium", out var d) ? d : "";
    }

    private static int ParseIsoDurationDays(string duration)
    {
        var match = DurationRegex().Match(duration);
        if (!match.Success)
            return -1;

        return int.Parse(match.Groups[1].Value);
    }
}
