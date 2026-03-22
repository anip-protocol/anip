using System.Text.Json.Serialization;

namespace Anip.Core;

public class CapabilityDeclaration
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("description")]
    public string Description { get; set; } = "";

    [JsonPropertyName("contract_version")]
    public string ContractVersion { get; set; } = "";

    [JsonPropertyName("inputs")]
    public List<CapabilityInput> Inputs { get; set; } = new();

    [JsonPropertyName("output")]
    public CapabilityOutput Output { get; set; } = new();

    [JsonPropertyName("side_effect")]
    public SideEffect SideEffect { get; set; } = new();

    [JsonPropertyName("minimum_scope")]
    public List<string> MinimumScope { get; set; } = new();

    [JsonPropertyName("cost")]
    public Cost? Cost { get; set; }

    [JsonPropertyName("requires")]
    public List<CapabilityRequirement>? Requires { get; set; }

    [JsonPropertyName("composes_with")]
    public List<CapabilityComposition>? ComposesWith { get; set; }

    [JsonPropertyName("session")]
    public SessionInfo? Session { get; set; }

    [JsonPropertyName("observability")]
    public ObservabilityContract? Observability { get; set; }

    [JsonPropertyName("response_modes")]
    public List<string>? ResponseModes { get; set; }
}
