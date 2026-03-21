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

    public DelegationToken(String tokenId, String issuer, String subject, List<String> scope,
                           Purpose purpose, String parent, String expires,
                           DelegationConstraints constraints, String rootPrincipal,
                           String callerClass) {
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
}
