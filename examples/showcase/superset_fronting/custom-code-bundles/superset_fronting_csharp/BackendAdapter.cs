using Anip.Service;
using System.Text;
using System.Text.Json;

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}};

public delegate Dictionary<string, object?> BackendAdapterHandler(
    Dictionary<string, object?> capability,
    Dictionary<string, object?> plan,
    Dictionary<string, object?> adapterInput,
    InvocationContext context);

public static class BackendAdapter
{
    public static BackendAdapterHandler Default => Execute;
    private static readonly HttpClient Http = new();

    private static Dictionary<string, object?> Execute(
        Dictionary<string, object?> capability,
        Dictionary<string, object?> plan,
        Dictionary<string, object?> adapterInput,
        InvocationContext context)
    {
        var unresolved = GeneratedCapabilities.StringList(plan.GetValueOrDefault("unresolved_required_backend_inputs"));
        if (unresolved.Count > 0)
        {
            return Result(capability, plan, "backend_input_incomplete", new() { ["unresolved_required_backend_inputs"] = unresolved });
        }

        var token = AccessToken();
        if (string.IsNullOrWhiteSpace(token))
        {
            return Result(capability, plan, "backend_error", new() { ["superset_error"] = new Dictionary<string, object?> { ["error"] = "missing_superset_credentials" } });
        }

        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "superset.analytics.discover_context" => DiscoverContext(capability, plan, adapterInput, token),
            "superset.analytics.answer_question" => AnswerQuestion(capability, plan, adapterInput),
            "superset.chart.preview.create" => ChartPreview(capability, plan, adapterInput),
            "superset.chart.publish.request" => ChartPublishRequest(capability, plan, adapterInput, context),
            "superset.dashboard.draft.prepare" => DashboardDraft(capability, plan, adapterInput),
            "superset.dataset.draft.prepare" => DatasetDraft(capability, plan, adapterInput, context),
            _ => Result(capability, plan, "backend_execution_stub", new() { ["note"] = "No Superset custom handler is registered for this capability." }),
        };
    }

    private static Dictionary<string, object?> DiscoverContext(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var workspaceScope = Text(parameters.GetValueOrDefault("workspace_scope"));
        if (!ScopeAllowed(workspaceScope)) return Restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.");
        var query = Text(parameters.GetValueOrDefault("query")).ToLowerInvariant();
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50);
        var assetType = Text(parameters.GetValueOrDefault("asset_type"));
        var endpoints = new[] { ("dataset", "/api/v1/dataset/"), ("chart", "/api/v1/chart/"), ("dashboard", "/api/v1/dashboard/") };
        var items = new List<Dictionary<string, object?>>();
        foreach (var (kind, endpoint) in endpoints)
        {
            if (!string.IsNullOrWhiteSpace(assetType) && assetType != kind) continue;
            var payload = RequestJson("GET", $"{endpoint}?page_size={limit}", token, null);
            if (payload.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["superset_error"] = payload });
            foreach (var item in ListResult(payload))
            {
                var title = FirstNonEmpty(Get(item, "table_name"), Get(item, "slice_name"), Get(item, "dashboard_title"), Get(item, "name"), Get(item, "id"));
                if (!string.IsNullOrWhiteSpace(query) && !title.ToLowerInvariant().Contains(query)) continue;
                items.Add(new() { ["asset_type"] = kind, ["id"] = Get(item, "id"), ["title"] = title, ["url"] = Get(item, "url") });
                if (items.Count >= limit) break;
            }
            if (items.Count >= limit) break;
        }
        return Result(capability, plan, "completed", new() { ["result"] = new Dictionary<string, object?> { ["workspace_scope"] = workspaceScope, ["items"] = items, ["count"] = items.Count } });
    }

    private static Dictionary<string, object?> AnswerQuestion(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters)
    {
        var datasetRef = Text(parameters.GetValueOrDefault("dataset_ref"));
        if (!DatasetAllowed(datasetRef)) return Restricted(capability, plan, "Dataset is outside the configured ANIP policy.");
        return Result(capability, plan, "completed", new()
        {
            ["mutation_performed"] = false,
            ["result"] = new Dictionary<string, object?>
            {
                ["question"] = parameters.GetValueOrDefault("question"),
                ["dataset_ref"] = datasetRef,
                ["metric"] = parameters.GetValueOrDefault("metric"),
                ["dimension"] = parameters.GetValueOrDefault("dimension"),
                ["time_window"] = parameters.GetValueOrDefault("time_window"),
                ["answer"] = "Governed analytics answer placeholder. The service owns SQL generation and execution policy.",
                ["raw_sql_disclosed"] = false,
            },
        });
    }

    private static Dictionary<string, object?> ChartPreview(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters)
    {
        var datasetRef = Text(parameters.GetValueOrDefault("dataset_ref"));
        if (!DatasetAllowed(datasetRef)) return Restricted(capability, plan, "Dataset is outside the configured ANIP policy.");
        var body = new Dictionary<string, object?>
        {
            ["dataset_ref"] = datasetRef,
            ["metric"] = parameters.GetValueOrDefault("metric"),
            ["dimension"] = parameters.GetValueOrDefault("dimension"),
            ["visualization_type"] = parameters.GetValueOrDefault("visualization_type"),
            ["title"] = FirstNonEmpty(parameters.GetValueOrDefault("title"), $"{Text(parameters.GetValueOrDefault("metric"))} by {FirstNonEmpty(parameters.GetValueOrDefault("dimension"), "time")}"),
            ["save_chart"] = false,
        };
        return WritePreview(capability, plan, "chart.preview", body, new() { ["dataset_ref"] = datasetRef });
    }

    private static Dictionary<string, object?> ChartPublishRequest(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, InvocationContext context)
    {
        var preview = WritePreview(capability, plan, "chart.publish", new() { ["chart_preview_ref"] = parameters.GetValueOrDefault("chart_preview_ref"), ["dashboard_scope"] = parameters.GetValueOrDefault("dashboard_scope"), ["reason"] = parameters.GetValueOrDefault("reason"), ["title"] = parameters.GetValueOrDefault("title") }, new() { ["dashboard_scope"] = parameters.GetValueOrDefault("dashboard_scope") });
        if (Environment.GetEnvironmentVariable("ANIP_SUPERSET_ALLOW_MUTATION") == "true" && !string.IsNullOrWhiteSpace(context?.ApprovalGrant))
        {
            preview["execution_status"] = "completed";
            preview["approval_required"] = false;
            preview["mutation_performed"] = false;
            preview["note"] = "Approved publish request recorded. Concrete chart save is intentionally left to deployment-specific Superset adapter code.";
        }
        return preview;
    }

    private static Dictionary<string, object?> DashboardDraft(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters) =>
        WritePreview(capability, plan, "dashboard.draft", new() { ["dashboard_scope"] = parameters.GetValueOrDefault("dashboard_scope"), ["objective"] = parameters.GetValueOrDefault("objective"), ["chart_refs"] = parameters.GetValueOrDefault("chart_refs"), ["layout_hint"] = parameters.GetValueOrDefault("layout_hint"), ["audience"] = parameters.GetValueOrDefault("audience") }, new() { ["dashboard_scope"] = parameters.GetValueOrDefault("dashboard_scope") });

    private static Dictionary<string, object?> DatasetDraft(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, InvocationContext context)
    {
        var preview = WritePreview(capability, plan, "dataset.draft", new() { ["database_ref"] = parameters.GetValueOrDefault("database_ref"), ["dataset_purpose"] = parameters.GetValueOrDefault("dataset_purpose"), ["query_intent"] = parameters.GetValueOrDefault("query_intent"), ["source_tables"] = parameters.GetValueOrDefault("source_tables"), ["metrics"] = parameters.GetValueOrDefault("metrics"), ["raw_sql_accepted"] = false }, new() { ["database_ref"] = parameters.GetValueOrDefault("database_ref") });
        if (Environment.GetEnvironmentVariable("ANIP_SUPERSET_ALLOW_MUTATION") == "true" && !string.IsNullOrWhiteSpace(context?.ApprovalGrant))
        {
            preview["execution_status"] = "completed";
            preview["approval_required"] = false;
            preview["mutation_performed"] = false;
            preview["note"] = "Approved dataset draft recorded. Raw SQL generation remains deployment-owned.";
        }
        return preview;
    }

    private static Dictionary<string, object?> WritePreview(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string action, Dictionary<string, object?> body, Dictionary<string, object?> metadata) =>
        Result(capability, plan, "prepared", new() { ["approval_required"] = true, ["mutation_performed"] = false, ["superset_action"] = action, ["superset_metadata"] = metadata, ["superset_request"] = new Dictionary<string, object?> { ["operation"] = action, ["body"] = body }, ["note"] = "Prepared a governed Superset analytics request. No Superset mutation was performed." });

    private static string AccessToken()
    {
        var direct = Text(Environment.GetEnvironmentVariable("SUPERSET_ACCESS_TOKEN"));
        if (!string.IsNullOrWhiteSpace(direct)) return direct;
        var username = Text(Environment.GetEnvironmentVariable("SUPERSET_USERNAME"));
        var password = Text(Environment.GetEnvironmentVariable("SUPERSET_PASSWORD"));
        if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password)) return "";
        var payload = RequestJson("POST", "/api/v1/security/login", "", new() { ["username"] = username, ["password"] = password, ["provider"] = FirstNonEmpty(Environment.GetEnvironmentVariable("SUPERSET_AUTH_PROVIDER"), "db"), ["refresh"] = true });
        return Text(payload.GetValueOrDefault("access_token"));
    }

    private static Dictionary<string, object?> RequestJson(string method, string path, string token, Dictionary<string, object?>? body)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), $"{FirstNonEmpty(Environment.GetEnvironmentVariable("SUPERSET_BASE_URL"), "http://127.0.0.1:18088").TrimEnd('/')}{path}");
        request.Headers.Accept.ParseAdd("application/json");
        request.Headers.UserAgent.ParseAdd("anip-superset-fronting-showcase");
        if (!string.IsNullOrWhiteSpace(token)) request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        try
        {
            using var response = Http.Send(request);
            var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
            var payload = string.IsNullOrWhiteSpace(text) ? new Dictionary<string, object?>() : JsonSerializer.Deserialize<Dictionary<string, object?>>(text)!;
            if (!response.IsSuccessStatusCode) return new() { ["error"] = "superset_http_error", ["status"] = (int)response.StatusCode, ["detail"] = payload };
            return payload;
        }
        catch (Exception exc)
        {
            return new() { ["error"] = "superset_connection_error", ["detail"] = exc.ToString() };
        }
    }

    private static Dictionary<string, object?> Result(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string status, Dictionary<string, object?> extra)
    {
        var result = new Dictionary<string, object?> { ["execution_status"] = status, ["capability_id"] = capability.GetValueOrDefault("capability_id"), ["selected_backend"] = plan.GetValueOrDefault("selected_binding"), ["semantic_input"] = plan.GetValueOrDefault("semantic_input"), ["backend_input_contract"] = plan.GetValueOrDefault("backend_input_contract") };
        foreach (var item in extra) result[item.Key] = item.Value;
        return result;
    }

    private static Dictionary<string, object?> Restricted(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string reason) =>
        Result(capability, plan, "restricted", new() { ["reason"] = reason });

    private static List<Dictionary<string, object?>> ListResult(Dictionary<string, object?> payload)
    {
        var result = new List<Dictionary<string, object?>>();
        if (payload.GetValueOrDefault("result") is JsonElement element && element.ValueKind == JsonValueKind.Object && element.TryGetProperty("data", out var data) && data.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in data.EnumerateArray())
            {
                result.Add(JsonSerializer.Deserialize<Dictionary<string, object?>>(item.GetRawText())!);
            }
        }
        return result;
    }

    private static string Get(Dictionary<string, object?> payload, string key) => payload.GetValueOrDefault(key) is JsonElement element ? (element.ValueKind == JsonValueKind.String ? element.GetString() ?? "" : element.ToString()) : Text(payload.GetValueOrDefault(key));
    private static bool ScopeAllowed(string scope) => !CsvEnv("ANIP_SUPERSET_BLOCKED_WORKSPACES").Contains(scope.ToLowerInvariant()) && (CsvEnv("ANIP_SUPERSET_ALLOWED_WORKSPACES").Count == 0 || CsvEnv("ANIP_SUPERSET_ALLOWED_WORKSPACES").Contains(scope.ToLowerInvariant()));
    private static bool DatasetAllowed(string datasetRef) => CsvEnv("ANIP_SUPERSET_ALLOWED_DATASETS").Count == 0 || CsvEnv("ANIP_SUPERSET_ALLOWED_DATASETS").Contains(datasetRef.ToLowerInvariant());
    private static int BoundedLimit(object? value, int defaultValue, int maximum) => int.TryParse(Text(value), out var parsed) ? Math.Max(1, Math.Min(parsed, maximum)) : defaultValue;
    private static string FirstNonEmpty(params object?[] values) => values.Select(Text).FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    private static string Text(object? value) => value is null ? "" : value.ToString()!.Trim();
    private static List<string> CsvEnv(string name) => (Environment.GetEnvironmentVariable(name) ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Select(item => item.ToLowerInvariant()).Distinct().ToList();
}
