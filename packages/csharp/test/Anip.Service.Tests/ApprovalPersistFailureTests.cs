using System.Reflection;
using Anip.Core;
using Anip.Server;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// SPEC.md §4.7 persistence invariant: when the ApprovalRequest cannot be
/// stored, the invocation fails with <c>service_unavailable</c>.
/// </summary>
public class ApprovalPersistFailureTests : IDisposable
{
    private readonly AnipService _service;

    public ApprovalPersistFailureTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "svc-persist",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "needs_approval",
                        Description = "always asks for approval",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "write" },
                        MinimumScope = new List<string> { "data.write" },
                        GrantPolicy = new GrantPolicy
                        {
                            AllowedGrantTypes = new() { "one_time" },
                            DefaultGrantType = "one_time",
                            ExpiresInSeconds = 600,
                            MaxUses = 1,
                        },
                    },
                    (ctx, p) => throw new AnipError(Constants.FailureApprovalRequired, "approval needed")
                        .WithResolution("request_approval")),
            },
            Authenticate = bearer => bearer == "valid-key" ? "alice" : null,
        });
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    /// <summary>Forwards to the real storage, except that an ApprovalRequest cannot be stored.</summary>
    public class StorageThatCannotStoreApprovalRequests : DispatchProxy
    {
        public IStorage Inner { get; set; } = null!;

        protected override object? Invoke(MethodInfo? targetMethod, object?[]? args)
        {
            if (targetMethod!.Name == nameof(IStorage.StoreApprovalRequest))
            {
                throw new InvalidOperationException("disk full");
            }
            try
            {
                return targetMethod.Invoke(Inner, args);
            }
            catch (TargetInvocationException e) when (e.InnerException != null)
            {
                throw e.InnerException;
            }
        }
    }

    private void BreakApprovalRequestStorage()
    {
        var field = typeof(AnipService).GetField("_storage", BindingFlags.Instance | BindingFlags.NonPublic)!;
        var proxy = DispatchProxy.Create<IStorage, StorageThatCannotStoreApprovalRequests>();
        ((StorageThatCannotStoreApprovalRequests)(object)proxy).Inner = (IStorage)field.GetValue(_service)!;
        field.SetValue(_service, proxy);
    }

    private DelegationToken Token() => _service.ResolveBearerToken(
        _service.IssueToken("alice", new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { "data.write" },
            Capability = "needs_approval",
            TtlHours = 1,
        }).Token);

    [Fact]
    public void Control_ApprovalRequestIsPersisted()
    {
        var response = _service.Invoke("needs_approval", Token(), new Dictionary<string, object?>(), new InvokeOpts());

        var failure = (Dictionary<string, object?>)response["failure"]!;
        Assert.Equal(Constants.FailureApprovalRequired, failure["type"]);
        Assert.True(failure.ContainsKey("approval_required"));
    }

    [Fact]
    public void WhenTheApprovalRequestCannotBeStored_TheFailureIsServiceUnavailable()
    {
        var token = Token();
        BreakApprovalRequestStorage();

        var response = _service.Invoke("needs_approval", token, new Dictionary<string, object?>(), new InvokeOpts());

        Assert.Equal(false, response["success"]);
        var failure = (Dictionary<string, object?>)response["failure"]!;
        Assert.Equal("service_unavailable", failure["type"]);
        Assert.Equal("approval flow unavailable: disk full", failure["detail"]);
        var resolution = (Dictionary<string, object?>)failure["resolution"]!;
        Assert.Equal("wait_and_retry", resolution["action"]);
        Assert.Equal("wait_then_retry", resolution["recovery_class"]);
        Assert.False(failure.ContainsKey("approval_required"));

        var entry = Assert.Single(
            _service.QueryAudit(token, new AuditFilters { InvocationId = (string)response["invocation_id"]!, Limit = 10 })
                .Entries);
        Assert.False(entry.Success);
        Assert.Equal("service_unavailable", entry.FailureType);
        Assert.Null(entry.ApprovalRequestId);
    }
}
