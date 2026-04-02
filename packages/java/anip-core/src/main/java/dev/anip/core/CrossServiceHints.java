package dev.anip.core;

import java.util.Collections;
import java.util.List;

/**
 * Hints for cross-service coordination attached to a capability declaration.
 */
public class CrossServiceHints {

    private List<ServiceCapabilityRef> handoffTo;
    private List<ServiceCapabilityRef> refreshVia;
    private List<ServiceCapabilityRef> verifyVia;
    private List<ServiceCapabilityRef> followupVia;

    /** No-arg constructor for Jackson deserialization. */
    public CrossServiceHints() {}

    public CrossServiceHints(List<ServiceCapabilityRef> handoffTo,
                             List<ServiceCapabilityRef> refreshVia,
                             List<ServiceCapabilityRef> verifyVia,
                             List<ServiceCapabilityRef> followupVia) {
        this.handoffTo = handoffTo != null ? handoffTo : Collections.emptyList();
        this.refreshVia = refreshVia != null ? refreshVia : Collections.emptyList();
        this.verifyVia = verifyVia != null ? verifyVia : Collections.emptyList();
        this.followupVia = followupVia != null ? followupVia : Collections.emptyList();
    }

    public List<ServiceCapabilityRef> getHandoffTo() {
        return handoffTo != null ? handoffTo : Collections.emptyList();
    }

    public List<ServiceCapabilityRef> getRefreshVia() {
        return refreshVia != null ? refreshVia : Collections.emptyList();
    }

    public List<ServiceCapabilityRef> getVerifyVia() {
        return verifyVia != null ? verifyVia : Collections.emptyList();
    }

    public List<ServiceCapabilityRef> getFollowupVia() {
        return followupVia != null ? followupVia : Collections.emptyList();
    }

    public void setHandoffTo(List<ServiceCapabilityRef> handoffTo) {
        this.handoffTo = handoffTo;
    }

    public void setRefreshVia(List<ServiceCapabilityRef> refreshVia) {
        this.refreshVia = refreshVia;
    }

    public void setVerifyVia(List<ServiceCapabilityRef> verifyVia) {
        this.verifyVia = verifyVia;
    }

    public void setFollowupVia(List<ServiceCapabilityRef> followupVia) {
        this.followupVia = followupVia;
    }
}
