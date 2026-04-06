package dev.anip.core;

/**
 * Describes how a failure can be resolved.
 */
public class Resolution {

    private final String action;
    private final String recoveryClass;
    private final String requires;
    private final String grantableBy;
    private final String estimatedAvailability;
    private final RecoveryTarget recoveryTarget;

    public Resolution(String action, String recoveryClass, String requires, String grantableBy, String estimatedAvailability) {
        this(action, recoveryClass, requires, grantableBy, estimatedAvailability, null);
    }

    public Resolution(String action, String recoveryClass, String requires, String grantableBy,
                      String estimatedAvailability, RecoveryTarget recoveryTarget) {
        this.action = action;
        this.recoveryClass = recoveryClass;
        this.requires = requires;
        this.grantableBy = grantableBy;
        this.estimatedAvailability = estimatedAvailability;
        this.recoveryTarget = recoveryTarget;
    }

    public String getAction() {
        return action;
    }

    public String getRecoveryClass() {
        return recoveryClass;
    }

    public String getRequires() {
        return requires;
    }

    public String getGrantableBy() {
        return grantableBy;
    }

    public String getEstimatedAvailability() {
        return estimatedAvailability;
    }

    public RecoveryTarget getRecoveryTarget() {
        return recoveryTarget;
    }
}
