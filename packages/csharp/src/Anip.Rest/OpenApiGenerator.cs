using Anip.Core;

namespace Anip.Rest;

/// <summary>
/// Generates an OpenAPI 3.1 specification from ANIP capabilities.
/// </summary>
public static class OpenApiGenerator
{
    private static readonly Dictionary<string, string> TypeMap = new()
    {
        ["string"] = "string",
        ["integer"] = "integer",
        ["number"] = "number",
        ["boolean"] = "boolean",
        ["date"] = "string",
        ["airport_code"] = "string",
    };

    /// <summary>
    /// Maps an ANIP input type to an OpenAPI type.
    /// </summary>
    public static string MapType(string anipType)
    {
        return TypeMap.TryGetValue(anipType, out var mapped) ? mapped : "string";
    }

    /// <summary>
    /// Generates a full OpenAPI 3.1 spec from the given routes.
    /// </summary>
    public static Dictionary<string, object?> GenerateSpec(string serviceId, List<RestRoute> routes)
    {
        var paths = new Dictionary<string, object?>();

        foreach (var route in routes)
        {
            var method = route.Method.ToLowerInvariant();
            var decl = route.Declaration;

            var seType = decl.SideEffect?.Type ?? "";
            if (string.IsNullOrEmpty(seType))
            {
                seType = "read";
            }

            var minScope = decl.MinimumScope ?? new List<string>();

            var financial = decl.Cost?.Financial != null;

            var operation = new Dictionary<string, object?>
            {
                ["summary"] = decl.Description,
                ["operationId"] = route.CapabilityName,
            };

            var responses = new Dictionary<string, object?>
            {
                ["200"] = new Dictionary<string, object?>
                {
                    ["description"] = "Success",
                    ["content"] = new Dictionary<string, object?>
                    {
                        ["application/json"] = new Dictionary<string, object?>
                        {
                            ["schema"] = new Dictionary<string, object?>
                            {
                                ["$ref"] = "#/components/schemas/ANIPResponse",
                            },
                        },
                    },
                },
                ["401"] = new Dictionary<string, object?> { ["description"] = "Authentication required" },
                ["403"] = new Dictionary<string, object?> { ["description"] = "Authorization failed" },
                ["404"] = new Dictionary<string, object?> { ["description"] = "Unknown capability" },
            };
            operation["responses"] = responses;

            operation["x-anip-side-effect"] = seType;
            operation["x-anip-minimum-scope"] = minScope;
            operation["x-anip-financial"] = financial;

            if (method == "get")
            {
                operation["parameters"] = BuildQueryParameters(decl);
            }
            else
            {
                operation["requestBody"] = BuildRequestBody(decl);
            }

            paths[route.Path] = new Dictionary<string, object?> { [method] = operation };
        }

        var spec = new Dictionary<string, object?>
        {
            ["openapi"] = "3.1.0",
            ["info"] = new Dictionary<string, object?>
            {
                ["title"] = "ANIP REST \u2014 " + serviceId,
                ["version"] = "1.0",
            },
            ["paths"] = paths,
        };

        var schemas = new Dictionary<string, object?>
        {
            ["ANIPResponse"] = new Dictionary<string, object?>
            {
                ["type"] = "object",
                ["properties"] = new Dictionary<string, object?>
                {
                    ["success"] = new Dictionary<string, object?> { ["type"] = "boolean" },
                    ["result"] = new Dictionary<string, object?> { ["type"] = "object" },
                    ["invocation_id"] = new Dictionary<string, object?> { ["type"] = "string" },
                    ["failure"] = new Dictionary<string, object?>
                    {
                        ["$ref"] = "#/components/schemas/ANIPFailure",
                    },
                },
            },
            ["ANIPFailure"] = new Dictionary<string, object?>
            {
                ["type"] = "object",
                ["properties"] = new Dictionary<string, object?>
                {
                    ["type"] = new Dictionary<string, object?> { ["type"] = "string" },
                    ["detail"] = new Dictionary<string, object?> { ["type"] = "string" },
                    ["resolution"] = new Dictionary<string, object?> { ["type"] = "object" },
                    ["retry"] = new Dictionary<string, object?> { ["type"] = "boolean" },
                },
            },
        };

        var components = new Dictionary<string, object?>
        {
            ["schemas"] = schemas,
            ["securitySchemes"] = new Dictionary<string, object?>
            {
                ["bearer"] = new Dictionary<string, object?>
                {
                    ["type"] = "http",
                    ["scheme"] = "bearer",
                    ["bearerFormat"] = "JWT",
                },
            },
        };

        spec["components"] = components;
        spec["security"] = new List<object>
        {
            new Dictionary<string, object?> { ["bearer"] = new List<string>() },
        };

        return spec;
    }

    private static List<Dictionary<string, object?>> BuildQueryParameters(CapabilityDeclaration decl)
    {
        var parameters = new List<Dictionary<string, object?>>();
        if (decl.Inputs == null) return parameters;

        foreach (var inp in decl.Inputs)
        {
            var schema = new Dictionary<string, object?>
            {
                ["type"] = MapType(inp.Type),
            };
            if (inp.Type == "date")
            {
                schema["format"] = "date";
            }
            if (inp.Default != null)
            {
                schema["default"] = inp.Default;
            }

            var param = new Dictionary<string, object?>
            {
                ["name"] = inp.Name,
                ["in"] = "query",
                ["required"] = inp.Required,
                ["schema"] = schema,
                ["description"] = inp.Description,
            };
            parameters.Add(param);
        }

        return parameters;
    }

    private static Dictionary<string, object?> BuildRequestBody(CapabilityDeclaration decl)
    {
        var properties = new Dictionary<string, object?>();
        var required = new List<string>();

        if (decl.Inputs != null)
        {
            foreach (var inp in decl.Inputs)
            {
                var prop = new Dictionary<string, object?>
                {
                    ["type"] = MapType(inp.Type),
                    ["description"] = inp.Description,
                };
                if (inp.Type == "date")
                {
                    prop["format"] = "date";
                }
                properties[inp.Name] = prop;
                if (inp.Required)
                {
                    required.Add(inp.Name);
                }
            }
        }

        var schema = new Dictionary<string, object?>
        {
            ["type"] = "object",
            ["properties"] = properties,
        };
        if (required.Count > 0)
        {
            schema["required"] = required;
        }

        return new Dictionary<string, object?>
        {
            ["required"] = true,
            ["content"] = new Dictionary<string, object?>
            {
                ["application/json"] = new Dictionary<string, object?>
                {
                    ["schema"] = schema,
                },
            },
        };
    }
}
