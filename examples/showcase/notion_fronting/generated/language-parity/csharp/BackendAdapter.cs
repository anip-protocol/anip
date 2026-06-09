using System.Text;
using System.Text.Json;
using Anip.Service;

namespace notiongovernedfrontingshowcase;

public delegate Dictionary<string, object?> BackendAdapterHandler(
    Dictionary<string, object?> capability,
    Dictionary<string, object?> plan,
    Dictionary<string, object?> adapterInput,
    InvocationContext context);

public static class BackendAdapter
{
    public static BackendAdapterHandler Default => Execute;

    private static readonly HttpClient Http = new();

    private static Dictionary<string, object?> Execute(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, InvocationContext context)
    {
        var unresolved = StringList(plan.GetValueOrDefault("unresolved_required_backend_inputs"));
        if (unresolved.Count > 0) return Result(capability, plan, "backend_input_incomplete", new() { ["unresolved_required_backend_inputs"] = unresolved });
        if (string.IsNullOrWhiteSpace(Token())) return Result(capability, plan, "backend_error", new() { ["notion_error"] = new Dictionary<string, object?> { ["error"] = "missing_notion_token" } });

        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "notion.workspace.search_context" => SearchWorkspace(capability, plan, parameters),
            "notion.database.query_context" => QueryDatabase(capability, plan, parameters),
            "notion.page.create.prepare" => PrepareOrCreatePage(capability, plan, parameters, context),
            "notion.page.update.prepare" => PreparePageUpdate(capability, plan, parameters),
            "notion.comment.prepare" => PrepareOrPostComment(capability, plan, parameters, context),
            _ => Result(capability, plan, "backend_execution_stub", new() { ["note"] = "No Notion custom handler is registered for this capability." }),
        };
    }

    private static Dictionary<string, object?> SearchWorkspace(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters)
    {
        var scope = Text(parameters.GetValueOrDefault("workspace_scope"));
        if (!ScopeAllowed(scope)) return Restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.");
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50);
        var response = Notion("POST", "/search", new() { ["query"] = Text(parameters.GetValueOrDefault("query")), ["page_size"] = limit });
        if (response.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["notion_error"] = response });
        var items = SummarizeResults(response, limit);
        return Result(capability, plan, "completed", new() { ["notion_query"] = parameters.GetValueOrDefault("query"), ["result"] = new Dictionary<string, object?> { ["workspace_scope"] = scope, ["items"] = items, ["count"] = items.Count } });
    }

    private static Dictionary<string, object?> QueryDatabase(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters)
    {
        var databaseId = Text(parameters.GetValueOrDefault("database_id"));
        if (!IdAllowed(databaseId, "ANIP_NOTION_ALLOWED_DATABASES")) return Restricted(capability, plan, "Database is outside the configured ANIP policy.");
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50);
        var dataSourceId = ConfiguredDataSourceId();
        if (!string.IsNullOrWhiteSpace(dataSourceId) && !IdAllowed(dataSourceId, "ANIP_NOTION_ALLOWED_DATA_SOURCES")) return Restricted(capability, plan, "Data source is outside the configured ANIP policy.");
        if (string.IsNullOrWhiteSpace(dataSourceId))
        {
            var database = Notion("GET", $"/databases/{databaseId}", null);
            if (database.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["notion_error"] = database });
            dataSourceId = Text(MapList(Path(database, "data_sources")).FirstOrDefault()?.GetValueOrDefault("id"));
        }
        var response = string.IsNullOrWhiteSpace(dataSourceId)
            ? Notion("POST", $"/databases/{databaseId}/query", new() { ["page_size"] = limit })
            : Notion("POST", $"/data_sources/{dataSourceId}/query", new() { ["page_size"] = limit });
        if (response.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["notion_error"] = response });
        var items = SummarizeResults(response, limit);
        return Result(capability, plan, "completed", new() { ["result"] = new Dictionary<string, object?> { ["database_id"] = databaseId, ["data_source_id"] = dataSourceId, ["items"] = items, ["count"] = items.Count } });
    }

    private static Dictionary<string, object?> PrepareOrCreatePage(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, InvocationContext context)
    {
        var parentId = Text(parameters.GetValueOrDefault("parent_id"));
        if (!IdAllowed(parentId, "ANIP_NOTION_ALLOWED_PARENTS")) return Restricted(capability, plan, "Parent page/database is outside the configured ANIP policy.");
        var body = new Dictionary<string, object?>
        {
            ["parent"] = new Dictionary<string, object?> { ["page_id"] = parentId },
            ["properties"] = new Dictionary<string, object?> { ["title"] = new Dictionary<string, object?> { ["title"] = RichText(Text(parameters.GetValueOrDefault("title"))) } },
            ["children"] = new object?[] { new Dictionary<string, object?> { ["object"] = "block", ["type"] = "paragraph", ["paragraph"] = new Dictionary<string, object?> { ["rich_text"] = RichText(Text(parameters.GetValueOrDefault("content_summary"))) } } },
        };
        var preview = WritePreview(capability, plan, "pages.create", body, new() { ["parent_id"] = parentId });
        if (!MutationEnabled(context)) return preview;
        var created = Notion("POST", "/pages", body);
        if (created.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["notion_error"] = created;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["created_page"] = SummarizeObject(created);
        return preview;
    }

    private static Dictionary<string, object?> PreparePageUpdate(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters)
    {
        var pageId = Text(parameters.GetValueOrDefault("page_id"));
        if (!IdAllowed(pageId, "ANIP_NOTION_ALLOWED_PAGES")) return Restricted(capability, plan, "Page is outside the configured ANIP policy.");
        return WritePreview(capability, plan, "pages.update.preview", new() { ["archived"] = false, ["change_summary"] = Text(parameters.GetValueOrDefault("change_summary")), ["content_patch"] = Text(parameters.GetValueOrDefault("content_patch")) }, new() { ["page_id"] = pageId });
    }

    private static Dictionary<string, object?> PrepareOrPostComment(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, InvocationContext context)
    {
        var pageId = Text(parameters.GetValueOrDefault("page_id"));
        if (!IdAllowed(pageId, "ANIP_NOTION_ALLOWED_PAGES")) return Restricted(capability, plan, "Page is outside the configured ANIP policy.");
        var body = new Dictionary<string, object?> { ["parent"] = new Dictionary<string, object?> { ["page_id"] = pageId }, ["rich_text"] = RichText($"[{Text(parameters.GetValueOrDefault("comment_purpose"))}] {Text(parameters.GetValueOrDefault("context"))}".Trim()) };
        var preview = WritePreview(capability, plan, "comments.create", body, new() { ["page_id"] = pageId });
        if (!MutationEnabled(context)) return preview;
        var created = Notion("POST", "/comments", body);
        if (created.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["notion_error"] = created;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["created_comment"] = created;
        return preview;
    }

    public static Dictionary<string, object?> Notion(string method, string path, Dictionary<string, object?>? body)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), $"{ApiBase()}{path}");
        request.Headers.Accept.ParseAdd("application/json");
        request.Headers.TryAddWithoutValidation("Authorization", $"Bearer {Token()}");
        request.Headers.TryAddWithoutValidation("Notion-Version", NotionVersion());
        request.Headers.UserAgent.ParseAdd("anip-notion-fronting-showcase");
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        var response = Http.Send(request);
        var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
        var payload = string.IsNullOrWhiteSpace(text) ? new Dictionary<string, object?>() : JsonSerializer.Deserialize<Dictionary<string, object?>>(text)!;
        if (!response.IsSuccessStatusCode) return new Dictionary<string, object?> { ["error"] = "notion_http_error", ["status"] = (int)response.StatusCode, ["detail"] = payload };
        return payload;
    }

    private static Dictionary<string, object?> WritePreview(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string action, Dictionary<string, object?> body, Dictionary<string, object?> metadata) =>
        Result(capability, plan, "prepared", new() { ["approval_required"] = true, ["mutation_performed"] = false, ["notion_action"] = action, ["notion_metadata"] = metadata, ["notion_request"] = new Dictionary<string, object?> { ["operation"] = action, ["body"] = body }, ["note"] = "Prepared a Notion API payload. No Notion mutation was performed." });

    private static Dictionary<string, object?> Result(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string status, Dictionary<string, object?> extra)
    {
        var result = new Dictionary<string, object?> { ["execution_status"] = status, ["capability_id"] = capability.GetValueOrDefault("capability_id"), ["selected_backend"] = plan.GetValueOrDefault("selected_binding"), ["semantic_input"] = plan.GetValueOrDefault("semantic_input"), ["backend_input_contract"] = plan.GetValueOrDefault("backend_input_contract") };
        foreach (var item in extra) result[item.Key] = item.Value;
        return result;
    }

    private static Dictionary<string, object?> Restricted(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string reason) =>
        Result(capability, plan, "restricted", new() { ["reason"] = reason });

    private static List<Dictionary<string, object?>> SummarizeResults(Dictionary<string, object?> response, int limit) =>
        MapList(Path(response, "results")).Take(limit).Select(SummarizeObject).ToList();

    private static Dictionary<string, object?> SummarizeObject(Dictionary<string, object?> item)
    {
        var title = Text(item.GetValueOrDefault("object")) == "page" ? TitleFromPage(item) : Text(item.GetValueOrDefault("url"));
        if (string.IsNullOrWhiteSpace(title)) title = Text(item.GetValueOrDefault("id"));
        return new() { ["id"] = item.GetValueOrDefault("id"), ["object"] = item.GetValueOrDefault("object"), ["title"] = title, ["url"] = item.GetValueOrDefault("url"), ["created_time"] = item.GetValueOrDefault("created_time"), ["last_edited_time"] = item.GetValueOrDefault("last_edited_time") };
    }

    private static string TitleFromPage(Dictionary<string, object?> page)
    {
        var properties = ObjectMap(page.GetValueOrDefault("properties"));
        foreach (var property in properties.Values.Select(ObjectMap))
        {
            if (Text(property.GetValueOrDefault("type")) != "title") continue;
            return string.Concat(MapList(property.GetValueOrDefault("title")).Select(part => Text(part.GetValueOrDefault("plain_text")))).Trim();
        }
        return "";
    }

    private static object?[] RichText(string value) => [new Dictionary<string, object?> { ["type"] = "text", ["text"] = new Dictionary<string, object?> { ["content"] = value.Length > 1900 ? value[..1900] : value } }];
    private static bool ScopeAllowed(string scope) => !CsvEnv("ANIP_NOTION_BLOCKED_WORKSPACES").Contains(scope.ToLowerInvariant()) && (CsvEnv("ANIP_NOTION_ALLOWED_WORKSPACES").Count == 0 || CsvEnv("ANIP_NOTION_ALLOWED_WORKSPACES").Contains(scope.ToLowerInvariant()));
    private static bool IdAllowed(string value, string envName) => CsvEnv(envName).Count == 0 || CsvEnv(envName).Contains(value.ToLowerInvariant());
    private static bool MutationEnabled(InvocationContext context) => Environment.GetEnvironmentVariable("ANIP_NOTION_ALLOW_MUTATION") == "true" && !string.IsNullOrWhiteSpace(context?.ApprovalGrant);
    private static string Token() => Environment.GetEnvironmentVariable("NOTION_TOKEN")?.Trim() ?? "";
    private static string ApiBase() => (Environment.GetEnvironmentVariable("NOTION_API_BASE")?.Trim() ?? "https://api.notion.com/v1").TrimEnd('/');
    private static string NotionVersion() => Environment.GetEnvironmentVariable("NOTION_VERSION")?.Trim() ?? "2026-03-11";
    private static string ConfiguredDataSourceId() => !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("NOTION_DATA_SOURCE_ID")) ? Environment.GetEnvironmentVariable("NOTION_DATA_SOURCE_ID")!.Trim() : Environment.GetEnvironmentVariable("ANIP_NOTION_DATA_SOURCE_ID")?.Trim() ?? "";
    private static int BoundedLimit(object? value, int defaultValue, int maximum) => int.TryParse(Text(value), out var parsed) ? Math.Max(1, Math.Min(parsed, maximum)) : defaultValue;
    private static string Text(object? value) => value is null ? "" : value.ToString()!.Trim();
    private static List<string> CsvEnv(string name) => StringList(Environment.GetEnvironmentVariable(name)).Select(item => item.ToLowerInvariant()).ToList();
    private static List<string> StringList(object? value) => value is IEnumerable<object?> items ? items.Select(Text).Where(item => item.Length > 0).Distinct().ToList() : value is string text ? text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Distinct().ToList() : [];

    private static object? Path(object? source, params string[] keys)
    {
        var current = source;
        foreach (var key in keys)
        {
            current = ObjectMap(current).GetValueOrDefault(key);
            if (current is null) return null;
        }
        return current;
    }

    private static List<Dictionary<string, object?>> MapList(object? value)
    {
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Array)
            return element.EnumerateArray().Select(item => JsonSerializer.Deserialize<Dictionary<string, object?>>(item.GetRawText()) ?? new()).ToList();
        if (value is IEnumerable<object?> items) return items.OfType<Dictionary<string, object?>>().ToList();
        return [];
    }

    private static Dictionary<string, object?> ObjectMap(object? value)
    {
        if (value is Dictionary<string, object?> dict) return dict;
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Object) return JsonSerializer.Deserialize<Dictionary<string, object?>>(element.GetRawText()) ?? new();
        return new();
    }
}
