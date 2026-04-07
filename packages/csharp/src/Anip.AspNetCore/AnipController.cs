using System.Text.Json;
using System.Text.Json.Serialization;
using Anip.Core;
using Anip.Service;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace Anip.AspNetCore;

/// <summary>
/// ASP.NET Core controller implementing all 9 ANIP protocol routes plus health.
/// </summary>
[ApiController]
public class AnipController : ControllerBase
{
    private static readonly JsonSerializerOptions s_serializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private readonly AnipService _service;
    private readonly bool _healthEnabled;

    public AnipController(AnipService service, AnipOptions options)
    {
        _service = service;
        _healthEnabled = options.HealthEndpoint;
    }

    // --- 1. Discovery (no auth) ---

    [HttpGet("/.well-known/anip")]
    public IActionResult Discovery()
    {
        var baseUrl = DeriveBaseUrl();
        var doc = _service.GetDiscovery(baseUrl);
        return Ok(doc);
    }

    // --- 2. JWKS (no auth) ---

    [HttpGet("/.well-known/jwks.json")]
    public IActionResult Jwks()
    {
        var jwks = _service.GetJwks();
        return Ok(jwks);
    }

    // --- 3. Manifest (no auth) ---

    [HttpGet("/anip/manifest")]
    public IActionResult Manifest()
    {
        var signed = _service.GetSignedManifest();
        Response.Headers["X-ANIP-Signature"] = signed.Signature;
        return File(signed.ManifestJson, "application/json");
    }

    // --- 4. Token issuance (bootstrap auth only) ---

    [HttpPost("/anip/tokens")]
    public IActionResult IssueToken([FromBody] TokenRequest request)
    {
        var bearer = ExtractBearer();
        if (string.IsNullOrEmpty(bearer))
        {
            return AuthRequiredResponse();
        }

        var principal = _service.AuthenticateBearer(bearer);
        if (principal == null)
        {
            return FailureResponse(401, Constants.FailureInvalidToken,
                "Invalid bootstrap credential", true);
        }

        try
        {
            var resp = _service.IssueToken(principal, request);
            return Ok(resp);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return AnipErrorResponse(status, e);
        }
        catch (Exception)
        {
            return FailureResponse(500, Constants.FailureInternalError,
                "Token issuance failed", false);
        }
    }

    // --- 5. Permissions (JWT auth) ---

    [HttpPost("/anip/permissions")]
    public IActionResult Permissions()
    {
        var (token, errorResult) = ResolveJwtAuth();
        if (token == null) return errorResult!;

        var resp = _service.DiscoverPermissions(token);
        return Ok(resp);
    }

    // --- 6. Invoke (JWT auth) ---

