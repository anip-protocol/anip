package dev.anip.core;

/**
 * Provides budget evaluation details in invocation responses.
 */
public class BudgetContext {

    private double budgetMax;
    private String budgetCurrency;
    private Double costCheckAmount;
    private String costCertainty;
    private Double costActual;
    private boolean withinBudget;

    /** No-arg constructor for Jackson deserialization. */
    public BudgetContext() {}

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

    public void setBudgetMax(double budgetMax) {
        this.budgetMax = budgetMax;
    }

    public void setBudgetCurrency(String budgetCurrency) {
        this.budgetCurrency = budgetCurrency;
    }

    public void setCostCheckAmount(Double costCheckAmount) {
        this.costCheckAmount = costCheckAmount;
    }

    public void setCostCertainty(String costCertainty) {
        this.costCertainty = costCertainty;
    }

    public void setCostActual(Double costActual) {
        this.costActual = costActual;
    }

    public void setWithinBudget(boolean withinBudget) {
        this.withinBudget = withinBudget;
    }
}
