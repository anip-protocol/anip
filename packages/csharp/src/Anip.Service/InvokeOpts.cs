namespace Anip.Service;

/// <summary>
/// Optional parameters for capability invocation.
/// </summary>
public class InvokeOpts
{
    public string? ClientReferenceId { get; set; }
    public bool Stream { get; set; }
}