    [HttpPost("/anip/invoke/{capability}")]
    public async Task<IActionResult> Invoke(string capability)
    {
        var (token, errorResult) = ResolveJwtAuth();
        if (token == null) return errorResult!;

        Dictionary<string, object?>? body;
        try
        {
            body = await JsonSerializer.DeserializeAsync<Dictionary<string, object?>>(
                Request.Body, s_serializerOptions);
        }
        catch
        {
            return FailureResponse(400, Constants.FailureInternalError,
                "Invalid request body", false);
        }

        body ??= new Dictionary<string, object?>();

        // Extract parameters: prefer "parameters" wrapper, fall back to body itself.
        Dictionary<string, object?> parameters;
        if (body.TryGetValue("parameters", out var parametersObj) &&
            parametersObj is JsonElement parametersElement &&
            parametersElement.ValueKind == JsonValueKind.Object)
        {
            parameters = JsonSerializer.Deserialize<Dictionary<string, object?>>(
                parametersElement.GetRawText(), s_serializerOptions) ?? new();
        }
        else
        {
            parameters = new Dictionary<string, object?>(body);
            parameters.Remove("stream");
            parameters.Remove("client_reference_id");
            parameters.Remove("task_id");
            parameters.Remove("parent_invocation_id");
            parameters.Remove("upstream_service");
        }

        // Check for streaming.
        var stream = false;
        if (body.TryGetValue("stream", out var streamObj))
        {
            if (streamObj is JsonElement streamEl)
            {
                stream = streamEl.ValueKind == JsonValueKind.True;
            }
            else if (streamObj is bool streamBool)
            {
                stream = streamBool;
            }
        }

        // Extract client reference ID.
        string? clientRefId = null;
        if (body.TryGetValue("client_reference_id", out var cridObj))
        {
            if (cridObj is JsonElement cridEl && cridEl.ValueKind == JsonValueKind.String)
            {
                clientRefId = cridEl.GetString();
            }
            else if (cridObj is string cridStr)
            {
                clientRefId = cridStr;
            }
        }
        clientRefId ??= Request.Headers["X-Client-Reference-Id"].FirstOrDefault();

        // Extract task_id.
        string? taskId = null;
        if (body.TryGetValue("task_id", out var taskIdObj))
        {
            if (taskIdObj is JsonElement taskIdEl && taskIdEl.ValueKind == JsonValueKind.String)
            {
                taskId = taskIdEl.GetString();
            }
            else if (taskIdObj is string taskIdStr)
            {
                taskId = taskIdStr;
            }
        }

        // Extract parent_invocation_id.
        string? parentInvocationId = null;
        if (body.TryGetValue("parent_invocation_id", out var pidObj))
        {
            if (pidObj is JsonElement pidEl && pidEl.ValueKind == JsonValueKind.String)
            {
                parentInvocationId = pidEl.GetString();
            }
            else if (pidObj is string pidStr)
            {
                parentInvocationId = pidStr;
            }
        }

        // Extract upstream_service.
        string? upstreamService = null;
        if (body.TryGetValue("upstream_service", out var usObj))
        {
            if (usObj is JsonElement usEl && usEl.ValueKind == JsonValueKind.String)
            {
                upstreamService = usEl.GetString();
            }
            else if (usObj is string usStr)
            {
                upstreamService = usStr;
            }
        }

        if (stream)
        {
            return await HandleStreamInvoke(capability, token, parameters, clientRefId, taskId, parentInvocationId, upstreamService);
        }

        var opts = new InvokeOpts
        {
            ClientReferenceId = clientRefId,
            TaskId = taskId,
            ParentInvocationId = parentInvocationId,
            UpstreamService = upstreamService,
            Stream = false,
        };

        var result = _service.Invoke(capability, token, parameters, opts);

        // Determine HTTP status from the result.
        var success = result.TryGetValue("success", out var successObj) && successObj is true;
        if (!success)
        {
            if (result.TryGetValue("failure", out var failureObj) &&
                failureObj is Dictionary<string, object?> failure &&
                failure.TryGetValue("type", out var failTypeObj) &&
                failTypeObj is string failType)
            {
                var statusCode = Constants.FailureStatusCode(failType);
                return StatusCode(statusCode, result);
            }

            return StatusCode(400, result);
        }

        return Ok(result);
    }

    // --- 7. Audit (JWT auth) ---

    [HttpPost("/anip/audit")]
    public async Task<IActionResult> Audit()
    {
        var (token, errorResult) = ResolveJwtAuth();
        if (token == null) return errorResult!;

        try
        {
            // Parse body (may be empty).
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
                // Empty or invalid body is OK — filters come from query params too.
            }

            var filters = new AuditFilters();

            // Read from body first.
            if (body != null)
            {
                filters.Capability = GetStringFromBody(body, "capability");
                filters.Since = GetStringFromBody(body, "since");
                filters.InvocationId = GetStringFromBody(body, "invocation_id");
                filters.ClientReferenceId = GetStringFromBody(body, "client_reference_id");
                filters.TaskId = GetStringFromBody(body, "task_id");
                filters.ParentInvocationId = GetStringFromBody(body, "parent_invocation_id");

                if (body.TryGetValue("limit", out var limitObj))
                {
                    if (limitObj is JsonElement limitEl && limitEl.TryGetInt32(out var limitVal))
                    {
                        filters.Limit = limitVal;
                    }
                    else if (limitObj is int limitInt)
                    {
                        filters.Limit = limitInt;
                    }
                }
            }

            // Default limit.
            if (filters.Limit <= 0) filters.Limit = 50;

            // Query params override body.
            var qCapability = Request.Query["capability"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qCapability)) filters.Capability = qCapability;

