using Anip.Core;

namespace Anip.Server;

/// <summary>
/// Result of <see cref="IStorage.TryReserveGrantAsync"/>. v0.23.
/// SPEC.md §4.8 Phase B — atomic compare-and-set increment of use_count.
/// On failure, <see cref="Reason"/> is one of:
/// <list type="bullet">
///   <item>grant_not_found</item>
///   <item>grant_expired</item>
///   <item>grant_consumed</item>
/// </list>
/// </summary>
public record GrantReservationResult(bool Ok, ApprovalGrant? Grant, string? Reason)
{
    public static GrantReservationResult Success(ApprovalGrant grant) =>
        new(true, grant, null);

    public static GrantReservationResult Failure(string reason) =>
        new(false, null, reason);
}
