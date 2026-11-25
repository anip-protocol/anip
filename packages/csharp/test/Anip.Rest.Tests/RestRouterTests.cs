using Anip.Core;
using Anip.Rest;
using Anip.Service;

namespace Anip.Rest.Tests;

public class RestRouterTests
{
    private static CapabilityDeclaration ReadCapability(string name = "get_flights") => new()
    {
        Name = name,
        Description = "Search for flights",
        SideEffect = new SideEffect { Type = "read" },
        MinimumScope = new List<string> { "flights.search" },
        Inputs = new List<CapabilityInput>
        {
            new() { Name = "origin", Type = "string", Required = true, Description = "Origin airport" },
            new() { Name = "limit", Type = "integer", Required = false, Description = "Max results" },
            new() { Name = "direct_only", Type = "boolean", Required = false, Description = "Direct flights only" },
        },
    };

    private static CapabilityDeclaration WriteCapability(string name = "book_flight") => new()
    {
        Name = name,
        Description = "Book a flight",
        SideEffect = new SideEffect { Type = "irreversible" },
        MinimumScope = new List<string> { "flights.book" },
        Inputs = new List<CapabilityInput>
        {
            new() { Name = "flight_id", Type = "string", Required = true, Description = "Flight ID" },
            new() { Name = "passengers", Type = "integer", Required = true, Description = "Number of passengers" },
        },
    };

    private static RestRoute MakeRoute(CapabilityDeclaration decl, string? pathOverride = null, string? methodOverride = null)
    {
        var path = pathOverride ?? "/api/" + decl.Name;
        var method = methodOverride ?? (decl.SideEffect?.Type == "read" ? "GET" : "POST");
        return new RestRoute(decl.Name, path, method, decl);
    }

    // --- Route generation from declarations ---

    [Fact]
    public void ReadCapability_GetsGetRoute()
    {
        var decl = ReadCapability();
        var route = MakeRoute(decl);

        Assert.Equal("get_flights", route.CapabilityName);
        Assert.Equal("/api/get_flights", route.Path);
        Assert.Equal("GET", route.Method);
        Assert.Same(decl, route.Declaration);
    }

    [Fact]
    public void WriteCapability_GetsPostRoute()
    {
        var decl = WriteCapability();
        var route = MakeRoute(decl);

        Assert.Equal("book_flight", route.CapabilityName);
        Assert.Equal("/api/book_flight", route.Path);
        Assert.Equal("POST", route.Method);
        Assert.Same(decl, route.Declaration);
    }

    // --- Overrides ---

    [Fact]
    public void Override_AppliesPathAndMethod()
    {
        var decl = ReadCapability();
        var ov = new RouteOverride("/custom/flights", "POST");

        var path = !string.IsNullOrEmpty(ov.Path) ? ov.Path : "/api/" + decl.Name;
        var method = !string.IsNullOrEmpty(ov.Method) ? ov.Method : "GET";
        var route = new RestRoute(decl.Name, path, method, decl);

        Assert.Equal("/custom/flights", route.Path);
        Assert.Equal("POST", route.Method);
    }

    [Fact]
    public void Override_NullFieldsKeepDefaults()
    {
        var decl = ReadCapability();
        var ov = new RouteOverride(null, null);

        var path = !string.IsNullOrEmpty(ov.Path) ? ov.Path : "/api/" + decl.Name;
        var method = !string.IsNullOrEmpty(ov.Method) ? ov.Method : "GET";
        var route = new RestRoute(decl.Name, path, method, decl);

        Assert.Equal("/api/get_flights", route.Path);
        Assert.Equal("GET", route.Method);
    }

    // --- ConvertQueryParams ---

    [Fact]
    public void ConvertQueryParams_IntegerConversion()
    {
        var decl = ReadCapability();
        var rawParams = new Dictionary<string, string>
        {
            ["origin"] = "JFK",
            ["limit"] = "10",
        };

        var result = RestRouter.ConvertQueryParams(rawParams, decl);

        Assert.Equal("JFK", result["origin"]);
        Assert.Equal(10, result["limit"]);
    }

    [Fact]
    public void ConvertQueryParams_BooleanConversion()
    {
        var decl = ReadCapability();
        var rawParams = new Dictionary<string, string>
        {
            ["direct_only"] = "true",
        };

        var result = RestRouter.ConvertQueryParams(rawParams, decl);

        Assert.Equal(true, result["direct_only"]);
    }

    [Fact]
    public void ConvertQueryParams_BooleanFalse()
    {
        var decl = ReadCapability();
        var rawParams = new Dictionary<string, string>
        {
            ["direct_only"] = "false",
        };

        var result = RestRouter.ConvertQueryParams(rawParams, decl);

        Assert.Equal(false, result["direct_only"]);
    }

    [Fact]
    public void ConvertQueryParams_InvalidIntegerKeepsString()
    {
        var decl = ReadCapability();
        var rawParams = new Dictionary<string, string>
        {
            ["limit"] = "abc",
        };

        var result = RestRouter.ConvertQueryParams(rawParams, decl);

        Assert.Equal("abc", result["limit"]);
    }

