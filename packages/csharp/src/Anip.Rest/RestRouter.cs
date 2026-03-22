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

            switch (inputType)
            {
                case "integer":
                    result[key] = int.TryParse(value, out var intVal) ? intVal : value;
                    break;
                case "number":
                    result[key] = double.TryParse(value, out var dblVal) ? dblVal : value;
                    break;
                case "boolean":
                    result[key] = value == "true";
                    break;
                default:
                    result[key] = value;
                    break;
            }
        }

        return result;
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
