using System.Text.Json;
using System.Text.Json.Serialization;
using Anip.Core;
using Anip.Service;

namespace Anip.Stdio;

/// <summary>
/// JSON-RPC 2.0 server wrapping an AnipService for stdio transport.
/// Reads newline-delimited JSON from a TextReader, writes JSON responses to a TextWriter.
/// </summary>
public class AnipStdioServer
{
    private static readonly JsonSerializerOptions s_jsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    private static readonly JsonSerializerOptions s_deserializeOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private readonly AnipService _service;

    // --- Valid ANIP methods ---

    private static readonly HashSet<string> ValidMethods = new()
    {
        "anip.discovery",
        "anip.manifest",
        "anip.jwks",
        "anip.tokens.issue",
        "anip.permissions",
        "anip.invoke",
        "anip.audit.query",
        "anip.checkpoints.list",
        "anip.checkpoints.get",
    };

    // --- JSON-RPC 2.0 error codes ---

    private const int ParseError = -32700;
    private const int InvalidRequest = -32600;
    private const int MethodNotFound = -32601;
    private const int AuthError = -32001;
    private const int ScopeError = -32002;
    private const int NotFoundError = -32004;
    private const int InternalError = -32603;

    // --- ANIP failure type to JSON-RPC error code mapping ---

    private static readonly Dictionary<string, int> FailureTypeToCode = new()
    {
        ["authentication_required"] = AuthError,
        ["invalid_token"] = AuthError,
        ["token_expired"] = AuthError,
        ["scope_insufficient"] = ScopeError,
        ["budget_exceeded"] = ScopeError,
        ["budget_currency_mismatch"] = ScopeError,
        ["budget_not_enforceable"] = ScopeError,
        ["binding_missing"] = ScopeError,
        ["binding_stale"] = ScopeError,
        ["control_requirement_unsatisfied"] = ScopeError,
        ["purpose_mismatch"] = ScopeError,
        ["unknown_capability"] = NotFoundError,
        ["not_found"] = NotFoundError,
        ["internal_error"] = InternalError,
        ["unavailable"] = InternalError,
        ["concurrent_lock"] = InternalError,
    };

    public AnipStdioServer(AnipService service)
    {
        _service = service;
    }

    /// <summary>
    /// Main serve loop: reads stdin line by line, dispatches, writes to stdout.
    /// Uses Console.In / Console.Out.
    /// </summary>
    public async Task ServeAsync(CancellationToken ct = default)
    {
        await ServeAsync(Console.In, Console.Out, ct);
    }

    /// <summary>
    /// Main serve loop: reads from the given reader line by line, dispatches, writes to the given writer.
    /// </summary>
    public async Task ServeAsync(TextReader reader, TextWriter writer, CancellationToken ct = default)
    {
        while (!ct.IsCancellationRequested)
        {
            string? line;
            try
            {
                line = await reader.ReadLineAsync(ct);
            }
            catch (OperationCanceledException)
            {
                break;
            }

            if (line == null)
                break; // EOF

            if (string.IsNullOrWhiteSpace(line))
                continue;

            // Parse JSON
            Dictionary<string, object?>? message;
            try
            {
                message = ParseJsonMessage(line);
            }
            catch (JsonException ex)
            {
                var errorResp = MakeError(null, ParseError, $"Parse error: {ex.Message}");
                await WriteResponse(writer, errorResp, ct);
                continue;
            }

            if (message == null)
            {
                var errorResp = MakeError(null, ParseError, "Parse error: null message");
                await WriteResponse(writer, errorResp, ct);
                continue;
            }

            var response = await HandleRequestAsync(message);

            if (response is List<Dictionary<string, object?>> multipleResponses)
            {
                foreach (var resp in multipleResponses)
                {
                    await WriteResponse(writer, resp, ct);
                }
            }
            else if (response is Dictionary<string, object?> singleResponse)
            {
                await WriteResponse(writer, singleResponse, ct);
            }
        }
    }

