package dev.anip.core;

/**
 * A single cross-service step with stronger semantics than advisory hints (v0.21).
 */
public class CrossServiceContractEntry {

    private ServiceCapabilityRef target;
    private boolean requiredForTaskCompletion;
    private String continuity;    // "same_task"
    private String completionMode; // "downstream_acceptance", "followup_status", "verification_result"

    /** No-arg constructor for Jackson deserialization. */
    public CrossServiceContractEntry() {}

    public CrossServiceContractEntry(ServiceCapabilityRef target, boolean requiredForTaskCompletion,
                                      String continuity, String completionMode) {
        this.target = target;
        this.requiredForTaskCompletion = requiredForTaskCompletion;
        this.continuity = continuity;
        this.completionMode = completionMode;
    }

    public ServiceCapabilityRef getTarget() {
        return target;
    }

    public boolean isRequiredForTaskCompletion() {
        return requiredForTaskCompletion;
    }

    public String getContinuity() {
        return continuity;
    }

    public String getCompletionMode() {
        return completionMode;
    }

    public void setTarget(ServiceCapabilityRef target) {
        this.target = target;
    }

    public void setRequiredForTaskCompletion(boolean requiredForTaskCompletion) {
        this.requiredForTaskCompletion = requiredForTaskCompletion;
    }

    public void setContinuity(String continuity) {
        this.continuity = continuity;
    }

    public void setCompletionMode(String completionMode) {
        this.completionMode = completionMode;
    }
}
