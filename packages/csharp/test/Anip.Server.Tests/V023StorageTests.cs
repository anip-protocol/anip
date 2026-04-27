using System.Globalization;
using Anip.Core;
using Anip.Server;
using Xunit;

namespace Anip.Server.Tests;

/// <summary>v0.23 storage primitives — round-trip, idempotency, atomic CAS.</summary>
public class V023StorageTests : IDisposable
{
    private readonly SqliteStorage _storage;

    public V023StorageTests()
    {
        _storage = new SqliteStorage(":memory:");
    }

    public void Dispose()
    {
        _storage.Dispose();
    }

    private static string NowIso() =>
        DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ", CultureInfo.InvariantCulture);

    private static string InIso(int seconds) =>
        DateTime.UtcNow.AddSeconds(seconds)
            .ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ", CultureInfo.InvariantCulture);

    private static GrantPolicy Gp() => new()
    {
        AllowedGrantTypes = new List<string> { "one_time", "session_bound" },
        DefaultGrantType = "one_time",
        ExpiresInSeconds = 900,
        MaxUses = 5,
    };

    private static ApprovalRequest PendingRequest(string id) => new()
    {
        ApprovalRequestId = id,
        Capability = "cap",
        Scope = new List<string> { "scope.read" },
        Requester = new Dictionary<string, object> { ["subject"] = "alice" },
        Preview = new Dictionary<string, object>(),
        PreviewDigest = "sha256:p",
        RequestedParameters = new Dictionary<string, object> { ["x"] = 1 },
        RequestedParametersDigest = "sha256:q",
        GrantPolicy = Gp(),
        Status = ApprovalRequest.StatusPending,
        CreatedAt = NowIso(),
        ExpiresAt = InIso(900),
    };

    private static ApprovalGrant GrantFor(ApprovalRequest req, int maxUses, int useCount, int expiresInSeconds) => new()
    {
        GrantId = "grant_" + req.ApprovalRequestId,
        ApprovalRequestId = req.ApprovalRequestId,
        GrantType = ApprovalGrant.TypeOneTime,
        Capability = req.Capability,
        Scope = new List<string>(req.Scope),
        ApprovedParametersDigest = req.RequestedParametersDigest,
        PreviewDigest = req.PreviewDigest,
        Requester = req.Requester,
        Approver = new Dictionary<string, object> { ["subject"] = "approver" },
        IssuedAt = NowIso(),
        ExpiresAt = InIso(expiresInSeconds),
        MaxUses = maxUses,
        UseCount = useCount,
        Signature = "sig.sig.sig",
    };

    [Fact]
    public void ApprovalRequestRoundTrip()
    {
        var req = PendingRequest("apr_round1");
        _storage.StoreApprovalRequest(req);
        var loaded = _storage.GetApprovalRequest("apr_round1");
        Assert.NotNull(loaded);
        Assert.Equal("apr_round1", loaded!.ApprovalRequestId);
        Assert.Equal(ApprovalRequest.StatusPending, loaded.Status);
    }

    [Fact]
    public void ApprovalRequestIdempotentSameContent()
    {
        var req = PendingRequest("apr_idem1");
        _storage.StoreApprovalRequest(req);
        // Same content — no exception.
        _storage.StoreApprovalRequest(req);
        Assert.NotNull(_storage.GetApprovalRequest("apr_idem1"));
    }

    [Fact]
    public void ApprovalRequestRejectsConflictingContent()
    {
        var req = PendingRequest("apr_conf");
        _storage.StoreApprovalRequest(req);
        var mutated = PendingRequest("apr_conf");
        mutated.Capability = "different_cap";
        var ex = Assert.Throws<InvalidOperationException>(() => _storage.StoreApprovalRequest(mutated));
        Assert.Contains("already stored with different content", ex.Message);
    }

    [Fact]
    public void ApproveRequestAndStoreGrantHappyPath()
    {
        var req = PendingRequest("apr_happy");
        _storage.StoreApprovalRequest(req);
        var grant = GrantFor(req, 3, 0, 300);
        var r = _storage.ApproveRequestAndStoreGrant(
            "apr_happy", grant,
            new Dictionary<string, object?> { ["subject"] = "approver" },
            NowIso(), NowIso());
        Assert.True(r.Ok);
        Assert.NotNull(r.Grant);
        var loaded = _storage.GetApprovalRequest("apr_happy");
        Assert.NotNull(loaded);
        Assert.Equal(ApprovalRequest.StatusApproved, loaded!.Status);
        Assert.NotNull(_storage.GetGrant("grant_apr_happy"));
    }

    [Fact]
    public void ApproveRequestAndStoreGrantRejectsNotFound()
    {
        var req = PendingRequest("apr_x");
        var grant = GrantFor(req, 1, 0, 300);
        var r = _storage.ApproveRequestAndStoreGrant(
            "apr_missing", grant,
            new Dictionary<string, object?> { ["subject"] = "a" }, NowIso(), NowIso());
        Assert.False(r.Ok);
        Assert.Equal("approval_request_not_found", r.Reason);
    }

    [Fact]
    public void ApproveRequestAndStoreGrantRejectsAlreadyDecided()
    {
        var req = PendingRequest("apr_dec");
        _storage.StoreApprovalRequest(req);
        var grant1 = GrantFor(req, 1, 0, 300);
        var first = _storage.ApproveRequestAndStoreGrant("apr_dec", grant1,
            new Dictionary<string, object?> { ["subject"] = "a" }, NowIso(), NowIso());
        Assert.True(first.Ok);
        var grant2 = GrantFor(req, 1, 0, 300);
        grant2.GrantId = "grant_dup";
        var second = _storage.ApproveRequestAndStoreGrant("apr_dec", grant2,
            new Dictionary<string, object?> { ["subject"] = "b" }, NowIso(), NowIso());
        Assert.False(second.Ok);
        Assert.Equal("approval_request_already_decided", second.Reason);
    }

