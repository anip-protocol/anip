using Anip.Core;
using Anip.GraphQL;
using Anip.Service;

namespace Anip.GraphQL.Tests;

public class GraphQLTests
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
            new() { Name = "destination", Type = "string", Required = false, Description = "Destination airport" },
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

    private static AnipService CreateTestService()
    {
        var service = new AnipService(new ServiceConfig
        {
            ServiceId = "test-graphql-service",
            Capabilities = new List<CapabilityDef>
            {
                new(ReadCapability(), (ctx, p) => new Dictionary<string, object?>
                {
                    ["flights"] = new List<object> { "FL-1", "FL-2" },
                }),
                new(WriteCapability(), (ctx, p) => new Dictionary<string, object?>
                {
                    ["confirmation"] = "BOOK-123",
                }),
            },
            Storage = ":memory:",
            RetentionIntervalSeconds = -1,
            Authenticate = bearer => bearer == "test-api-key" ? "test-user" : null,
        });
        service.Start();
        return service;
    }

    // --- Schema building ---

    [Fact]
    public void BuildSchema_ReturnsSchemaAndSdl()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.NotNull(result.Schema);
        Assert.NotNull(result.Sdl);
        Assert.True(result.Sdl.Length > 0);
    }

    [Fact]
    public void BuildSchema_QueryContainsReadCapability()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        var queryType = result.Schema.Query;
        Assert.NotNull(queryType);

        // getFlights should be a query field (read side effect).
        var field = queryType.Fields.FirstOrDefault(f => f.Name == "getFlights");
        Assert.NotNull(field);
    }

    [Fact]
    public void BuildSchema_MutationContainsWriteCapability()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        var mutationType = result.Schema.Mutation;
        Assert.NotNull(mutationType);

        // bookFlight should be a mutation field (irreversible side effect).
        var field = mutationType.Fields.FirstOrDefault(f => f.Name == "bookFlight");
        Assert.NotNull(field);
    }

    [Fact]
    public void BuildSchema_FieldHasArguments()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        var field = result.Schema.Query.Fields.First(f => f.Name == "getFlights");
        Assert.NotNull(field.Arguments);
        Assert.True(field.Arguments.Count > 0);

        // Check that the required "origin" arg exists.
        var originArg = field.Arguments.FirstOrDefault(a => a.Name == "origin");
        Assert.NotNull(originArg);
    }

    // --- SDL generation ---

    [Fact]
    public void SDL_ContainsQueryType()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("type Query {", result.Sdl);
        Assert.Contains("getFlights", result.Sdl);
    }

    [Fact]
    public void SDL_ContainsMutationType()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("type Mutation {", result.Sdl);
        Assert.Contains("bookFlight", result.Sdl);
    }

    [Fact]
    public void SDL_ContainsDirectives()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("directive @anipSideEffect", result.Sdl);
        Assert.Contains("directive @anipCost", result.Sdl);
        Assert.Contains("directive @anipRequires", result.Sdl);
        Assert.Contains("directive @anipScope", result.Sdl);
    }

    [Fact]
    public void SDL_ContainsSharedTypes()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("type ANIPFailure", result.Sdl);
        Assert.Contains("type CostActual", result.Sdl);
        Assert.Contains("type FinancialCost", result.Sdl);
        Assert.Contains("type Resolution", result.Sdl);
        Assert.Contains("scalar JSON", result.Sdl);
    }

    [Fact]
    public void SDL_ContainsResultTypes()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("type GetFlightsResult", result.Sdl);
        Assert.Contains("type BookFlightResult", result.Sdl);
    }

    [Fact]
    public void SDL_ContainsSideEffectDirective()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("@anipSideEffect(type: \"read\")", result.Sdl);
        Assert.Contains("@anipSideEffect(type: \"irreversible\")", result.Sdl);
    }

    [Fact]
    public void SDL_ContainsScopeDirective()
    {
        using var service = CreateTestService();
        var result = SchemaBuilder.BuildSchema(service);

        Assert.Contains("@anipScope(scopes: [\"flights.search\"])", result.Sdl);
        Assert.Contains("@anipScope(scopes: [\"flights.book\"])", result.Sdl);
    }

    // --- Case conversion ---

    [Theory]
    [InlineData("cost_actual", "costActual")]
    [InlineData("get_flights", "getFlights")]
    [InlineData("simple", "simple")]
    [InlineData("a_b_c", "aBC")]
    [InlineData("", "")]
    public void ToCamelCase_ConvertsCorrectly(string input, string expected)
    {
        Assert.Equal(expected, GraphQLResponseMapper.ToCamelCase(input));
    }

    [Theory]
    [InlineData("costActual", "cost_actual")]
    [InlineData("searchFlights", "search_flights")]
    [InlineData("simple", "simple")]
    [InlineData("ABC", "a_b_c")]
    [InlineData("", "")]
    public void ToSnakeCase_ConvertsCorrectly(string input, string expected)
    {
        Assert.Equal(expected, GraphQLResponseMapper.ToSnakeCase(input));
    }

    [Theory]
    [InlineData("cost_actual", "CostActual")]
    [InlineData("get_flights", "GetFlights")]
    [InlineData("simple", "Simple")]
    [InlineData("", "")]
    public void ToPascalCase_ConvertsCorrectly(string input, string expected)
    {
        Assert.Equal(expected, GraphQLResponseMapper.ToPascalCase(input));
    }

    [Fact]
    public void ToCamelCase_NullReturnsNull()
    {
        Assert.Null(GraphQLResponseMapper.ToCamelCase(null!));
    }

    [Fact]
    public void ToSnakeCase_NullReturnsNull()
    {
        Assert.Null(GraphQLResponseMapper.ToSnakeCase(null!));
    }

    [Fact]
    public void ToPascalCase_NullReturnsNull()
    {
        Assert.Null(GraphQLResponseMapper.ToPascalCase(null!));
    }

    // --- Response mapping ---

    [Fact]
    public void BuildGraphQLResponse_SuccessResult()
    {
        var result = new Dictionary<string, object?>
        {
            ["success"] = true,
            ["result"] = new Dictionary<string, object?> { ["data"] = "test" },
        };

        var mapped = GraphQLResponseMapper.BuildGraphQLResponse(result);

        Assert.Equal(true, mapped["success"]);
        Assert.NotNull(mapped["result"]);
        Assert.Null(mapped["costActual"]);
        Assert.Null(mapped["failure"]);
    }

    [Fact]
    public void BuildGraphQLResponse_FailureResult()
    {
        var result = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = new Dictionary<string, object?>
            {
                ["type"] = "auth_required",
                ["detail"] = "No token",
                ["retry"] = true,
                ["resolution"] = new Dictionary<string, object?>
                {
                    ["action"] = "provide_credentials",
                    ["grantable_by"] = "admin",
                },
            },
        };

        var mapped = GraphQLResponseMapper.BuildGraphQLResponse(result);

        Assert.Equal(false, mapped["success"]);
        Assert.Null(mapped["result"]);

        var failure = mapped["failure"] as Dictionary<string, object?>;
        Assert.NotNull(failure);
        Assert.Equal("auth_required", failure!["type"]);
        Assert.Equal("No token", failure["detail"]);
        Assert.Equal(true, failure["retry"]);

        var resolution = failure["resolution"] as Dictionary<string, object?>;
        Assert.NotNull(resolution);
        Assert.Equal("provide_credentials", resolution!["action"]);
        Assert.Equal("admin", resolution["grantableBy"]);
    }

    [Fact]
    public void BuildGraphQLResponse_CostActualMapping()
    {
        var result = new Dictionary<string, object?>
        {
            ["success"] = true,
            ["result"] = null,
            ["cost_actual"] = new Dictionary<string, object?>
            {
                ["financial"] = new Dictionary<string, object?> { ["amount"] = 10.5, ["currency"] = "USD" },
                ["variance_from_estimate"] = "within_range",
            },
        };

        var mapped = GraphQLResponseMapper.BuildGraphQLResponse(result);

        var costActual = mapped["costActual"] as Dictionary<string, object?>;
        Assert.NotNull(costActual);
        Assert.NotNull(costActual!["financial"]);
        Assert.Equal("within_range", costActual["varianceFromEstimate"]);
    }

    // --- Auth bridge ---

    [Fact]
    public void AuthBridge_ApiKeyResolves()
    {
        using var service = CreateTestService();

        // The API key "test-api-key" resolves to principal "test-user".
        var token = GraphQLAuthBridge.ResolveAuth("test-api-key", service, "get_flights");

        Assert.NotNull(token);
        Assert.Equal("adapter:anip-graphql", token.Subject);
    }

    [Fact]
    public void AuthBridge_InvalidBearerThrows()
    {
        using var service = CreateTestService();

        Assert.Throws<AnipError>(() =>
            GraphQLAuthBridge.ResolveAuth("invalid-token", service, "get_flights"));
    }

    // --- Type mapping ---

    [Theory]
    [InlineData("string", "String")]
    [InlineData("date", "String")]
    [InlineData("airport_code", "String")]
    [InlineData("integer", "Int")]
    [InlineData("number", "Float")]
    [InlineData("boolean", "Boolean")]
    [InlineData("unknown_type", "JSON")]
    public void AnipTypeToGraphQLName_CorrectMapping(string anipType, string expected)
    {
        Assert.Equal(expected, SchemaBuilder.AnipTypeToGraphQLName(anipType));
    }
}
