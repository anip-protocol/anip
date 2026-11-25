namespace Anip.Service;

/// <summary>
/// Optional parameters for capability invocation.
/// </summary>
public class InvokeOpts
{
    public string? ClientReferenceId { get; set; }
    public string? TaskId { get; set; }
    public string? ParentInvocationId { get; set; }
    public string? UpstreamService { get; set; }
    public bool Stream { get; set; }
    public Anip.Core.Budget? Budget { get; set; }
    public List<string> RequestedEffects { get; set; } = new();

    /// <summary>
    /// v0.23: continuation grant ID supplied with an invoke. Carries Phase A+B
    /// validation when set. SPEC.md §4.8.
    /// </summary>
    public string? ApprovalGrant { get; set; }

    /// <summary>
    /// Reads <c>approval_grant</c> from a decoded request member. Returns
    /// null when the member is absent or null (no grant supplied), the string
    /// when it is one, and <c>""</c> for any other value. A supplied grant is
    /// always validated by the service, and a blank one names no grant.
    /// </summary>
    public static string? ApprovalGrantFromRequest(object? value)
    {
        switch (value)
        {
            case null:
                return null;
            case string text:
                return text;
            case System.Text.Json.JsonElement element:
                return element.ValueKind switch
                {
                    System.Text.Json.JsonValueKind.Null or System.Text.Json.JsonValueKind.Undefined => null,
                    System.Text.Json.JsonValueKind.String => element.GetString(),
                    _ => "",
                };
            default:
                return "";
        }
    }
}
