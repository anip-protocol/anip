using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// SPEC.md §6.3 Budget Enforcement: with a budget, an estimated cost and a
/// binding requirement, the bound price is what is checked. A binding that
/// carries no numeric price leaves nothing to check, and the invocation is
/// refused with <c>budget_not_enforceable</c> before the handler.
/// </summary>
public class BudgetNotEnforceableTests : IDisposable
{
    private readonly AnipService _service;
    private int _handlerRuns;

    public BudgetNotEnforceableTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "svc-budget",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "book",
                        Description = "estimated cost, priced by a quote binding",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "irreversible" },
                        MinimumScope = new List<string> { "travel.book" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "quote_id", Type = "object", Required = false },
                        },
                        Cost = new Cost
                        {
                            Certainty = "estimated",
                            Financial = new FinancialCost { Currency = "USD", RangeMin = 280, RangeMax = 500 },
                        },
                        RequiresBinding = new List<BindingRequirement>
                        {
                            new() { Type = "quote", Field = "quote_id", SourceCapability = "search" },
                        },
                    },
                    (ctx, p) =>
                    {
                        Interlocked.Increment(ref _handlerRuns);
                        return new Dictionary<string, object?> { ["booked"] = true };
                    }),
            },
            Authenticate = bearer => bearer == "valid-key" ? "alice" : null,
        });
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    private DelegationToken Token(Budget? budget) => _service.ResolveBearerToken(
        _service.IssueToken("alice", new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { "travel.book" },
            Capability = "book",
            Budget = budget,
            TtlHours = 1,
        }).Token);

    private static Budget Usd(double max) => new() { Currency = "USD", MaxAmount = max };

    private static Dictionary<string, object?> Body(string json) =>
        JsonSerializer.Deserialize<Dictionary<string, object?>>(json)!;

    private void AssertNotEnforceable(Dictionary<string, object?> response)
    {
        Assert.Equal(false, response["success"]);
        var failure = Assert.IsType<Dictionary<string, object?>>(response["failure"]);
        Assert.Equal(Constants.FailureBudgetNotEnforceable, failure["type"]);
        Assert.Equal(
            "Capability book has estimated cost with requires_binding but the provided binding does not carry a resolvable price",
            failure["detail"]);
        Assert.Equal(false, failure["retry"]);
        var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
        Assert.Equal("obtain_binding", resolution["action"]);
        Assert.Equal("refresh_then_retry", resolution["recovery_class"]);
        Assert.False(string.IsNullOrEmpty(resolution["requires"] as string));
        Assert.StartsWith("inv-", Assert.IsType<string>(response["invocation_id"]));
        Assert.Equal(0, _handlerRuns);
    }

    [Theory]
    [InlineData("""{"quote_id": {"id": "qt-1", "issued_at": 1743300000}}""")]
    [InlineData("""{"quote_id": {"id": "qt-1", "price": "420"}}""")]
    [InlineData("""{"quote_id": {"id": "qt-1", "price": null}}""")]
    [InlineData("""{"quote_id": {"id": "qt-1", "price": true}}""")]
    [InlineData("""{"quote_id": {"id": "qt-1", "price": {"amount": 420}}}""")]
    [InlineData("""{"quote_id": "qt-1"}""")]
    public void TokenBudget_AndABindingWithoutANumericPrice_IsRefused(string parameters)
    {
        // A budget of 1 would be exceeded by any real price.
        AssertNotEnforceable(_service.Invoke("book", Token(Usd(1)), Body(parameters), new InvokeOpts()));
        _handlerRuns = 0;
        // A generous budget is no more enforceable.
        AssertNotEnforceable(_service.Invoke("book", Token(Usd(100000)), Body(parameters), new InvokeOpts()));
    }

    [Fact]
    public void TokenBudget_AndAClrBindingWithoutAPrice_IsRefused()
    {
        var parameters = new Dictionary<string, object?>
        {
            ["quote_id"] = new Dictionary<string, object?> { ["id"] = "qt-1", ["price"] = "420" },
        };

        AssertNotEnforceable(_service.Invoke("book", Token(Usd(100000)), parameters, new InvokeOpts()));
    }

    [Fact]
    public void RequestBudget_AndABindingWithoutAPrice_IsRefused()
    {
        var response = _service.Invoke("book", Token(null),
            Body("""{"quote_id": {"id": "qt-1"}}"""), new InvokeOpts { Budget = Usd(100000) });

        AssertNotEnforceable(response);
    }

    [Fact]
    public void TokenBudget_AndABindingWithAPriceWithinIt_Runs()
    {
        var response = _service.Invoke("book", Token(Usd(500)),
            Body("""{"quote_id": {"id": "qt-1", "price": 420}}"""), new InvokeOpts());

        Assert.Equal(true, response["success"]);
        Assert.Equal(1, _handlerRuns);
        var budget = Assert.IsType<Dictionary<string, object?>>(response["budget_context"]);
        Assert.Equal(420.0, budget["cost_check_amount"]);
    }

    [Theory]
    [InlineData(420)]
    [InlineData(420L)]
    [InlineData(420.0)]
    [InlineData(420.0f)]
    public void TokenBudget_AndAClrPrice_IsEnforced(object price)
    {
        var parameters = new Dictionary<string, object?>
        {
            ["quote_id"] = new Dictionary<string, object?> { ["id"] = "qt-1", ["price"] = price },
        };

        var within = _service.Invoke("book", Token(Usd(500)), parameters, new InvokeOpts());
        var beyond = _service.Invoke("book", Token(Usd(1)), parameters, new InvokeOpts());

        Assert.Equal(true, within["success"]);
        Assert.Equal(Constants.FailureBudgetExceeded,
            ((Dictionary<string, object?>)beyond["failure"]!)["type"]);
    }

    [Fact]
    public void TokenBudget_AndABindingWithAPriceBeyondIt_IsBudgetExceeded()
    {
        var response = _service.Invoke("book", Token(Usd(1)),
            Body("""{"quote_id": {"id": "qt-1", "price": 420}}"""), new InvokeOpts());

        Assert.Equal(Constants.FailureBudgetExceeded,
            ((Dictionary<string, object?>)response["failure"]!)["type"]);
        Assert.Equal(0, _handlerRuns);
    }

    [Fact]
    public void NoBudget_AndABindingWithoutAPrice_Runs()
    {
        var response = _service.Invoke("book", Token(null),
            Body("""{"quote_id": {"id": "qt-1"}}"""), new InvokeOpts());

        Assert.Equal(true, response["success"]);
        Assert.Equal(1, _handlerRuns);
    }

    [Fact]
    public void NoBudget_AndNoBinding_IsBindingMissing()
    {
        var response = _service.Invoke("book", Token(null), new Dictionary<string, object?>(), new InvokeOpts());

        Assert.Equal(Constants.FailureBindingMissing,
            ((Dictionary<string, object?>)response["failure"]!)["type"]);
    }
}
