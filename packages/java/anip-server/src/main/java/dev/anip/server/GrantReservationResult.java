package dev.anip.server;

import dev.anip.core.ApprovalGrant;

/**
 * Discriminated result for {@link Storage#tryReserveGrant}.
 *
 * <p>{@code ok=true} -> {@link #grant} is set with the post-reservation
 * use_count, {@link #reason} is null. {@code ok=false} -> {@link #reason}
 * is one of: {@code grant_not_found}, {@code grant_expired},
 * {@code grant_consumed}; {@link #grant} is null.</p>
 *
 * <p>v0.23. See SPEC.md §4.8 Phase B (atomic CAS reservation).</p>
 */
public record GrantReservationResult(boolean ok, ApprovalGrant grant, String reason) {

    public static GrantReservationResult success(ApprovalGrant grant) {
        return new GrantReservationResult(true, grant, null);
    }

    public static GrantReservationResult failure(String reason) {
        return new GrantReservationResult(false, null, reason);
    }
}
