using Anip.Core;
using Anip.Mcp;

namespace Anip.Mcp.Tests;

public class McpToolTranslatorTests
{
    private static CapabilityDeclaration ReadDecl() => new()
    {
        Name = "search_flights",
        Description = "Search for flights",
        ContractVersion = "1.0",
        SideEffect = new SideEffect { Type = "read", RollbackWindow = "not_applicable" },
        MinimumScope = new List<string> { "travel" },
        Inputs = new List<CapabilityInput>
        {
            new() { Name = "origin", Type = "string", Required = true, Description = "Origin airport" },
            new() { Name = "destination", Type = "string", Required = true, Description = "Destination airport" },
            new() { Name = "max_results", Type = "integer", Required = false, Default = 10, Description = "Max results" },
        },
    };

    private static CapabilityDeclaration WriteDecl() => new()
    {
        Name = "book_flight",
        Description = "Book a flight",
        ContractVersion = "1.0",
        SideEffect = new SideEffect { Type = "irreversible", RollbackWindow = "none" },
        MinimumScope = new List<string> { "travel", "finance" },
        Inputs = new List<CapabilityInput>
        {
            new() { Name = "flight_id", Type = "string", Required = true, Description = "Flight ID" },
        },
        Cost = new Cost
        {
            Certainty = "estimated",
            Financial = new Dictionary<string, object>
            {
                ["currency"] = "USD",
                ["estimated_range"] = new Dictionary<string, object>
                {
                    ["min"] = 100,
                    ["max"] = 500,
                },
            },
        },
        Requires = new List<CapabilityRequirement>
        {
            new() { Capability = "search_flights", Reason = "Must search first" },
        },
    };

    // --- BuildTool ---

    [Fact]
    public void BuildTool_ReadCapability_ProducesNameAndDescription()
    {
        var tool = McpToolTranslator.BuildTool("search_flights", ReadDecl(), false);

        Assert.Equal("search_flights", tool["name"]);
        Assert.Equal("Search for flights", tool["description"]);
        Assert.NotNull(tool["inputSchema"]);

        var annotations = (Dictionary<string, object?>)tool["annotations"]!;
        Assert.Equal(true, annotations["readOnlyHint"]);
        Assert.Equal(false, annotations["destructiveHint"]);
    }

    [Fact]
    public void BuildTool_WriteCapability_SetsDestructiveHint()
    {
        var tool = McpToolTranslator.BuildTool("book_flight", WriteDecl(), false);

        Assert.Equal("book_flight", tool["name"]);

        var annotations = (Dictionary<string, object?>)tool["annotations"]!;
        Assert.Equal(false, annotations["readOnlyHint"]);
        Assert.Equal(true, annotations["destructiveHint"]);
    }

    // --- BuildInputSchema ---

    [Fact]
    public void BuildInputSchema_ProducesJsonSchema()
    {
        var schema = McpToolTranslator.BuildInputSchema(ReadDecl());

        Assert.Equal("object", schema["type"]);

        var properties = (Dictionary<string, object?>)schema["properties"]!;
        Assert.Equal(3, properties.Count);
        Assert.True(properties.ContainsKey("origin"));
        Assert.True(properties.ContainsKey("destination"));
        Assert.True(properties.ContainsKey("max_results"));

        var required = (List<string>)schema["required"]!;
        Assert.Contains("origin", required);
        Assert.Contains("destination", required);
        Assert.DoesNotContain("max_results", required);
    }

    [Fact]
    public void BuildInputSchema_IntegerType()
    {
        var schema = McpToolTranslator.BuildInputSchema(ReadDecl());
        var properties = (Dictionary<string, object?>)schema["properties"]!;
        var maxResults = (Dictionary<string, object?>)properties["max_results"]!;

        Assert.Equal("integer", maxResults["type"]);
        Assert.Equal(10, maxResults["default"]);
    }

