using System.Text;
using System.Text.Json;
using Anip.Core;
using Anip.Service;
using GraphQL;
using GraphQL.Execution;
using GraphQL.Types;

namespace Anip.GraphQL;

/// <summary>
/// Builds a graphql-dotnet schema at runtime from ANIP capabilities.
/// Query for read, Mutation for write. CamelCase field names.
/// </summary>
public static class SchemaBuilder
{
    /// <summary>
    /// Maps an ANIP type name to the corresponding GraphQL type name string (for SDL).
    /// </summary>
    public static string AnipTypeToGraphQLName(string anipType) => anipType switch
    {
        "string" or "date" or "airport_code" => "String",
        "integer" => "Int",
        "number" => "Float",
        "boolean" => "Boolean",
        _ => "JSON",
    };

    /// <summary>
    /// Maps an ANIP type name to a graphql-dotnet scalar graph type.
    /// </summary>
    private static IGraphType AnipTypeToGraphQL(string anipType) => anipType switch
    {
        "string" or "date" or "airport_code" => new StringGraphType(),
        "integer" => new IntGraphType(),
        "number" => new FloatGraphType(),
        "boolean" => new BooleanGraphType(),
        _ => new JsonGraphType(),
    };

    /// <summary>
    /// Builds an executable ISchema and SDL text from the service's capabilities.
    /// </summary>
    public static SchemaResult BuildSchema(AnipService service)
    {
        var manifest = service.GetManifest();
        var capabilities = manifest.Capabilities;

        // Sorted for deterministic output.
        var capNames = capabilities.Keys.OrderBy(k => k).ToList();

        // Shared output types.
        var financialCostType = new ObjectGraphType { Name = "FinancialCost" };
        financialCostType.Field<FloatGraphType>("amount");
        financialCostType.Field<StringGraphType>("currency");

        var costActualType = new ObjectGraphType { Name = "CostActual" };
        costActualType.AddField(new FieldType
        {
            Name = "financial",
            ResolvedType = financialCostType,
        });
        costActualType.Field<StringGraphType>("varianceFromEstimate");

        var resolutionType = new ObjectGraphType { Name = "Resolution" };
        resolutionType.Field<NonNullGraphType<StringGraphType>>("action");
        resolutionType.Field<NonNullGraphType<StringGraphType>>("recoveryClass");
        resolutionType.Field<StringGraphType>("requires");
        resolutionType.Field<StringGraphType>("grantableBy");

        var anipFailureType = new ObjectGraphType { Name = "ANIPFailure" };
        anipFailureType.Field<NonNullGraphType<StringGraphType>>("type");
        anipFailureType.Field<NonNullGraphType<StringGraphType>>("detail");
        anipFailureType.AddField(new FieldType
        {
            Name = "resolution",
            ResolvedType = resolutionType,
        });
        anipFailureType.Field<NonNullGraphType<BooleanGraphType>>("retry");

        var queryType = new ObjectGraphType { Name = "Query" };
        var mutationType = new ObjectGraphType { Name = "Mutation" };

        foreach (var name in capNames)
        {
            var decl = service.GetCapabilityDeclaration(name);
            if (decl == null) continue;

            var pascal = GraphQLResponseMapper.ToPascalCase(name);
            var camel = GraphQLResponseMapper.ToCamelCase(name);

            // Result type for this capability.
            var resultType = new ObjectGraphType { Name = pascal + "Result" };
            resultType.Field<NonNullGraphType<BooleanGraphType>>("success");
            resultType.AddField(new FieldType
            {
                Name = "result",
                ResolvedType = new JsonGraphType(),
            });
            resultType.AddField(new FieldType
            {
                Name = "costActual",
                ResolvedType = costActualType,
            });
            resultType.AddField(new FieldType
            {
                Name = "failure",
                ResolvedType = anipFailureType,
            });

            // Build the field.
            var field = new FieldType
            {
                Name = camel,
                ResolvedType = new NonNullGraphType(resultType),
                Resolver = new AnipFieldResolver(service, name),
            };

            // Build arguments from inputs.
            if (decl.Inputs != null)
            {
                var queryArgs = new QueryArguments();
                foreach (var inp in decl.Inputs)
                {
                    var argName = GraphQLResponseMapper.ToCamelCase(inp.Name);
                    var baseType = AnipTypeToGraphQL(inp.Type);
                    IGraphType argType = inp.Required
                        ? new NonNullGraphType(baseType)
                        : baseType;

                    queryArgs.Add(new QueryArgument(argType) { Name = argName });
                }
                field.Arguments = queryArgs;
            }

            var seType = decl.SideEffect?.Type ?? "";
            if (string.IsNullOrEmpty(seType) || seType == "read")
            {
                queryType.AddField(field);
            }
            else
            {
                mutationType.AddField(field);
            }
        }

        // graphql-dotnet requires a Query type; add a dummy if empty.
        if (queryType.Fields.Count() == 0)
        {
            queryType.AddField(new FieldType
            {
                Name = "_empty",
                ResolvedType = new StringGraphType(),
            });
        }

        var schema = new Schema
        {
            Query = queryType,
        };

        if (mutationType.Fields.Count() > 0)
        {
            schema.Mutation = mutationType;
        }

        var sdl = GenerateSDL(service, capNames);

        return new SchemaResult(schema, sdl);
    }

