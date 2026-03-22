using Anip.Core;
using Anip.Rest;

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
