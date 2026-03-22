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

    public TokenRequest(String subject, List<String> scope, String capability,
                        Map<String, Object> purposeParameters, String parentToken,
                        int ttlHours, String callerClass) {
        this.subject = subject;
        this.scope = scope;
        this.capability = capability;
        this.purposeParameters = purposeParameters;
        this.parentToken = parentToken;
        this.ttlHours = ttlHours;
        this.callerClass = callerClass;
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

    /** JWT string of parent token. */
    public String getParentToken() {
        return parentToken;
    }

    public int getTtlHours() {
        return ttlHours;
    }

    public String getCallerClass() {
        return callerClass;
    }
}