    /// <summary>
    /// Generates SDL text including custom @anip* directives.
    /// </summary>
    private static string GenerateSDL(AnipService service, List<string> capNames)
    {
        var lines = new List<string>
        {
            "directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION",
            "directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION",
            "directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION",
            "directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION",
            "",
            "scalar JSON",
            "",
            "type CostActual { financial: FinancialCost, varianceFromEstimate: String }",
            "type FinancialCost { amount: Float, currency: String }",
            "type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }",
            "type Resolution { action: String!, recoveryClass: String!, requires: String, grantableBy: String }",
            "type RestrictedCapability { capability: String!, reason: String!, reasonType: String!, grantableBy: String!, unmetTokenRequirements: [String!]!, resolutionHint: String }",
            "type DeniedCapability { capability: String!, reason: String!, reasonType: String! }",
            "",
        };

        var queries = new List<string>();
        var mutations = new List<string>();

        foreach (var name in capNames)
        {
            var decl = service.GetCapabilityDeclaration(name);
            if (decl == null) continue;

            var pascal = GraphQLResponseMapper.ToPascalCase(name);
            var camel = GraphQLResponseMapper.ToCamelCase(name);

            // Result type.
            lines.Add($"type {pascal}Result {{ success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }}");

            var argsStr = BuildSDLArgs(decl);
            var dirStr = BuildSDLDirectives(decl);

            var fieldLine = $"  {camel}{argsStr}: {pascal}Result! {dirStr}";

            var seType = decl.SideEffect?.Type ?? "";
            if (string.IsNullOrEmpty(seType) || seType == "read")
            {
                queries.Add(fieldLine);
            }
            else
            {
                mutations.Add(fieldLine);
            }
        }

        lines.Add("");
        if (queries.Count > 0)
        {
            lines.Add("type Query {");
            lines.AddRange(queries);
            lines.Add("}");
        }
        if (mutations.Count > 0)
        {
            lines.Add("type Mutation {");
            lines.AddRange(mutations);
            lines.Add("}");
        }

        return string.Join("\n", lines);
    }

    private static string BuildSDLArgs(CapabilityDeclaration decl)
    {
        if (decl.Inputs == null || decl.Inputs.Count == 0)
        {
            return "";
        }

        var args = new List<string>();
        foreach (var inp in decl.Inputs)
        {
            var argName = GraphQLResponseMapper.ToCamelCase(inp.Name);
            var gqlType = AnipTypeToGraphQLName(inp.Type);
            if (inp.Required)
            {
                gqlType += "!";
            }
            args.Add($"{argName}: {gqlType}");
        }
        return "(" + string.Join(", ", args) + ")";
    }

    private static string BuildSDLDirectives(CapabilityDeclaration decl)
    {
        var parts = new List<string>();

        // @anipSideEffect
        var seType = decl.SideEffect?.Type ?? "";
        if (string.IsNullOrEmpty(seType)) seType = "read";
        var seDir = new StringBuilder($"@anipSideEffect(type: \"{seType}\"");
        if (!string.IsNullOrEmpty(decl.SideEffect?.RollbackWindow))
        {
            seDir.Append($", rollbackWindow: \"{decl.SideEffect.RollbackWindow}\"");
        }
        seDir.Append(')');
        parts.Add(seDir.ToString());

        // @anipCost
        if (decl.Cost != null)
        {
            var certainty = decl.Cost.Certainty;
            if (string.IsNullOrEmpty(certainty)) certainty = "estimate";
            var costDir = new StringBuilder($"@anipCost(certainty: \"{certainty}\"");
            if (decl.Cost.Financial != null)
            {
                if (!string.IsNullOrEmpty(decl.Cost.Financial.Currency))
                {
                    costDir.Append($", currency: \"{decl.Cost.Financial.Currency}\"");
                }
                if (decl.Cost.Financial.RangeMin != null)
                {
                    costDir.Append($", rangeMin: {decl.Cost.Financial.RangeMin}");
                }
                if (decl.Cost.Financial.RangeMax != null)
                {
                    costDir.Append($", rangeMax: {decl.Cost.Financial.RangeMax}");
                }
            }
            costDir.Append(')');
            parts.Add(costDir.ToString());
        }

        // @anipRequires
        if (decl.Requires != null && decl.Requires.Count > 0)
        {
            var capStrs = decl.Requires.Select(r => $"\"{r.Capability}\"");
            parts.Add($"@anipRequires(capabilities: [{string.Join(", ", capStrs)}])");
        }

        // @anipScope
        if (decl.MinimumScope != null && decl.MinimumScope.Count > 0)
        {
            var scopeVals = decl.MinimumScope.Select(s => $"\"{s}\"");
            parts.Add($"@anipScope(scopes: [{string.Join(", ", scopeVals)}])");
        }

        return string.Join(" ", parts);
    }

