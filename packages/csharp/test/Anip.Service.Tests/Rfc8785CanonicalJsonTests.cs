using System.Numerics;
using System.Text;
using System.Text.Json;
using Anip.Core;
using Anip.Service;

namespace Anip.Service.Tests;

/// <summary>
/// SPEC.md §4.7 "Canonical JSON and Digests": approval digests are computed
/// over RFC 8785 (JCS) canonical JSON. The shared vectors are JSON texts; each
/// is parsed the way the HTTP binding parses an invocation body, so the test
/// covers parse → canonicalise, including how the parser represents numbers.
/// </summary>
public class Rfc8785CanonicalJsonTests
{
    public sealed record Vector(string Name, string Input, string Canonical, string CanonicalUtf8Hex, string Sha256);

    private static string FixturePath() => Path.GetFullPath(Path.Combine(
        AppContext.BaseDirectory, "..", "..", "..", "..", "..", "..",
        "canonical-json-fixtures", "rfc8785-vectors.json"));

    private static List<Vector> LoadVectors()
    {
        using var fixture = JsonDocument.Parse(File.ReadAllText(FixturePath()));
        return fixture.RootElement.GetProperty("vectors").EnumerateArray()
            .Select(v => new Vector(
                v.GetProperty("name").GetString()!,
                v.GetProperty("input").GetString()!,
                v.GetProperty("canonical").GetString()!,
                v.GetProperty("canonical_utf8_hex").GetString()!,
                v.GetProperty("sha256").GetString()!))
            .ToList();
    }

    public static IEnumerable<object[]> VectorNames() => LoadVectors().Select(v => new object[] { v.Name });

