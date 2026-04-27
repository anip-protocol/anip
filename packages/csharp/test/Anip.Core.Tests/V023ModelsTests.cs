using System.Text.Json;
using Anip.Core;
using Xunit;

namespace Anip.Core.Tests;

public class V023ModelsTests
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull,
    };

    private static T RoundTrip<T>(T value)
    {
        var json = JsonSerializer.Serialize(value, JsonOpts);
        return JsonSerializer.Deserialize<T>(json, JsonOpts)!;
    }

    private static GrantPolicy GrantPolicy() => new()
    {
        AllowedGrantTypes = new() { "one_time", "session_bound" },
        DefaultGrantType = "one_time",
        ExpiresInSeconds = 900,
        MaxUses = 1,
    };

    [Fact]
    public void CapabilityKindAtomicByDefault()
    {
        var d = new CapabilityDeclaration { Name = "cap", Description = "d" };
        Assert.Equal("atomic", d.Kind);
        Assert.Null(d.Composition);
        Assert.Null(d.GrantPolicy);
        var d2 = RoundTrip(d);
        Assert.Equal("atomic", d2.Kind);
    }

    [Fact]
    public void ComposedDeclarationCarriesAllFields()
    {
        var comp = new Composition
        {
            AuthorityBoundary = "same_service",
            Steps = new List<CompositionStep>
            {
                new() { Id = "select", Capability = "select_at_risk", EmptyResultSource = true },
                new() { Id = "enrich", Capability = "enrich_accounts" },
            },
            InputMapping = new()
            {
                ["select"] = new() { ["quarter"] = "$.input.quarter" },
                ["enrich"] = new() { ["accounts"] = "$.steps.select.output.accounts" },
            },
            OutputMapping = new() { ["count"] = "$.steps.enrich.output.count" },
            EmptyResultPolicy = "return_success_no_results",
            EmptyResultOutput = new() { ["count"] = 0 },
            FailurePolicy = new(),
            AuditPolicy = new() { RecordChildInvocations = true, ParentTaskLineage = true },
        };
        var d = new CapabilityDeclaration
        {
            Name = "summary",
            Kind = "composed",
            Composition = comp,
            GrantPolicy = GrantPolicy(),
        };

        var d2 = RoundTrip(d);
        Assert.Equal("composed", d2.Kind);
        Assert.NotNull(d2.Composition);
        Assert.Equal("same_service", d2.Composition!.AuthorityBoundary);
        Assert.Equal(2, d2.Composition.Steps.Count);
        Assert.True(d2.Composition.Steps[0].EmptyResultSource);
        Assert.False(d2.Composition.Steps[1].EmptyResultSource);
        Assert.Equal("return_success_no_results", d2.Composition.EmptyResultPolicy);
        Assert.Equal("fail_parent", d2.Composition.FailurePolicy.ChildError);
        Assert.NotNull(d2.GrantPolicy);
    }

    [Fact]
    public void ApprovalRequestPendingState()
    {
        var r = new ApprovalRequest
        {
            ApprovalRequestId = "apr_test",
            Capability = "cap",
            Scope = new() { "s" },
            Requester = new() { ["principal"] = "u1" },
            Preview = new(),
            PreviewDigest = "d2",
            RequestedParameters = new(),
            RequestedParametersDigest = "d1",
            GrantPolicy = GrantPolicy(),
            Status = ApprovalRequest.StatusPending,
            CreatedAt = "2026-01-01T00:00:00Z",
            ExpiresAt = "2026-01-01T00:15:00Z",
        };
        var r2 = RoundTrip(r);
        Assert.Equal("pending", r2.Status);
        Assert.Null(r2.Approver);
        Assert.Null(r2.DecidedAt);
    }

    [Fact]
    public void ApprovalRequestExpiredHasNoApprover()
    {
        var r = new ApprovalRequest
        {
            ApprovalRequestId = "apr_test",
            Capability = "cap",
            Scope = new() { "s" },
            Requester = new(),
            Preview = new(),
            PreviewDigest = "d2",
            RequestedParameters = new(),
            RequestedParametersDigest = "d1",
            GrantPolicy = GrantPolicy(),
            Status = ApprovalRequest.StatusExpired,
            DecidedAt = "2026-01-01T00:15:01Z",
            CreatedAt = "2026-01-01T00:00:00Z",
            ExpiresAt = "2026-01-01T00:15:00Z",
        };
        var r2 = RoundTrip(r);
        Assert.Equal("expired", r2.Status);
        Assert.Null(r2.Approver);
        Assert.NotNull(r2.DecidedAt);
    }

    [Fact]
    public void ApprovalGrantOneTimeRoundTrip()
    {
        var g = new ApprovalGrant
        {
            GrantId = "grant_test",
            ApprovalRequestId = "apr_test",
            GrantType = ApprovalGrant.TypeOneTime,
            Capability = "finance.transfer_funds",
            Scope = new() { "finance.write" },
            ApprovedParametersDigest = "d1",
            PreviewDigest = "d2",
            Requester = new() { ["principal"] = "u1" },
            Approver = new() { ["principal"] = "u2" },
            IssuedAt = "2026-01-01T00:00:00Z",
            ExpiresAt = "2026-01-01T00:15:00Z",
            MaxUses = 1,
            UseCount = 0,
            Signature = "sig",
        };
        var g2 = RoundTrip(g);
        Assert.Equal("apr_test", g2.ApprovalRequestId);
        Assert.Equal("one_time", g2.GrantType);
        Assert.Null(g2.SessionId);
        Assert.Equal(0, g2.UseCount);
    }

    [Fact]
    public void ApprovalGrantSessionBoundRoundTrip()
    {
        var g = new ApprovalGrant
        {
            GrantId = "grant_test",
            ApprovalRequestId = "apr_test",
            GrantType = ApprovalGrant.TypeSessionBound,
            Capability = "cap",
            Scope = new() { "s" },
            ApprovedParametersDigest = "d1",
            PreviewDigest = "d2",
            Requester = new(),
            Approver = new(),
            IssuedAt = "2026-01-01T00:00:00Z",
            ExpiresAt = "2026-01-01T00:15:00Z",
            MaxUses = 5,
            UseCount = 0,
            SessionId = "sess_1",
            Signature = "sig",
        };
        var g2 = RoundTrip(g);
        Assert.Equal("session_bound", g2.GrantType);
        Assert.Equal("sess_1", g2.SessionId);
        Assert.Equal(5, g2.MaxUses);
    }

    [Fact]
    public void AnipErrorWithApprovalRequiredMetadata()
    {
        var e = new AnipError("approval_required", "needs approval")
            .WithResolution("contact_service_owner")
            .WithApprovalRequired(new ApprovalRequiredMetadata
            {
                ApprovalRequestId = "apr_test",
                PreviewDigest = "d2",
                RequestedParametersDigest = "d1",
                GrantPolicy = GrantPolicy(),
            });
        Assert.NotNull(e.ApprovalRequired);
        Assert.Equal("apr_test", e.ApprovalRequired!.ApprovalRequestId);
        Assert.Equal(900, e.ApprovalRequired.GrantPolicy.ExpiresInSeconds);
    }

    [Fact]
    public void AnipErrorWithoutApprovalRequiredIsNull()
    {
        var e = new AnipError("budget_exceeded", "too expensive")
            .WithResolution("request_budget_increase");
        Assert.Null(e.ApprovalRequired);
    }

    [Fact]
    public void InvokeRequestApprovalGrantDefaultsToNull()
    {
        var ir = new InvokeRequest { Token = "jwt" };
        Assert.Null(ir.ApprovalGrant);
    }

    [Fact]
    public void InvokeRequestApprovalGrantRoundTrip()
    {
        var ir = new InvokeRequest { Token = "jwt", ApprovalGrant = "grant_test" };
        var ir2 = RoundTrip(ir);
        Assert.Equal("grant_test", ir2.ApprovalGrant);
    }

    [Fact]
    public void IssueApprovalGrantRequestRoundTrip()
    {
        var req = new IssueApprovalGrantRequest
        {
            ApprovalRequestId = "apr_test",
            GrantType = "one_time",
            ExpiresInSeconds = 600,
            MaxUses = 1,
        };
        var req2 = RoundTrip(req);
        Assert.Equal("one_time", req2.GrantType);
        Assert.Equal(600, req2.ExpiresInSeconds);
    }

    [Fact]
    public void GrantPolicyValidateRejectsDefaultNotInAllowed()
    {
        var p = new GrantPolicy
        {
            AllowedGrantTypes = new() { "one_time" },
            DefaultGrantType = "session_bound",
            ExpiresInSeconds = 900,
            MaxUses = 1,
        };
        var ex = Assert.Throws<ArgumentException>(() => p.Validate());
        Assert.Contains("DefaultGrantType", ex.Message);
    }

    [Fact]
    public void GrantPolicyValidateRejectsEmptyAllowed()
    {
        var p = new GrantPolicy
        {
            AllowedGrantTypes = new(),
            DefaultGrantType = "one_time",
            ExpiresInSeconds = 900,
            MaxUses = 1,
        };
        Assert.Throws<ArgumentException>(() => p.Validate());
    }

    [Fact]
    public void GrantPolicyValidateAcceptsDefaultInAllowed()
    {
        var p = new GrantPolicy
        {
            AllowedGrantTypes = new() { "one_time", "session_bound" },
            DefaultGrantType = "session_bound",
            ExpiresInSeconds = 900,
            MaxUses = 1,
        };
        p.Validate(); // should not throw
        Assert.Equal("session_bound", p.DefaultGrantType);
    }

    // SPEC.md §4.9: 200 response for POST /anip/approval_grants IS the bare
    // ApprovalGrant — no IssueApprovalGrantResponse wrapper exists.
    [Fact]
    public void IssueApprovalGrantResponseIsBareGrant()
    {
        var g = new ApprovalGrant
        {
            GrantId = "grant_test",
            ApprovalRequestId = "apr_test",
            GrantType = "one_time",
            Capability = "cap",
            Scope = new() { "s" },
            ApprovedParametersDigest = "d1",
            PreviewDigest = "d2",
            Requester = new(),
            Approver = new(),
            IssuedAt = "x",
            ExpiresAt = "y",
            MaxUses = 1,
            Signature = "sig",
        };
        var rt = RoundTrip(g);
        Assert.Equal("grant_test", rt.GrantId);
        Assert.Equal("apr_test", rt.ApprovalRequestId);
    }
}