    [Fact]
    public void ApproveRequestAndStoreGrantRejectsExpired()
    {
        var req = PendingRequest("apr_exp");
        req.CreatedAt = "2000-01-01T00:00:00Z";
        req.ExpiresAt = "2000-01-01T00:00:01Z";
        _storage.StoreApprovalRequest(req);
        var grant = GrantFor(req, 1, 0, 60);
        var r = _storage.ApproveRequestAndStoreGrant("apr_exp", grant,
            new Dictionary<string, object?> { ["subject"] = "a" }, NowIso(), NowIso());
        Assert.False(r.Ok);
        Assert.Equal("approval_request_expired", r.Reason);
    }

    [Fact]
    public async Task ConcurrentIssuanceRaceLeavesExactlyOneSuccess()
    {
        var req = PendingRequest("apr_race");
        _storage.StoreApprovalRequest(req);

        var okCount = 0;
        var sync = new object();
        var tasks = Enumerable.Range(0, 16).Select(i => Task.Run(() =>
        {
            try
            {
                var grant = new ApprovalGrant
                {
                    GrantId = $"grant_race_{i}",
                    ApprovalRequestId = req.ApprovalRequestId,
                    GrantType = ApprovalGrant.TypeOneTime,
                    Capability = req.Capability,
                    Scope = req.Scope,
                    ApprovedParametersDigest = req.RequestedParametersDigest,
                    PreviewDigest = req.PreviewDigest,
                    Requester = req.Requester,
                    Approver = new Dictionary<string, object> { ["subject"] = "approver_" + i },
                    IssuedAt = NowIso(),
                    ExpiresAt = InIso(60),
                    MaxUses = 1,
                    UseCount = 0,
                    Signature = "sig",
                };
                var r = _storage.ApproveRequestAndStoreGrant(req.ApprovalRequestId, grant,
                    new Dictionary<string, object?> { ["subject"] = "approver_" + i }, NowIso(), NowIso());
                if (r.Ok)
                {
                    lock (sync) { okCount++; }
                }
            }
            catch
            {
                // Conflicting writes are expected in races; only one txn should win.
            }
        }));
        await Task.WhenAll(tasks);
        Assert.Equal(1, okCount);
    }

    [Fact]
    public void TryReserveGrantHappyPath()
    {
        var req = PendingRequest("apr_res1");
        _storage.StoreApprovalRequest(req);
        var grant = GrantFor(req, 3, 0, 300);
        _storage.ApproveRequestAndStoreGrant("apr_res1", grant,
            new Dictionary<string, object?> { ["subject"] = "approver" }, NowIso(), NowIso());
        var r = _storage.TryReserveGrant(grant.GrantId, NowIso());
        Assert.True(r.Ok);
        Assert.NotNull(r.Grant);
        Assert.Equal(1, r.Grant!.UseCount);
    }

    [Fact]
    public void TryReserveGrantNotFound()
    {
        var r = _storage.TryReserveGrant("nope", NowIso());
        Assert.False(r.Ok);
        Assert.Equal("grant_not_found", r.Reason);
    }

    [Fact]
    public void TryReserveGrantExpired()
    {
        var req = PendingRequest("apr_exp2");
        _storage.StoreApprovalRequest(req);
        var grant = new ApprovalGrant
        {
            GrantId = "grant_exp",
            ApprovalRequestId = req.ApprovalRequestId,
            GrantType = ApprovalGrant.TypeOneTime,
            Capability = req.Capability,
            Scope = req.Scope,
            ApprovedParametersDigest = req.RequestedParametersDigest,
            PreviewDigest = req.PreviewDigest,
            Requester = req.Requester,
            Approver = new Dictionary<string, object> { ["subject"] = "approver" },
            IssuedAt = "2000-01-01T00:00:00Z",
            ExpiresAt = "2000-01-01T00:00:01Z",
            MaxUses = 1,
            UseCount = 0,
            Signature = "sig",
        };
        _storage.StoreGrant(grant);
        var r = _storage.TryReserveGrant("grant_exp", NowIso());
        Assert.False(r.Ok);
        Assert.Equal("grant_expired", r.Reason);
    }

    [Fact]
    public void TryReserveGrantConsumed()
    {
        var req = PendingRequest("apr_cons");
        _storage.StoreApprovalRequest(req);
        var grant = GrantFor(req, 1, 1, 300); // already at max_uses
        _storage.StoreGrant(grant);
        var r = _storage.TryReserveGrant(grant.GrantId, NowIso());
        Assert.False(r.Ok);
        Assert.Equal("grant_consumed", r.Reason);
    }

    [Fact]
    public async Task ConcurrentReservationNeverExceedsMaxUses()
    {
        var req = PendingRequest("apr_concres");
        _storage.StoreApprovalRequest(req);
        var grant = GrantFor(req, 5, 0, 300);
        _storage.ApproveRequestAndStoreGrant("apr_concres", grant,
            new Dictionary<string, object?> { ["subject"] = "approver" }, NowIso(), NowIso());

        var okCount = 0;
        var sync = new object();
        var tasks = Enumerable.Range(0, 20).Select(_ => Task.Run(() =>
        {
            try
            {
                var r = _storage.TryReserveGrant(grant.GrantId, NowIso());
                if (r.Ok)
                {
                    lock (sync) { okCount++; }
                }
            }
            catch { }
        }));
        await Task.WhenAll(tasks);
        Assert.Equal(5, okCount);
        var after = _storage.GetGrant(grant.GrantId);
        Assert.NotNull(after);
        Assert.Equal(5, after!.UseCount);
    }
}