    /// <summary>
    /// Validates and dispatches a single JSON-RPC request message.
    /// Returns either a Dictionary (single response) or a List of Dictionaries
    /// (for streaming invocations: notifications followed by the final response).
    /// </summary>
    public async Task<object> HandleRequestAsync(Dictionary<string, object?> message)
    {
        // Validate request
        var error = ValidateRequest(message);
        if (error != null)
        {
            return MakeError(GetId(message), InvalidRequest, error);
        }

        var requestId = GetId(message);
        var method = GetString(message, "method")!;
        var parameters = GetParams(message);

        if (!ValidMethods.Contains(method))
        {
            return MakeError(requestId, MethodNotFound, $"Unknown method: {method}");
        }

        try
        {
            var result = await DispatchAsync(method, parameters);

            // Streaming invoke returns (notifications, result) as a tuple
            if (result is (List<Dictionary<string, object?>> notifications, Dictionary<string, object?> finalResult))
            {
                var messages = new List<Dictionary<string, object?>>(notifications);
                messages.Add(MakeResponse(requestId, finalResult));
                return messages;
            }

            return MakeResponse(requestId, result);
        }
        catch (AnipError ex)
        {
            var code = FailureTypeToCode.GetValueOrDefault(ex.ErrorType, InternalError);
            return MakeError(requestId, code, ex.Detail, new Dictionary<string, object?>
            {
                ["type"] = ex.ErrorType,
                ["detail"] = ex.Detail,
                ["retry"] = ex.Retry,
            });
        }
        catch (Exception ex)
        {
            return MakeError(requestId, InternalError, ex.Message);
        }
    }

    // --- Method handlers ---

    private async Task<object> DispatchAsync(string method, Dictionary<string, object?> parameters)
    {
        return method switch
        {
            "anip.discovery" => HandleDiscovery(parameters),
            "anip.manifest" => HandleManifest(parameters),
            "anip.jwks" => HandleJwks(parameters),
            "anip.tokens.issue" => HandleTokensIssue(parameters),
            "anip.permissions" => HandlePermissions(parameters),
            "anip.invoke" => await HandleInvokeAsync(parameters),
            "anip.audit.query" => HandleAuditQuery(parameters),
            "anip.checkpoints.list" => HandleCheckpointsList(parameters),
            "anip.checkpoints.get" => HandleCheckpointsGet(parameters),
            _ => throw new InvalidOperationException($"No handler for {method}"),
        };
    }

    private Dictionary<string, object?> HandleDiscovery(Dictionary<string, object?> parameters)
    {
        return _service.GetDiscovery(null);
    }

    private Dictionary<string, object?> HandleManifest(Dictionary<string, object?> parameters)
    {
        var signed = _service.GetSignedManifest();
        var manifestObj = JsonSerializer.Deserialize<Dictionary<string, object?>>(signed.ManifestJson, s_deserializeOptions);
        return new Dictionary<string, object?>
        {
            ["manifest"] = manifestObj,
            ["signature"] = signed.Signature,
        };
    }

    private object HandleJwks(Dictionary<string, object?> parameters)
    {
        return _service.GetJwks();
    }

    private object HandleTokensIssue(Dictionary<string, object?> parameters)
    {
        var bearer = ExtractAuth(parameters);
        if (bearer == null)
        {
            throw new AnipError("authentication_required", "This method requires auth.bearer");
        }

        var principal = _service.AuthenticateBearer(bearer);
        if (principal == null)
        {
            throw new AnipError("invalid_token", "Bearer token not recognized");
        }

        var request = new TokenRequest
        {
            Subject = GetString(parameters, "subject") ?? "",
            Scope = GetStringList(parameters, "scope"),
            Capability = GetString(parameters, "capability") ?? "",
            TtlHours = GetInt(parameters, "ttl_hours"),
            ParentToken = GetString(parameters, "parent_token"),
            CallerClass = GetString(parameters, "caller_class"),
            Budget = ExtractBudget(parameters),
        };

