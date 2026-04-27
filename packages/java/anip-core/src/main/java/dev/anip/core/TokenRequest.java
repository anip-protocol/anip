package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * The client's request body for token issuance.
 */
public class TokenRequest {

    private final String subject;
    private final List<String> scope;
    private final String capability;
    private final Map<String, Object> purposeParameters;
    private final String parentToken;
    private final int ttlHours;
    private final String callerClass;
    private final Budget budget;
    private final String concurrentBranches;
    /**
     * v0.23: bind a session identity to the issued token. Required for callers
     * that intend to redeem session_bound ApprovalGrants. Only honored at root
     * issuance — child tokens inherit parent's session_id verbatim. SPEC §4.8.
     */
    private final String sessionId;

    public TokenRequest(String subject, List<String> scope, String capability,
                        Map<String, Object> purposeParameters, String parentToken,
                        int ttlHours, String callerClass) {
        this(subject, scope, capability, purposeParameters, parentToken, ttlHours, callerClass, null, null, null);
    }

    public TokenRequest(String subject, List<String> scope, String capability,
                        Map<String, Object> purposeParameters, String parentToken,
                        int ttlHours, String callerClass, Budget budget) {
        this(subject, scope, capability, purposeParameters, parentToken, ttlHours, callerClass, budget, null, null);
    }

    public TokenRequest(String subject, List<String> scope, String capability,
                        Map<String, Object> purposeParameters, String parentToken,
                        int ttlHours, String callerClass, Budget budget,
                        String concurrentBranches) {
        this(subject, scope, capability, purposeParameters, parentToken, ttlHours, callerClass, budget, concurrentBranches, null);
    }

    public TokenRequest(String subject, List<String> scope, String capability,
                        Map<String, Object> purposeParameters, String parentToken,
                        int ttlHours, String callerClass, Budget budget,
                        String concurrentBranches, String sessionId) {
        this.subject = subject;
        this.scope = scope;
        this.capability = capability;
        this.purposeParameters = purposeParameters;
        this.parentToken = parentToken;
        this.ttlHours = ttlHours;
        this.callerClass = callerClass;
        this.budget = budget;
        this.concurrentBranches = concurrentBranches;
        this.sessionId = sessionId;
    }

    public String getSubject() {
        return subject;
    }

    public List<String> getScope() {
        return scope;
    }

    public String getCapability() {
        return capability;
    }

    public Map<String, Object> getPurposeParameters() {
        return purposeParameters;
    }

    /** Token ID string of the parent token (not a JWT). The service looks up the parent by ID in storage. */
    public String getParentToken() {
        return parentToken;
    }

    public int getTtlHours() {
        return ttlHours;
    }

    public String getCallerClass() {
        return callerClass;
    }

    public Budget getBudget() {
        return budget;
    }

    /** Returns "allowed" or "exclusive"; null means default ("allowed"). */
    public String getConcurrentBranches() {
        return concurrentBranches;
    }

    /** v0.23: session identity to bind to the issued token. */
    public String getSessionId() {
        return sessionId;
    }
}
