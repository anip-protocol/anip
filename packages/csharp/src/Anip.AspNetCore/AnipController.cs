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

    // A typed request body is decoded the way the framework's [FromBody]
    // binding decodes it: member names are matched case-insensitively.
    private static readonly JsonSerializerOptions s_requestOptions = new(JsonSerializerDefaults.Web)
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

    // --- 4. Token issuance (bootstrap credential, or a delegation token for delegating) ---

    [HttpPost("/anip/tokens")]
    public async Task<IActionResult> IssueToken()
    {
        var bearer = ExtractBearer();
        if (string.IsNullOrEmpty(bearer))
        {
            return AuthRequiredResponse();
        }

        // Bootstrap credential, or a delegation token issued by this service.
        var issuer = _service.AuthenticateIssuer(bearer);
        if (issuer == null)
        {
            // SPEC.md §6.3 Token Issuance: an unrecognised credential is
            // authentication_required, like no credential at all.
            return AuthRequiredResponse(
                "A bootstrap credential, or a delegation token issued by this service, is required to issue delegation tokens");
        }

        // The body is read here, after the credential check, so that a body
        // that is not a token request is an ANIP failure (SPEC.md §6.3) and
        // a missing credential is still 401.
        TokenRequest? request;
        try
        {
            request = await JsonSerializer.DeserializeAsync<TokenRequest>(Request.Body, s_requestOptions);
        }
        catch
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "request body must be a JSON token request", false);
        }
        if (request == null)
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "request body must be a JSON token request", false);
        }

        try
        {
            var resp = _service.IssueTokenAs(issuer, request);
            return Ok(resp);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return AnipErrorResponse(status, e);
        }
        catch (Exception)
        {
            return FailureResponse(Constants.FailureInternalError,
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
            // SPEC.md §6.3: a request body that is not JSON is invalid_parameters.
            return FailureResponse(Constants.FailureInvalidParameters,
                "request body must be a JSON object", false);
        }

        body ??= new Dictionary<string, object?>();

        // SPEC.md §6.3: a "parameters" value that is neither an object nor
        // null does not match the request schema.
        if (body.TryGetValue("parameters", out var rawParameters) &&
            rawParameters is JsonElement rawParametersElement &&
            rawParametersElement.ValueKind is not (JsonValueKind.Object or JsonValueKind.Null or JsonValueKind.Undefined))
        {
            var shapeFailure = ParameterValidation.Failure(
                $"{capability} parameters must be an object, got {ParameterValidation.JsonTypeOf(rawParametersElement)}");
            return new ObjectResult(new Dictionary<string, object?>
            {
                ["success"] = false,
                ["failure"] = shapeFailure,
            })
            {
                StatusCode = Constants.FailureStatusCode(Constants.FailureInvalidParameters),
            };
        }

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
            parameters.Remove("approval_grant"); // v0.23
            parameters.Remove("requested_effects");
            parameters.Remove("budget");
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

        // v0.23: continuation grant_id from body. NOTE: session_id is NEVER
        // read from the body — it must come from the signed delegation token.
        string? approvalGrant = null;
        if (body.TryGetValue("approval_grant", out var agObj))
        {
            approvalGrant = InvokeOpts.ApprovalGrantFromRequest(agObj);
        }

        var requestedEffects = ExtractStringList(body, "requested_effects");

        if (stream)
        {
            return await HandleStreamInvoke(capability, token, parameters, clientRefId, taskId, parentInvocationId, upstreamService, approvalGrant, requestedEffects);
        }

        var opts = new InvokeOpts
        {
            ClientReferenceId = clientRefId,
            TaskId = taskId,
            ParentInvocationId = parentInvocationId,
            UpstreamService = upstreamService,
            Stream = false,
            ApprovalGrant = approvalGrant,
            RequestedEffects = requestedEffects,
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

            return StatusCode(Constants.FailureStatusCode(null), result);
        }

        return Ok(result);
    }

    // --- v0.23: Approval grants (JWT auth) ---
    //
    // SPEC.md §4.9 — POST /anip/approval_grants. Validation order is
    // security-relevant:
    //   1. authn (resolveJwtAuth)
    //   2. parse + schema-validate body
    //   3. load ApprovalRequest
    //   4. state check (decided / expired) — BEFORE approver auth
    //   5. approver authority check (token must hold approver:* or
    //      approver:<capability>)
    //   6. service.IssueApprovalGrant
    // The 200 body IS the signed grant — no wrapper.

    [HttpPost("/anip/approval_grants")]
    public async Task<IActionResult> ApprovalGrants()
    {
        var (token, errorResult) = ResolveJwtAuth();
        if (token == null) return errorResult!;

        IssueApprovalGrantRequest? body;
        try
        {
            body = await JsonSerializer.DeserializeAsync<IssueApprovalGrantRequest>(
                Request.Body, s_serializerOptions);
        }
        catch
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "request body must be JSON", false);
        }
        if (body == null)
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "request body must be JSON", false);
        }

        // Schema validation.
        if (string.IsNullOrEmpty(body.ApprovalRequestId))
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "approval_request_id: required", false);
        }
        if (body.GrantType != ApprovalGrant.TypeOneTime && body.GrantType != ApprovalGrant.TypeSessionBound)
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "grant_type: must be one_time or session_bound", false);
        }
        if (body.GrantType == ApprovalGrant.TypeSessionBound &&
            string.IsNullOrEmpty(body.SessionId))
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "session_id: required when grant_type=session_bound", false);
        }
        if (body.GrantType == ApprovalGrant.TypeOneTime && !string.IsNullOrEmpty(body.SessionId))
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "session_id: must not be set when grant_type=one_time", false);
        }
        if (body.ExpiresInSeconds.HasValue && body.ExpiresInSeconds.Value < 1)
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "expires_in_seconds: must be a positive integer", false);
        }
        if (body.MaxUses.HasValue && body.MaxUses.Value < 1)
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "max_uses: must be a positive integer", false);
        }
        // Schema: a one_time grant allows max_uses 1 only. Asking for more
        // is refused, not silently lowered.
        if (body.GrantType == ApprovalGrant.TypeOneTime &&
            body.MaxUses.HasValue && body.MaxUses.Value != 1)
        {
            return FailureResponse(Constants.FailureInvalidParameters,
                "max_uses: must be 1 or omitted when grant_type=one_time", false);
        }

        ApprovalRequest? req;
        try
        {
            req = _service.GetApprovalRequest(body.ApprovalRequestId);
        }
        catch (Exception)
        {
            return FailureResponse(Constants.FailureInternalError,
                "lookup failed", false);
        }
        if (req == null)
        {
            return FailureResponse(Constants.FailureApprovalRequestNotFound,
                $"approval_request_id '{body.ApprovalRequestId}' not found", false);
        }

        // 4. State check BEFORE approver auth.
        var nowIso = DateTime.UtcNow.ToString("o");
        if (req.Status != ApprovalRequest.StatusPending)
        {
            return FailureResponse(Constants.FailureApprovalRequestAlreadyDecided,
                $"approval_request '{body.ApprovalRequestId}' status={req.Status}", false);
        }
        if (!string.IsNullOrEmpty(req.ExpiresAt) &&
            string.CompareOrdinal(req.ExpiresAt, nowIso) <= 0)
        {
            return FailureResponse(Constants.FailureApprovalRequestExpired,
                $"approval_request '{body.ApprovalRequestId}' expired", false);
        }

        // 5. Approver authority — token must hold approver:* OR approver:<capability>.
        var authorized = false;
        var required = "approver:" + req.Capability;
        foreach (var sc in token.Scope)
        {
            if (sc == "approver:*" || sc == required) { authorized = true; break; }
        }
        if (!authorized)
        {
            return FailureResponse(Constants.FailureApproverNotAuthorized,
                $"token lacks approver:{req.Capability} scope", false);
        }

        // 6. Issue.
        var approver = new Dictionary<string, object?>
        {
            ["subject"] = token.Subject,
            ["root_principal"] = token.RootPrincipal ?? token.Issuer,
        };
        try
        {
            var grant = _service.IssueApprovalGrant(
                body.ApprovalRequestId, body.GrantType, approver,
                body.SessionId, body.ExpiresInSeconds, body.MaxUses);
            // SPEC.md §4.9: 200 IS the signed grant, no wrapper.
            return Ok(grant);
        }
        catch (AnipError e)
        {
            var status = Constants.FailureStatusCode(e.ErrorType);
            return AnipErrorResponse(status, e);
        }
        catch (Exception e)
        {
            return FailureResponse(Constants.FailureInternalError,
                "issuance failed: " + e.Message, false);
        }
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
            return FailureResponse(Constants.FailureInternalError,
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
            return FailureResponse(Constants.FailureNotFound,
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
            return FailureResponse(Constants.FailureInternalError,
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
            return FailureResponse(Constants.FailureInternalError,
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
        string? upstreamService,
        string? approvalGrant = null,
        List<string>? requestedEffects = null)
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
                ApprovalGrant = approvalGrant,
                RequestedEffects = requestedEffects ?? new(),
            };
            sr = _service.InvokeStream(capability, token, parameters, opts);
        }
        catch (InvocationRefusedError refused)
        {
            // Refused before the handler: the response a unary invocation
            // returns (failure, invocation_id, lineage), with the mapped status.
            return StatusCode(Constants.FailureStatusCode(refused.ErrorType), refused.Response);
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
            return (null, FailureResponse(Constants.FailureInvalidToken,
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

    private ObjectResult AuthRequiredResponse(string detail = "Authorization header with Bearer token required")
    {
        var failure = new Dictionary<string, object?>
        {
            ["type"] = Constants.FailureAuthRequired,
            ["detail"] = detail,
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

        return StatusCode(Constants.FailureStatusCode(Constants.FailureAuthRequired), body);
    }

    /// <summary>A failure the binding raises itself, with the status the table gives its type.</summary>
    private ObjectResult FailureResponse(string type, string detail, bool retry)
    {
        var statusCode = Constants.FailureStatusCode(type);
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
        // The caller corrects the request and sends a new one (SPEC.md §6.3).
        Constants.FailureInvalidParameters => new Dictionary<string, object?>
        {
            ["action"] = "retry_now",
            ["recovery_class"] = Constants.RecoveryClassForAction("retry_now"),
        },
        // The manifest says which response modes a capability supports.
        Constants.FailureStreamingNotSupported => new Dictionary<string, object?>
        {
            ["action"] = "check_manifest",
            ["recovery_class"] = Constants.RecoveryClassForAction("check_manifest"),
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

    private static List<string> ExtractStringList(Dictionary<string, object?> body, string key)
    {
        if (!body.TryGetValue(key, out var val) || val is null) return new();
        if (val is JsonElement { ValueKind: JsonValueKind.Array } array)
        {
            return array.EnumerateArray()
                .Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() ?? string.Empty : item.ToString())
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Select(item => item.Trim())
                .Distinct()
                .ToList();
        }
        if (val is IEnumerable<object?> objects)
        {
            return objects
                .Where(item => item is not null)
                .Select(item => item!.ToString() ?? string.Empty)
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Select(item => item.Trim())
                .Distinct()
                .ToList();
        }
        return new();
    }
}
