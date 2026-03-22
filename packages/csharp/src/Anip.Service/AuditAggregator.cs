namespace Anip.Service;

/// <summary>
/// Time-window bucketed aggregation for low-value denial events.
/// Implements SPEC section 6.9.
/// </summary>
public class AuditAggregator
{
    private readonly long _windowSeconds;
    private readonly object _lock = new();
    private readonly Dictionary<(string ActorKey, string Capability, string FailureType, long Epoch), Bucket> _windows = new();

    public AuditAggregator(int windowSeconds)
    {
        _windowSeconds = windowSeconds;
    }

    /// <summary>
    /// Adds an event to the aggregator.
    /// </summary>
    public void Submit(Dictionary<string, object?> eventData)
    {
        lock (_lock)
        {
            var actorKey = GetString(eventData, "actor_key") ?? "anonymous";
            var capability = GetString(eventData, "capability") ?? "_pre_auth";
            var failureType = GetString(eventData, "failure_type") ?? "unknown";

            var ts = ParseTimestamp(eventData);
            var epoch = ts.ToUnixTimeSeconds() - (ts.ToUnixTimeSeconds() % _windowSeconds);

            var key = (actorKey, capability, failureType, epoch);

            if (!_windows.TryGetValue(key, out var bucket))
            {
                var detail = GetString(eventData, "detail") ?? "";
                if (detail.Length > 200)
                    detail = detail[..200];

                bucket = new Bucket
                {
                    FirstSeen = ts,
                    LastSeen = ts,
                    RepresentativeDetail = detail,
                };
                _windows[key] = bucket;
            }

            bucket.Events.Add(eventData);
            if (ts > bucket.LastSeen)
                bucket.LastSeen = ts;
        }
    }

    /// <summary>
    /// Closes all windows whose end time is less than or equal to now and returns the results.
    /// Single-event buckets pass through as Dictionary. Multi-event buckets produce AggregatedEntry.
    /// </summary>
    public List<object> Flush(DateTimeOffset now)
    {
        lock (_lock)
        {
            var results = new List<object>();
            var nowUnix = now.ToUnixTimeSeconds();
            var toRemove = new List<(string, string, string, long)>();

            foreach (var (key, bucket) in _windows)
            {
                var windowEnd = key.Epoch + _windowSeconds;
                if (windowEnd > nowUnix)
                    continue; // window still open

                var windowStartStr = DateTimeOffset.FromUnixTimeSeconds(key.Epoch).UtcDateTime.ToString("o");
                var windowEndStr = DateTimeOffset.FromUnixTimeSeconds(windowEnd).UtcDateTime.ToString("o");

                if (bucket.Events.Count == 1)
                {
                    results.Add(bucket.Events[0]);
                }
                else
                {
                    results.Add(new AggregatedEntry
                    {
                        EventClass = "repeated_low_value_denial",
                        RetentionTier = "aggregate_only",
                        GroupingKey = new Dictionary<string, string>
                        {
                            ["actor_key"] = key.ActorKey,
                            ["capability"] = key.Capability,
                            ["failure_type"] = key.FailureType,
                        },
                        WindowStart = windowStartStr,
                        WindowEnd = windowEndStr,
                        Count = bucket.Events.Count,
                        FirstSeen = bucket.FirstSeen.UtcDateTime.ToString("o"),
                        LastSeen = bucket.LastSeen.UtcDateTime.ToString("o"),
                        RepresentativeDetail = bucket.RepresentativeDetail,
                    });
                }

                toRemove.Add(key);
            }

            foreach (var key in toRemove)
                _windows.Remove(key);

            return results;
        }
    }

    private static string? GetString(Dictionary<string, object?> dict, string key)
    {
        return dict.TryGetValue(key, out var val) ? val as string : null;
    }

    private static DateTimeOffset ParseTimestamp(Dictionary<string, object?> eventData)
    {
        if (eventData.TryGetValue("timestamp", out var tsObj) && tsObj is string ts)
        {
            if (DateTimeOffset.TryParse(ts, out var parsed))
                return parsed;
        }
        return DateTimeOffset.UtcNow;
    }

    private class Bucket
    {
        public List<Dictionary<string, object?>> Events { get; } = new();
        public DateTimeOffset FirstSeen { get; set; }
        public DateTimeOffset LastSeen { get; set; }
        public string RepresentativeDetail { get; set; } = "";
    }
}

/// <summary>
/// Emitted when a window closes with more than one event for a grouping key.
/// </summary>
public class AggregatedEntry
{
    public string EventClass { get; set; } = "";
    public string RetentionTier { get; set; } = "";
    public Dictionary<string, string> GroupingKey { get; set; } = new();
    public string WindowStart { get; set; } = "";
    public string WindowEnd { get; set; } = "";
    public int Count { get; set; }
    public string FirstSeen { get; set; } = "";
    public string LastSeen { get; set; } = "";
    public string RepresentativeDetail { get; set; } = "";

    /// <summary>
    /// Converts to a dictionary suitable for audit persistence.
    /// </summary>
    public Dictionary<string, object?> ToAuditDict()
    {
        return new Dictionary<string, object?>
        {
            ["entry_type"] = "aggregated",
            ["event_class"] = EventClass,
            ["retention_tier"] = RetentionTier,
            ["grouping_key"] = GroupingKey,
            ["aggregation_window"] = new Dictionary<string, string> { ["start"] = WindowStart, ["end"] = WindowEnd },
            ["aggregation_count"] = Count,
            ["count"] = Count,
            ["first_seen"] = FirstSeen,
            ["last_seen"] = LastSeen,
            ["representative_detail"] = RepresentativeDetail,
            ["capability"] = GroupingKey.TryGetValue("capability", out var cap) ? cap : null,
            ["failure_type"] = GroupingKey.TryGetValue("failure_type", out var ft) ? ft : null,
            ["success"] = false,
        };
    }
}
