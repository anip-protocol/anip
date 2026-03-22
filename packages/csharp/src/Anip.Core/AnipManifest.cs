using System.Text.Json.Serialization;

namespace Anip.Core;

public class AnipManifest
{
    [JsonPropertyName("protocol")]
    public string Protocol { get; set; } = "";

    [JsonPropertyName("profile")]
    public ProfileVersions Profile { get; set; } = new();

    [JsonPropertyName("capabilities")]
    public Dictionary<string, CapabilityDeclaration> Capabilities { get; set; } = new();

    [JsonPropertyName("manifest_metadata")]
    public ManifestMetadata? ManifestMetadata { get; set; }

    [JsonPropertyName("service_identity")]
    public ServiceIdentity? ServiceIdentity { get; set; }

    [JsonPropertyName("trust")]
    public TrustPosture? Trust { get; set; }
}
