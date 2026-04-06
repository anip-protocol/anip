package dev.anip.core;

import java.util.Collections;
import java.util.List;

/**
 * Declares bounded cross-service step meaning for a capability (v0.21).
 */
public class CrossServiceContract {

    private List<CrossServiceContractEntry> handoff;
    private List<CrossServiceContractEntry> followup;
    private List<CrossServiceContractEntry> verification;

    /** No-arg constructor for Jackson deserialization. */
    public CrossServiceContract() {}

    public CrossServiceContract(List<CrossServiceContractEntry> handoff,
                                 List<CrossServiceContractEntry> followup,
                                 List<CrossServiceContractEntry> verification) {
        this.handoff = handoff != null ? handoff : Collections.emptyList();
        this.followup = followup != null ? followup : Collections.emptyList();
        this.verification = verification != null ? verification : Collections.emptyList();
    }

    public List<CrossServiceContractEntry> getHandoff() {
        return handoff != null ? handoff : Collections.emptyList();
    }

    public List<CrossServiceContractEntry> getFollowup() {
        return followup != null ? followup : Collections.emptyList();
    }

    public List<CrossServiceContractEntry> getVerification() {
        return verification != null ? verification : Collections.emptyList();
    }

    public void setHandoff(List<CrossServiceContractEntry> handoff) {
        this.handoff = handoff;
    }

    public void setFollowup(List<CrossServiceContractEntry> followup) {
        this.followup = followup;
    }

    public void setVerification(List<CrossServiceContractEntry> verification) {
        this.verification = verification;
    }
}
