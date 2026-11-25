using Anip.Core;
using Anip.Service;

namespace Anip.Rest;

/// <summary>
/// Shared route generation and parameter conversion for the REST interface.
/// Framework-agnostic — used by both ASP.NET Core and other adapters.
///
/// Note: RouteOverride paths and methods affect OpenAPI metadata only.
/// HTTP routing always uses /api/{capability} dispatched by capability name.
/// </summary>
public static class RestRouter
{
    public static List<RestRoute> GenerateRoutes(AnipService service,
                                                  Dictionary<string, RouteOverride>? overrides)
    {
        var routes = new List<RestRoute>();
        var manifest = service.GetManifest();

        foreach (var (name, decl) in manifest.Capabilities)
        {
            var path = "/api/" + name;
            var method = "POST";
            if (decl.SideEffect != null && decl.SideEffect.Type == "read")
            {
                method = "GET";
            }

            if (overrides != null && overrides.TryGetValue(name, out var ov))
            {
                if (!string.IsNullOrEmpty(ov.Path))
                {
                    path = ov.Path;
                }
                if (!string.IsNullOrEmpty(ov.Method))
                {
                    method = ov.Method;
                }
            }

            routes.Add(new RestRoute(name, path, method, decl));
        }

        return routes;
    }

    public static RestRoute? FindRoute(List<RestRoute> routes, string capabilityName)
    {
        foreach (var r in routes)
        {
            if (r.CapabilityName == capabilityName)
            {
                return r;
            }
        }
        return null;
    }

    public static Dictionary<string, object?> ConvertQueryParams(
        Dictionary<string, string> rawParams, CapabilityDeclaration decl)
    {
        var typeMap = new Dictionary<string, string>();
        if (decl.Inputs != null)
        {
            foreach (var inp in decl.Inputs)
            {
                typeMap[inp.Name] = inp.Type;
            }
        }

        var result = new Dictionary<string, object?>();
        foreach (var (key, value) in rawParams)
        {
            if (string.IsNullOrEmpty(value)) continue;

            var inputType = typeMap.TryGetValue(key, out var t) ? t : "string";

            result[key] = ConvertQueryValue(value, inputType);
        }

        return result;
    }

    // The JSON number grammar (RFC 8259 §6).
    private static readonly System.Text.RegularExpressions.Regex s_jsonNumber =
        new(@"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$");

    /// <summary>
    /// Reads a query string value as the JSON value its declared type calls
    /// for: a JSON number for integer and number, true or false for boolean,
    /// JSON text for array and object (the only way a query string can carry
    /// one). A value that cannot be read that way stays a string, and the
    /// service's parameter validation (SPEC.md §6.3) refuses it by name.
    /// </summary>
    private static object? ConvertQueryValue(string value, string declaredType)
    {
        switch (declaredType)
        {
            case "integer":
            case "number":
                if (declaredType == "integer" &&
                    int.TryParse(value, System.Globalization.NumberStyles.AllowLeadingSign,
                        System.Globalization.CultureInfo.InvariantCulture, out var intValue))
                {
                    return intValue;
                }
                if (s_jsonNumber.IsMatch(value) &&
                    double.TryParse(value, System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out var number))
                {
                    return number;
                }
                return value;
            case "boolean":
                return value switch { "true" => true, "false" => false, _ => value };
            case "array":
            case "object":
                try
                {
                    var element = System.Text.Json.JsonDocument.Parse(value).RootElement.Clone();
                    var kind = declaredType == "array"
                        ? System.Text.Json.JsonValueKind.Array
                        : System.Text.Json.JsonValueKind.Object;
                    return element.ValueKind == kind ? element : value;
                }
                catch (System.Text.Json.JsonException)
                {
                    return value;
                }
            default:
                return value;
        }
    }

    public static Dictionary<string, object?> ExtractBodyParams(Dictionary<string, object?>? body)
    {
        if (body == null) return new Dictionary<string, object?>();

        if (body.TryGetValue("parameters", out var p) && p is Dictionary<string, object?> paramDict)
        {
            return paramDict;
        }

        var result = new Dictionary<string, object?>(body);
        result.Remove("parameters");
        return result;
    }
}
