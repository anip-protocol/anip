package dev.anip.server;

import dev.anip.core.ApprovalGrant;

/**
 * Discriminated result for {@link Storage#approveRequestAndStoreGrant}.
 *
 * <p>{@code ok=true} -> {@link #grant} is set, {@link #reason} is null.
 * {@code ok=false} -> {@link #reason} is one of:
 * {@code approval_request_not_found}, {@code approval_request_expired},
 * {@code approval_request_already_decided}; {@link #grant} is null.</p>
 *
 * <p>v0.23. See SPEC.md §4.9 (Decision 0.9a — atomic approve+issue).</p>
 */
public record ApprovalDecisionResult(boolean ok, ApprovalGrant grant, String reason) {

    public static ApprovalDecisionResult success(ApprovalGrant grant) {
        return new ApprovalDecisionResult(true, grant, null);
    }

    public static ApprovalDecisionResult failure(String reason) {
        return new ApprovalDecisionResult(false, null, reason);
    }
}
