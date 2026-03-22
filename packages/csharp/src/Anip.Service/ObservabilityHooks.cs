namespace Anip.Service;

/// <summary>
/// Optional callbacks for logging, metrics, and tracing.
/// All hooks are nil-safe. Panics within hooks are recovered.
/// Hooks must never affect correctness.
/// </summary>
public class ObservabilityHooks
{
    // Logging hooks
    public Action<string, string, string>? OnTokenIssued { get; set; }
    public Action<string, string>? OnTokenResolved { get; set; }
    public Action<string, string, string>? OnInvokeStart { get; set; }
    public Action<string, string, bool, long>? OnInvokeComplete { get; set; }
    public Action<int, string, string>? OnAuditAppend { get; set; }
    public Action<string, int>? OnCheckpointCreated { get; set; }
    public Action<string, string>? OnAuthFailure { get; set; }
    public Action<string, bool>? OnScopeValidation { get; set; }

    // Metrics hooks
    public Action<string, long, bool>? OnInvokeDuration { get; set; }

    /// <summary>
    /// Safely invokes a hook function, recovering from any exceptions.
    /// </summary>
    internal static void CallHook(Action action)
    {
        try
        {
            action();
        }
        catch
        {
            // Hooks must never affect correctness.
        }
    }
}