    // --- EnrichDescription ---

    [Fact]
    public void EnrichDescription_ReadCapability_IncludesSideEffectAndScope()
    {
        var desc = McpToolTranslator.EnrichDescription(ReadDecl());

        Assert.Contains("Search for flights", desc);
        Assert.Contains("Read-only, no side effects", desc);
        Assert.Contains("Delegation scope: travel", desc);
    }

    [Fact]
    public void EnrichDescription_IrreversibleCapability_IncludesWarningAndCost()
    {
        var desc = McpToolTranslator.EnrichDescription(WriteDecl());

        Assert.Contains("Book a flight", desc);
        Assert.Contains("IRREVERSIBLE", desc);
        Assert.Contains("No rollback window", desc);
        Assert.Contains("Estimated cost: USD 100-500", desc);
        Assert.Contains("Requires calling first: search_flights", desc);
        Assert.Contains("Delegation scope: travel, finance", desc);
    }

    // --- TranslateResponse ---

    [Fact]
    public void TranslateResponse_Success()
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = true,
            ["result"] = new Dictionary<string, object?>
            {
                ["flights"] = new List<Dictionary<string, object?>>
                {
                    new() { ["id"] = "FL-001" },
                },
            },
        };

        var result = McpToolTranslator.TranslateResponse(response);

        Assert.False(result.IsError);
        Assert.Contains("FL-001", result.Text);
    }

    [Fact]
    public void TranslateResponse_Failure()
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = new Dictionary<string, object?>
            {
                ["type"] = "scope_insufficient",
                ["detail"] = "Missing travel scope",
                ["retry"] = false,
            },
        };

        var result = McpToolTranslator.TranslateResponse(response);

        Assert.True(result.IsError);
        Assert.Contains("FAILED: scope_insufficient", result.Text);
        Assert.Contains("Missing travel scope", result.Text);
        Assert.Contains("Retryable: no", result.Text);
    }

    [Fact]
    public void TranslateResponse_FailureWithResolution()
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = new Dictionary<string, object?>
            {
                ["type"] = "scope_insufficient",
                ["detail"] = "Missing scope",
                ["retry"] = false,
                ["resolution"] = new Dictionary<string, object?>
                {
                    ["action"] = "Request broader delegation",
                    ["requires"] = "admin approval",
                },
            },
        };

        var result = McpToolTranslator.TranslateResponse(response);

        Assert.True(result.IsError);
        Assert.Contains("Resolution: Request broader delegation", result.Text);
        Assert.Contains("Requires: admin approval", result.Text);
    }

    [Fact]
    public void TranslateResponse_FailureRetryable()
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = new Dictionary<string, object?>
            {
                ["type"] = "rate_limited",
                ["detail"] = "Too many requests",
                ["retry"] = true,
            },
        };

        var result = McpToolTranslator.TranslateResponse(response);

        Assert.True(result.IsError);
        Assert.Contains("Retryable: yes", result.Text);
    }

    [Fact]
    public void TranslateResponse_NoFailureObject()
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = false,
        };

        var result = McpToolTranslator.TranslateResponse(response);

        Assert.True(result.IsError);
        Assert.Contains("FAILED: unknown", result.Text);
        Assert.Contains("no detail", result.Text);
    }

    [Fact]
    public void TranslateResponse_SuccessWithCostAnnotation()
    {
        var response = new Dictionary<string, object?>
        {
            ["success"] = true,
            ["result"] = new Dictionary<string, object?> { ["booking_id"] = "BK-123" },
            ["cost_actual"] = new Dictionary<string, object?>
            {
                ["financial"] = new Dictionary<string, object?>
                {
                    ["amount"] = 250,
                    ["currency"] = "USD",
                },
            },
        };

        var result = McpToolTranslator.TranslateResponse(response);

        Assert.False(result.IsError);
        Assert.Contains("[Cost: USD 250]", result.Text);
    }
}
