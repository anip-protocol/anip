package dev.anip.core;

import java.util.Map;

/**
 * The actual cost incurred by an invocation.
 */
public class CostActual {

    private final Map<String, Object> financial;
    private final String varianceFromEstimate;

    public CostActual(Map<String, Object> financial, String varianceFromEstimate) {
        this.financial = financial;
        this.varianceFromEstimate = varianceFromEstimate;
    }

    public Map<String, Object> getFinancial() {
        return financial;
    }

    public String getVarianceFromEstimate() {
        return varianceFromEstimate;
    }
}
