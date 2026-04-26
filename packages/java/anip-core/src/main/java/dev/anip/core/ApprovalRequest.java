package dev.anip.core;

import java.util.List;
import java.util.Map;

/**
 * Persistent record of a request for human/principal approval. Created when a
 * capability raises approval_required. v0.23. See SPEC.md §4.7.
 */
public class ApprovalRequest {

    public static final String STATUS_PENDING = "pending";
    public static final String STATUS_APPROVED = "approved";
    public static final String STATUS_DENIED = "denied";
    public static final String STATUS_EXPIRED = "expired";

    private final String approvalRequestId;
    private final String capability;
    private final List<String> scope;
    private final Map<String, Object> requester;
    private String parentInvocationId;
    private final Map<String, Object> preview;
    private final String previewDigest;
    private final Map<String, Object> requestedParameters;
    private final String requestedParametersDigest;
    private final GrantPolicy grantPolicy;
    private String status;
    private Map<String, Object> approver;
    private String decidedAt;
    private final String createdAt;
    private final String expiresAt;

    public ApprovalRequest(String approvalRequestId, String capability, List<String> scope,
                           Map<String, Object> requester, Map<String, Object> preview,
                           String previewDigest, Map<String, Object> requestedParameters,
                           String requestedParametersDigest, GrantPolicy grantPolicy,
                           String status, String createdAt, String expiresAt) {
        this.approvalRequestId = approvalRequestId;
        this.capability = capability;
        this.scope = scope;
        this.requester = requester;
        this.preview = preview;
        this.previewDigest = previewDigest;
        this.requestedParameters = requestedParameters;
        this.requestedParametersDigest = requestedParametersDigest;
        this.grantPolicy = grantPolicy;
        this.status = status;
        this.createdAt = createdAt;
        this.expiresAt = expiresAt;
    }

    public String getApprovalRequestId() { return approvalRequestId; }
    public String getCapability() { return capability; }
    public List<String> getScope() { return scope; }
    public Map<String, Object> getRequester() { return requester; }
    public String getParentInvocationId() { return parentInvocationId; }
    public ApprovalRequest setParentInvocationId(String parentInvocationId) { this.parentInvocationId = parentInvocationId; return this; }
    public Map<String, Object> getPreview() { return preview; }
    public String getPreviewDigest() { return previewDigest; }
    public Map<String, Object> getRequestedParameters() { return requestedParameters; }
    public String getRequestedParametersDigest() { return requestedParametersDigest; }
    public GrantPolicy getGrantPolicy() { return grantPolicy; }
    public String getStatus() { return status; }
    public ApprovalRequest setStatus(String status) { this.status = status; return this; }
    public Map<String, Object> getApprover() { return approver; }
    public ApprovalRequest setApprover(Map<String, Object> approver) { this.approver = approver; return this; }
    public String getDecidedAt() { return decidedAt; }
    public ApprovalRequest setDecidedAt(String decidedAt) { this.decidedAt = decidedAt; return this; }
    public String getCreatedAt() { return createdAt; }
    public String getExpiresAt() { return expiresAt; }
}
