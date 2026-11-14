using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// SPEC.md §6.3: every refusal made before the handler is audited. Budget,
/// binding and control-requirement refusals are recorded like scope,
/// purpose and parameter refusals, on unary and streaming invocations.
/// </summary>
public class PrehandlerAuditTests
{
    private static readonly long Now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

    private static void Fixed(CapabilityDeclaration d) =>
        d.Cost = new Cost { Certainty = "fixed", Financial = new FinancialCost { Currency = "USD", Amount = 500 } };

    private static void Estimated(CapabilityDeclaration d)
    {
        d.Cost = new Cost
        {
            Certainty = "estimated",
            Financial = new FinancialCost { Currency = "USD", RangeMin = 100, RangeMax = 500 },
        };
        d.RequiresBinding = new List<BindingRequirement> { new() { Type = "quote", Field = "quote", MaxAge = "PT15M" } };
    }

    private static void Control(CapabilityDeclaration d) =>
        d.ControlRequirements = new List<ControlRequirement> { new() { Type = "cost_ceiling" } };

    public static IEnumerable<object?[]> Cases()
    {
        foreach (var stream in new[] { false, true })
        {
            yield return new object?[] { "budget_exceeded fixed", "fixed", "{}", "USD", 1.0, "budget_exceeded", stream };
            yield return new object?[] { "budget_exceeded bound", "estimated", $$$"""{"quote":{"price":420,"issued_at":{{{Now}}}}}""", "USD", 100.0, "budget_exceeded", stream };
            yield return new object?[] { "budget_currency_mismatch", "fixed", "{}", "EUR", 1000.0, "budget_currency_mismatch", stream };
            yield return new object?[] { "budget_not_enforceable", "estimated", $$$"""{"quote":{"issued_at":{{{Now}}}}}""", "USD", 1000.0, "budget_not_enforceable", stream };
            yield return new object?[] { "binding_missing", "estimated", "{}", null, null, "binding_missing", stream };
            yield return new object?[] { "binding_stale", "estimated", $$$"""{"quote":{"price":420,"issued_at":{{{Now - 86400}}}}}""", null, null, "binding_stale", stream };
            yield return new object?[] { "control requirement", "control", "{}", null, null, "control_requirement_unsatisfied", stream };
        }
    }

    [Theory]
    [MemberData(nameof(Cases))]
    public void RefusalBeforeTheHandlerIsAudited(
        string name, string shape, string parametersJson, string? currency, double? maxAmount,
        string expected, bool stream)
    {
        var runs = 0;
        var declaration = new CapabilityDeclaration
        {
            Name = "book",
            Description = name,
            ContractVersion = "1.0",
            Inputs = new List<CapabilityInput> { new() { Name = "quote", Type = "object", Required = false } },
            SideEffect = new SideEffect { Type = "irreversible", RollbackWindow = "none" },
            MinimumScope = new List<string> { "book" },
            ResponseModes = new List<string> { "unary", "streaming" },
        };
        (shape switch { "fixed" => (Action<CapabilityDeclaration>)Fixed, "estimated" => Estimated, _ => Control })(declaration);
        using var service = new AnipService(new ServiceConfig
        {
            ServiceId = "test-prehandler-audit",
            Storage = ":memory:",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(declaration, (ctx, p) =>
                {
                    runs++;
                    return new Dictionary<string, object?> { ["ok"] = true };
                }),
            },
        });
        service.Start();
        var token = service.ResolveBearerToken(service.IssueToken("alice", new TokenRequest
        {
            Scope = new List<string> { "book" },
            Capability = "book",
        }).Token);
        var parameters = System.Text.Json.JsonSerializer.Deserialize<Dictionary<string, object?>>(parametersJson)!;
        var opts = new InvokeOpts
        {
            ClientReferenceId = "ref-audit",
            Stream = stream,
            Budget = currency == null ? null : new Budget { Currency = currency, MaxAmount = maxAmount!.Value },
        };

        if (stream)
        {
            var error = Assert.ThrowsAny<AnipError>(() => service.InvokeStream("book", token, parameters, opts));
            Assert.Equal(expected, error.ErrorType);
            Assert.NotNull(error.Resolution);
        }
        else
        {
            var response = service.Invoke("book", token, parameters, opts);
            Assert.Equal(false, response["success"]);
            var failure = (Dictionary<string, object?>)response["failure"]!;
            Assert.Equal(expected, failure["type"]);
            var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
            Assert.NotNull(resolution["recovery_class"]);
        }
        Assert.Equal(0, runs);

        var entry = Assert.Single(service.QueryAudit(token, new AuditFilters { ClientReferenceId = "ref-audit" }).Entries);
        Assert.False(entry.Success);
        Assert.Equal(expected, entry.FailureType);
        Assert.Equal(EventClassification.Classify("irreversible", false, expected), entry.EventClass);
    }
}
