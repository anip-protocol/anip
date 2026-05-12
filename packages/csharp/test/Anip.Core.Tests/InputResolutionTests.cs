using System.Text.Json;
using Xunit;
using Anip.Core;

namespace Anip.Core.Tests;

public class InputResolutionTests
{
    private static readonly JsonSerializerOptions Opts = new() { PropertyNameCaseInsensitive = false };

    [Fact]
    public void V023ShapedInputParsesUnchanged()
    {
        var raw = @"{""name"":""q"",""type"":""string""}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Null(inp.Resolution);
        Assert.False(inp.EntityReference);
        Assert.Null(inp.CatalogRef);
    }

    [Fact]
    public void BackendResolvedParses()
    {
        var raw = @"{""name"":""cohort_ref"",""type"":""string"",""required"":true," +
                  @"""semantic_type"":""cohort_reference"",""entity_reference"":true,""catalog_ref"":""gtm.cohort_catalog""," +
                  @"""resolution"":{""mode"":""backend_resolved"",""resolver_ref"":""gtm.cohort_catalog"",""on_missing"":""clarify""}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        CapabilityInput.Validate(inp);
        Assert.Equal(ResolutionMode.BackendResolved, inp.Resolution!.Mode);
        Assert.Equal("gtm.cohort_catalog", inp.CatalogRef);
        Assert.True(inp.EntityReference);
    }

    [Fact]
    public void UnknownModeRejected()
    {
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{""mode"":""not_real""}}";
        Assert.Throws<JsonException>(() => JsonSerializer.Deserialize<CapabilityInput>(raw, Opts));
    }

    [Fact]
    public void MissingModeRejectedAtValidate()
    {
        // {"resolution":{}} deserializes successfully with Mode==null;
        // Validate() must reject it.
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Null(inp.Resolution!.Mode);
        Assert.Throws<ArgumentException>(() => CapabilityInput.Validate(inp));
    }

    [Fact]
    public void ClosedValuesWithoutAllowedValuesRejected()
    {
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{""mode"":""closed_values""}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Throws<ArgumentException>(() => CapabilityInput.Validate(inp));
    }

    [Fact]
    public void UseDefaultWithoutDefaultRejected()
    {
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{""mode"":""clarify"",""on_missing"":""use_default""}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Throws<ArgumentException>(() => CapabilityInput.Validate(inp));
    }

    [Fact]
    public void RoundTrip()
    {
        var inp = new CapabilityInput
        {
            Name = "cohort_ref",
            Type = "string",
            Required = true,
            SemanticType = "cohort_reference",
            EntityReference = true,
            CatalogRef = "gtm.cohort_catalog",
            Resolution = new InputResolution
            {
                Mode = ResolutionMode.BackendResolved,
                ResolverRef = "gtm.cohort_catalog",
                OnMissing = ResolutionBehavior.Clarify
            }
        };
        var json = JsonSerializer.Serialize(inp, Opts);
        var rt = JsonSerializer.Deserialize<CapabilityInput>(json, Opts)!;
        Assert.Equal(inp.Resolution.Mode, rt.Resolution!.Mode);
        Assert.Equal(inp.CatalogRef, rt.CatalogRef);
    }
}