    [Fact]
    public void ConvertQueryParams_UnknownParamTreatedAsString()
    {
        var decl = ReadCapability();
        var rawParams = new Dictionary<string, string>
        {
            ["unknown_param"] = "hello",
        };

        var result = RestRouter.ConvertQueryParams(rawParams, decl);

        Assert.Equal("hello", result["unknown_param"]);
    }

    // --- ExtractBodyParams ---

    [Fact]
    public void ExtractBodyParams_WithWrapper()
    {
        var innerParams = new Dictionary<string, object?>
        {
            ["flight_id"] = "FL-123",
            ["passengers"] = 2,
        };
        var body = new Dictionary<string, object?>
        {
            ["parameters"] = innerParams,
        };

        var result = RestRouter.ExtractBodyParams(body);

        Assert.Equal("FL-123", result["flight_id"]);
        Assert.Equal(2, result["passengers"]);
    }

    [Fact]
    public void ExtractBodyParams_FlatBody()
    {
        var body = new Dictionary<string, object?>
        {
            ["flight_id"] = "FL-123",
            ["passengers"] = 2,
        };

        var result = RestRouter.ExtractBodyParams(body);

        Assert.Equal("FL-123", result["flight_id"]);
        Assert.Equal(2, result["passengers"]);
    }

    [Fact]
    public void ExtractBodyParams_NullReturnsEmpty()
    {
        var result = RestRouter.ExtractBodyParams(null);

        Assert.Empty(result);
    }

    // --- FindRoute ---