            var qSince = Request.Query["since"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qSince)) filters.Since = qSince;

            var qInvocationId = Request.Query["invocation_id"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qInvocationId)) filters.InvocationId = qInvocationId;

            var qClientReferenceId = Request.Query["client_reference_id"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qClientReferenceId)) filters.ClientReferenceId = qClientReferenceId;

            var qTaskId = Request.Query["task_id"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qTaskId)) filters.TaskId = qTaskId;

            var qParentInvocationId = Request.Query["parent_invocation_id"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qParentInvocationId)) filters.ParentInvocationId = qParentInvocationId;

            var qLimit = Request.Query["limit"].FirstOrDefault();
            if (!string.IsNullOrEmpty(qLimit) && int.TryParse(qLimit, out var parsedLimit))
            {
                filters.Limit = parsedLimit;
            }

            var resp = _service.QueryAudit(token, filters);
            return Ok(resp);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return AnipErrorResponse(status, e);
        }
        catch (Exception)
        {
            return FailureResponse(500, Constants.FailureInternalError,
                "Audit query failed", false);
        }
    }

    // --- Graph (no auth) ---

    [HttpGet("/anip/graph/{capability}")]
    public IActionResult Graph(string capability)
    {
        var graph = _service.GetCapabilityGraph(capability);
        if (graph == null)
        {
            return FailureResponse(404, Constants.FailureNotFound,
                $"Capability '{capability}' not found", false);
        }
        return Ok(graph);
    }

    // --- 8. List Checkpoints (no auth) ---

    [HttpGet("/anip/checkpoints")]
    public IActionResult ListCheckpoints([FromQuery] int limit = 50)
    {
        try
        {
            var resp = _service.ListCheckpoints(limit);
            return Ok(resp);
        }
        catch (Exception)
        {
            return FailureResponse(500, Constants.FailureInternalError,
                "Failed to list checkpoints", false);
        }
    }

    // --- 9. Get Checkpoint (no auth) ---

    [HttpGet("/anip/checkpoints/{id}")]
    public IActionResult GetCheckpoint(
        string id,
        [FromQuery(Name = "include_proof")] bool includeProof = false,
        [FromQuery(Name = "leaf_index")] int leafIndex = 0)
    {
        try
        {
            var resp = _service.GetCheckpoint(id, includeProof, leafIndex);
            return Ok(resp);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return AnipErrorResponse(status, e);
        }
        catch (Exception)
        {
            return FailureResponse(500, Constants.FailureInternalError,
                "Failed to get checkpoint", false);
        }
    }

    // --- 10. Health (optional, no auth) ---

    [HttpGet("/-/health")]
    public IActionResult Health()
    {
        if (!_healthEnabled)
        {
            return NotFound();
        }

        var report = _service.GetHealth();
        return Ok(report);
    }

    // --- SSE streaming ---

    private async Task<IActionResult> HandleStreamInvoke(
        string capability,
        DelegationToken token,
        Dictionary<string, object?> parameters,
        string? clientRefId,
        string? taskId,
        string? parentInvocationId,
        string? upstreamService)
    {
        StreamResult sr;
        try
        {
            var opts = new InvokeOpts
            {
                ClientReferenceId = clientRefId,
                TaskId = taskId,
                ParentInvocationId = parentInvocationId,
                UpstreamService = upstreamService,
                Stream = true,
            };
            sr = _service.InvokeStream(capability, token, parameters, opts);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return AnipErrorResponse(status, e);
        }

        Response.ContentType = "text/event-stream";
        Response.Headers.CacheControl = "no-cache";
        Response.Headers.Connection = "keep-alive";
        await Response.Body.FlushAsync();

        try
        {
            while (await sr.Events.WaitToReadAsync())
            {
                while (sr.Events.TryRead(out var evt))
                {
                    var data = JsonSerializer.Serialize(evt.Payload, s_serializerOptions);
                    var sseMessage = $"event: {evt.Type}\ndata: {data}\n\n";
                    await Response.WriteAsync(sseMessage);
                    await Response.Body.FlushAsync();
                }
            }
        }
        catch (Exception)
        {
            sr.Cancel();
        }

        // Return empty result since we wrote directly to the response.
        return new EmptyResult();
    }

    // --- Auth helpers ---

    private string? ExtractBearer()
    {
        var auth = Request.Headers.Authorization.FirstOrDefault();
        if (auth != null && auth.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return auth["Bearer ".Length..].Trim();
        }
        return null;
    }

    private (DelegationToken? token, IActionResult? error) ResolveJwtAuth()
    {
        var bearer = ExtractBearer();
        if (string.IsNullOrEmpty(bearer))
        {
            return (null, AuthRequiredResponse());
        }

        try
        {
            var token = _service.ResolveBearerToken(bearer);
            return (token, null);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return (null, AnipErrorResponse(status, e));
        }
        catch (Exception)
        {
            return (null, FailureResponse(401, Constants.FailureInvalidToken,
                "Invalid bearer token", false));
        }
    }

    // --- Response helpers ---

    private string DeriveBaseUrl()
    {
        var scheme = Request.Scheme;

        var forwardedProto = Request.Headers["X-Forwarded-Proto"].FirstOrDefault();
        if (!string.IsNullOrEmpty(forwardedProto))
        {
            scheme = forwardedProto;
        }

        return $"{scheme}://{Request.Host}";
    }

    private ObjectResult AuthRequiredResponse()
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = Constants.FailureAuthRequired,
            ["detail"] = "Authorization header with Bearer token required",
            ["resolution"] = new Dictionary<string, object?>
            {
                ["action"] = "provide_credentials",
                ["recovery_class"] = Constants.RecoveryClassForAction("provide_credentials"),
                ["requires"] = "Bearer token",
            },
            ["retry"] = true,
        };

        var body = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = failure,
        };

        return StatusCode(401, body);
    }

    private ObjectResult FailureResponse(int statusCode, string type, string detail, bool retry)
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = type,
            ["detail"] = detail,
            ["resolution"] = DefaultResolution(type),
            ["retry"] = retry,
        };

        var body = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = failure,
        };

        return StatusCode(statusCode, body);
    }

    private ObjectResult AnipErrorResponse(int statusCode, AnipError e)
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = e.ErrorType,
            ["detail"] = e.Detail,
            ["retry"] = e.Retry,
        };

        if (e.Resolution != null)
        {
            var res = new Dictionary<string, object?>
            {
                ["action"] = e.Resolution.Action,
                ["recovery_class"] = e.Resolution.RecoveryClass,
            };
            if (e.Resolution.Requires != null)
                res["requires"] = e.Resolution.Requires;
            if (e.Resolution.GrantableBy != null)
                res["grantable_by"] = e.Resolution.GrantableBy;

            failure["resolution"] = res;
        }
        else
        {
            failure["resolution"] = DefaultResolution(e.ErrorType);
        }

        var body = new Dictionary<string, object?>
        {
            ["success"] = false,
            ["failure"] = failure,
        };

        return StatusCode(statusCode, body);
    }

    private static Dictionary<string, object?> DefaultResolution(string failureType) => failureType switch
    {
        Constants.FailureAuthRequired => new Dictionary<string, object?>
        {
            ["action"] = "provide_credentials",
            ["recovery_class"] = Constants.RecoveryClassForAction("provide_credentials"),
            ["requires"] = "Bearer token",
        },
        Constants.FailureInvalidToken or Constants.FailureTokenExpired => new Dictionary<string, object?>
        {
            ["action"] = "request_new_delegation",
            ["recovery_class"] = Constants.RecoveryClassForAction("request_new_delegation"),
        },
        Constants.FailureScopeInsufficient => new Dictionary<string, object?>
        {
            ["action"] = "request_broader_scope",
            ["recovery_class"] = Constants.RecoveryClassForAction("request_broader_scope"),
        },
        Constants.FailureBudgetExceeded => new Dictionary<string, object?>
        {
            ["action"] = "request_budget_increase",
            ["recovery_class"] = Constants.RecoveryClassForAction("request_budget_increase"),
        },
        _ => new Dictionary<string, object?>
        {
            ["action"] = "contact_service_owner",
            ["recovery_class"] = Constants.RecoveryClassForAction("contact_service_owner"),
        },
    };

    private static string? GetStringFromBody(Dictionary<string, object?> body, string key)
    {
        if (!body.TryGetValue(key, out var val)) return null;
        if (val is JsonElement el && el.ValueKind == JsonValueKind.String)
            return el.GetString();
        return val as string;
    }
}
