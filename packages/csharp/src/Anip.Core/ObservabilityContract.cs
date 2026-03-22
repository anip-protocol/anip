using System.Text.Json.Serialization;

namespace Anip.Core;

public class ObservabilityContract
{
    [JsonPropertyName("logged")]
    public bool Logged { get; set; }

    [JsonPropertyName("retention")]
    public string Retention { get; set; } = "";

    [JsonPropertyName("fields_logged")]
    public List<string> FieldsLogged { get; set; } = new();

    [JsonPropertyName("audit_accessible_by")]
    public List<string> AuditAccessibleBy { get; set; } = new();
}
