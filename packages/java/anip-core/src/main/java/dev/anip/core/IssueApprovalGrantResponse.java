package dev.anip.core;

/**
 * Type alias for {@link ApprovalGrant} on the v0.23 issuance response wire
 * format. SPEC.md §4.9: the 200 body IS the signed grant — there is no
 * wrapping object. Routes should serialize the {@link ApprovalGrant} directly;
 * this class exists only as a marker so calling code can name the response.
 */
public final class IssueApprovalGrantResponse {

    private final ApprovalGrant grant;

    public IssueApprovalGrantResponse(ApprovalGrant grant) {
        this.grant = grant;
    }

    public ApprovalGrant getGrant() {
        return grant;
    }
}
