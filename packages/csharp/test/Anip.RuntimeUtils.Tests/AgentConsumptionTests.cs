using System.Text.Json;
using Anip.RuntimeUtils;

namespace Anip.RuntimeUtils.Tests;

public class AgentConsumptionTests
{
    [Fact]
    public async Task SharedAgentConsumptionFixturesPass()
    {
        var fixturePath = Path.GetFullPath(
            Path.Combine(
                AppContext.BaseDirectory,
                "..",
                "..",
                "..",
                "..",
                "..",
                "..",
                "agent-consumption-fixtures",
                "capability-selection.json"));
        var fixtureJson = await File.ReadAllTextAsync(fixturePath);
        using var fixture = JsonDocument.Parse(fixtureJson);

        foreach (var testCase in fixture.RootElement.GetProperty("cases").EnumerateArray())
        {
            var id = testCase.GetProperty("id").GetString();
            var conversation = testCase.GetProperty("conversation").GetString()!;
            var selectedCapability = testCase.GetProperty("selected_capability").GetString()!;
            var metadata = testCase.GetProperty("metadata");

            var chosen = AgentConsumption.SelectConsumableCapability(conversation, selectedCapability, metadata);

            Assert.Equal(testCase.GetProperty("expected_capability").GetString(), chosen);
            Assert.Equal(
                SortedStrings(testCase.GetProperty("expected_missing_inputs")),
                AgentConsumption.MissingRequiredInputNames(conversation, metadata.GetProperty(chosen)).Order().ToArray());
            Assert.Equal(
                SortedStrings(testCase.GetProperty("expected_unsupported_effects")),
                AgentConsumption.DetectUnsupportedEffects(conversation, metadata.GetProperty(selectedCapability)).Order().ToArray());
            Assert.Equal(
                SortedStrings(testCase.GetProperty("expected_unsupported_effects")),
                AgentConsumption.RequestedUnsupportedEffects(conversation, metadata.GetProperty(selectedCapability)).Order().ToArray());
        }
    }

    [Fact]
    public async Task SharedPlannerFallbackValidationFixturesPass()
    {
        var fixturePath = Path.GetFullPath(
            Path.Combine(
                AppContext.BaseDirectory,
                "..",
                "..",
                "..",
                "..",
                "..",
                "..",
                "agent-consumption-fixtures",
                "planner-fallback-validation.json"));
        var fixtureJson = await File.ReadAllTextAsync(fixturePath);
        using var fixture = JsonDocument.Parse(fixtureJson);

        foreach (var testCase in fixture.RootElement.GetProperty("cases").EnumerateArray())
        {
            var id = testCase.GetProperty("id").GetString();
            var conversation = testCase.GetProperty("conversation").GetString()!;
            var plan = testCase.GetProperty("plan");
            var metadata = testCase.GetProperty("metadata");
            var compactCandidateIds = testCase.TryGetProperty("compact_candidate_ids", out var candidateElement)
                ? candidateElement.EnumerateArray().Select(item => item.GetString()!).ToArray()
                : [];

            Assert.Equal(
                ExpectedStrings(testCase.GetProperty("expected_reasons")),
                AgentConsumption.ValidateInvocationPlanForFallback(
                    plan,
                    conversation,
                    metadata,
                    new AgentConsumption.FallbackValidationOptions(compactCandidateIds)).ToArray());
        }
    }

    /// <summary>SPEC.md §4.1: an input spec that does not state <c>required</c> is required.</summary>
    [Fact]
    public void InputSpecWithoutRequired_IsRequired()
    {
        using var metadata = JsonDocument.Parse("""
            {"input_specs": [
              {"name": "ticket_ref", "type": "string"},
              {"name": "priority_ref", "type": "string", "required": true},
              {"name": "note_ref", "type": "string", "required": false},
              {"name": "queue_ref", "type": "string", "required": null}
            ]}
            """);

        var missing = AgentConsumption.MissingRequiredInputNames("hello", metadata.RootElement);

        Assert.Equal(new[] { "priority_ref", "queue_ref", "ticket_ref" }, missing.Order().ToArray());
    }

    private static string[] SortedStrings(JsonElement value)
    {
        return value.EnumerateArray().Select(item => item.GetString()!).Order().ToArray();
    }

    private static string[] ExpectedStrings(JsonElement value)
    {
        return value.EnumerateArray().Select(item => item.GetString()!).ToArray();
    }
}
