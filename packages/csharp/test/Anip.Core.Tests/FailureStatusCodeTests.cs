namespace Anip.Core.Tests;

/// <summary>
/// SPEC.md §6.3 "HTTP Status Codes": one status per failure type, and 400 for
/// every type the table does not list.
/// </summary>
public class FailureStatusCodeTests
{
    // The table, row by row, as the specification spells the type names.
    public static IEnumerable<object[]> Table()
    {
        var rows = new (int Status, string[] Types)[]
        {
            (400, new[]
            {
                "invalid_parameters", "streaming_not_supported", "approval_required", "grant_not_found",
                "grant_capability_mismatch", "grant_scope_mismatch", "grant_param_drift",
                "grant_session_invalid", "grant_type_not_allowed_by_policy",
            }),
            (401, new[] { "authentication_required", "invalid_token", "token_expired", "token_not_registered" }),
            (403, new[]
            {
                "scope_insufficient", "insufficient_authority", "purpose_mismatch", "scope_escalation",
                "constraint_escalation", "broken_delegation_chain", "delegation_depth_exceeded",
                "parent_token_expired", "budget_exceeded", "budget_currency_mismatch",
                "budget_not_enforceable", "binding_missing", "binding_stale",
                "control_requirement_unsatisfied", "approver_not_authorized",
                "grant_requester_mismatch",
            }),
            (404, new[] { "unknown_capability", "not_found", "approval_request_not_found" }),
            (409, new[]
            {
                "grant_consumed", "grant_expired", "approval_request_already_decided",
                "approval_request_expired", "concurrent_lock", "concurrent_request_rejected", "unavailable",
            }),
            (500, new[] { "internal_error" }),
            (503, new[] { "service_unavailable" }),
        };
        foreach (var (status, types) in rows)
        {
            foreach (var type in types)
            {
                yield return new object[] { type, status };
            }
        }
    }

    [Theory]
    [MemberData(nameof(Table))]
    public void EveryRowOfTheTable(string failureType, int status)
    {
        Assert.Equal(status, Constants.FailureStatusCode(failureType));
    }

    [Fact]
    public void TheTableHasFortyOneRows()
    {
        Assert.Equal(41, Table().Count());
        Assert.Equal(41, Table().Select(row => (string)row[0]).Distinct().Count());
    }

    [Theory]
    [InlineData("composition_child_failed")]
    [InlineData("non_delegable_action")]
    [InlineData("clarification_required")]
    [InlineData("a_type_a_handler_defines")]
    [InlineData("Internal_Error")]
    [InlineData("")]
    [InlineData(null)]
    public void ATypeTheTableDoesNotList_Is400(string? failureType)
    {
        Assert.Equal(400, Constants.FailureStatusCode(failureType));
    }

    [Fact]
    public void ConstantsSpellTheTableNames()
    {
        Assert.Equal("token_not_registered", Constants.FailureTokenNotRegistered);
        Assert.Equal("constraint_escalation", Constants.FailureConstraintEscalation);
        Assert.Equal("concurrent_request_rejected", Constants.FailureConcurrentRequestRejected);
        Assert.Equal("service_unavailable", Constants.FailureServiceUnavailable);
        Assert.Equal("unavailable", Constants.FailureUnavailable);
    }
}
