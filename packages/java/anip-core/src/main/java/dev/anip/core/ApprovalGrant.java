package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * Signed authorization object issued after approval. Bound to capability,
 * scope, parameter digest, requester, approver, expiry, and finite use count.
 * v0.23. See SPEC.md §4.8.
 */
public class ApprovalGrant {

    public static final String TYPE_ONE_TIME = "one_time";
    public static final String TYPE_SESSION_BOUND = "session_bound";

    private final String grantId;
    private final String approvalRequestId;
    private final String grantType;
    private final String capability;
    private final List<String> scope;
    private final String approvedParametersDigest;
    private final String previewDigest;
    private final Map<String, Object> requester;
    private final Map<String, Object> approver;
    private final String issuedAt;
    private final String expiresAt;
    private final int maxUses;
    private int useCount;
    private String sessionId;
    private final String signature;

    public ApprovalGrant(String grantId, String approvalRequestId, String grantType,
                         String capability, List<String> scope,
                         String approvedParametersDigest, String previewDigest,
                         Map<String, Object> requester, Map<String, Object> approver,
                         String issuedAt, String expiresAt, int maxUses, int useCount,
                         String sessionId, String signature) {
        this.grantId = grantId;
        this.approvalRequestId = approvalRequestId;
        this.grantType = grantType;
        this.capability = capability;
        this.scope = scope;
        this.approvedParametersDigest = approvedParametersDigest;
        this.previewDigest = previewDigest;
        this.requester = requester;
        this.approver = approver;
        this.issuedAt = issuedAt;
        this.expiresAt = expiresAt;
        this.maxUses = maxUses;
        this.useCount = useCount;
        this.sessionId = sessionId;
        this.signature = signature;
    }

    public String getGrantId() { return grantId; }
    public String getApprovalRequestId() { return approvalRequestId; }
    public String getGrantType() { return grantType; }
    public String getCapability() { return capability; }
    public List<String> getScope() { return scope; }
    public String getApprovedParametersDigest() { return approvedParametersDigest; }
    public String getPreviewDigest() { return previewDigest; }
    public Map<String, Object> getRequester() { return requester; }
    public Map<String, Object> getApprover() { return approver; }
    public String getIssuedAt() { return issuedAt; }
    public String getExpiresAt() { return expiresAt; }
    public int getMaxUses() { return maxUses; }
    public int getUseCount() { return useCount; }
    public ApprovalGrant setUseCount(int useCount) { this.useCount = useCount; return this; }
    public String getSessionId() { return sessionId; }
    public ApprovalGrant setSessionId(String sessionId) { this.sessionId = sessionId; return this; }
    public String getSignature() { return signature; }
}
