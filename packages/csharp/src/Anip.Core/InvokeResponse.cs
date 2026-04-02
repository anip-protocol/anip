using System.Text.Json.Serialization;

namespace Anip.Core;

public class InvokeResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("invocation_id")]
    public string InvocationId { get; set; } = "";

    [JsonPropertyName("client_reference_id")]
    public string? ClientReferenceId { get; set; }

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("parent_invocation_id")]
    public string? ParentInvocationId { get; set; }

    [JsonPropertyName("upstream_service")]
    public string? UpstreamService { get; set; }

    [JsonPropertyName("result")]
    public object? Result { get; set; }

    [JsonPropertyName("cost_actual")]
    public CostActual? CostActual { get; set; }

    [JsonPropertyName("failure")]
    public AnipError? Failure { get; set; }

    [JsonPropertyName("budget_context")]
    public BudgetContext? BudgetContext { get; set; }
}
