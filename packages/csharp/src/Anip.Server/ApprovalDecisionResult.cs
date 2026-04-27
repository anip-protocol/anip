using Anip.Core;

namespace Anip.Server;

/// <summary>
/// Result of <see cref="IStorage.ApproveRequestAndStoreGrantAsync"/>. v0.23.
/// SPEC.md §4.9 (Decision 0.9a) — atomic state transition for an
/// ApprovalRequest into "approved" + grant insert.
/// On failure, <see cref="Reason"/> is one of:
/// <list type="bullet">
///   <item>approval_request_not_found</item>
///   <item>approval_request_already_decided</item>
///   <item>approval_request_expired</item>
/// </list>
/// </summary>
public record ApprovalDecisionResult(bool Ok, ApprovalGrant? Grant, string? Reason)
{
    public static ApprovalDecisionResult Success(ApprovalGrant grant) =>
        new(true, grant, null);

    public static ApprovalDecisionResult Failure(string reason) =>
        new(false, null, reason);
}
