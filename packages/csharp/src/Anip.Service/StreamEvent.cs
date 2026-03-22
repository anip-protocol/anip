namespace Anip.Service;

/// <summary>
/// Represents a single SSE event in a streaming invocation.
/// </summary>
public class StreamEvent
{
    /// <summary>Event type: "progress", "completed", or "failed".</summary>
    public string Type { get; set; } = "";

    /// <summary>Full SSE data payload.</summary>
    public Dictionary<string, object?> Payload { get; set; } = new();
}
