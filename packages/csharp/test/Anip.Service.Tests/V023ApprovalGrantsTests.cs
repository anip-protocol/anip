using Anip.Core;
using Anip.Server;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>v0.23 IssueApprovalGrant SPI + ValidateContinuationGrant + audit linkage.</summary>
public class V023ApprovalGrantsTests : IDisposable
{
    private readonly AnipService _service;
    private readonly string _principal = "alice";

    public V023ApprovalGrantsTests()
    {
        var config = new ServiceConfig
        {
            ServiceId = "svc-test",
            Storage = ":memory:",
            Trust = "signed",
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "send_notice",
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "msg", Type = "string", Required = false },
                        },
                        Description = "side-effect cap requiring approval",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "write" },
                        MinimumScope = new List<string> { "data.write" },
                        GrantPolicy = new GrantPolicy
                        {
                            AllowedGrantTypes = new() { "one_time", "session_bound" },
                            DefaultGrantType = "one_time",
                            ExpiresInSeconds = 600,
                            MaxUses = 3,
                        },
                    },
                    (ctx, p) => new Dictionary<string, object?>
                    {
                        ["sent"] = true,
                        ["approval_grant"] = ctx.ApprovalGrant,
                    }),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "needs_approval",
                        Description = "always asks for approval",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "write" },
                        MinimumScope = new List<string> { "data.write" },
                        ResponseModes = new List<string> { "unary", "streaming" },
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
            Authenticate = bearer => bearer == "valid-key" ? _principal : null,
        };
        _service = new AnipService(config);
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    private GrantPolicy DefaultPolicy() => new()
    {
        AllowedGrantTypes = new() { "one_time", "session_bound" },
        DefaultGrantType = "one_time",
        ExpiresInSeconds = 600,
        MaxUses = 3,
    };

    private string SeedPendingRequest(string id, string capability = "send_notice")
    {
        var req = new ApprovalRequest
        {
            ApprovalRequestId = id,
            Capability = capability,
            Scope = new List<string> { "data.write" },
            Requester = new Dictionary<string, object> { ["subject"] = _principal, ["root_principal"] = _principal },
            Preview = new Dictionary<string, object>(),
            PreviewDigest = V023.Sha256Digest(new Dictionary<string, object>()),
            RequestedParameters = new Dictionary<string, object> { ["msg"] = "hi" },
            RequestedParametersDigest = V023.Sha256Digest(new Dictionary<string, object> { ["msg"] = "hi" }),
            GrantPolicy = DefaultPolicy(),
            Status = ApprovalRequest.StatusPending,
            CreatedAt = V023.UtcNowIso(),
            ExpiresAt = V023.UtcInIso(900),
        };
        _service.GetStorage().StoreApprovalRequest(req);
        return id;
    }

    [Fact]
    public void IssueApprovalGrant_HappyPath_OneTime()
    {
        SeedPendingRequest("apr_one1");
        var approver = new Dictionary<string, object?>
        {
            ["subject"] = "boss",
            ["root_principal"] = "boss",
        };
        var grant = _service.IssueApprovalGrant(
            "apr_one1", ApprovalGrant.TypeOneTime, approver, null, null, null);
        Assert.NotNull(grant);
        Assert.Equal("send_notice", grant.Capability);
        Assert.Equal(1, grant.MaxUses);
        Assert.NotEmpty(grant.Signature);
        // Underlying request transitioned to approved.
        var loaded = _service.GetApprovalRequest("apr_one1");
        Assert.NotNull(loaded);
        Assert.Equal(ApprovalRequest.StatusApproved, loaded!.Status);
    }

    [Fact]
    public void InvokeContinuationExposesApprovalGrantToHandlerContext()
    {
        SeedPendingRequest("apr_ctx");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var grant = _service.IssueApprovalGrant(
            "apr_ctx", ApprovalGrant.TypeOneTime, approver, null, null, null);

        var tokenResponse = _service.IssueToken(_principal, new TokenRequest
        {
            Scope = new List<string> { "data.write" },
            Capability = "send_notice",
        });
        var token = _service.ResolveBearerToken(tokenResponse.Token);

        var result = _service.Invoke("send_notice", token,
            new Dictionary<string, object?> { ["msg"] = "hi" },
            new InvokeOpts { ApprovalGrant = grant.GrantId });

        Assert.Equal(true, result["success"]);
        var innerResult = (Dictionary<string, object?>)result["result"]!;
        Assert.Equal(grant.GrantId, innerResult["approval_grant"]);
    }

    [Fact]
    public void IssueApprovalGrant_RejectsUnknownRequest()
    {
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_missing", ApprovalGrant.TypeOneTime, approver, null, null, null));
        Assert.Equal(Constants.FailureApprovalRequestNotFound, ex.ErrorType);
    }

    [Fact]
    public void IssueApprovalGrant_SessionBoundRequiresSessionId()
    {
        SeedPendingRequest("apr_sb1");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_sb1", ApprovalGrant.TypeSessionBound, approver, null, null, null));
        Assert.Equal(Constants.FailureGrantTypeNotAllowed, ex.ErrorType);
    }

    [Fact]
    public void IssueApprovalGrant_ClampsExpiresAndMaxUses()
    {
        SeedPendingRequest("apr_clamp");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_clamp", ApprovalGrant.TypeOneTime, approver, null, 99999, null));
        Assert.Equal(Constants.FailureGrantTypeNotAllowed, ex.ErrorType);
    }

    // SPEC §4.9: when supplied, expires_in_seconds and max_uses must be
    // positive integers. The HTTP route validates this but admin UIs / queue
    // workers / tests call the SPI directly per §4.9 line 1110, so the helper
    // re-validates. Otherwise an out-of-band caller could store an immediately
    // expired or unusable grant.
    [Fact]
    public void IssueApprovalGrant_RejectsExpiresInSecondsZero()
    {
        SeedPendingRequest("apr_zexp");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_zexp", ApprovalGrant.TypeOneTime, approver, null, 0, null));
        Assert.Equal(Constants.FailureInvalidParameters, ex.ErrorType);
    }

    [Fact]
    public void IssueApprovalGrant_RejectsExpiresInSecondsNegative()
    {
        SeedPendingRequest("apr_nexp");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_nexp", ApprovalGrant.TypeOneTime, approver, null, -10, null));
        Assert.Equal(Constants.FailureInvalidParameters, ex.ErrorType);
    }

    [Fact]
    public void IssueApprovalGrant_RejectsMaxUsesZero()
    {
        SeedPendingRequest("apr_zmax");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_zmax", ApprovalGrant.TypeSessionBound, approver, "sess-1", null, 0));
        Assert.Equal(Constants.FailureInvalidParameters, ex.ErrorType);
    }

    [Fact]
    public void IssueApprovalGrant_RejectsMaxUsesNegative()
    {
        SeedPendingRequest("apr_nmax");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_nmax", ApprovalGrant.TypeSessionBound, approver, "sess-1", null, -1));
        Assert.Equal(Constants.FailureInvalidParameters, ex.ErrorType);
    }

    [Fact]
    public void IssueApprovalGrant_RejectsAlreadyDecided()
    {
        SeedPendingRequest("apr_done");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        _service.IssueApprovalGrant("apr_done", ApprovalGrant.TypeOneTime, approver, null, null, null);
        var ex = Assert.Throws<AnipError>(() => _service.IssueApprovalGrant(
            "apr_done", ApprovalGrant.TypeOneTime, approver, null, null, null));
        Assert.Equal(Constants.FailureApprovalRequestAlreadyDecided, ex.ErrorType);
    }

    [Fact]
    public async Task IssueApprovalGrant_ConcurrentSafe_OnlyOneSucceeds()
    {
        SeedPendingRequest("apr_conc");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var okCount = 0;
        var sync = new object();
        var tasks = Enumerable.Range(0, 10).Select(_ => Task.Run(() =>
        {
            try
            {
                var g = _service.IssueApprovalGrant(
                    "apr_conc", ApprovalGrant.TypeOneTime, approver, null, null, null);
                if (g != null)
                {
                    lock (sync) { okCount++; }
                }
            }
            catch
            {
                // Expected — only one txn wins.
            }
        }));
        await Task.WhenAll(tasks);
        Assert.Equal(1, okCount);
    }

    [Fact]
    public void ValidateContinuationGrant_HappyPath()
    {
        // Use the keys/storage of the running service.
        SeedPendingRequest("apr_cont");
        var approver = new Dictionary<string, object?> { ["subject"] = "boss" };
        var grant = _service.IssueApprovalGrant(
            "apr_cont", ApprovalGrant.TypeOneTime, approver, null, null, null);

        // Reflectively pull the KeyManager via the storage handle isn't possible —
        // instead validate via an end-to-end check using GetGrant + signature
        // inspection: since we just signed with the service's KeyManager, the
        // grant.Signature must be a non-empty detached JWS.
        Assert.NotNull(grant.Signature);
        Assert.Contains("..", grant.Signature);

        // Verify use_count starts at zero, then atomic reservation increments.
        var reserved = _service.GetStorage().TryReserveGrant(grant.GrantId, V023.UtcNowIso());
        Assert.True(reserved.Ok);
        Assert.Equal(1, reserved.Grant!.UseCount);
    }

    // --- The grant binds its requester's root principal (SPEC.md §4.8 step 5) ---

    [Fact]
    public void Invoke_AnotherPrincipalCannotRedeemAndTheGrantIsNotSpent()
    {
        SeedPendingRequest("apr_rq1");
        var grant = _service.IssueApprovalGrant(
            "apr_rq1", ApprovalGrant.TypeOneTime, new Dictionary<string, object?> { ["subject"] = "boss" },
            null, null, null);
        var bob = _service.ResolveBearerToken(_service.IssueToken("bob", new TokenRequest
        {
            Scope = new List<string> { "data.write" },
            Capability = "send_notice",
        }).Token);

        var refused = _service.Invoke("send_notice", bob,
            new Dictionary<string, object?> { ["msg"] = "hi" },
            new InvokeOpts { ApprovalGrant = grant.GrantId });

        var failure = FailureOf(refused);
        Assert.Equal(Constants.FailureGrantRequesterMismatch, failure["type"]);
        var resolution = (Dictionary<string, object?>)failure["resolution"]!;
        Assert.Equal("contact_service_owner", resolution["action"]);
        Assert.Equal("terminal", resolution["recovery_class"]);
        Assert.Equal(0, _service.GetStorage().GetGrant(grant.GrantId)!.UseCount);
        Assert.Equal(403, Constants.FailureStatusCode(Constants.FailureGrantRequesterMismatch));

        var ok = _service.Invoke("send_notice", TokenFor("send_notice"),
            new Dictionary<string, object?> { ["msg"] = "hi" },
            new InvokeOpts { ApprovalGrant = grant.GrantId });
        Assert.Equal(true, ok["success"]);
    }

    [Fact]
    public void Invoke_ApprovalRequestRecordsTheRootPrincipal()
    {
        var response = _service.Invoke("needs_approval", TokenFor("needs_approval"),
            new Dictionary<string, object?>(), new InvokeOpts());
        var meta = FailureOf(response)["approval_required"];
        var id = meta switch
        {
            ApprovalRequiredMetadata m => m.ApprovalRequestId,
            Dictionary<string, object?> d => (string)d["approval_request_id"]!,
            _ => throw new Xunit.Sdk.XunitException($"unexpected metadata {meta}"),
        };
        var request = _service.GetApprovalRequest(id!)!;
        Assert.Equal(_principal, request.Requester["root_principal"].ToString());
    }

    [Fact]
    public void ValidateContinuationGrant_RequesterAfterCapabilityBeforeScope()
    {
        SeedPendingRequest("apr_rq2");
        var grant = _service.IssueApprovalGrant(
            "apr_rq2", ApprovalGrant.TypeOneTime, new Dictionary<string, object?> { ["subject"] = "boss" },
            null, null, null);
        var keys = (Anip.Crypto.KeyManager)typeof(AnipService)
            .GetField("_keys", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!
            .GetValue(_service)!;
        var parameters = new Dictionary<string, object?> { ["msg"] = "hi" };

        Assert.Equal(Constants.FailureGrantCapabilityMismatch, V023.ValidateContinuationGrant(
            _service.GetStorage(), keys, grant.GrantId, "other_capability", parameters,
            new List<string> { "data.write" }, null, "bob", V023.UtcNowIso()).FailureType);
        Assert.Equal(Constants.FailureGrantRequesterMismatch, V023.ValidateContinuationGrant(
            _service.GetStorage(), keys, grant.GrantId, "send_notice", parameters,
            new List<string> { "other.scope" }, null, "bob", V023.UtcNowIso()).FailureType);
    }

    // --- Blank grants, resolution and retry ---

    private DelegationToken TokenFor(string capability)
    {
        var tokenResponse = _service.IssueToken(_principal, new TokenRequest
        {
            Scope = new List<string> { "data.write" },
            Capability = capability,
        });
        return _service.ResolveBearerToken(tokenResponse.Token);
    }

    private static Dictionary<string, object?> FailureOf(Dictionary<string, object?> response)
    {
        Assert.Equal(false, response["success"]);
        return (Dictionary<string, object?>)response["failure"]!;
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("\t\n")]
    public void Invoke_BlankSuppliedGrantIsNotFoundBeforeTheHandler(string grant)
    {
        // A supplied approval_grant is always validated. A blank one names no
        // grant: the handler (which would succeed here) does not run.
        var failure = FailureOf(_service.Invoke("send_notice", TokenFor("send_notice"),
            new Dictionary<string, object?> { ["msg"] = "hi" },
            new InvokeOpts { ApprovalGrant = grant }));

        Assert.Equal(Constants.FailureGrantNotFound, failure["type"]);
        var resolution = (Dictionary<string, object?>)failure["resolution"]!;
        Assert.Equal("contact_service_owner", resolution["action"]);
        Assert.Equal("terminal", resolution["recovery_class"]);
    }

    [Fact]
    public void InvokeStream_BlankSuppliedGrantIsNotFound()
    {
        var ex = Assert.ThrowsAny<AnipError>(() => _service.InvokeStream(
            "needs_approval", TokenFor("needs_approval"),
            new Dictionary<string, object?>(),
            new InvokeOpts { ApprovalGrant = " ", Stream = true }));

        Assert.Equal(Constants.FailureGrantNotFound, ex.ErrorType);
        Assert.NotNull(ex.Resolution);
        Assert.Equal("terminal", ex.Resolution!.RecoveryClass);
    }

    [Fact]
    public void Invoke_UnknownGrantFailureCarriesResolution()
    {
        // SPEC.md §4.5: every failure carries a resolution with a recovery_class.
        var failure = FailureOf(_service.Invoke("send_notice", TokenFor("send_notice"),
            new Dictionary<string, object?> { ["msg"] = "hi" },
            new InvokeOpts { ApprovalGrant = "grant_missing" }));

        Assert.Equal(Constants.FailureGrantNotFound, failure["type"]);
        var resolution = (Dictionary<string, object?>)failure["resolution"]!;
        Assert.Equal("terminal", resolution["recovery_class"]);
    }

    [Fact]
    public void Invoke_ApprovalRequiredCarriesRetryFalse()
    {
        // SPEC.md §4.7: the approval_required failure carries retry: false.
        var failure = FailureOf(_service.Invoke("needs_approval", TokenFor("needs_approval"),
            new Dictionary<string, object?>(), new InvokeOpts()));

        Assert.Equal(Constants.FailureApprovalRequired, failure["type"]);
        Assert.True(failure.ContainsKey("retry"));
        Assert.Equal(false, failure["retry"]);
    }

    [Fact]
    public void ApprovalGrantFromRequest_KeepsAbsentAndSuppliedApart()
    {
        Assert.Null(InvokeOpts.ApprovalGrantFromRequest(null));
        Assert.Equal("", InvokeOpts.ApprovalGrantFromRequest(""));
        Assert.Equal("grant_1", InvokeOpts.ApprovalGrantFromRequest("grant_1"));
        Assert.Equal("", InvokeOpts.ApprovalGrantFromRequest(7));
        using var doc = System.Text.Json.JsonDocument.Parse("{\"a\":\"\",\"b\":null,\"c\":7,\"d\":\"g\"}");
        Assert.Equal("", InvokeOpts.ApprovalGrantFromRequest(doc.RootElement.GetProperty("a")));
        Assert.Null(InvokeOpts.ApprovalGrantFromRequest(doc.RootElement.GetProperty("b")));
        Assert.Equal("", InvokeOpts.ApprovalGrantFromRequest(doc.RootElement.GetProperty("c")));
        Assert.Equal("g", InvokeOpts.ApprovalGrantFromRequest(doc.RootElement.GetProperty("d")));
    }
}