    [Fact]
    public void FindRoute_ExistingCapability()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(ReadCapability()),
            MakeRoute(WriteCapability()),
        };

        var found = RestRouter.FindRoute(routes, "get_flights");

        Assert.NotNull(found);
        Assert.Equal("get_flights", found!.CapabilityName);
        Assert.Equal("GET", found.Method);
    }

    [Fact]
    public void FindRoute_UnknownCapabilityReturnsNull()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(ReadCapability()),
        };

        var found = RestRouter.FindRoute(routes, "nonexistent");

        Assert.Null(found);
    }

    // --- OpenApiGenerator ---

    [Fact]
    public void GenerateSpec_ContainsOpenApiVersion()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(ReadCapability()),
            MakeRoute(WriteCapability()),
        };

        var spec = OpenApiGenerator.GenerateSpec("test-service", routes);

        Assert.Equal("3.1.0", spec["openapi"]);
    }

    [Fact]
    public void GenerateSpec_ContainsPathsForAllRoutes()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(ReadCapability()),
            MakeRoute(WriteCapability()),
        };

        var spec = OpenApiGenerator.GenerateSpec("test-service", routes);
        var paths = (Dictionary<string, object?>)spec["paths"]!;

        Assert.True(paths.ContainsKey("/api/get_flights"));
        Assert.True(paths.ContainsKey("/api/book_flight"));
    }

    [Fact]
    public void GenerateSpec_GetRouteHasQueryParameters()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(ReadCapability()),
        };

        var spec = OpenApiGenerator.GenerateSpec("test-service", routes);
        var paths = (Dictionary<string, object?>)spec["paths"]!;
        var pathItem = (Dictionary<string, object?>)paths["/api/get_flights"]!;
        var operation = (Dictionary<string, object?>)pathItem["get"]!;

        Assert.True(operation.ContainsKey("parameters"));
        var parameters = (List<Dictionary<string, object?>>)operation["parameters"]!;
        Assert.Equal(3, parameters.Count);
        Assert.Equal("origin", parameters[0]["name"]);
    }

    [Fact]
    public void GenerateSpec_PostRouteHasRequestBody()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(WriteCapability()),
        };

        var spec = OpenApiGenerator.GenerateSpec("test-service", routes);
        var paths = (Dictionary<string, object?>)spec["paths"]!;
        var pathItem = (Dictionary<string, object?>)paths["/api/book_flight"]!;
        var operation = (Dictionary<string, object?>)pathItem["post"]!;

        Assert.True(operation.ContainsKey("requestBody"));
    }

    private static CapabilityDeclaration OnMissingCapability(string sideEffect) => new()
    {
        Name = "draft_notice",
        SideEffect = new SideEffect { Type = sideEffect },
        Inputs = new List<CapabilityInput>
        {
            new() { Name = "cohort", Type = "string", Required = true,
                Resolution = new InputResolution { Mode = ResolutionMode.Clarify, OnMissing = ResolutionBehavior.Clarify } },
            new() { Name = "text", Type = "string", Required = true },
        },
    };

    [Fact]
    public void GenerateSpec_DoesNotRequireAnInputThatDeclaresOnMissing()
    {
        // SPEC.md §6.3 / §4.10: the service answers its absence through on_missing.
        var spec = OpenApiGenerator.GenerateSpec("test-service", new List<RestRoute>
        {
            MakeRoute(OnMissingCapability("read"), "/api/draft_get"),
            MakeRoute(OnMissingCapability("write"), "/api/draft_post"),
        });
        var paths = (Dictionary<string, object?>)spec["paths"]!;

        var get = (Dictionary<string, object?>)((Dictionary<string, object?>)paths["/api/draft_get"]!)["get"]!;
        var parameters = (List<Dictionary<string, object?>>)get["parameters"]!;
        Assert.Equal(false, parameters.Single(p => (string)p["name"]! == "cohort")["required"]);
        Assert.Equal(true, parameters.Single(p => (string)p["name"]! == "text")["required"]);

        var post = (Dictionary<string, object?>)((Dictionary<string, object?>)paths["/api/draft_post"]!)["post"]!;
        var body = (Dictionary<string, object?>)post["requestBody"]!;
        var content = (Dictionary<string, object?>)body["content"]!;
        var json = (Dictionary<string, object?>)content["application/json"]!;
        var schema = (Dictionary<string, object?>)json["schema"]!;
        Assert.Equal(new List<string> { "text" }, (List<string>)schema["required"]!);
    }

    [Fact]
    public void GenerateSpec_ContainsSecurityScheme()
    {
        var routes = new List<RestRoute>
        {
            MakeRoute(ReadCapability()),
        };

        var spec = OpenApiGenerator.GenerateSpec("test-service", routes);
        var components = (Dictionary<string, object?>)spec["components"]!;
        var securitySchemes = (Dictionary<string, object?>)components["securitySchemes"]!;

        Assert.True(securitySchemes.ContainsKey("bearer"));
    }

    // --- query values are read as the JSON value their declared type calls for ---

    private static CapabilityDeclaration TypedQueryCapability() => new()
    {
        Name = "typed",
        SideEffect = new SideEffect { Type = "read" },
        Inputs = new List<CapabilityInput>
        {
            new() { Name = "count", Type = "integer", Required = false },
            new() { Name = "ratio", Type = "number", Required = false },
            new() { Name = "flag", Type = "boolean", Required = false },
            new() { Name = "tags", Type = "array", Required = false },
            new() { Name = "filter", Type = "object", Required = false },
            new() { Name = "day", Type = "date", Required = false },
        },
    };

    [Fact]
    public void ConvertQueryParams_ReadsValuesAsTheirDeclaredJsonType()
    {
        var converted = RestRouter.ConvertQueryParams(new Dictionary<string, string>
        {
            ["count"] = "5.0", ["ratio"] = "1.5", ["flag"] = "false",
            ["tags"] = "[\"a\",\"b\"]", ["filter"] = "{\"k\":1}", ["day"] = "2026-03-10",
        }, TypedQueryCapability());

        Assert.Equal(5.0, Assert.IsType<double>(converted["count"]));
        Assert.Equal(1.5, Assert.IsType<double>(converted["ratio"]));
        Assert.Equal(false, converted["flag"]);
        Assert.Equal("array", ParameterValidation.JsonTypeOf(converted["tags"]));
        Assert.Equal("object", ParameterValidation.JsonTypeOf(converted["filter"]));
        Assert.Equal("2026-03-10", converted["day"]);
    }

    [Fact]
    public void ConvertQueryParams_LeavesAValueThatIsNotOfTheDeclaredTypeAsAString()
    {
        // Parameter validation (SPEC.md §6.3) then refuses it by name.
        var converted = RestRouter.ConvertQueryParams(new Dictionary<string, string>
        {
            ["count"] = "five", ["ratio"] = "1,5", ["flag"] = "yes", ["tags"] = "a,b", ["filter"] = "k=1",
        }, TypedQueryCapability());

        Assert.Equal("five", converted["count"]);
        Assert.Equal("1,5", converted["ratio"]);
        Assert.Equal("yes", converted["flag"]);
        Assert.Equal("a,b", converted["tags"]);
        Assert.Equal("k=1", converted["filter"]);
    }

    [Fact]
    public void GenerateSpec_NamesArrayAndObjectTypes()
    {
        var spec = OpenApiGenerator.GenerateSpec("test-service",
            new List<RestRoute> { MakeRoute(TypedQueryCapability()) });
        var paths = (Dictionary<string, object?>)spec["paths"]!;
        var get = (Dictionary<string, object?>)((Dictionary<string, object?>)paths["/api/typed"]!)["get"]!;
        var parameters = (List<Dictionary<string, object?>>)get["parameters"]!;
        string TypeOf(string name) =>
            (string)((Dictionary<string, object?>)parameters.Single(p => (string)p["name"]! == name)["schema"]!)["type"]!;

        Assert.Equal("array", TypeOf("tags"));
        Assert.Equal("object", TypeOf("filter"));
    }

    // --- OpenApiGenerator.MapType ---

    [Theory]
    [InlineData("string", "string")]
    [InlineData("integer", "integer")]
    [InlineData("number", "number")]
    [InlineData("boolean", "boolean")]
    [InlineData("date", "string")]
    [InlineData("airport_code", "string")]
    [InlineData("unknown_type", "string")]
    public void MapType_CorrectMapping(string anipType, string expected)
    {
        Assert.Equal(expected, OpenApiGenerator.MapType(anipType));
    }
}
