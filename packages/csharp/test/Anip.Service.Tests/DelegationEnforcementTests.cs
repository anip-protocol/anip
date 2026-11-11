using System.Collections.Concurrent;
using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// Delegation enforcement (SPEC.md §3.2, §6.3 and the behavioral-conformance
/// list). Mirrors the Python reference in anip_server/delegation.py and the
/// cross-runtime suite in conformance/test_delegation.py.
///
/// - Purpose binding: "a token issued for book_flight cannot invoke
///   search_flights", even when its scope would cover both.
/// - Only the holder of a token (its subject) may delegate from it.
/// - A delegated token cannot widen its parent's scope or scope budget.
/// - Chains deeper than max_delegation_depth are rejected.
/// - A delegation token is a credential for delegating, never for root issuance.
///
/// Composed capabilities (§4.6) must still work under those rules: each child
/// step runs with its own token, delegated from the caller's token and bound
/// to the child capability, and its audit entry links back to the parent
/// invocation.
/// </summary>
public class DelegationEnforcementTests : IDisposable
{
    private const string Human = "human:test@example.com";

    private readonly AnipService _service;
    private readonly ConcurrentDictionary<string, DelegationToken> _seenTokens = new();

    public DelegationEnforcementTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "test-service",
            Storage = ":memory:",
            Trust = "signed",
            Capabilities = new List<CapabilityDef>
            {
                Recording("search_flights", new() { "travel.search" }, streaming: true,
                    new() { ["flights"] = new List<object?> { "FL-001" } }),
                Recording("book_flight", new() { "travel.book" }, streaming: true,
                    new() { ["booking_id"] = "BK-001" }),
                Recording("select_cap", new() { "inv.read" }, streaming: false,
                    new() { ["items"] = new List<object?> { "a", "b" } }),
                Recording("enrich_cap", new() { "inv.read" }, streaming: false,
                    new() { ["count"] = 2 }),
                new(SummaryDeclaration(), (ctx, parameters) => new Dictionary<string, object?>()),
            },
            Authenticate = bearer => bearer == "test-key" ? Human : null,
        });
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    // --- fixtures --------------------------------------------------------------

    private static CapabilityDeclaration Declaration(string name, List<string> scope, bool streaming) => new()
    {
        Name = name,
        Description = name,
        ContractVersion = "1.0",
        SideEffect = new SideEffect { Type = "read" },
        MinimumScope = scope,
        ResponseModes = streaming ? new List<string> { "sync", "streaming" } : new List<string> { "sync" },
    };

    private CapabilityDef Recording(string name, List<string> scope, bool streaming,
        Dictionary<string, object?> result) =>
        new(Declaration(name, scope, streaming), (ctx, parameters) =>
        {
            _seenTokens[name] = ctx.Token;
            return result;
        });

    private static CapabilityDeclaration SummaryDeclaration()
    {
        var decl = Declaration("summary", new() { "inv.read" }, streaming: false);
        decl.Kind = "composed";
        decl.Composition = new Composition
        {
            AuthorityBoundary = "same_service",
            Steps = new List<CompositionStep>
            {
                new() { Id = "select", Capability = "select_cap" },
                new() { Id = "enrich", Capability = "enrich_cap" },
            },
            InputMapping = new Dictionary<string, Dictionary<string, string>>
            {
                ["select"] = new() { ["q"] = "$.input.q" },
                ["enrich"] = new() { ["items"] = "$.steps.select.output.items" },
            },
            OutputMapping = new Dictionary<string, string>
            {
                ["count"] = "$.steps.enrich.output.count",
            },
        };
        return decl;
    }

    private TokenResponse Issue(string principal, string? subject, List<string> scope,
        string capability, string? parentToken = null) =>
        _service.IssueToken(principal, new TokenRequest
        {
            Subject = subject ?? "",
            Scope = scope,
            Capability = capability,
            ParentToken = parentToken,
        });

    private DelegationToken IssueBound(string capability, List<string> scope) =>
        _service.ResolveBearerToken(Issue(Human, Human, scope, capability).Token);

    private static string? FailureType(Dictionary<string, object?> result)
    {
        var failure = Assert.IsAssignableFrom<IDictionary<string, object?>>(result["failure"]);
        return failure["type"] as string;
    }

    private static void AssertIssuanceFails(string expectedType, Action call)
    {
        var error = Assert.Throws<AnipError>(call);
        Assert.Equal(expectedType, error.ErrorType);
    }

    private static readonly Dictionary<string, object?> NoParams = new();

    // --- purpose binding -------------------------------------------------------

    [Fact]
    public void Invoke_RejectsTokenBoundToAnotherCapability()
    {
        // Scope covers both capabilities; the token is bound to book_flight.
        var token = IssueBound("book_flight", new() { "travel.search", "travel.book" });

        var result = _service.Invoke("search_flights", token, NoParams, new InvokeOpts());

        Assert.Equal(false, result["success"]);
        Assert.Equal(Constants.FailurePurposeMismatch, FailureType(result));
        Assert.False(_seenTokens.ContainsKey("search_flights"), "the handler must not run");

        var entries = _service.QueryAudit(token, new AuditFilters()).Entries;
        var entry = Assert.Single(entries);
        Assert.Equal("search_flights", entry.Capability);
        Assert.False(entry.Success);
        Assert.Equal(Constants.FailurePurposeMismatch, entry.FailureType);
    }

    [Fact]
    public void InvokeStream_RejectsTokenBoundToAnotherCapability()
    {
        var token = IssueBound("book_flight", new() { "travel.search", "travel.book" });

        var error = Assert.Throws<AnipError>(() =>
            _service.InvokeStream("search_flights", token, NoParams, new InvokeOpts { Stream = true }));

        Assert.Equal(Constants.FailurePurposeMismatch, error.ErrorType);
    }

    // --- delegated issuance ----------------------------------------------------

    [Fact]
    public void IssueToken_HolderDelegatesWithinScope()
    {
        var root = Issue(Human, Human, new() { "travel.search", "travel.book" }, "search_flights");

        var child = Issue(Human, "agent:helper", new() { "travel.search" }, "search_flights", root.TokenId);

        var token = _service.ResolveBearerToken(child.Token);
        Assert.Equal(root.TokenId, token.Parent);
        Assert.Equal(Human, token.RootPrincipal);
    }

    [Fact]
    public void IssueToken_RejectsDelegationByNonHolder()
    {
        var root = Issue(Human, Human, new() { "travel.search" }, "search_flights");

        AssertIssuanceFails(Constants.FailureInsufficientAuthority, () =>
            Issue("agent:someone-else", null, new() { "travel.search" }, "search_flights", root.TokenId));
    }

    [Fact]
    public void IssueToken_RejectsScopeWidening()
    {
        var root = Issue(Human, Human, new() { "travel.search" }, "search_flights");

        AssertIssuanceFails(Constants.FailureScopeEscalation, () =>
            Issue(Human, null, new() { "travel.search", "travel.book" }, "book_flight", root.TokenId));
    }

    [Theory]
    [InlineData("same scope", "travel.search", "travel.search", true)]
    [InlineData("sub-scope of parent", "travel", "travel.search", true)]
    [InlineData("sibling scope", "travel.search", "travel.book", false)]
    [InlineData("prefix without a dot boundary", "travel", "travelogue.read", false)]
    [InlineData("keeps scope budget", "travel.book:max_$500", "travel.book:max_$500", true)]
    [InlineData("lowers scope budget", "travel.book:max_$500", "travel.book:max_$100", true)]
    [InlineData("drops scope budget", "travel.book:max_$500", "travel.book", false)]
    [InlineData("raises scope budget", "travel.book:max_$500", "travel.book:max_$900", false)]
    // A budget that is not a finite, non-negative number must fail closed:
    // NaN compares false against everything.
    [InlineData("NaN scope budget", "travel.book:max_$500", "travel.book:max_$NaN", false)]
    [InlineData("infinite scope budget", "travel.book:max_$500", "travel.book:max_$Infinity", false)]
    [InlineData("negative scope budget", "travel.book:max_$500", "travel.book:max_$-1", false)]
    [InlineData("unparseable scope budget", "travel.book:max_$500", "travel.book:max_$lots", false)]
    public void IssueToken_ScopeNarrowingRules(string name, string parentScope, string childScope, bool allowed)
    {
        var root = Issue(Human, Human, new() { parentScope }, "book_flight");

        if (allowed)
        {
            var child = Issue(Human, null, new() { childScope }, "book_flight", root.TokenId);
            Assert.True(child.Issued, name);
        }
        else
        {
            AssertIssuanceFails(Constants.FailureScopeEscalation, () =>
                Issue(Human, null, new() { childScope }, "book_flight", root.TokenId));
        }
    }

    // --- delegation depth ------------------------------------------------------

    [Fact]
    public void Invoke_EnforcesDelegationDepth()
    {
        var token = Issue(Human, Human, new() { "travel.search" }, "search_flights");

        // The default max_delegation_depth is 3: depths 1..3 work, depth 4 does not.
        for (var depth = 1; depth <= 4; depth++)
        {
            token = Issue(Human, null, new() { "travel.search" }, "search_flights", token.TokenId);
            var result = _service.Invoke("search_flights", _service.ResolveBearerToken(token.Token),
                NoParams, new InvokeOpts());
            if (depth <= 3)
            {
                Assert.True((bool)result["success"]!, $"depth {depth} is within the limit");
            }
            else
            {
                Assert.Equal(false, result["success"]);
                Assert.Equal(Constants.FailureDelegationDepthExceeded, FailureType(result));
            }
        }
    }

    // --- who may ask for a token -----------------------------------------------

    [Fact]
    public void AuthenticateIssuer_AcceptsBootstrapCredentialAndTokens()
    {
        var bootstrap = _service.AuthenticateIssuer("test-key");
        Assert.NotNull(bootstrap);
        Assert.Equal(Human, bootstrap!.Principal);
        Assert.False(bootstrap.ViaToken);

        var held = Issue(Human, "agent:helper", new() { "travel.search" }, "search_flights");
        var viaToken = _service.AuthenticateIssuer(held.Token);
        Assert.NotNull(viaToken);
        Assert.Equal("agent:helper", viaToken!.Principal);
        Assert.True(viaToken.ViaToken);

        Assert.Null(_service.AuthenticateIssuer("not-a-credential"));
    }

    [Fact]
    public void IssueTokenAs_RejectsRootIssuanceWithTokenCredential()
    {
        var held = Issue(Human, "agent:helper", new() { "travel.search" }, "search_flights");
        var issuer = _service.AuthenticateIssuer(held.Token)!;

        // No parent_token: this asks for a root token, with more scope than
        // the agent was ever given.
        AssertIssuanceFails(Constants.FailureInsufficientAuthority, () =>
            _service.IssueTokenAs(issuer, new TokenRequest
            {
                Scope = new() { "travel.search", "travel.book" },
                Capability = "book_flight",
            }));
    }

    [Fact]
    public void IssueTokenAs_HolderDelegatesWithTokenCredential()
    {
        var held = Issue(Human, "agent:helper", new() { "travel.search" }, "search_flights");
        var issuer = _service.AuthenticateIssuer(held.Token)!;

        var child = _service.IssueTokenAs(issuer, new TokenRequest
        {
            Subject = "agent:sub-helper",
            Scope = new() { "travel.search" },
            Capability = "search_flights",
            ParentToken = held.TokenId,
        });

        var token = _service.ResolveBearerToken(child.Token);
        Assert.Equal(Human, token.RootPrincipal);
        Assert.Equal("agent:helper", token.Issuer);
    }

    [Fact]
    public void IssueTokenAs_BootstrapCredentialIssuesRootToken()
    {
        var issuer = _service.AuthenticateIssuer("test-key")!;

        var root = _service.IssueTokenAs(issuer, new TokenRequest
        {
            Scope = new() { "travel.search" },
            Capability = "search_flights",
        });

        Assert.True(root.Issued);
    }

    // --- composed capabilities -------------------------------------------------

    [Fact]
    public void ComposedInvocation_RunsChildrenWithChildBoundTokens()
    {
        var token = IssueBound("summary", new() { "inv.read" });

        var result = _service.Invoke("summary", token,
            new Dictionary<string, object?> { ["q"] = "x" }, new InvokeOpts());

        Assert.True((bool)result["success"]!, "the composed invocation should succeed");
        var parentInvocationId = (string)result["invocation_id"]!;

        foreach (var child in new[] { "select_cap", "enrich_cap" })
        {
            Assert.True(_seenTokens.TryGetValue(child, out var childToken), $"child {child} was not invoked");
            Assert.Equal(child, childToken!.Purpose.Capability);
            Assert.Equal(token.TokenId, childToken.Parent);
        }

        var byCapability = _service.QueryAudit(token, new AuditFilters()).Entries
            .GroupBy(e => e.Capability).ToDictionary(g => g.Key, g => g.Last());
        Assert.True(byCapability.TryGetValue("summary", out var parentEntry), "no audit entry for the parent");
        foreach (var child in new[] { "select_cap", "enrich_cap" })
        {
            Assert.True(byCapability.TryGetValue(child, out var entry), $"no audit entry for child {child}");
            Assert.True(entry!.Success, $"child {child} failed: {entry.FailureType}");
            Assert.Equal(parentInvocationId, entry.ParentInvocationId);
            Assert.False(string.IsNullOrEmpty(entry.TaskId));
            Assert.Equal(parentEntry!.TaskId, entry.TaskId);
        }
    }
}
