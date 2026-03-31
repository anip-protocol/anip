package dev.anip.core;

/**
 * Describes the financial cost of a capability invocation.
 */
public class FinancialCost {

    private final String currency;
    private final Double amount;
    private final Double rangeMin;
    private final Double rangeMax;
    private final Double typical;
    private final Double upperBound;

    public FinancialCost(String currency, Double amount, Double rangeMin,
                         Double rangeMax, Double typical, Double upperBound) {
        this.currency = currency;
        this.amount = amount;
        this.rangeMin = rangeMin;
        this.rangeMax = rangeMax;
        this.typical = typical;
        this.upperBound = upperBound;
    }

    /** Convenience constructor for fixed costs. */
    public FinancialCost(String currency, Double amount) {
        this(currency, amount, null, null, null, null);
    }

    public String getCurrency() {
        return currency;
    }

    public Double getAmount() {
        return amount;
    }

    public Double getRangeMin() {
        return rangeMin;
    }

    public Double getRangeMax() {
        return rangeMax;
    }

    public Double getTypical() {
        return typical;
    }

    public Double getUpperBound() {
        return upperBound;
    }
}
