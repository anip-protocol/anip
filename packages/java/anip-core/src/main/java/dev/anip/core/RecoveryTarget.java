package dev.anip.core;

/**
 * Structured recovery step for failure handling (v0.21).
 */
public class RecoveryTarget {

    private String kind;       // "refresh", "redelegation", "revalidation", "escalation"
    private ServiceCapabilityRef target;
    private String continuity; // "same_task"
    private boolean retryAfterTarget;

    /** No-arg constructor for Jackson deserialization. */
    public RecoveryTarget() {}

    public RecoveryTarget(String kind, ServiceCapabilityRef target,
                           String continuity, boolean retryAfterTarget) {
        this.kind = kind;
        this.target = target;
        this.continuity = continuity;
        this.retryAfterTarget = retryAfterTarget;
    }

    public String getKind() {
        return kind;
    }

    public ServiceCapabilityRef getTarget() {
        return target;
    }

    public String getContinuity() {
        return continuity;
    }

    public boolean isRetryAfterTarget() {
        return retryAfterTarget;
    }

    public void setKind(String kind) {
        this.kind = kind;
    }

    public void setTarget(ServiceCapabilityRef target) {
        this.target = target;
    }

    public void setContinuity(String continuity) {
        this.continuity = continuity;
    }

    public void setRetryAfterTarget(boolean retryAfterTarget) {
        this.retryAfterTarget = retryAfterTarget;
    }
}
