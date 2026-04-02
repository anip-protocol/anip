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
}
