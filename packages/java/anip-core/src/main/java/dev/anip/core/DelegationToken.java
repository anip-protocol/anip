package dev.anip.core;

import java.util.List;

/**
 * A stored delegation token record.
 */
public class DelegationToken {

    private final String tokenId;
    private final String issuer;
    private final String subject;
    private final List<String> scope;
    private final Purpose purpose;
    private final String parent;
    private final String expires;
    private final DelegationConstraints constraints;
    private final String rootPrincipal;
    private final String callerClass;
    /**
     * v0.23: session identity bound at issuance, validated for session_bound
     * ApprovalGrant continuations per SPEC.md §4.8. Trust comes from the
     * signed token, never from caller-supplied invocation input. Null/empty
     * for tokens that were not bound to a session.
     */
    private final String sessionId;

    public DelegationToken(String tokenId, String issuer, String subject, List<String> scope,
                           Purpose purpose, String parent, String expires,
                           DelegationConstraints constraints, String rootPrincipal,
                           String callerClass) {
        this(tokenId, issuer, subject, scope, purpose, parent, expires,
             constraints, rootPrincipal, callerClass, null);
    }

    public DelegationToken(String tokenId, String issuer, String subject, List<String> scope,
                           Purpose purpose, String parent, String expires,
                           DelegationConstraints constraints, String rootPrincipal,
                           String callerClass, String sessionId) {
        this.tokenId = tokenId;
        this.issuer = issuer;
        this.subject = subject;
        this.scope = scope;
        this.purpose = purpose;
        this.parent = parent;
        this.expires = expires;
        this.constraints = constraints;
        this.rootPrincipal = rootPrincipal;
        this.callerClass = callerClass;
        this.sessionId = sessionId;
    }

    public String getTokenId() {
        return tokenId;
    }

    public String getIssuer() {
        return issuer;
    }

    public String getSubject() {
        return subject;
    }

    public List<String> getScope() {
        return scope;
    }

    public Purpose getPurpose() {
        return purpose;
    }

    /** Empty for root tokens. */
    public String getParent() {
        return parent;
    }

    public String getExpires() {
        return expires;
    }

    public DelegationConstraints getConstraints() {
        return constraints;
    }

    public String getRootPrincipal() {
        return rootPrincipal;
    }

    public String getCallerClass() {
        return callerClass;
    }

    /** v0.23: session identity for session_bound ApprovalGrant validation. */
    public String getSessionId() {
        return sessionId;
    }
}
