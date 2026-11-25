using System.Text.Json;
using System.Text.Json.Serialization;
using Anip.Core;

namespace Anip.Core.Tests;

/// <summary>SPEC.md §4.1: <c>required</c> defaults to <c>true</c> wherever a declaration is read.</summary>
public class CapabilityInputRequiredTests
{
    [Fact]
    public void InitialiserWithoutRequired_IsRequired()
    {
        var input = new CapabilityInput { Name = "origin", Type = "string" };

        Assert.True(input.Required);
    }

    [Fact]
    public void InitialiserCanDeclareAnOptionalInput()
    {
        var input = new CapabilityInput { Name = "limit", Type = "integer", Required = false };

        Assert.False(input.Required);
    }

    [Fact]
    public void DecodedWithoutRequired_IsRequired()
    {
        var input = JsonSerializer.Deserialize<CapabilityInput>(@"{""name"":""origin"",""type"":""string""}")!;

        Assert.True(input.Required);
    }

    [Theory]
    [InlineData("true", true)]
    [InlineData("false", false)]
    public void DecodedWithRequired_KeepsTheDeclaredValue(string literal, bool expected)
    {
        var input = JsonSerializer.Deserialize<CapabilityInput>(
            @"{""name"":""origin"",""type"":""string"",""required"":" + literal + "}")!;

        Assert.Equal(expected, input.Required);
    }

    [Fact]
    public void DecodedDeclarationAppliesTheDefaultToEveryInput()
    {
        var declaration = JsonSerializer.Deserialize<CapabilityDeclaration>(
            @"{""name"":""search"",""inputs"":[" +
            @"{""name"":""origin"",""type"":""string""}," +
            @"{""name"":""limit"",""type"":""integer"",""required"":false}," +
            @"{""name"":""date"",""type"":""date"",""default"":""today""}]}")!;

        Assert.Equal(new[] { true, false, true }, declaration.Inputs.Select(i => i.Required));
    }

    [Fact]
    public void DecodedManifestAppliesTheDefault()
    {
        var manifest = JsonSerializer.Deserialize<AnipManifest>(
            @"{""capabilities"":{""search"":{""name"":""search"",""inputs"":[{""name"":""origin"",""type"":""string""}]}}}")!;

        Assert.True(manifest.Capabilities["search"].Inputs[0].Required);
    }

    [Theory]
    [InlineData(true, @"""required"":true")]
    [InlineData(false, @"""required"":false")]
    public void SerialisationAlwaysWritesRequired(bool required, string expected)
    {
        var input = new CapabilityInput { Name = "origin", Type = "string", Required = required };

        // The options every runtime serialiser uses: nulls are dropped, `required` never is.
        var options = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        };
        var skipDefaults = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingDefault,
        };
        Assert.Contains(expected, JsonSerializer.Serialize(input));
        Assert.Contains(expected, JsonSerializer.Serialize(input, options));
        Assert.Contains(expected, JsonSerializer.Serialize(input, skipDefaults));
    }

    [Fact]
    public void SerialisedDefaultSurvivesARoundTrip()
    {
        var json = JsonSerializer.Serialize(new CapabilityInput { Name = "origin", Type = "string" });

        Assert.Contains(@"""required"":true", json);
        Assert.True(JsonSerializer.Deserialize<CapabilityInput>(json)!.Required);
    }
}
