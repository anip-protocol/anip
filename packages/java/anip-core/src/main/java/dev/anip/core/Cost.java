package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * Describes the cost characteristics of a capability.
 */
public class Cost {

    private final String certainty;
    private final Map<String, Object> financial;
    private final String determinedBy;
    private final List<String> factors;
    private final Map<String, Object> compute;
    private final Map<String, Object> rateLimit;

    public Cost(String certainty, Map<String, Object> financial, String determinedBy,
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

    public Map<String, Object> getFinancial() {
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
}
