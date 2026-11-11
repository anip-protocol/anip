using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>v0.23 composition validator + executor tests.</summary>
public class V023CompositionTests
{
    private static CapabilityDeclaration AtomicDecl(string name, string scope = "data") => new()
    {
        Name = name,
        Description = name,
        ContractVersion = "1.0",
        SideEffect = new SideEffect { Type = "none" },
        MinimumScope = new List<string> { scope },
        Kind = "atomic",
    };

    [Fact]
    public void ValidateComposition_HappyPath()
    {
        var step = AtomicDecl("step1");
        var parent = new CapabilityDeclaration
        {
            Name = "parent",
            Description = "parent",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "step1" },
                },
            },
        };
        var registry = new Dictionary<string, CapabilityDeclaration>
        {
            ["step1"] = step,
            ["parent"] = parent,
        };
        // Should not throw.
        V023.ValidateComposition("parent", parent, registry);
    }

    [Fact]
    public void ValidateComposition_RejectsMissingComposition()
    {
        var parent = new CapabilityDeclaration
        {
            Name = "parent", Description = "parent", ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = null,
        };
        var registry = new Dictionary<string, CapabilityDeclaration> { ["parent"] = parent };
        Assert.Throws<V023.CompositionValidationError>(() =>
            V023.ValidateComposition("parent", parent, registry));
    }

    [Fact]
    public void ValidateComposition_RejectsSelfReference()
    {
        var parent = new CapabilityDeclaration
        {
            Name = "parent", Description = "p", ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "parent" },
                },
            },
        };
        var registry = new Dictionary<string, CapabilityDeclaration> { ["parent"] = parent };
        Assert.Throws<V023.CompositionValidationError>(() =>
            V023.ValidateComposition("parent", parent, registry));
    }

    [Fact]
    public void ValidateComposition_RejectsForwardInputReference()
    {
        var step1 = AtomicDecl("step1");
        var step2 = AtomicDecl("step2");
        var parent = new CapabilityDeclaration
        {
            Name = "parent", Description = "p", ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "step1" },
                    new() { Id = "s2", Capability = "step2" },
                },
                InputMapping = new Dictionary<string, Dictionary<string, string>>
                {
                    ["s1"] = new()
                    {
                        ["k"] = "$.steps.s2.output.x", // forward ref — invalid
                    },
                },
            },
        };
        var registry = new Dictionary<string, CapabilityDeclaration>
        {
            ["step1"] = step1,
            ["step2"] = step2,
            ["parent"] = parent,
        };
        Assert.Throws<V023.CompositionValidationError>(() =>
            V023.ValidateComposition("parent", parent, registry));
    }

    [Fact]
    public void ValidateComposition_RejectsComposedChildStep()
    {
        var nested = new CapabilityDeclaration
        {
            Name = "nested",
            Description = "nested",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
        };
        var parent = new CapabilityDeclaration
        {
            Name = "parent",
            Description = "parent",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "nested" },
                },
            },
        };
        var registry = new Dictionary<string, CapabilityDeclaration>
        {
            ["nested"] = nested,
            ["parent"] = parent,
        };
        Assert.Throws<V023.CompositionValidationError>(() =>
            V023.ValidateComposition("parent", parent, registry));
    }

    [Fact]
    public void ExecuteComposition_HappyPath_OutputMapping()
    {
        var parent = new CapabilityDeclaration
        {
            Name = "parent",
            Description = "p",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "step1" },
                },
                OutputMapping = new Dictionary<string, string>
                {
                    ["greeting"] = "$.steps.s1.output.echo",
                },
            },
        };

        V023.InvokeStepFunc invoker = (cap, p) =>
        {
            Assert.Equal("step1", cap);
            return new Dictionary<string, object?>
            {
                ["success"] = true,
                ["result"] = new Dictionary<string, object?> { ["echo"] = "hi" },
            };
        };

        var result = V023.ExecuteComposition("parent", parent,
            new Dictionary<string, object?>(), invoker);
        Assert.Equal("hi", result["greeting"]);
    }

    [Fact]
    public void ExecuteComposition_FailureFailParentCollapses()
    {
        var parent = new CapabilityDeclaration
        {
            Name = "parent",
            Description = "p",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "step1" },
                },
                FailurePolicy = new FailurePolicy { ChildError = "fail_parent" },
            },
        };

        V023.InvokeStepFunc invoker = (cap, p) =>
        {
            return new Dictionary<string, object?>
            {
                ["success"] = false,
                ["failure"] = new Dictionary<string, object?>
                {
                    ["type"] = "internal_error",
                    ["detail"] = "boom",
                },
            };
        };

        var ex = Assert.Throws<AnipError>(() =>
            V023.ExecuteComposition("parent", parent,
                new Dictionary<string, object?>(), invoker));
        Assert.Equal(Constants.FailureCompositionChildFailed, ex.ErrorType);
    }

    [Fact]
    public void ExecuteComposition_ClarificationRequiredPropagatesByDefault()
    {
        var parent = new CapabilityDeclaration
        {
            Name = "parent",
            Description = "p",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "step1" },
                },
            },
        };

        V023.InvokeStepFunc invoker = (cap, p) => new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = new Dictionary<string, object?>
            {
                ["type"] = "clarification_required",
                ["detail"] = "quarter is required",
            },
        };

        var ex = Assert.Throws<AnipError>(() =>
            V023.ExecuteComposition("parent", parent,
                new Dictionary<string, object?>(), invoker));
        Assert.Equal("clarification_required", ex.ErrorType);
    }

    [Fact]
    public void ExecuteComposition_RestrictedPropagatesByDefault()
    {
        var parent = new CapabilityDeclaration
        {
            Name = "parent",
            Description = "p",
            ContractVersion = "1.0",
            SideEffect = new SideEffect { Type = "none" },
            MinimumScope = new List<string> { "data" },
            Kind = "composed",
            Composition = new Composition
            {
                AuthorityBoundary = "same_service",
                Steps = new List<CompositionStep>
                {
                    new() { Id = "s1", Capability = "step1" },
                },
            },
        };

        V023.InvokeStepFunc invoker = (cap, p) => new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = new Dictionary<string, object?>
            {
                ["type"] = "restricted",
                ["detail"] = "scope is restricted",
            },
        };

        var ex = Assert.Throws<AnipError>(() =>
            V023.ExecuteComposition("parent", parent,
                new Dictionary<string, object?>(), invoker));
        Assert.Equal("restricted", ex.ErrorType);
    }

    [Fact]
    public void CanonicalJsonSortsKeys()
    {
        var v = new Dictionary<string, object?>
        {
            ["b"] = 1,
            ["a"] = new Dictionary<string, object?> { ["z"] = 2, ["y"] = 3 },
        };
        var json = V023.CanonicalJson(v);
        Assert.Equal("{\"a\":{\"y\":3,\"z\":2},\"b\":1}", json);
    }

    [Fact]
    public void Sha256DigestIsStable()
    {
        var v = new Dictionary<string, object?> { ["k"] = "v" };
        var d1 = V023.Sha256Digest(v);
        var d2 = V023.Sha256Digest(new Dictionary<string, object?> { ["k"] = "v" });
        Assert.Equal(d1, d2);
        Assert.StartsWith("sha256:", d1);
    }

    // A Composition loaded from JSON (as generated projects and stored
    // definitions do) holds empty_result_output values as JsonElement, not
    // as .NET strings. References must behave the same either way.
    private static CapabilityDeclaration ParentWithJsonComposition(string compositionJson) => new()
    {
        Name = "parent",
        Description = "p",
        ContractVersion = "1.0",
        SideEffect = new SideEffect { Type = "none" },
        MinimumScope = new List<string> { "data" },
        Kind = "composed",
        Composition = JsonSerializer.Deserialize<Composition>(compositionJson),
    };

    [Fact]
    public void ExecuteComposition_ResolvesEmptyResultReferencesLoadedFromJson()
    {
        var parent = ParentWithJsonComposition("""
            {
              "authority_boundary": "same_service",
              "steps": [{ "id": "search", "capability": "step1", "empty_result_source": true }],
              "output_mapping": { "items": "$.steps.search.output.items" },
              "empty_result_policy": "return_success_no_results",
              "empty_result_output": {
                "query": "$.input.query",
                "items": "$.steps.search.output.items",
                "note": "no matches"
              }
            }
            """);

        V023.InvokeStepFunc invoker = (cap, p) => new Dictionary<string, object?>
        {
            ["success"] = true,
            ["result"] = new Dictionary<string, object?> { ["items"] = new List<object?>() },
        };

        var result = V023.ExecuteComposition("parent", parent,
            new Dictionary<string, object?> { ["query"] = "red shoes" }, invoker);

        Assert.Equal("red shoes", result["query"]);
        Assert.Empty(Assert.IsAssignableFrom<IList<object?>>(result["items"]));
        Assert.Equal("no matches", result["note"]?.ToString());
    }

    [Fact]
    public void ValidateComposition_RejectsEmptyResultReferenceToOtherStepLoadedFromJson()
    {
        var parent = ParentWithJsonComposition("""
            {
              "authority_boundary": "same_service",
              "steps": [
                { "id": "s1", "capability": "step1", "empty_result_source": true },
                { "id": "s2", "capability": "step2" }
              ],
              "output_mapping": { "x": "$.steps.s2.output.x" },
              "empty_result_policy": "return_success_no_results",
              "empty_result_output": { "x": "$.steps.s2.output.x" }
            }
            """);
        var registry = new Dictionary<string, CapabilityDeclaration>
        {
            ["step1"] = AtomicDecl("step1"),
            ["step2"] = AtomicDecl("step2"),
            ["parent"] = parent,
        };

        var error = Assert.Throws<V023.CompositionValidationError>(() =>
            V023.ValidateComposition("parent", parent, registry));
        Assert.Contains("empty_result_output['x']", error.Message);
    }
}
