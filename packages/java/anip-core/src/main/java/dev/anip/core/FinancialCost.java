package dev.anip.core;

/**
 * Describes the financial cost of a capability invocation.
 */
public class FinancialCost {

    private String currency;
    private Double amount;
    private Double rangeMin;
    private Double rangeMax;
    private Double typical;
    private Double upperBound;

    /** No-arg constructor for Jackson deserialization. */
    public FinancialCost() {}

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

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public void setAmount(Double amount) {
        this.amount = amount;
    }

    public void setRangeMin(Double rangeMin) {
        this.rangeMin = rangeMin;
    }

    public void setRangeMax(Double rangeMax) {
        this.rangeMax = rangeMax;
    }

    public void setTypical(Double typical) {
        this.typical = typical;
    }

    public void setUpperBound(Double upperBound) {
        this.upperBound = upperBound;
    }
}
