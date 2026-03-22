namespace Anip.Service;

/// <summary>
/// Configures automatic checkpoint creation.
/// </summary>
public class CheckpointPolicy
{
    /// <summary>How often to check for new entries (default 60 seconds).</summary>
    public int IntervalSeconds { get; set; } = 60;

    /// <summary>Minimum new entries before creating a checkpoint.</summary>
    public int MinEntries { get; set; } = 1;
}
