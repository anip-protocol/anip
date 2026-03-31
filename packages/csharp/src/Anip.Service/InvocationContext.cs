using Anip.Core;

namespace Anip.Service;

/// <summary>
/// Provides the handler with delegation context for a capability invocation.
/// </summary>
public class InvocationContext
{
    public DelegationToken Token { get; }
    public string RootPrincipal { get; }
    public string Subject { get; }
    public List<string> Scopes { get; }
    public List<string> DelegationChain { get; }
    public string InvocationId { get; }
    public string? ClientReferenceId { get; }
    public string? TaskId { get; }
    public string? ParentInvocationId { get; }
    public CostActual? CostActual { get; set; }
    public Func<Dictionary<string, object?>, bool> EmitProgress { get; }

    public InvocationContext(
        DelegationToken token,
        string rootPrincipal,
        string subject,
        List<string> scopes,
        List<string> delegationChain,
        string invocationId,
        string? clientReferenceId,
        string? taskId,
        string? parentInvocationId,
        Func<Dictionary<string, object?>, bool> emitProgress)
    {
        Token = token;
        RootPrincipal = rootPrincipal;
        Subject = subject;
        Scopes = scopes;
        DelegationChain = delegationChain;
        InvocationId = invocationId;
        ClientReferenceId = clientReferenceId;
        TaskId = taskId;
        ParentInvocationId = parentInvocationId;
        EmitProgress = emitProgress;
    }
}
