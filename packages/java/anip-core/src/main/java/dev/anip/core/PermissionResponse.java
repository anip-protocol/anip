package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * The response from the permissions endpoint.
 */
public class PermissionResponse {

    private final List<AvailableCapability> available;
    private final List<RestrictedCapability> restricted;
    private final List<DeniedCapability> denied;

    public PermissionResponse(List<AvailableCapability> available,
                               List<RestrictedCapability> restricted,
                               List<DeniedCapability> denied) {
        this.available = available;
        this.restricted = restricted;
        this.denied = denied;
    }

    public List<AvailableCapability> getAvailable() {
        return available;
    }

    public List<RestrictedCapability> getRestricted() {
        return restricted;
    }

    public List<DeniedCapability> getDenied() {
        return denied;
    }

    /** A capability the token can invoke. */
    public static class AvailableCapability {
        private final String capability;
        private final String scopeMatch;
        private final Map<String, Object> constraints;

        public AvailableCapability(String capability, String scopeMatch, Map<String, Object> constraints) {
            this.capability = capability;
            this.scopeMatch = scopeMatch;
            this.constraints = constraints;
        }

        public String getCapability() { return capability; }
        public String getScopeMatch() { return scopeMatch; }
        public Map<String, Object> getConstraints() { return constraints; }
    }

    /** A capability the token lacks scope for. */
    public static class RestrictedCapability {
        private final String capability;
        private final String reason;
        private final String reasonType;
        private final String grantableBy;
        private final List<String> unmetTokenRequirements;
        private final String resolutionHint;

        public RestrictedCapability(String capability, String reason, String reasonType, String grantableBy) {
            this(capability, reason, reasonType, grantableBy, null, null);
        }

        public RestrictedCapability(String capability, String reason, String reasonType, String grantableBy,
                                     List<String> unmetTokenRequirements, String resolutionHint) {
            this.capability = capability;
            this.reason = reason;
            this.reasonType = reasonType;
            this.grantableBy = grantableBy;
            this.unmetTokenRequirements = unmetTokenRequirements;
            this.resolutionHint = resolutionHint;
        }

        public String getCapability() { return capability; }
        public String getReason() { return reason; }
        public String getReasonType() { return reasonType; }
        public String getGrantableBy() { return grantableBy; }
        public List<String> getUnmetTokenRequirements() { return unmetTokenRequirements; }
        public String getResolutionHint() { return resolutionHint; }
    }

    /** A capability that cannot be granted. */
    public static class DeniedCapability {
        private final String capability;
        private final String reason;
        private final String reasonType;

        public DeniedCapability(String capability, String reason, String reasonType) {
            this.capability = capability;
            this.reason = reason;
            this.reasonType = reasonType;
        }

        public String getCapability() { return capability; }
        public String getReason() { return reason; }
        public String getReasonType() { return reasonType; }
    }
}
