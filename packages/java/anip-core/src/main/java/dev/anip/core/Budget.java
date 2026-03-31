package dev.anip.core;

/**
 * Constrains the maximum spend for a delegation token or invocation.
 */
public class Budget {

    private String currency;
    private double maxAmount;

    /** No-arg constructor for Jackson deserialization. */
    public Budget() {}

    public Budget(String currency, double maxAmount) {
        this.currency = currency;
        this.maxAmount = maxAmount;
    }

    public String getCurrency() {
        return currency;
    }

    public double getMaxAmount() {
        return maxAmount;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public void setMaxAmount(double maxAmount) {
        this.maxAmount = maxAmount;
    }
}
