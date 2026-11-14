using System.Numerics;
using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// SPEC.md §6.3 "Parameter Validation": the check itself, for every in-memory
/// representation a transport hands to the service (JsonElement and CLR values).
/// </summary>
public class ParameterValidationTests
{
    private static CapabilityDeclaration Declaration(params CapabilityInput[] inputs) => new()
    {
        Name = "book_flight",
        Inputs = inputs.ToList(),
    };

    private static CapabilityDeclaration BookFlight() => Declaration(
        new CapabilityInput { Name = "flight_number", Type = "string" },
        new CapabilityInput { Name = "date", Type = "date" },
        new CapabilityInput { Name = "passengers", Type = "integer", Required = false, Default = 1 },
        new CapabilityInput { Name = "quote_id", Type = "object", Required = false });

    private static JsonElement Json(string text)
    {
        using var doc = JsonDocument.Parse(text);
        return doc.RootElement.Clone();
    }

    /// <summary>Parameters the way the HTTP binding decodes an invocation body.</summary>
    private static Dictionary<string, object?> Body(string json) =>
        JsonSerializer.Deserialize<Dictionary<string, object?>>(json)!;

    private static string? Check(CapabilityDeclaration declaration, Dictionary<string, object?>? parameters) =>
        ParameterValidation.Check("book_flight", declaration, parameters);

    // --- required inputs ---

    // --- inputs that declare resolution.on_missing (SPEC.md §6.3 exception, §4.10) ---

    private static CapabilityInput Cohort(InputResolution? resolution) => new()
    {
        Name = "cohort", Type = "string", Required = true, Resolution = resolution,
    };

    [Theory]
    [InlineData(ResolutionBehavior.Clarify)]
    [InlineData(ResolutionBehavior.UseDefault)]
    [InlineData(ResolutionBehavior.Deny)]
    [InlineData(ResolutionBehavior.Omit)]
    public void RequiredInputThatDeclaresOnMissing_IsLeftToTheService(ResolutionBehavior onMissing)
    {
        var declaration = Declaration(Cohort(new InputResolution
        {
            Mode = ResolutionMode.Clarify, OnMissing = onMissing,
        }));

        Assert.Null(Check(declaration, Body("{}")));
        Assert.Null(Check(declaration, Body(@"{""cohort"": null}")));
    }

    [Fact]
    public void RequiredInputWithoutAResolutionBlock_IsRefusedWhenAbsent()
    {
        Assert.Equal("book_flight is missing required input(s): cohort",
            Check(Declaration(Cohort(null)), Body("{}")));
    }

    [Fact]
    public void RequiredInputWithAResolutionThatDoesNotSetOnMissing_IsRefusedWhenAbsent()
    {
        var declaration = Declaration(Cohort(new InputResolution { Mode = ResolutionMode.BackendResolved }));

        Assert.Equal("book_flight is missing required input(s): cohort", Check(declaration, Body("{}")));
    }

    [Fact]
    public void ASuppliedValueForAnOnMissingInput_IsStillTypeChecked()
    {
        var declaration = Declaration(Cohort(new InputResolution
        {
            Mode = ResolutionMode.Clarify, OnMissing = ResolutionBehavior.Clarify,
        }));

        Assert.Equal("book_flight has invalid input(s): 'cohort' must be string, got number",
            Check(declaration, Body(@"{""cohort"": 7}")));
    }