    /// <summary>
    /// Result of building the schema: executable schema + SDL text.
    /// </summary>
    public record SchemaResult(ISchema Schema, string Sdl);
}

/// <summary>
/// A simple JSON scalar type for graphql-dotnet.
/// Passes through any object value without conversion.
/// </summary>
internal class JsonGraphType : ScalarGraphType
{
    public JsonGraphType()
    {
        Name = "JSON";
    }

    public override object? ParseLiteral(GraphQLParser.AST.GraphQLValue value) => value;
    public override object? ParseValue(object? value) => value;
    public override object? Serialize(object? value) => value;
}

/// <summary>
/// Data resolver for ANIP capability fields. Handles auth and invocation.
/// </summary>
internal class AnipFieldResolver : global::GraphQL.Resolvers.IFieldResolver
{
    private readonly AnipService _service;
    private readonly string _capName;

    public AnipFieldResolver(AnipService service, string capName)
    {
        _service = service;
        _capName = capName;
    }

    public ValueTask<object?> ResolveAsync(IResolveFieldContext context)
    {
        // Extract auth header from context.
        var authHeader = context.GetArgument<string>("__authHeader");
        // Also check user context.
        if (string.IsNullOrEmpty(authHeader))
        {
            authHeader = context.UserContext.TryGetValue("authHeader", out var ah) ? ah as string : null;
        }

        var bearer = ExtractBearer(authHeader);

        if (string.IsNullOrEmpty(bearer))
        {
            var noAuthResult = GraphQLResponseMapper.BuildGraphQLResponse(new Dictionary<string, object?>
            {
                ["success"] = false,
                ["failure"] = new Dictionary<string, object?>
                {
                    ["type"] = Constants.FailureAuthRequired,
                    ["detail"] = "Authorization header required",
                    ["resolution"] = new Dictionary<string, object?> { ["action"] = "provide_credentials", ["recovery_class"] = Constants.RecoveryClassForAction("provide_credentials") },
                    ["retry"] = true,
                },
            });
            return new ValueTask<object?>(noAuthResult);
        }

        DelegationToken token;
        try
        {
            token = GraphQLAuthBridge.ResolveAuth(bearer, _service, _capName);
        }
        catch (AnipError e)
        {
            var failure = new Dictionary<string, object?>
            {
                ["type"] = e.ErrorType,
                ["detail"] = e.Detail,
                ["retry"] = e.Retry,
            };
            if (e.Resolution != null)
            {
                failure["resolution"] = new Dictionary<string, object?>
                {
                    ["action"] = e.Resolution.Action,
                    ["recovery_class"] = !string.IsNullOrEmpty(e.Resolution.RecoveryClass)
                        ? e.Resolution.RecoveryClass
                        : Constants.RecoveryClassForAction(e.Resolution.Action),
                };
            }
            var authFailResult = GraphQLResponseMapper.BuildGraphQLResponse(new Dictionary<string, object?>
            {
                ["success"] = false,
                ["failure"] = failure,
            });
            return new ValueTask<object?>(authFailResult);
        }
        catch (Exception)
        {
            var internalFailResult = GraphQLResponseMapper.BuildGraphQLResponse(new Dictionary<string, object?>
            {
                ["success"] = false,
                ["failure"] = new Dictionary<string, object?>
                {
                    ["type"] = Constants.FailureInternalError,
                    ["detail"] = "Authentication failed",
                    ["retry"] = false,
                },
            });
            return new ValueTask<object?>(internalFailResult);
        }

        // Convert camelCase args to snake_case for ANIP invocation.
        var snakeArgs = new Dictionary<string, object?>();
        if (context.Arguments != null)
        {
            foreach (var arg in context.Arguments)
            {
                snakeArgs[GraphQLResponseMapper.ToSnakeCase(arg.Key)] = arg.Value.Value;
            }
        }

        var result = _service.Invoke(_capName, token, snakeArgs, new InvokeOpts());

        var response = GraphQLResponseMapper.BuildGraphQLResponse(result);
        return new ValueTask<object?>(response);
    }

    private static string? ExtractBearer(string? authHeader)
    {
        if (authHeader != null && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authHeader["Bearer ".Length..].Trim();
        }
        return null;
    }
}
