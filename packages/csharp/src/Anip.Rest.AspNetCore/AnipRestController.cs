using System.Text.Json;
using System.Text.Json.Serialization;
using Anip.Core;
using Anip.Rest;
using Anip.Service;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace Anip.Rest.AspNetCore;

/// <summary>
/// ASP.NET Core REST controller that dispatches to ANIP capabilities via /api/{capability}.
/// GET for read capabilities, POST for write/irreversible.
/// Also serves OpenAPI spec at /rest/openapi.json and Swagger UI at /rest/docs.
/// </summary>
[ApiController]
public class AnipRestController : ControllerBase
{
    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private readonly AnipService _service;
    private readonly List<RestRoute> _routes;
    private readonly Dictionary<string, object?> _openApiSpec;

    /// <summary>
    /// Creates the REST controller from the service and optional route overrides.
    /// </summary>
    public AnipRestController(AnipService service, Dictionary<string, RouteOverride>? overrides = null)
    {
        _service = service;
        _routes = RestRouter.GenerateRoutes(service, overrides);
        _openApiSpec = OpenApiGenerator.GenerateSpec(service.ServiceId, _routes);
    }

    // --- OpenAPI ---

    [HttpGet("/rest/openapi.json")]
    [Produces("application/json")]
    public IActionResult OpenApi()
    {
        return Ok(_openApiSpec);
    }

    // --- Swagger UI ---

    [HttpGet("/rest/docs")]
    [Produces("text/html")]
    public ContentResult Docs()
    {
        var html = """
                   <!DOCTYPE html>
                   <html><head><title>ANIP REST API</title>
                   <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
                   </head><body>
                   <div id="swagger-ui"></div>
                   <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
                   <script>SwaggerUIBundle({ url: "/rest/openapi.json", dom_id: "#swagger-ui" });</script>
                   </body></html>
                   """;
        return Content(html, "text/html");
    }

    // --- Capability dispatchers ---

    [HttpGet("/api/{capability}")]
    [Produces("application/json")]
    public IActionResult HandleGet(string capability)
    {
        return HandleRoute(capability, "GET", null);
    }

    [HttpPost("/api/{capability}")]
    [Produces("application/json")]
    public async Task<IActionResult> HandlePost(string capability)
    {
        Dictionary<string, object?>? body = null;
        try
        {
            if (Request.ContentLength is > 0)
            {
                body = await JsonSerializer.DeserializeAsync<Dictionary<string, object?>>(
                    Request.Body, s_serializerOptions);
            }
        }
        catch
        {
            // Treat invalid body as empty.
        }

        return HandleRoute(capability, "POST", body);
    }

    // --- Internal ---

    private IActionResult HandleRoute(string capability, string method,
                                       Dictionary<string, object?>? body)
    {
        // Find route.
        var route = RestRouter.FindRoute(_routes, capability);
        if (route == null)
        {
            return FailureResponse(404, Constants.FailureUnknownCapability,
                $"Capability '{capability}' not found", false);
        }

        // Extract auth.
        var authHeader = Request.Headers.Authorization.FirstOrDefault();
        var bearer = ExtractBearer(authHeader);
        if (string.IsNullOrEmpty(bearer))
        {
            var failure = new Dictionary<string, object?>
            {
                ["type"] = Constants.FailureAuthRequired,
                ["detail"] = "Authorization header with Bearer token or API key required",
                ["resolution"] = new Dictionary<string, object?>
                {
                    ["action"] = "provide_credentials",
                    ["requires"] = "Bearer token or API key",
                },
                ["retry"] = true,
            };

            var resp = new Dictionary<string, object?>
            {
                ["success"] = false,
                ["failure"] = failure,
            };
            return StatusCode(401, resp);
        }

        DelegationToken token;
        try
        {
            token = RestAuthBridge.ResolveAuth(bearer, _service, capability);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return FailureResponse(status, e.ErrorType, e.Detail, e.Retry);
        }
        catch (Exception)
        {
            return FailureResponse(500, Constants.FailureInternalError,
                "Authentication failed", false);
        }

        // Extract parameters.
        Dictionary<string, object?> parameters;
        if (method == "GET")
        {
            var rawParams = new Dictionary<string, string>();
            foreach (var (key, values) in Request.Query)
            {
                var val = values.FirstOrDefault();
                if (val != null)
                {
                    rawParams[key] = val;
                }
            }
            parameters = RestRouter.ConvertQueryParams(rawParams, route.Declaration);
        }
        else
        {
            parameters = RestRouter.ExtractBodyParams(body);
        }

        var clientRefId = Request.Headers["X-Client-Reference-Id"].FirstOrDefault();

        // Extract budget from request body (v0.14).
        Anip.Core.Budget? budget = null;
        if (body != null && body.TryGetValue("budget", out var budgetObj) && budgetObj != null)
        {
            budget = ExtractBudget(budgetObj);
        }

        var opts = new InvokeOpts
        {
            ClientReferenceId = clientRefId,
            Stream = false,
            Budget = budget,
        };

        var result = _service.Invoke(capability, token, parameters, opts);

        var success = result.TryGetValue("success", out var successObj) && successObj is true;
        if (!success)
        {
            if (result.TryGetValue("failure", out var failureObj) &&
                failureObj is Dictionary<string, object?> failureDict &&
                failureDict.TryGetValue("type", out var failTypeObj) &&
                failTypeObj is string failType)
            {
                var statusCode = Constants.FailureStatusCode(failType);
                return StatusCode(statusCode, result);
            }

            return StatusCode(400, result);
        }

        return Ok(result);
    }

    private static string? ExtractBearer(string? authHeader)
    {
        if (authHeader != null && authHeader.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authHeader["Bearer ".Length..].Trim();
        }
        return null;
    }

    private ObjectResult FailureResponse(int status, string type, string detail, bool retry)
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = type,
            ["detail"] = detail,
            ["retry"] = retry,
        };

        var resp = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = failure,
        };
        return StatusCode(status, resp);
    }

    private static Anip.Core.Budget? ExtractBudget(object? budgetObj)
    {
        if (budgetObj is JsonElement je && je.ValueKind == JsonValueKind.Object)
        {
            var currency = je.TryGetProperty("currency", out var currProp) && currProp.ValueKind == JsonValueKind.String
                ? currProp.GetString() : null;
            var maxAmount = je.TryGetProperty("max_amount", out var amtProp) && amtProp.ValueKind == JsonValueKind.Number
                ? amtProp.GetDouble() : 0.0;
            if (!string.IsNullOrEmpty(currency) && maxAmount > 0)
            {
                return new Anip.Core.Budget { Currency = currency, MaxAmount = maxAmount };
            }
        }
        else if (budgetObj is Dictionary<string, object?> dict)
        {
            var currency = dict.TryGetValue("currency", out var currVal) ? currVal?.ToString() : null;
            double maxAmount = 0;
            if (dict.TryGetValue("max_amount", out var amtVal))
            {
                if (amtVal is double d) maxAmount = d;
                else if (amtVal is int i) maxAmount = i;
                else if (amtVal is long l) maxAmount = l;
            }
            if (!string.IsNullOrEmpty(currency) && maxAmount > 0)
            {
                return new Anip.Core.Budget { Currency = currency, MaxAmount = maxAmount };
            }
        }
        return null;
    }

    /// <summary>
    /// Returns generated routes (for testing).
    /// </summary>
    [Microsoft.AspNetCore.Mvc.NonAction]
    public List<RestRoute> GetRoutes() => _routes;
}
