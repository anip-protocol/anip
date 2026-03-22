using System.Text.Json.Serialization;

namespace Anip.Core;

public class CheckpointDetailResponse
{
    [JsonPropertyName("checkpoint")]
    public Dictionary<string, object>? Checkpoint { get; set; }

    [JsonPropertyName("inclusion_proof")]
    public Dictionary<string, object>? InclusionProof { get; set; }

    [JsonPropertyName("consistency_proof")]
    public Dictionary<string, object>? ConsistencyProof { get; set; }

    [JsonPropertyName("proof_unavailable")]
    public string? ProofUnavailable { get; set; }

    [JsonPropertyName("expires_hint")]
    public string? ExpiresHint { get; set; }
}
