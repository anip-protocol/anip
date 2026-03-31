package dev.anip.core;

/**
 * Constrains the maximum spend for a delegation token or invocation.
 */
public class Budget {

    private final String currency;
    private final double maxAmount;

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
}
