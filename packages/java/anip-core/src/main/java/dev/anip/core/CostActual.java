package dev.anip.core;

/**
 * The actual cost incurred by an invocation.
 */
public class CostActual {

    private FinancialCost financial;
    private String varianceFromEstimate;

    /** No-arg constructor for Jackson deserialization. */
    public CostActual() {}

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

    public void setFinancial(FinancialCost financial) {
        this.financial = financial;
    }

    public void setVarianceFromEstimate(String varianceFromEstimate) {
        this.varianceFromEstimate = varianceFromEstimate;
    }
}
