package dev.anip.core;

/** Request body for POST {approval_grants}. v0.23. See SPEC.md §4.9. */
public class IssueApprovalGrantRequest {
    private final String approvalRequestId;
    private final String grantType;
    private String sessionId;
    private Integer expiresInSeconds;
    private Integer maxUses;

    public IssueApprovalGrantRequest(String approvalRequestId, String grantType) {
        this.approvalRequestId = approvalRequestId;
        this.grantType = grantType;
    }

    public String getApprovalRequestId() { return approvalRequestId; }
    public String getGrantType() { return grantType; }
    public String getSessionId() { return sessionId; }
    public IssueApprovalGrantRequest setSessionId(String sessionId) { this.sessionId = sessionId; return this; }
    public Integer getExpiresInSeconds() { return expiresInSeconds; }
    public IssueApprovalGrantRequest setExpiresInSeconds(Integer expiresInSeconds) { this.expiresInSeconds = expiresInSeconds; return this; }
    public Integer getMaxUses() { return maxUses; }
    public IssueApprovalGrantRequest setMaxUses(Integer maxUses) { this.maxUses = maxUses; return this; }
}