    /// <summary>
    /// What <c>AnipController.Invoke</c> does with a request body: the body is
    /// decoded to a dictionary, and its <c>parameters</c> member is decoded to
    /// the dictionary handed to the service.
    /// </summary>
    private static Dictionary<string, object?> ParametersAsTheHttpBindingDecodesThem(string bodyJson)
    {
        var options = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull,
        };
        var body = JsonSerializer.Deserialize<Dictionary<string, object?>>(bodyJson, options)!;
        var parameters = (JsonElement)body["parameters"]!;
        return JsonSerializer.Deserialize<Dictionary<string, object?>>(parameters.GetRawText(), options)!;
    }

    private static string Hex(string text) => Convert.ToHexString(Encoding.UTF8.GetBytes(text)).ToLowerInvariant();

    [Fact]
    public void TheFixtureHasSixtyFiveVectors()
    {
        Assert.Equal(65, LoadVectors().Count);
    }

    [Theory]
    [MemberData(nameof(VectorNames))]
    public void Vector_AsAParameterValue(string name)
    {
        var vector = LoadVectors().Single(v => v.Name == name);
        var parameters = ParametersAsTheHttpBindingDecodesThem("{\"parameters\":{\"value\":" + vector.Input + "}}");

        var value = parameters["value"];

        Assert.Equal(vector.CanonicalUtf8Hex, Hex(V023.CanonicalJson(value)));
        Assert.Equal(vector.Canonical, V023.CanonicalJson(value));
        Assert.Equal(vector.Sha256, V023.Sha256Digest(value));
    }

    [Theory]
    [MemberData(nameof(VectorNames))]
    public void Vector_AsTheParametersObject(string name)
    {
        var vector = LoadVectors().Single(v => v.Name == name);
        using var input = JsonDocument.Parse(vector.Input);
        if (input.RootElement.ValueKind != JsonValueKind.Object)
        {
            // Parameters are an object; the other vectors are covered as parameter values.
            return;
        }
        var parameters = ParametersAsTheHttpBindingDecodesThem("{\"parameters\":" + vector.Input + "}");

        Assert.Equal(vector.CanonicalUtf8Hex, Hex(V023.CanonicalJson(parameters)));
        Assert.Equal(vector.Sha256, V023.Sha256Digest(parameters));
    }

    [Fact]
    public void SomeVectorsAreParametersObjects()
    {
        var objects = LoadVectors().Count(v =>
        {
            using var input = JsonDocument.Parse(v.Input);
            return input.RootElement.ValueKind == JsonValueKind.Object;
        });

        Assert.True(objects >= 10, $"only {objects} object vectors");
    }

    // --- CLR values: transports other than HTTP hand the service native numbers ---

    public static IEnumerable<object?[]> ClrNumbers() => new[]
    {
        new object?[] { 5, "5" },
        new object?[] { 5L, "5" },
        new object?[] { 5.0, "5" },
        new object?[] { 5.0f, "5" },
        new object?[] { 5.0m, "5" },
        new object?[] { 4.50m, "4.5" },
        new object?[] { (short)-7, "-7" },
        new object?[] { 0.0, "0" },
        new object?[] { -0.0, "0" },
        new object?[] { 1e21, "1e+21" },
        new object?[] { 1e20, "100000000000000000000" },
        new object?[] { 1e-6, "0.000001" },
        new object?[] { 1e-7, "1e-7" },
        new object?[] { 123456789e-15, "1.23456789e-7" },
        new object?[] { 5e-324, "5e-324" },
        new object?[] { double.MaxValue, "1.7976931348623157e+308" },
        new object?[] { 0.1 + 0.2, "0.30000000000000004" },
        new object?[] { 9007199254740993L, "9007199254740992" },
        new object?[] { long.MaxValue, "9223372036854776000" },
        new object?[] { ulong.MaxValue, "18446744073709552000" },
        new object?[] { 0.1m, "0.1" },
    };

    [Theory]
    [MemberData(nameof(ClrNumbers))]
    public void ClrNumbersAreDoubles(object value, string expected)
    {
        Assert.Equal(expected, V023.CanonicalJson(value));
        Assert.Equal("{\"n\":" + expected + "}",
            V023.CanonicalJson(new Dictionary<string, object?> { ["n"] = value }));
    }

    [Theory]
    [InlineData(double.NaN)]
    [InlineData(double.PositiveInfinity)]
    [InlineData(double.NegativeInfinity)]
    public void NonFiniteNumbersAreAnError(double value)
    {
        Assert.ThrowsAny<Exception>(() => V023.CanonicalJson(new Dictionary<string, object?> { ["n"] = value }));
    }

    [Fact]
    public void ANumberTooLargeForADoubleIsAnError()
    {
        using var doc = JsonDocument.Parse("{\"n\":1e400}");

        Assert.ThrowsAny<Exception>(() => V023.CanonicalJson(doc.RootElement.Clone()));
    }

    [Fact]
    public void ClrObjectGraph()
    {
        var value = new Dictionary<string, object?>
        {
            ["b"] = new List<object?> { 1, "x", null, true, 2.50 },
            ["a"] = new Dictionary<string, object> { ["é"] = "</script>", ["A"] = 1.0 },
            ["😀"] = "astral",
            ["～"] = "bmp",
        };

        Assert.Equal(
            "{\"a\":{\"A\":1,\"é\":\"</script>\"},\"b\":[1,\"x\",null,true,2.5],\"😀\":\"astral\",\"～\":\"bmp\"}",
            V023.CanonicalJson(value));
    }

    [Fact]
    public void TypedObjectsAreCanonicalisedByTheirJsonNames()
    {
        var policy = new GrantPolicy
        {
            AllowedGrantTypes = new() { "one_time" },
            DefaultGrantType = "one_time",
            ExpiresInSeconds = 900,
            MaxUses = 1,
        };

        Assert.Equal(
            "{\"allowed_grant_types\":[\"one_time\"],\"default_grant_type\":\"one_time\",\"expires_in_seconds\":900,\"max_uses\":1}",
            V023.CanonicalJson(policy));
    }

    [Fact]
    public void IntegralFloatAndIntegerHaveTheSameDigest_AndAnotherIntegerDoesNot()
    {
        static Dictionary<string, object?> P(string passengers) => ParametersAsTheHttpBindingDecodesThem(
            "{\"parameters\":{\"flight_number\":\"AA100\",\"passengers\":" + passengers + "}}");

        var five = V023.Sha256Digest(P("5"));

        Assert.Equal(five, V023.Sha256Digest(P("5.0")));
        Assert.Equal(five, V023.Sha256Digest(P("5e0")));
        Assert.Equal(five, V023.Sha256Digest(new Dictionary<string, object?> { ["flight_number"] = "AA100", ["passengers"] = 5 }));
        Assert.Equal(five, V023.Sha256Digest(new Dictionary<string, object?> { ["passengers"] = 5.0, ["flight_number"] = "AA100" }));
        Assert.NotEqual(five, V023.Sha256Digest(P("6")));
        Assert.NotEqual(five, V023.Sha256Digest(P("\"5\"")));
    }
}

/// <summary>§4.8 step 6 through the invoke pipeline: <c>5</c> approved, <c>5.0</c> continued.</summary>
public class ApprovalDigestContinuationTests : IDisposable
{
    private readonly AnipService _service;

