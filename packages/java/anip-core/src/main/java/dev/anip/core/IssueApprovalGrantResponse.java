package dev.anip.core;

/** Response body for POST {approval_grants}. v0.23. See SPEC.md §4.9. */
public class IssueApprovalGrantResponse {
    private final ApprovalGrant grant;

    public IssueApprovalGrantResponse(ApprovalGrant grant) {
        this.grant = grant;
    }

    public ApprovalGrant getGrant() {
        return grant;
    }
}
