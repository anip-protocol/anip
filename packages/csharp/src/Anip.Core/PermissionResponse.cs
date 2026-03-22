using System.Text.Json.Serialization;

namespace Anip.Core;

public class PermissionResponse
{
    [JsonPropertyName("available")]
    public List<AvailableCapability> Available { get; set; } = new();

    [JsonPropertyName("restricted")]
    public List<RestrictedCapability> Restricted { get; set; } = new();

    [JsonPropertyName("denied")]
    public List<DeniedCapability> Denied { get; set; } = new();
}
