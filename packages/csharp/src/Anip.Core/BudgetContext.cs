using System.Text.Json.Serialization;

namespace Anip.Core;

public class BudgetContext
{
    [JsonPropertyName("budget_max")]
    public double BudgetMax { get; set; }

    [JsonPropertyName("budget_currency")]
    public string BudgetCurrency { get; set; } = "";

    [JsonPropertyName("cost_check_amount")]
    public double? CostCheckAmount { get; set; }

    [JsonPropertyName("cost_certainty")]
    public string? CostCertainty { get; set; }

    [JsonPropertyName("cost_actual")]
    public double? CostActual { get; set; }

    [JsonPropertyName("within_budget")]
    public bool WithinBudget { get; set; }
}
