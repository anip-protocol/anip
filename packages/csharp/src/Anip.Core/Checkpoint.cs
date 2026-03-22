using System.Text.Json.Serialization;

namespace Anip.Core;

public class Checkpoint
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("service_id")]
    public string ServiceId { get; set; } = "";

    [JsonPropertyName("checkpoint_id")]
    public string CheckpointId { get; set; } = "";

    [JsonPropertyName("range")]
    public Dictionary<string, int> Range { get; set; } = new();

    [JsonPropertyName("merkle_root")]
    public string MerkleRoot { get; set; } = "";

    [JsonPropertyName("previous_checkpoint")]
    public string? PreviousCheckpoint { get; set; }

    [JsonPropertyName("timestamp")]
    public string Timestamp { get; set; } = "";

    [JsonPropertyName("entry_count")]
    public int EntryCount { get; set; }
}
