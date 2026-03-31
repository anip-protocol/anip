package dev.anip.core;

/**
 * Provides budget evaluation details in invocation responses.
 */
public class BudgetContext {

    private final double budgetMax;
    private final String budgetCurrency;
    private final Double costCheckAmount;
    private final String costCertainty;
    private final Double costActual;
    private final boolean withinBudget;

    public BudgetContext(double budgetMax, String budgetCurrency,
                         Double costCheckAmount, String costCertainty,
                         Double costActual, boolean withinBudget) {
        this.budgetMax = budgetMax;
        this.budgetCurrency = budgetCurrency;
        this.costCheckAmount = costCheckAmount;
        this.costCertainty = costCertainty;
        this.costActual = costActual;
        this.withinBudget = withinBudget;
    }

    public double getBudgetMax() {
        return budgetMax;
    }

    public String getBudgetCurrency() {
        return budgetCurrency;
    }

    public Double getCostCheckAmount() {
        return costCheckAmount;
    }

    public String getCostCertainty() {
        return costCertainty;
    }

    public Double getCostActual() {
        return costActual;
    }

    public boolean isWithinBudget() {
        return withinBudget;
    }
}
