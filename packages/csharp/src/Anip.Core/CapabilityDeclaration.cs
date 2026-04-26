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

    [JsonPropertyName("requires_binding")]
    public List<BindingRequirement>? RequiresBinding { get; set; }

    [JsonPropertyName("control_requirements")]
    public List<ControlRequirement>? ControlRequirements { get; set; }

    [JsonPropertyName("refresh_via")]
    public List<string>? RefreshVia { get; set; }

    [JsonPropertyName("verify_via")]
    public List<string>? VerifyVia { get; set; }

    [JsonPropertyName("cross_service")]
    public CrossServiceHints? CrossService { get; set; }

    [JsonPropertyName("cross_service_contract")]
    public CrossServiceContract? CrossServiceContract { get; set; }

    // v0.23
    [JsonPropertyName("kind")]
    public string Kind { get; set; } = "atomic";

    [JsonPropertyName("composition")]
    public Composition? Composition { get; set; }

    [JsonPropertyName("grant_policy")]
    public GrantPolicy? GrantPolicy { get; set; }
}
