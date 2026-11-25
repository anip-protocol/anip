using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// A streaming invocation runs the checks the unary path runs before the
/// handler, in the same order (SPEC.md §6.3): delegation, budget, binding,
/// control requirements, parameter validation and the approval grant. For
/// each case the unary answer is the control; the streaming call must be
/// refused with the same failure type, must not run the handler, and must be
/// audited exactly where the unary refusal is.
/// </summary>
public class StreamingPreHandlerChecksTests : IDisposable
{
    private const string Principal = "alice";

    private readonly AnipService _service;
    private readonly Dictionary<string, int> _handlerRuns = new();

    public StreamingPreHandlerChecksTests()
    {
        CapabilityDef Streaming(CapabilityDeclaration declaration) => new(declaration, (ctx, p) =>
        {
            _handlerRuns[declaration.Name] = _handlerRuns.GetValueOrDefault(declaration.Name) + 1;
            return new Dictionary<string, object?> { ["ok"] = true };
        });

        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "svc-streaming-checks",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                Streaming(new CapabilityDeclaration
                {
                    Name = "watch_fixed",
                    Description = "fixed cost, streaming",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "read" },
                    MinimumScope = new List<string> { "travel.book" },
                    ResponseModes = new List<string> { "unary", "streaming" },
                    Inputs = new List<CapabilityInput> { new() { Name = "route", Type = "string" } },
                    Cost = new Cost
                    {
                        Certainty = "fixed",
                        Financial = new FinancialCost { Currency = "USD", Amount = 100 },
                    },
                }),
                Streaming(new CapabilityDeclaration
                {
                    Name = "watch_quote",
                    Description = "estimated cost priced by a quote binding, streaming",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "read" },
                    MinimumScope = new List<string> { "travel.book" },
                    ResponseModes = new List<string> { "unary", "streaming" },
                    Inputs = new List<CapabilityInput>
                    {
                        new() { Name = "route", Type = "string" },
                        new() { Name = "quote", Type = "object", Required = false },
                    },
                    Cost = new Cost
                    {
                        Certainty = "estimated",
                        Financial = new FinancialCost { Currency = "USD", RangeMin = 1, RangeMax = 500 },
                    },
                    RequiresBinding = new List<BindingRequirement>
                    {
                        new() { Type = "quote", Field = "quote", SourceCapability = "search", MaxAge = "PT15M" },
                    },
                }),
                Streaming(new CapabilityDeclaration
                {
                    Name = "watch_ceiling",
                    Description = "needs a cost ceiling, streaming",
                    ContractVersion = "1.0",
                    SideEffect = new SideEffect { Type = "read" },
                    MinimumScope = new List<string> { "travel.book" },
                    ResponseModes = new List<string> { "unary", "streaming" },
                    Inputs = new List<CapabilityInput> { new() { Name = "route", Type = "string" } },
                    ControlRequirements = new List<ControlRequirement> { new() { Type = "cost_ceiling" } },
                }),
            },
            Authenticate = bearer => bearer == "valid-key" ? Principal : null,
        });
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    private DelegationToken Token(string capability, string scope = "travel.book", Budget? budget = null)
    {
        var issued = _service.IssueToken(Principal, new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { scope },
            Capability = capability,
            Budget = budget,
            TtlHours = 1,
        });
        return _service.ResolveBearerToken(issued.Token);
    }

    private static Dictionary<string, object?> Body(string json) =>
        JsonSerializer.Deserialize<Dictionary<string, object?>>(json)!;

    private static string Quote(bool withPrice = true, long? issuedAt = null)
    {
        var at = issuedAt ?? DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        return withPrice
            ? $@"{{""id"":""q-1"",""price"":42,""issued_at"":{at}}}"
            : $@"{{""id"":""q-1"",""issued_at"":{at}}}";
    }

    /// <summary>One case: capability, token, parameters and options, and the failure the unary path gives.</summary>
    private (string Capability, DelegationToken Token, Dictionary<string, object?> Parameters, InvokeOpts Opts, string Expected)
        Case(string name)
    {
        var usd = new Budget { Currency = "USD", MaxAmount = 50 };
        var bigUsd = new Budget { Currency = "USD", MaxAmount = 10_000 };
        return name switch
        {
            "budget_exceeded" => ("watch_fixed", Token("watch_fixed", budget: usd),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts(), Constants.FailureBudgetExceeded),
            "budget_not_enforceable" => ("watch_quote", Token("watch_quote", budget: bigUsd),
                Body($@"{{""route"":""SEA-SFO"",""quote"":{Quote(withPrice: false)}}}"), new InvokeOpts(),
                Constants.FailureBudgetNotEnforceable),
            "binding_missing" => ("watch_quote", Token("watch_quote"),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts(), Constants.FailureBindingMissing),
            "binding_stale" => ("watch_quote", Token("watch_quote"),
                Body($@"{{""route"":""SEA-SFO"",""quote"":{Quote(issuedAt: DateTimeOffset.UtcNow.AddDays(-2).ToUnixTimeSeconds())}}}"),
                new InvokeOpts(), Constants.FailureBindingStale),
            "control_requirement_unsatisfied" => ("watch_ceiling", Token("watch_ceiling"),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts(), Constants.FailureControlRequirementUnsatisfied),
            "purpose_mismatch" => ("watch_fixed", Token("watch_ceiling"),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts(), Constants.FailurePurposeMismatch),
            "scope_insufficient" => ("watch_fixed", Token("watch_fixed", scope: "travel.search"),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts(), Constants.FailureScopeInsufficient),
            "blank_grant" => ("watch_fixed", Token("watch_fixed"),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts { ApprovalGrant = "" }, Constants.FailureGrantNotFound),
            "unknown_grant" => ("watch_fixed", Token("watch_fixed"),
                Body(@"{""route"":""SEA-SFO""}"), new InvokeOpts { ApprovalGrant = "grant_none" }, Constants.FailureGrantNotFound),
            "invalid_parameters" => ("watch_fixed", Token("watch_fixed"),
                Body("{}"), new InvokeOpts(), Constants.FailureInvalidParameters),
            _ => throw new ArgumentOutOfRangeException(nameof(name)),
        };
    }

    private int AuditCount(DelegationToken token, string capability, string failureType) =>
        _service.QueryAudit(token, new AuditFilters { Capability = capability, Limit = 1000 })
            .Entries.Count(e => !e.Success && e.FailureType == failureType);

    [Theory]
    [InlineData("budget_exceeded")]
    [InlineData("budget_not_enforceable")]
    [InlineData("binding_missing")]
    [InlineData("binding_stale")]
    [InlineData("control_requirement_unsatisfied")]
    [InlineData("purpose_mismatch")]
    [InlineData("scope_insufficient")]
    [InlineData("blank_grant")]
    [InlineData("unknown_grant")]
    [InlineData("invalid_parameters")]
    public void StreamingInvocation_IsRefusedLikeTheUnaryInvocation(string name)
    {
        var (capability, token, parameters, opts, expected) = Case(name);

        // Control: the unary path refuses the request.
        var before = AuditCount(token, capability, expected);
        var unary = _service.Invoke(capability, token, new Dictionary<string, object?>(parameters), opts);
        Assert.Equal(false, unary["success"]);
        Assert.Equal(expected, ((Dictionary<string, object?>)unary["failure"]!)["type"]);
        var unaryAudited = AuditCount(token, capability, expected) - before;

        // The streaming path refuses it the same way, before any stream opens.
        before = AuditCount(token, capability, expected);
        var streamOpts = new InvokeOpts { Stream = true, ApprovalGrant = opts.ApprovalGrant };
        StreamResult? opened = null;
        AnipError? refused = null;
        try
        {
            opened = _service.InvokeStream(capability, token, new Dictionary<string, object?>(parameters), streamOpts);
        }
        catch (AnipError e)
        {
            refused = e;
        }
        if (opened != null)
        {
            var events = new List<StreamEvent>();
            while (opened.Events.WaitToReadAsync().AsTask().GetAwaiter().GetResult())
            {
                while (opened.Events.TryRead(out var evt)) events.Add(evt);
            }
            Assert.Fail($"The streaming invocation was not refused: the handler ran {_handlerRuns.GetValueOrDefault(capability)} time(s) " +
                        $"and the stream ended with '{events.LastOrDefault()?.Type}'");
        }
        Assert.NotNull(refused);
        Assert.Equal(expected, refused!.ErrorType);
        Assert.Equal(0, _handlerRuns.GetValueOrDefault(capability));
        Assert.Equal(unaryAudited, AuditCount(token, capability, expected) - before);

        // The refusal carries the response a unary refusal returns.
        var response = Assert.IsType<InvocationRefusedError>(refused).Response;
        Assert.Equal(false, response["success"]);
        Assert.StartsWith("inv-", (string)response["invocation_id"]!);
        Assert.Equal(expected, ((Dictionary<string, object?>)response["failure"]!)["type"]);
    }
}
