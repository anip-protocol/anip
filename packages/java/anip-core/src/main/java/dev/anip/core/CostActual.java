package dev.anip.core;

/**
 * The actual cost incurred by an invocation.
 */
public class CostActual {

    private final FinancialCost financial;
    private final String varianceFromEstimate;

    public CostActual(FinancialCost financial, String varianceFromEstimate) {
        this.financial = financial;
        this.varianceFromEstimate = varianceFromEstimate;
    }

    public FinancialCost getFinancial() {
        return financial;
    }

    public String getVarianceFromEstimate() {
        return varianceFromEstimate;
    }
}
