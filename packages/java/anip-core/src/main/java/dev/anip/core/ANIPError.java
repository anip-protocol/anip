package dev.anip.core;

/**
 * Structured protocol failure. Extends RuntimeException so it can be thrown
 * and caught throughout the ANIP runtime.
 */
public class ANIPError extends RuntimeException {

    private final String errorType;
    private final String detail;
    private Resolution resolution;
    private boolean retry;

    public ANIPError(String errorType, String detail) {
        super(errorType + ": " + detail);
        this.errorType = errorType;
        this.detail = detail;
    }

    /** Builder: adds a resolution with the given action, auto-populating recovery_class. */
    public ANIPError withResolution(String action) {
        this.resolution = new Resolution(action, Constants.recoveryClassForAction(action), null, null, null);
        return this;
    }

    /** Builder: adds a full resolution. */
    public ANIPError withResolution(Resolution resolution) {
        this.resolution = resolution;
        return this;
    }

    /** Builder: marks the error as retryable. */
    public ANIPError withRetry() {
        this.retry = true;
        return this;
    }

    public String getErrorType() {
        return errorType;
    }

    public String getDetail() {
        return detail;
    }

    public Resolution getResolution() {
        return resolution;
    }

    public boolean isRetry() {
        return retry;
    }
}