    [Fact]
    public void ValidCallPasses()
    {
        Assert.Null(Check(BookFlight(), Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10""}")));
    }

    [Fact]
    public void MissingRequiredInputsAreNamedInDeclarationOrder()
    {
        Assert.Equal(
            "book_flight is missing required input(s): flight_number, date",
            Check(BookFlight(), Body(@"{""passengers"":2}")));
    }

    [Fact]
    public void NullOrAbsentParametersCountAsEmpty()
    {
        Assert.Equal("book_flight is missing required input(s): flight_number, date", Check(BookFlight(), null));
        Assert.Equal("book_flight is missing required input(s): flight_number, date",
            Check(BookFlight(), new Dictionary<string, object?>()));
    }

    [Fact]
    public void JsonNullForARequiredInputIsMissing()
    {
        Assert.Equal(
            "book_flight is missing required input(s): date",
            Check(BookFlight(), Body(@"{""flight_number"":""AA100"",""date"":null}")));
        // A JsonElement of kind Null, and a CLR null.
        Assert.Equal(
            "book_flight is missing required input(s): flight_number, date",
            Check(BookFlight(), new Dictionary<string, object?>
            {
                ["flight_number"] = Json("null"),
                ["date"] = null,
            }));
    }

    [Fact]
    public void ADeclaredDefaultDoesNotSatisfyRequired()
    {
        var declaration = Declaration(new CapabilityInput { Name = "passengers", Type = "integer", Default = 1 });

        Assert.Equal("book_flight is missing required input(s): passengers",
            Check(declaration, new Dictionary<string, object?>()));
    }

    [Fact]
    public void MissingInputsAreReportedBeforeWrongTypes()
    {
        Assert.Equal(
            "book_flight is missing required input(s): date",
            Check(BookFlight(), Body(@"{""flight_number"":7,""passengers"":""two""}")));
    }

    [Fact]
    public void OptionalInputMayBeAbsentOrNull()
    {
        Assert.Null(Check(BookFlight(),
            Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10"",""passengers"":null,""quote_id"":null}")));
    }

    [Fact]
    public void UndeclaredParametersAreNamed()
    {
        Assert.Equal(
            "book_flight has undeclared parameter(s): meal, seat",
            Check(BookFlight(),
                Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10"",""seat"":[1,2],""meal"":false}")));
    }

    [Fact]
    public void AnUndeclaredParameterWithANullValueIsUndeclared()
    {
        Assert.Equal(
            "book_flight has undeclared parameter(s): seat",
            Check(BookFlight(), Body(@"{""flight_number"":""AA100"",""date"":""2026-03-10"",""seat"":null}")));
    }

    [Fact]
    public void UndeclaredParametersAreNamedInUtf16Order()
    {
        // RFC 8785 member order (SPEC.md §4.7): U+FF5E sorts after U+1F600.
        Assert.Equal(
            "book_flight has undeclared parameter(s): Beta, alpha, zeta, \U0001F600, \uFF5E",
            Check(BookFlight(), Body(
                @"{""flight_number"":""AA100"",""date"":""2026-03-10"",""zeta"":1,""\uff5e"":2,""Beta"":null,""\ud83d\ude00"":3,""alpha"":4}")));
    }

    [Fact]
    public void MissingComesBeforeUndeclaredAndUndeclaredBeforeWrongTypes()
    {
        Assert.Equal(
            "book_flight is missing required input(s): date",
            Check(BookFlight(), Body(@"{""flight_number"":""AA100"",""seat"":1}")));
        Assert.Equal(
            "book_flight has undeclared parameter(s): seat",
            Check(BookFlight(), Body(@"{""flight_number"":7,""date"":""2026-03-10"",""seat"":1}")));
    }

    [Fact]
    public void ADeclarationWithoutInputsAcceptsOnlyEmptyParameters()
    {
        Assert.Equal("book_flight has undeclared parameter(s): anything",
            ParameterValidation.Check("book_flight", Declaration(), Body(@"{""anything"":1}")));
        Assert.Null(Check(Declaration(), null));
        Assert.Null(Check(Declaration(), Body("{}")));
    }

    // --- primitive types ---

    [Fact]
    public void WrongTypesAreNamedInDeclarationOrder()
    {
        Assert.Equal(
            "book_flight has invalid input(s): 'passengers' must be integer, got string; 'quote_id' must be object, got array",
            Check(BookFlight(),
                Body(@"{""quote_id"":[1],""passengers"":""two"",""flight_number"":""AA100"",""date"":""2026-03-10""}")));
    }

    public static IEnumerable<object[]> TypeMatrix()
    {
        var values = new (string Received, string Json)[]
        {
            ("string", @"""x"""),
            ("number", "1.5"),
            ("boolean", "true"),
            ("boolean", "false"),
            ("array", "[1]"),
            ("object", @"{""a"":1}"),
        };
        var accepts = new Dictionary<string, string[]>
        {
            ["string"] = new[] { "string" },
            ["integer"] = Array.Empty<string>(), // 1.5 is a number but not integral
            ["number"] = new[] { "number" },
            ["boolean"] = new[] { "boolean" },
            ["array"] = new[] { "array" },
            ["object"] = new[] { "object" },
        };
        foreach (var (declared, accepted) in accepts)
        {
            foreach (var (received, json) in values)
            {
                yield return new object[] { declared, json, received, accepted.Contains(received) };
            }
        }
    }

    [Theory]
    [MemberData(nameof(TypeMatrix))]
    public void PrimitiveTypeMatrix_JsonElementValues(string declared, string json, string received, bool ok)
    {
        var declaration = Declaration(new CapabilityInput { Name = "value", Type = declared });

        var detail = Check(declaration, new Dictionary<string, object?> { ["value"] = Json(json) });

        Assert.Equal(ok ? null : $"book_flight has invalid input(s): 'value' must be {declared}, got {received}", detail);
    }

    public static IEnumerable<object?[]> ClrValues() => new[]
    {
        new object?[] { "x", "string" },
        new object?[] { 'x', "string" },
        new object?[] { 1, "number" },
        new object?[] { 1L, "number" },
        new object?[] { (short)1, "number" },
        new object?[] { (byte)1, "number" },
        new object?[] { 1u, "number" },
        new object?[] { 1ul, "number" },
        new object?[] { 1.5, "number" },
        new object?[] { 1.5f, "number" },
        new object?[] { 1.5m, "number" },
        new object?[] { BigInteger.Parse("123456789012345678901234567890"), "number" },
        new object?[] { true, "boolean" },
        new object?[] { false, "boolean" },
        new object?[] { new List<object?> { 1 }, "array" },
        new object?[] { new[] { "a" }, "array" },
        new object?[] { new Dictionary<string, object?> { ["a"] = 1 }, "object" },
        new object?[] { new Dictionary<string, object> { ["a"] = 1 }, "object" },
        new object?[] { new SortedDictionary<string, string> { ["a"] = "b" }, "object" },
        new object?[] { new Budget { Currency = "USD", MaxAmount = 1 }, "object" },
    };

    [Theory]
    [MemberData(nameof(ClrValues))]
    public void JsonTypeOfClrValues(object value, string expected)
    {
        Assert.Equal(expected, ParameterValidation.JsonTypeOf(value));
    }

    [Theory]
    [InlineData(@"""x""", "string")]
    [InlineData("0", "number")]
    [InlineData("-1.5e3", "number")]
    [InlineData("true", "boolean")]
    [InlineData("false", "boolean")]
    [InlineData("[]", "array")]
    [InlineData("{}", "object")]
    public void JsonTypeOfJsonElementsAndNodes(string json, string expected)
    {
        Assert.Equal(expected, ParameterValidation.JsonTypeOf(Json(json)));
        Assert.Equal(expected, ParameterValidation.JsonTypeOf(System.Text.Json.Nodes.JsonNode.Parse(json)));
    }

    [Fact]
    public void JsonTypeOfNullIsNull()
    {
        Assert.Null(ParameterValidation.JsonTypeOf(null));
        Assert.Null(ParameterValidation.JsonTypeOf(Json("null")));
        Assert.Null(ParameterValidation.JsonTypeOf(default(JsonElement)));
    }

    [Theory]
    [InlineData("5")]
    [InlineData("5.0")]
    [InlineData("1e2")]
    [InlineData("1.5e1")]
    [InlineData("-0")]
    [InlineData("-7")]
    [InlineData("9007199254740993")]
    [InlineData("123456789012345678901234567890")]
    [InlineData("1E+30")]
    public void IntegerAcceptsEveryIntegralJsonNumber(string json)
    {
        var declaration = Declaration(new CapabilityInput { Name = "passengers", Type = "integer" });

        Assert.Null(Check(declaration, Body(@"{""passengers"":" + json + "}")));
    }

    [Theory]
    [InlineData("1.5", "number")]
    [InlineData("0.1", "number")]
    [InlineData("1e-2", "number")]
    [InlineData("true", "boolean")]
    [InlineData("false", "boolean")]
    [InlineData(@"""5""", "string")]
    public void IntegerRejectsEverythingElse(string json, string received)
    {
        var declaration = Declaration(new CapabilityInput { Name = "passengers", Type = "integer" });

        Assert.Equal(
            $"book_flight has invalid input(s): 'passengers' must be integer, got {received}",
            Check(declaration, Body(@"{""passengers"":" + json + "}")));
    }

    public static IEnumerable<object?[]> ClrIntegers() => new[]
    {
        new object?[] { 5, true },
        new object?[] { 5L, true },
        new object?[] { 5.0, true },
        new object?[] { 5.0f, true },
        new object?[] { 5.0m, true },
        new object?[] { 1e30, true },
        new object?[] { BigInteger.Parse("123456789012345678901234567890"), true },
        new object?[] { 1.5, false },
        new object?[] { 1.5f, false },
        new object?[] { 1.5m, false },
        new object?[] { double.NaN, false },
        new object?[] { double.PositiveInfinity, false },
    };

    [Theory]
    [MemberData(nameof(ClrIntegers))]
    public void IntegerChecksClrNumbers(object value, bool ok)
    {
        var declaration = Declaration(new CapabilityInput { Name = "passengers", Type = "integer" });

        var detail = Check(declaration, new Dictionary<string, object?> { ["passengers"] = value });

        Assert.Equal(ok ? null : "book_flight has invalid input(s): 'passengers' must be integer, got number", detail);
    }

    [Fact]
    public void ABooleanIsNotANumber()
    {
        var declaration = Declaration(new CapabilityInput { Name = "amount", Type = "number" });

        Assert.Equal("book_flight has invalid input(s): 'amount' must be number, got boolean",
            Check(declaration, new Dictionary<string, object?> { ["amount"] = true }));
        Assert.Equal("book_flight has invalid input(s): 'amount' must be number, got boolean",
            Check(declaration, Body(@"{""amount"":false}")));
    }

    [Theory]
    [InlineData("airport_code")]
    [InlineData("date")]
    [InlineData("String")]
    [InlineData("int")]
    [InlineData("")]
    public void OtherTypeNamesAreNotChecked(string declared)
    {
        var declaration = Declaration(new CapabilityInput { Name = "value", Type = declared });

        foreach (var json in new[] { @"""x""", "1.5", "true", "[1]", @"{""a"":1}" })
        {
            Assert.Null(Check(declaration, Body(@"{""value"":" + json + "}")));
        }
    }

    // --- the failure object ---

    [Fact]
    public void FailureObjectIsTheSpecifiedOne()
    {
        var failure = ParameterValidation.Failure("book_flight is missing required input(s): date");

        Assert.Equal(Constants.FailureInvalidParameters, failure["type"]);
        Assert.Equal("book_flight is missing required input(s): date", failure["detail"]);
        Assert.Equal(false, failure["retry"]);
        var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
        Assert.Equal("retry_now", resolution["action"]);
        Assert.Equal("retry_now", resolution["recovery_class"]);
        Assert.Equal("parameters that match the capability's declared inputs", resolution["requires"]);
    }
}