        var resp = _service.IssueToken(principal, request);
        return SerializeToDict(resp);
    }

    private object HandlePermissions(Dictionary<string, object?> parameters)
    {
        var token = ResolveJwt(parameters);
        var perms = _service.DiscoverPermissions(token);
        return SerializeToDict(perms);
    }

    private async Task<object> HandleInvokeAsync(Dictionary<string, object?> parameters)
    {
        var token = ResolveJwt(parameters);

        var capability = GetString(parameters, "capability");
        if (string.IsNullOrEmpty(capability))
        {
            throw new AnipError("unknown_capability", "Missing 'capability' in params");
        }

        var invokeParams = GetDict(parameters, "parameters");
        var clientReferenceId = GetString(parameters, "client_reference_id");
        var taskId = GetString(parameters, "task_id");
        var parentInvocationId = GetString(parameters, "parent_invocation_id");
        var stream = GetBool(parameters, "stream");

        // Extract budget from params (v0.13).
        var budget = ExtractBudget(parameters);

        if (stream)
        {
            // Streaming invocation — collect progress notifications then return final result.
            var streamResult = _service.InvokeStream(capability, token, invokeParams, new InvokeOpts
            {
                ClientReferenceId = clientReferenceId,
                TaskId = taskId,
                ParentInvocationId = parentInvocationId,
                Stream = true,
                Budget = budget,
            });

            var notifications = new List<Dictionary<string, object?>>();
            Dictionary<string, object?>? finalResult = null;

            while (await streamResult.Events.WaitToReadAsync())
            {
                while (streamResult.Events.TryRead(out var evt))
                {
                    switch (evt.Type)
                    {
                        case "progress":
                            notifications.Add(MakeNotification("anip.invoke.progress", evt.Payload));
                            break;
                        case "completed":
                        case "failed":
                            finalResult = evt.Payload;
                            break;
                    }
                }
            }

            return (notifications, finalResult ?? new Dictionary<string, object?>());
        }

        // Unary invocation.
        var opts = new InvokeOpts
        {
            ClientReferenceId = clientReferenceId,
            TaskId = taskId,
            ParentInvocationId = parentInvocationId,
            Budget = budget,
        };

        return _service.Invoke(capability, token, invokeParams, opts);
    }

    private object HandleAuditQuery(Dictionary<string, object?> parameters)
    {
        var token = ResolveJwt(parameters);

        var filters = new AuditFilters
        {
            Capability = GetString(parameters, "capability"),
            Since = GetString(parameters, "since"),
            InvocationId = GetString(parameters, "invocation_id"),
            ClientReferenceId = GetString(parameters, "client_reference_id"),
            TaskId = GetString(parameters, "task_id"),
            ParentInvocationId = GetString(parameters, "parent_invocation_id"),
            Limit = GetInt(parameters, "limit"),
        };

        var resp = _service.QueryAudit(token, filters);
        return SerializeToDict(resp);
    }

    private object HandleCheckpointsList(Dictionary<string, object?> parameters)
    {
        var limit = GetInt(parameters, "limit");
        if (limit <= 0) limit = 10;

        var resp = _service.ListCheckpoints(limit);
        return SerializeToDict(resp);
    }

    private object HandleCheckpointsGet(Dictionary<string, object?> parameters)
    {
        var checkpointId = GetString(parameters, "id");
        if (string.IsNullOrEmpty(checkpointId))
        {
            throw new AnipError("not_found", "Missing 'id' in params");
        }

        var includeProof = GetBool(parameters, "include_proof");
        var leafIndex = GetInt(parameters, "leaf_index");

        var resp = _service.GetCheckpoint(checkpointId, includeProof, leafIndex);
        return SerializeToDict(resp);
    }

