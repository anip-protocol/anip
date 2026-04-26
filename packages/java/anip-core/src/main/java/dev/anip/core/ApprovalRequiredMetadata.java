package dev.anip.core;

/** Metadata attached to an approval_required failure response. v0.23. See SPEC.md §4.7. */
public class ApprovalRequiredMetadata {
    private final String approvalRequestId;
    private final String previewDigest;
    private final String requestedParametersDigest;
    private final GrantPolicy grantPolicy;

    public ApprovalRequiredMetadata(String approvalRequestId, String previewDigest,
                                     String requestedParametersDigest, GrantPolicy grantPolicy) {
        this.approvalRequestId = approvalRequestId;
        this.previewDigest = previewDigest;
        this.requestedParametersDigest = requestedParametersDigest;
        this.grantPolicy = grantPolicy;
    }

    public String getApprovalRequestId() {
        return approvalRequestId;
    }

    public String getPreviewDigest() {
        return previewDigest;
    }

    public String getRequestedParametersDigest() {
        return requestedParametersDigest;
    }

    public GrantPolicy getGrantPolicy() {
        return grantPolicy;
    }
}
