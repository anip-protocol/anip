using System.Text.Json.Serialization;

namespace Anip.Core;

public class DelegationConstraints
{
    [JsonPropertyName("max_delegation_depth")]
    public int MaxDelegationDepth { get; set; }

    [JsonPropertyName("concurrent_branches")]
    public string ConcurrentBranches { get; set; } = "";

    [JsonPropertyName("budget")]
    public Budget? Budget { get; set; }
}
