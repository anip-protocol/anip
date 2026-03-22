using System.Text.Json.Serialization;

namespace Anip.Core;

public class CheckpointListResponse
{
    [JsonPropertyName("checkpoints")]
    public List<Checkpoint> Checkpoints { get; set; } = new();

    [JsonPropertyName("next_cursor")]
    public string? NextCursor { get; set; }
}
