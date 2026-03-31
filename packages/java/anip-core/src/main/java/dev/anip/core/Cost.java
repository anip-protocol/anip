package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * Describes the cost characteristics of a capability.
 */
public class Cost {

    private String certainty;
    private FinancialCost financial;
    private String determinedBy;
    private List<String> factors;
    private Map<String, Object> compute;
    private Map<String, Object> rateLimit;

    /** No-arg constructor for Jackson deserialization. */
    public Cost() {}

    public Cost(String certainty, FinancialCost financial, String determinedBy,
                List<String> factors, Map<String, Object> compute, Map<String, Object> rateLimit) {
        this.certainty = certainty;
        this.financial = financial;
        this.determinedBy = determinedBy;
        this.factors = factors;
        this.compute = compute;
        this.rateLimit = rateLimit;
    }

    /** Cost certainty: "fixed", "estimated", "dynamic". */
    public String getCertainty() {
        return certainty;
    }

    public FinancialCost getFinancial() {
        return financial;
    }

    /** Capability that resolves actual cost. */
    public String getDeterminedBy() {
        return determinedBy;
    }

    /** What drives cost variation (for dynamic). */
    public List<String> getFactors() {
        return factors;
    }

    public Map<String, Object> getCompute() {
        return compute;
    }

    public Map<String, Object> getRateLimit() {
        return rateLimit;
    }

    public void setCertainty(String certainty) {
        this.certainty = certainty;
    }

    public void setFinancial(FinancialCost financial) {
        this.financial = financial;
    }

    public void setDeterminedBy(String determinedBy) {
        this.determinedBy = determinedBy;
    }

    public void setFactors(List<String> factors) {
        this.factors = factors;
    }

    public void setCompute(Map<String, Object> compute) {
        this.compute = compute;
    }

    public void setRateLimit(Map<String, Object> rateLimit) {
        this.rateLimit = rateLimit;
    }
}
