using Anip.Core;

namespace Anip.Service;

/// <summary>
/// Configuration for an ANIP service.
/// </summary>
public class ServiceConfig
{
    public string ServiceId { get; set; } = "";
    public List<CapabilityDef> Capabilities { get; set; } = new();

    /// <summary>"sqlite:///path" or ":memory:" (default).</summary>
    public string Storage { get; set; } = ":memory:";

    /// <summary>"signed" or "anchored".</summary>
    public string Trust { get; set; } = "signed";

    /// <summary>Path for key persistence. Null/empty for in-memory keys.</summary>
    public string? KeyPath { get; set; }

    /// <summary>
    /// Bootstrap authentication function. Takes a bearer token string,
    /// returns the principal string or null if not authenticated.
    /// </summary>
    public Func<string, string?>? Authenticate { get; set; }

    /// <summary>Observability hooks (optional).</summary>
    public ObservabilityHooks? Hooks { get; set; }

    /// <summary>Automatic checkpoint scheduling. Null disables.</summary>
    public CheckpointPolicy? CheckpointPolicy { get; set; }

    /// <summary>
    /// How often the retention sweep runs in seconds (default 60).
    /// Set to -1 to disable automatic retention enforcement.
    /// </summary>
    public int RetentionIntervalSeconds { get; set; } = 60;

    /// <summary>
    /// Event class to tier to duration mapping.
    /// Null uses defaults.
    /// </summary>
    public RetentionPolicy? RetentionPolicy { get; set; }

    /// <summary>
    /// Controls failure detail disclosure.
    /// One of "full", "reduced", "redacted", "policy". Default: "full".
    /// </summary>
    public string DisclosureLevel { get; set; } = "full";

    /// <summary>
    /// Maps caller classes to disclosure levels.
    /// Only used when DisclosureLevel is "policy".
    /// </summary>
    public Dictionary<string, string>? DisclosurePolicy { get; set; }

    /// <summary>
    /// Aggregation window size in seconds.
    /// 0 or negative disables aggregation. Default: 0 (disabled).
    /// </summary>
    public int AggregationWindowSeconds { get; set; }
}
