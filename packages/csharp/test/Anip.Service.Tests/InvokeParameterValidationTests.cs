using System.Text.Json;
using Anip.Core;
using Anip.Server;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// SPEC.md §6.3 "Parameter Validation" in the invoke pipeline: where the check
/// runs, what a refusal looks like, and that a refused call has no effect.
/// </summary>
public class InvokeParameterValidationTests : IDisposable
{
    private const string Principal = "alice";

    private readonly AnipService _service;
    private readonly Dictionary<string, int> _handlerRuns = new();
    private readonly List<(string InvocationId, bool Success)> _completed = new();
    private readonly List<(string Capability, bool Granted)> _scopeChecks = new();

    public InvokeParameterValidationTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "svc-validation",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Hooks = new ObservabilityHooks
            {
                OnInvokeComplete = (id, _, success, _) => _completed.Add((id, success)),
                OnScopeValidation = (capability, granted) => _scopeChecks.Add((capability, granted)),
            },
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "book",
                        Description = "books a flight; five or more passengers need approval",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "irreversible" },
                        MinimumScope = new List<string> { "travel.book" },
                        ResponseModes = new List<string> { "unary", "streaming" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "flight_number", Type = "string" },
                            new() { Name = "date", Type = "date" },
                            new() { Name = "passengers", Type = "integer", Required = false, Default = 1 },
                        },
                        GrantPolicy = new GrantPolicy
                        {
                            AllowedGrantTypes = new() { "one_time" },
                            DefaultGrantType = "one_time",
                            ExpiresInSeconds = 600,
                            MaxUses = 1,
                        },
                    },
                    (ctx, p) =>
                    {
                        Ran("book");
                        if (p.TryGetValue("flight_number", out var flight) && flight?.ToString() == "REJECT")
                        {
                            throw new AnipError(Constants.FailureInvalidParameters, "flight REJECT cannot be booked");
                        }
                        var passengers = p.TryGetValue("passengers", out var value) && value != null
                            ? (value is JsonElement element ? (int)element.GetDouble() : Convert.ToInt32(value))
                            : 1;
                        if (passengers >= 5 && string.IsNullOrWhiteSpace(ctx.ApprovalGrant))
                        {
                            throw new AnipError(Constants.FailureApprovalRequired, "approval needed")
                                .WithResolution("request_approval");
                        }
                        return new Dictionary<string, object?>
                        {
                            ["booked"] = passengers,
                            ["seat"] = p.TryGetValue("seat", out var seat) ? seat : null,
                        };
                    }),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "pay",
                        Description = "needs a quote binding and has an estimated cost",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "irreversible" },
                        MinimumScope = new List<string> { "travel.book" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "account", Type = "string" },
                            new() { Name = "quote", Type = "object", Required = false },
                        },
                        Cost = new Cost
                        {
                            Certainty = "estimated",
                            Financial = new FinancialCost { Currency = "USD", RangeMin = 1, RangeMax = 500 },
                        },
                        RequiresBinding = new List<BindingRequirement>
                        {
                            new() { Type = "quote", Field = "quote", SourceCapability = "search" },
                        },
                        ControlRequirements = new List<ControlRequirement>
                        {
                            new() { Type = "cost_ceiling" },
                        },
                    },
                    (ctx, p) =>
                    {
                        Ran("pay");
                        return new Dictionary<string, object?> { ["paid"] = true };
                    }),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "lookup",
                        Description = "atomic child step",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "read" },
                        MinimumScope = new List<string> { "travel.book" },
                        Kind = "atomic",
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "code", Type = "string" },
                        },
                    },
                    (ctx, p) =>
                    {
                        Ran("lookup");
                        return new Dictionary<string, object?> { ["name"] = "found " + p["code"] };
                    }),
                new(
                    new CapabilityDeclaration
                    {
                        Name = "plan",
                        Description = "composed capability",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "read" },
                        MinimumScope = new List<string> { "travel.book" },
                        Kind = "composed",
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "trip", Type = "string" },
                            new() { Name = "code", Type = "airport_code", Required = false },
                        },
                        Composition = new Composition
                        {
                            AuthorityBoundary = "same_service",
                            Steps = new List<CompositionStep> { new() { Id = "s1", Capability = "lookup" } },
                            InputMapping = new Dictionary<string, Dictionary<string, string>>
                            {
                                ["s1"] = new() { ["code"] = "$.input.code" },
                            },
                            OutputMapping = new Dictionary<string, string> { ["name"] = "$.steps.s1.output.name" },
                        },
                    },
                    (ctx, p) => throw new InvalidOperationException("a composed capability has no handler")),
            },
            Authenticate = bearer => bearer == "valid-key" ? Principal : null,
        });
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    private void Ran(string capability) =>
        _handlerRuns[capability] = _handlerRuns.GetValueOrDefault(capability) + 1;

    private int Runs(string capability) => _handlerRuns.GetValueOrDefault(capability);

    private DelegationToken Token(
        string capability, string scope = "travel.book", Budget? budget = null, string? taskId = null)
    {
        var issued = _service.IssueToken(Principal, new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { scope },
            Capability = capability,
            Budget = budget,
            PurposeParameters = taskId == null ? null : new Dictionary<string, object> { ["task_id"] = taskId },
            TtlHours = 1,
        });
        return _service.ResolveBearerToken(issued.Token);
    }

    private static Dictionary<string, object?> Body(string json) =>
        JsonSerializer.Deserialize<Dictionary<string, object?>>(json)!;

    private static Dictionary<string, object?> Failure(Dictionary<string, object?> response)
    {
        Assert.Equal(false, response["success"]);
        return Assert.IsType<Dictionary<string, object?>>(response["failure"]);
    }

    private static void AssertInvalidParameters(Dictionary<string, object?> response, string detail)
    {
        var failure = Failure(response);
        Assert.Equal(Constants.FailureInvalidParameters, failure["type"]);
        Assert.Equal(detail, failure["detail"]);
        Assert.Equal(false, failure["retry"]);
        var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
        Assert.Equal("retry_now", resolution["action"]);
        Assert.Equal("retry_now", resolution["recovery_class"]);
        Assert.Equal("parameters that match the capability's declared inputs", resolution["requires"]);
        Assert.False(response.ContainsKey("result"));
        Assert.False(failure.ContainsKey("approval_required"));
    }

    private AuditEntry AuditEntryFor(DelegationToken token, string invocationId)
    {
        var entries = _service.QueryAudit(token, new AuditFilters { InvocationId = invocationId, Limit = 50 })
            .Entries.Where(e => e.InvocationId == invocationId).ToList();
        return Assert.Single(entries);
    }

    // --- the refusal ---

    [Fact]
    public void MissingRequiredInput_IsRefusedBeforeTheHandler()
    {
        var token = Token("book", taskId: "task-1");

        var response = _service.Invoke("book", token, Body(@"{""passengers"":2}"), new InvokeOpts
        {
            ClientReferenceId = "ref-1",
            TaskId = "task-1",
            ParentInvocationId = "inv-aaaaaaaaaaaa",
            UpstreamService = "planner",
        });

        AssertInvalidParameters(response, "book is missing required input(s): flight_number, date");
        Assert.Equal(0, Runs("book"));
        var invocationId = Assert.IsType<string>(response["invocation_id"]);
        Assert.StartsWith("inv-", invocationId);
        Assert.Equal("ref-1", response["client_reference_id"]);
        Assert.Equal("task-1", response["task_id"]);
        Assert.Equal("inv-aaaaaaaaaaaa", response["parent_invocation_id"]);
        Assert.Equal("planner", response["upstream_service"]);
    }

    [Fact]
    public void RefusalIsAuditedAsAFailure()
    {
        var token = Token("book", taskId: "task-2");

        var response = _service.Invoke("book", token, Body(@"{""flight_number"":""AA100""}"), new InvokeOpts
        {
            ClientReferenceId = "ref-2",
            TaskId = "task-2",
            ParentInvocationId = "inv-bbbbbbbbbbbb",
        });

        var entry = AuditEntryFor(token, (string)response["invocation_id"]!);
        Assert.False(entry.Success);
        Assert.Equal(Constants.FailureInvalidParameters, entry.FailureType);
        Assert.Equal("book", entry.Capability);
        Assert.Equal("ref-2", entry.ClientReferenceId);
        Assert.Equal("task-2", entry.TaskId);
        Assert.Equal("inv-bbbbbbbbbbbb", entry.ParentInvocationId);
        Assert.Null(entry.ApprovalRequestId);
        Assert.Null(entry.ApprovalGrantId);
    }

    [Fact]
    public void RefusalFiresTheSameHooksAsADelegationFailure()
    {
        var token = Token("book");

        var response = _service.Invoke("book", token, new Dictionary<string, object?>(), new InvokeOpts());

        Assert.Contains(("book", true), _scopeChecks);
        Assert.Contains(((string)response["invocation_id"]!, false), _completed);
    }

    [Fact]
    public void WrongType_IsRefusedBeforeTheHandler()
    {
        var token = Token("book");

        var response = _service.Invoke("book", token,
            Body(@"{""flight_number"":12345,""date"":""2026-03-10"",""passengers"":""two""}"), new InvokeOpts());

        AssertInvalidParameters(response,
            "book has invalid input(s): 'flight_number' must be string, got number; 'passengers' must be integer, got string");
        Assert.Equal(0, Runs("book"));
    }

    [Fact]
    public void ValidCall_ReachesTheHandler()
    {
        var token = Token("book");

        var response = _service.Invoke("book", token,
            new Dictionary<string, object?>
            {
                ["flight_number"] = "AA100",
                ["date"] = "2026-03-10",
                ["passengers"] = 2.0,
            },
            new InvokeOpts());

        Assert.Equal(true, response["success"]);
        var result = Assert.IsType<Dictionary<string, object?>>(response["result"]);
        Assert.Equal(2, result["booked"]);
        Assert.Equal(1, Runs("book"));
    }

    [Fact]
    public void UndeclaredParameters_AreRefusedBeforeTheHandler()
    {
        var token = Token("book");

        var response = _service.Invoke("book", token,
            Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10"",""seat"":""12A"",""also"":null}"),
            new InvokeOpts());

        AssertInvalidParameters(response, "book has undeclared parameter(s): also, seat");
        Assert.Equal(0, Runs("book"));
    }

    [Fact]
    public void Streaming_UndeclaredParameter_IsRefused()
    {
        var token = Token("book");

        var error = Assert.ThrowsAny<AnipError>(() => _service.InvokeStream("book", token,
            Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10"",""seat"":""12A""}"),
            new InvokeOpts { Stream = true }));

        Assert.Equal(Constants.FailureInvalidParameters, error.ErrorType);
        Assert.Equal("book has undeclared parameter(s): seat", error.Detail);
        Assert.Equal(0, Runs("book"));
    }

    [Fact]
    public void OptionalInputWithADefault_MayBeOmitted()
    {
        var token = Token("book");

        var response = _service.Invoke("book", token,
            Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10""}"), new InvokeOpts());

        Assert.Equal(true, response["success"]);
    }

    [Fact]
    public void HandlerRaisedInvalidParameters_GetsTheSameResolution()
    {
        var token = Token("book");

        // Declared inputs match; the handler itself rejects the value.
        var response = _service.Invoke("book", token,
            Body(@"{""flight_number"":""REJECT"",""date"":""2026-03-10""}"), new InvokeOpts());

        AssertInvalidParameters(response, "flight REJECT cannot be booked");
        Assert.Equal(1, Runs("book"));
    }

    // --- position in the pipeline ---

    [Fact]
    public void DelegationFailureComesFirst()
    {
        var token = Token("book", scope: "travel.search");

        var response = _service.Invoke("book", token, new Dictionary<string, object?>(), new InvokeOpts());

        Assert.Equal(Constants.FailureScopeInsufficient, Failure(response)["type"]);
    }

    [Fact]
    public void BindingEnforcementComesFirst()
    {
        var token = Token("pay");

        // `account` (required) and the `quote` binding are both absent: the
        // binding is what the caller is told about.
        var response = _service.Invoke("pay", token, new Dictionary<string, object?>(), new InvokeOpts());

        Assert.Equal(Constants.FailureBindingMissing, Failure(response)["type"]);
        Assert.Equal(0, Runs("pay"));
    }

    [Fact]
    public void BudgetEnforcementComesFirst()
    {
        var token = Token("pay", budget: new Budget { Currency = "USD", MaxAmount = 10 });

        var response = _service.Invoke("pay", token,
            Body(@"{""quote"":{""id"":""q1"",""price"":420}}"), new InvokeOpts());

        Assert.Equal(Constants.FailureBudgetExceeded, Failure(response)["type"]);
    }

    [Fact]
    public void ControlRequirementComesFirst()
    {
        var token = Token("pay");

        var response = _service.Invoke("pay", token,
            Body(@"{""quote"":{""id"":""q1"",""price"":420}}"), new InvokeOpts());

        Assert.Equal(Constants.FailureControlRequirementUnsatisfied, Failure(response)["type"]);
    }

    [Fact]
    public void AfterBudgetBindingAndControl_TheParametersAreChecked()
    {
        var token = Token("pay", budget: new Budget { Currency = "USD", MaxAmount = 1000 });

        var response = _service.Invoke("pay", token,
            Body(@"{""quote"":{""id"":""q1"",""price"":420}}"), new InvokeOpts());

        AssertInvalidParameters(response, "pay is missing required input(s): account");
        Assert.Equal(0, Runs("pay"));
    }

    // --- no effect: approvals ---

    [Fact]
    public void InvalidCall_DoesNotReachAHandlerThatAsksForApproval()
    {
        var token = Token("book");
        var parameters = @"{""flight_number"":""AA100"",""date"":""2026-03-10"",""passengers"":5}";

        var control = _service.Invoke("book", token, Body(parameters), new InvokeOpts());
        Assert.Equal(Constants.FailureApprovalRequired, Failure(control)["type"]);
        Assert.Equal(1, Runs("book"));

        var response = _service.Invoke("book", token,
            Body(@"{""flight_number"":12345,""date"":""2026-03-10"",""passengers"":5}"), new InvokeOpts());

        AssertInvalidParameters(response, "book has invalid input(s): 'flight_number' must be string, got number");
        Assert.Equal(1, Runs("book"));
        var entry = AuditEntryFor(token, (string)response["invocation_id"]!);
        Assert.Null(entry.ApprovalRequestId);
    }

    private ApprovalGrant ApprovedGrant(DelegationToken token, string parameters)
    {
        var asked = _service.Invoke("book", token, Body(parameters), new InvokeOpts());
        var approval = Assert.IsType<Dictionary<string, object?>>(Failure(asked)["approval_required"]);
        return _service.IssueApprovalGrant(
            (string)approval["approval_request_id"]!, ApprovalGrant.TypeOneTime,
            new Dictionary<string, object?> { ["subject"] = "boss" }, null, null, null);
    }

    [Fact]
    public void InvalidContinuation_DoesNotSpendTheGrant()
    {
        var token = Token("book");
        var parameters = @"{""flight_number"":""AA100"",""date"":""2026-03-10"",""passengers"":5}";
        var grant = ApprovedGrant(token, parameters);
        var runsBefore = Runs("book");

        var refused = _service.Invoke("book", token,
            Body(@"{""flight_number"":12345,""date"":""2026-03-10"",""passengers"":5}"),
            new InvokeOpts { ApprovalGrant = grant.GrantId });

        // invalid_parameters, not grant_param_drift: the check runs before Phase A.
        AssertInvalidParameters(refused, "book has invalid input(s): 'flight_number' must be string, got number");
        Assert.Equal(runsBefore, Runs("book"));
        Assert.Equal(0, _service.GetStorage().GetGrant(grant.GrantId)!.UseCount);
        Assert.Null(AuditEntryFor(token, (string)refused["invocation_id"]!).ApprovalGrantId);

        var continued = _service.Invoke("book", token, Body(parameters),
            new InvokeOpts { ApprovalGrant = grant.GrantId });

        Assert.Equal(true, continued["success"]);
        Assert.Equal(1, _service.GetStorage().GetGrant(grant.GrantId)!.UseCount);
    }

    [Fact]
    public void InvalidCallWithAnUnknownGrant_IsInvalidParameters()
    {
        var token = Token("book");

        var response = _service.Invoke("book", token, new Dictionary<string, object?>(),
            new InvokeOpts { ApprovalGrant = "grant_doesnotexist" });

        AssertInvalidParameters(response, "book is missing required input(s): flight_number, date");
    }

    // --- composition ---

    [Fact]
    public void ComposedCapability_IsCheckedBeforeAnyChildStep()
    {
        var token = Token("plan");

        var response = _service.Invoke("plan", token, Body(@"{""code"":""SEA""}"), new InvokeOpts());

        AssertInvalidParameters(response, "plan is missing required input(s): trip");
        Assert.Equal(0, Runs("lookup"));
    }

    [Fact]
    public void ChildStep_IsCheckedAgainstTheChildDeclaration()
    {
        var token = Token("plan");

        // `code` is a domain type on the parent (not checked) and a string on the child.
        var response = _service.Invoke("plan", token, Body(@"{""trip"":""t1"",""code"":42}"), new InvokeOpts());

        AssertInvalidParameters(response, "lookup has invalid input(s): 'code' must be string, got number");
        Assert.Equal(0, Runs("lookup"));
        var children = _service.QueryAudit(token, new AuditFilters
        {
            ParentInvocationId = (string)response["invocation_id"]!,
            Limit = 50,
        }).Entries;
        var child = Assert.Single(children);
        Assert.Equal("lookup", child.Capability);
        Assert.False(child.Success);
        Assert.Equal(Constants.FailureInvalidParameters, child.FailureType);
    }

    [Fact]
    public void ChildStep_WithValidInput_Runs()
    {
        var token = Token("plan");

        var response = _service.Invoke("plan", token, Body(@"{""trip"":""t1"",""code"":""SEA""}"), new InvokeOpts());

        Assert.Equal(true, response["success"]);
        Assert.Equal(1, Runs("lookup"));
    }

    // --- streaming ---

    [Fact]
    public void Streaming_MissingRequiredInput_IsRefusedBeforeTheHandler()
    {
        var token = Token("book", taskId: "task-s");

        var error = Assert.ThrowsAny<AnipError>(() => _service.InvokeStream("book", token,
            Body(@"{""passengers"":2}"),
            new InvokeOpts { Stream = true, ClientReferenceId = "ref-s", TaskId = "task-s" }));

        Assert.Equal(Constants.FailureInvalidParameters, error.ErrorType);
        Assert.Equal("book is missing required input(s): flight_number, date", error.Detail);
        Assert.False(error.Retry);
        Assert.Equal("retry_now", error.Resolution!.Action);
        Assert.Equal("retry_now", error.Resolution.RecoveryClass);
        Assert.Equal("parameters that match the capability's declared inputs", error.Resolution.Requires);
        Assert.Equal(0, Runs("book"));

        // The refusal carries the response a unary refusal would, and is audited.
        var refused = Assert.IsType<InvocationRefusedError>(error);
        AssertInvalidParameters(refused.Response, "book is missing required input(s): flight_number, date");
        Assert.Equal("ref-s", refused.Response["client_reference_id"]);
        Assert.Equal("task-s", refused.Response["task_id"]);
        var entry = AuditEntryFor(token, (string)refused.Response["invocation_id"]!);
        Assert.False(entry.Success);
        Assert.Equal(Constants.FailureInvalidParameters, entry.FailureType);
        Assert.Equal("ref-s", entry.ClientReferenceId);
    }

    [Fact]
    public void Streaming_WrongType_IsRefused()
    {
        var token = Token("book");

        var error = Assert.ThrowsAny<AnipError>(() => _service.InvokeStream("book", token,
            Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10"",""passengers"":1.5}"),
            new InvokeOpts { Stream = true }));

        Assert.Equal(Constants.FailureInvalidParameters, error.ErrorType);
        Assert.Equal("book has invalid input(s): 'passengers' must be integer, got number", error.Detail);
        Assert.Equal(0, Runs("book"));
    }

    [Fact]
    public void Streaming_DelegationFailureComesFirst()
    {
        var token = Token("book", scope: "travel.search");

        var error = Assert.ThrowsAny<AnipError>(() => _service.InvokeStream("book", token,
            new Dictionary<string, object?>(), new InvokeOpts { Stream = true }));

        Assert.Equal(Constants.FailureScopeInsufficient, error.ErrorType);
    }

    [Fact]
    public void Streaming_InvalidContinuation_DoesNotSpendTheGrant()
    {
        var token = Token("book");
        var grant = ApprovedGrant(token, @"{""flight_number"":""AA100"",""date"":""2026-03-10"",""passengers"":5}");

        var error = Assert.ThrowsAny<AnipError>(() => _service.InvokeStream("book", token,
            Body(@"{""flight_number"":12345,""date"":""2026-03-10"",""passengers"":5}"),
            new InvokeOpts { Stream = true, ApprovalGrant = grant.GrantId }));

        Assert.Equal(Constants.FailureInvalidParameters, error.ErrorType);
        Assert.Equal(0, _service.GetStorage().GetGrant(grant.GrantId)!.UseCount);
    }

    [Fact]
    public async Task Streaming_ValidCall_Completes()
    {
        var token = Token("book");

        var stream = _service.InvokeStream("book", token,
            Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10""}"), new InvokeOpts { Stream = true });

        var events = new List<StreamEvent>();
        await foreach (var evt in stream.Events.ReadAllAsync())
        {
            events.Add(evt);
        }
        Assert.Equal("completed", Assert.Single(events).Type);
        Assert.Equal(1, Runs("book"));
    }
}