    // --- Internal helpers ---

    private DelegationToken ResolveJwt(Dictionary<string, object?> parameters)
    {
        var bearer = ExtractAuth(parameters);
        if (bearer == null)
        {
            throw new AnipError("authentication_required", "This method requires auth.bearer");
        }
        return _service.ResolveBearerToken(bearer);
    }

    private static string? ExtractAuth(Dictionary<string, object?> parameters)
    {
        if (!parameters.TryGetValue("auth", out var authObj) || authObj == null)
            return null;

        if (authObj is JsonElement authElement)
        {
            if (authElement.ValueKind != JsonValueKind.Object)
                return null;
            if (authElement.TryGetProperty("bearer", out var bearerProp))
                return bearerProp.GetString();
            return null;
        }

        if (authObj is Dictionary<string, object?> authDict)
        {
            if (authDict.TryGetValue("bearer", out var bearerVal))
                return bearerVal?.ToString();
            return null;
        }

        return null;
    }

    // --- JSON-RPC message constructors ---

    private static Dictionary<string, object?> MakeResponse(object? requestId, object result)
    {
        return new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["id"] = requestId,
            ["result"] = result,
        };
    }

    private static Dictionary<string, object?> MakeNotification(string method, object parameters)
    {
        return new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["method"] = method,
            ["params"] = parameters,
        };
    }

    private static Dictionary<string, object?> MakeError(
        object? requestId, int code, string message, Dictionary<string, object?>? data = null)
    {
        var error = new Dictionary<string, object?>
        {
            ["code"] = code,
            ["message"] = message,
        };
        if (data != null)
        {
            error["data"] = data;
        }
        return new Dictionary<string, object?>
        {
            ["jsonrpc"] = "2.0",
            ["id"] = requestId,
            ["error"] = error,
        };
    }

    // --- Request validation ---

    private static string? ValidateRequest(Dictionary<string, object?> msg)
    {
        if (!msg.TryGetValue("jsonrpc", out var jsonrpc) || GetStringValue(jsonrpc) != "2.0")
            return "Missing or invalid 'jsonrpc' field (must be '2.0')";

        if (!msg.TryGetValue("method", out var method))
            return "Missing 'method' field";

        var methodStr = GetStringValue(method);
        if (methodStr == null)
            return "'method' must be a string";

        if (!msg.ContainsKey("id"))
            return "Missing 'id' field (notifications not supported as requests)";

        return null;
    }

    // --- Serialization helpers ---

    private static Dictionary<string, object?>? ParseJsonMessage(string json)
    {
        using var doc = JsonDocument.Parse(json);
        return ElementToDict(doc.RootElement);
    }

    private static Dictionary<string, object?> ElementToDict(JsonElement element)
    {
        var dict = new Dictionary<string, object?>();
        foreach (var property in element.EnumerateObject())
        {
            dict[property.Name] = ElementToValue(property.Value);
        }
        return dict;
    }

    private static object? ElementToValue(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.Object => ElementToDict(element),
            JsonValueKind.Array => ElementToArray(element),
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Number => element.TryGetInt64(out var l) ? l : element.GetDouble(),
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            _ => element.GetRawText(),
        };
    }

    private static List<object?> ElementToArray(JsonElement element)
    {
        var list = new List<object?>();
        foreach (var item in element.EnumerateArray())
        {
            list.Add(ElementToValue(item));
        }
        return list;
    }

    private static async Task WriteResponse(TextWriter writer, Dictionary<string, object?> response, CancellationToken ct)
    {
        var json = JsonSerializer.Serialize(response, s_jsonOptions);
        await writer.WriteLineAsync(json.AsMemory(), ct);
        await writer.FlushAsync(ct);
    }

    private static object? GetId(Dictionary<string, object?> msg)
    {
        msg.TryGetValue("id", out var id);
        return id;
    }

    private static string? GetString(Dictionary<string, object?> dict, string key)
    {
        if (!dict.TryGetValue(key, out var val) || val == null)
            return null;
        return GetStringValue(val);
    }

    private static string? GetStringValue(object? val)
    {
        if (val is string s)
            return s;
        if (val is JsonElement je && je.ValueKind == JsonValueKind.String)
            return je.GetString();
        return val?.ToString();
    }

    private static int GetInt(Dictionary<string, object?> dict, string key)
    {
        if (!dict.TryGetValue(key, out var val) || val == null)
            return 0;
        if (val is int i)
            return i;
        if (val is long l)
            return (int)l;
        if (val is JsonElement je && je.ValueKind == JsonValueKind.Number)
            return je.GetInt32();
        if (int.TryParse(val.ToString(), out var parsed))
            return parsed;
        return 0;
    }

    private static bool GetBool(Dictionary<string, object?> dict, string key)
    {
        if (!dict.TryGetValue(key, out var val) || val == null)
            return false;
        if (val is bool b)
            return b;
        if (val is JsonElement je)
        {
            if (je.ValueKind == JsonValueKind.True) return true;
            if (je.ValueKind == JsonValueKind.False) return false;
        }
        return false;
    }

    private static List<string> GetStringList(Dictionary<string, object?> dict, string key)
    {
        if (!dict.TryGetValue(key, out var val) || val == null)
            return new List<string>();

        if (val is List<object?> objList)
            return objList.Where(x => x != null).Select(x => x!.ToString()!).ToList();

        if (val is JsonElement je && je.ValueKind == JsonValueKind.Array)
        {
            var result = new List<string>();
            foreach (var item in je.EnumerateArray())
            {
                if (item.ValueKind == JsonValueKind.String)
                    result.Add(item.GetString()!);
            }
            return result;
        }

        return new List<string>();
    }

    private static Dictionary<string, object?> GetDict(Dictionary<string, object?> dict, string key)
    {
        if (!dict.TryGetValue(key, out var val) || val == null)
            return new Dictionary<string, object?>();

        if (val is Dictionary<string, object?> d)
            return d;

        if (val is JsonElement je && je.ValueKind == JsonValueKind.Object)
            return ElementToDict(je);

        return new Dictionary<string, object?>();
    }

    private static Budget? ExtractBudget(Dictionary<string, object?> parameters)
    {
        if (!parameters.TryGetValue("budget", out var budgetObj) || budgetObj == null)
            return null;

        if (budgetObj is Dictionary<string, object?> dict)
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
                return new Budget { Currency = currency, MaxAmount = maxAmount };
            }
        }
        else if (budgetObj is JsonElement je && je.ValueKind == JsonValueKind.Object)
        {
            var currency = je.TryGetProperty("currency", out var currProp) && currProp.ValueKind == JsonValueKind.String
                ? currProp.GetString() : null;
            var maxAmount = je.TryGetProperty("max_amount", out var amtProp) && amtProp.ValueKind == JsonValueKind.Number
                ? amtProp.GetDouble() : 0.0;
            if (!string.IsNullOrEmpty(currency) && maxAmount > 0)
            {
                return new Budget { Currency = currency, MaxAmount = maxAmount };
            }
        }

        return null;
    }

    private static Dictionary<string, object?> GetParams(Dictionary<string, object?> msg)
    {
        if (!msg.TryGetValue("params", out var val) || val == null)
            return new Dictionary<string, object?>();

        if (val is Dictionary<string, object?> d)
            return d;

        if (val is JsonElement je && je.ValueKind == JsonValueKind.Object)
            return ElementToDict(je);

        return new Dictionary<string, object?>();
    }

    private static Dictionary<string, object?> SerializeToDict(object obj)
    {
        var json = JsonSerializer.Serialize(obj, s_jsonOptions);
        using var doc = JsonDocument.Parse(json);
        return ElementToDict(doc.RootElement);
    }
}