    public ApprovalDigestContinuationTests()
    {
        _service = new AnipService(new ServiceConfig
        {
            ServiceId = "svc-digest",
            Storage = ":memory:",
            Trust = "signed",
            RetentionIntervalSeconds = -1,
            Capabilities = new List<CapabilityDef>
            {
                new(
                    new CapabilityDeclaration
                    {
                        Name = "book",
                        Description = "needs approval until a grant is supplied",
                        ContractVersion = "1.0",
                        SideEffect = new SideEffect { Type = "irreversible" },
                        MinimumScope = new List<string> { "travel.book" },
                        Inputs = new List<CapabilityInput>
                        {
                            new() { Name = "flight_number", Type = "string" },
                            new() { Name = "passengers", Type = "integer" },
                            new() { Name = "note", Type = "string", Required = false },
                        },
                        GrantPolicy = new GrantPolicy
                        {
                            AllowedGrantTypes = new() { "one_time" },
                            DefaultGrantType = "one_time",
                            ExpiresInSeconds = 600,
                            MaxUses = 1,
                        },
                    },
                    (ctx, p) => string.IsNullOrWhiteSpace(ctx.ApprovalGrant)
                        ? throw new AnipError(Constants.FailureApprovalRequired, "approval needed")
                            .WithResolution("request_approval")
                        : new Dictionary<string, object?> { ["booked"] = true }),
            },
            Authenticate = bearer => bearer == "valid-key" ? "alice" : null,
        });
        _service.Start();
    }

    public void Dispose() => _service.Dispose();

    private static Dictionary<string, object?> Body(string json) =>
        JsonSerializer.Deserialize<Dictionary<string, object?>>(json)!;

    private (DelegationToken Token, string GrantId) Approve(string parameters)
    {
        var token = _service.ResolveBearerToken(_service.IssueToken("alice", new TokenRequest
        {
            Subject = "agent-1",
            Scope = new List<string> { "travel.book" },
            Capability = "book",
            TtlHours = 1,
        }).Token);
        var asked = _service.Invoke("book", token, Body(parameters), new InvokeOpts());
        var failure = (Dictionary<string, object?>)asked["failure"]!;
        var approval = (Dictionary<string, object?>)failure["approval_required"]!;
        var grant = _service.IssueApprovalGrant(
            (string)approval["approval_request_id"]!, ApprovalGrant.TypeOneTime,
            new Dictionary<string, object?> { ["subject"] = "boss" }, null, null, null);
        return (token, grant.GrantId);
    }

    [Fact]
    public void IntegralFloatIsNotDrift_AndAnotherIntegerIs()
    {
        var (token, grantId) = Approve("""{"flight_number":"AA100","passengers":5}""");

        var other = _service.Invoke("book", token, Body("""{"flight_number":"AA100","passengers":6}"""),
            new InvokeOpts { ApprovalGrant = grantId });
        Assert.Equal(Constants.FailureGrantParamDrift, ((Dictionary<string, object?>)other["failure"]!)["type"]);

        var asFloat = _service.Invoke("book", token, Body("""{"passengers":5.0,"flight_number":"AA100"}"""),
            new InvokeOpts { ApprovalGrant = grantId });
        Assert.Equal(true, asFloat["success"]);
    }

    public static IEnumerable<object[]> NativeFives() => new[]
    {
        new object[] { 5 },
        new object[] { 5L },
        new object[] { 5.0 },
        new object[] { 5.0f },
        // System.Text.Json writes this one as "5.0".
        new object[] { 5.0m },
    };

    [Theory]
    [MemberData(nameof(NativeFives))]
    public void ANativeNumberFromAnotherTransportIsNotDrift(object five)
    {
        var (token, grantId) = Approve("""{"flight_number":"AA100","passengers":5}""");

        var continued = _service.Invoke("book", token,
            new Dictionary<string, object?> { ["flight_number"] = "AA100", ["passengers"] = five },
            new InvokeOpts { ApprovalGrant = grantId });

        Assert.Equal(true, continued["success"]);
    }

    [Fact]
    public void ANullParameterIsDigestedAsNull()
    {
        var (token, grantId) = Approve("""{"flight_number":"AA100","passengers":5,"note":null}""");

        // null is not the empty string...
        var withEmptyString = _service.Invoke("book", token,
            Body("""{"flight_number":"AA100","passengers":5,"note":""}"""),
            new InvokeOpts { ApprovalGrant = grantId });
        Assert.Equal(Constants.FailureGrantParamDrift,
            ((Dictionary<string, object?>)withEmptyString["failure"]!)["type"]);

        // ...and the request that was approved continues.
        var continued = _service.Invoke("book", token,
            Body("""{"flight_number":"AA100","passengers":5,"note":null}"""),
            new InvokeOpts { ApprovalGrant = grantId });
        Assert.Equal(true, continued["success"]);
    }

    [Fact]
    public void NonAsciiParametersAreNotDrift()
    {
        var (token, grantId) = Approve("""{"flight_number":"AA100","passengers":5,"note":"café <b>&</b> 日本語 😀"}""");

        var continued = _service.Invoke("book", token,
            Body("""{"note":"café <b>&</b> 日本語 😀","passengers":5e0,"flight_number":"AA100"}"""),
            new InvokeOpts { ApprovalGrant = grantId });

        Assert.Equal(true, continued["success"]);
    }
}
