using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Anip.Service;

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
        Dictionary<string, object?> parameters,
        InvocationContext context)
    {
        var unresolved = StringList(plan.GetValueOrDefault("unresolved_required_backend_inputs"));
        if (unresolved.Count > 0)
        {
            return Result(capability, plan, "backend_input_incomplete", new() { ["unresolved_required_backend_inputs"] = unresolved });
        }

        var token = Environment.GetEnvironmentVariable("GITLAB_TOKEN")?.Trim() ?? "";
        if (string.IsNullOrWhiteSpace(token))
        {
            return Result(capability, plan, "backend_error", new() { ["gitlab_error"] = new Dictionary<string, object?> { ["error"] = "missing_gitlab_token" } });
        }

        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "gitlab.project.search_context" => SearchProjectContext(capability, plan, parameters, token),
            "gitlab.issue.prepare" => PrepareOrCreateIssue(capability, plan, parameters, token, context),
            "gitlab.mr.comment.prepare" => PrepareMergeRequestComment(capability, plan, parameters, token, context),
            "gitlab.pipeline.trigger.request" => PreparePipelineTrigger(capability, plan, parameters, token),
            "gitlab.release_notes.prepare" => PrepareReleaseNotes(capability, plan, parameters, token),
            _ => Result(capability, plan, "backend_execution_stub", new() { ["note"] = "No GitLab custom handler is registered for this capability." }),
        };
    }

    private static Dictionary<string, object?> SearchProjectContext(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var project = ProjectId(parameters);
        if (!ProjectAllowed(project)) return Restricted(capability, plan, project);
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50);
        var query = Text(parameters.GetValueOrDefault("query"));
        var issues = GitLab("GET", $"/projects/{Uri.EscapeDataString(project)}/issues?search={Uri.EscapeDataString(query)}&per_page={limit}", token, null);
        var mergeRequests = GitLab("GET", $"/projects/{Uri.EscapeDataString(project)}/merge_requests?search={Uri.EscapeDataString(query)}&per_page={limit}", token, null);
        if (issues.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["gitlab_error"] = issues });
        if (mergeRequests.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["gitlab_error"] = mergeRequests });
        var items = new List<Dictionary<string, object?>>();
        foreach (var item in JsonList(issues.GetValueOrDefault("items")))
        {
            if (items.Count >= limit) break;
            items.Add(new() { ["kind"] = "issue", ["iid"] = Get(item, "iid"), ["title"] = Get(item, "title"), ["state"] = Get(item, "state"), ["web_url"] = Get(item, "web_url") });
        }
        foreach (var item in JsonList(mergeRequests.GetValueOrDefault("items")))
        {
            if (items.Count >= limit) break;
            items.Add(new() { ["kind"] = "merge_request", ["iid"] = Get(item, "iid"), ["title"] = Get(item, "title"), ["state"] = Get(item, "state"), ["web_url"] = Get(item, "web_url") });
        }
        return Result(capability, plan, "completed", new() { ["gitlab_query"] = query, ["result"] = new Dictionary<string, object?> { ["items"] = items, ["count"] = items.Count, ["project_id"] = project } });
    }

    private static Dictionary<string, object?> PrepareOrCreateIssue(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token, InvocationContext context)
    {
        var project = ProjectMetadata(capability, plan, parameters, token);
        if (project.Error is not null) return project.Error;
        var body = new Dictionary<string, object?> { ["title"] = Text(parameters.GetValueOrDefault("title")), ["description"] = FirstNonEmpty(Text(parameters.GetValueOrDefault("body")), Text(parameters.GetValueOrDefault("description"))) };
        var labels = StringList(parameters.GetValueOrDefault("labels"));
        if (labels.Count > 0) body["labels"] = string.Join(",", labels);
        var preview = WritePreview(capability, plan, "issues.create", $"/projects/{project.Id}/issues", body, project.Payload!);
        if (!MutationEnabled(context)) return preview;
        var created = GitLab("POST", $"/projects/{Uri.EscapeDataString(project.Id)}/issues", token, body);
        if (created.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["gitlab_error"] = created;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["created_issue"] = new Dictionary<string, object?> { ["iid"] = created.GetValueOrDefault("iid"), ["web_url"] = created.GetValueOrDefault("web_url"), ["state"] = created.GetValueOrDefault("state") };
        preview["note"] = "Created GitLab issue after the ANIP runtime validated and reserved an approval grant.";
        return preview;
    }

    private static Dictionary<string, object?> PrepareMergeRequestComment(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token, InvocationContext context)
    {
        var project = ProjectMetadata(capability, plan, parameters, token);
        if (project.Error is not null) return project.Error;
        var iid = Text(parameters.GetValueOrDefault("merge_request_iid"));
        var mergeRequest = GitLab("GET", $"/projects/{Uri.EscapeDataString(project.Id)}/merge_requests/{Uri.EscapeDataString(iid)}", token, null);
        if (mergeRequest.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["gitlab_error"] = mergeRequest });
        var body = new Dictionary<string, object?> { ["body"] = $"[{FirstNonEmpty(Text(parameters.GetValueOrDefault("comment_purpose")), "triage_update")}] {Text(parameters.GetValueOrDefault("context"))}".Trim() };
        var preview = WritePreview(capability, plan, "merge_requests.createNote", $"/projects/{project.Id}/merge_requests/{iid}/notes", body, project.Payload!);
        preview["merge_request"] = new Dictionary<string, object?> { ["iid"] = mergeRequest.GetValueOrDefault("iid"), ["title"] = mergeRequest.GetValueOrDefault("title"), ["state"] = mergeRequest.GetValueOrDefault("state") };
        if (!MutationEnabled(context)) return preview;
        var posted = GitLab("POST", $"/projects/{Uri.EscapeDataString(project.Id)}/merge_requests/{Uri.EscapeDataString(iid)}/notes", token, body);
        if (posted.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["gitlab_error"] = posted;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["posted_comment"] = new Dictionary<string, object?> { ["id"] = posted.GetValueOrDefault("id") };
        return preview;
    }

    private static Dictionary<string, object?> PreparePipelineTrigger(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var project = ProjectMetadata(capability, plan, parameters, token);
        if (project.Error is not null) return project.Error;
        var body = new Dictionary<string, object?> { ["ref"] = Text(parameters.GetValueOrDefault("ref")), ["variables"] = ObjectMap(parameters.GetValueOrDefault("variables")), ["purpose"] = Text(parameters.GetValueOrDefault("pipeline_purpose")) };
        return WritePreview(capability, plan, "pipeline.trigger", $"/projects/{project.Id}/pipeline", body, project.Payload!);
    }

    private static Dictionary<string, object?> PrepareReleaseNotes(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var project = ProjectMetadata(capability, plan, parameters, token);
        if (project.Error is not null) return project.Error;
        var range = Text(parameters.GetValueOrDefault("range"));
        return Result(capability, plan, "completed", new()
        {
            ["mutation_performed"] = false,
            ["result"] = new Dictionary<string, object?>
            {
                ["title"] = $"Release notes for {FirstNonEmpty(Text(project.Payload!.GetValueOrDefault("path_with_namespace")), project.Id)} {range}",
                ["audience"] = FirstNonEmpty(Text(parameters.GetValueOrDefault("audience")), "internal"),
                ["project"] = ProjectSummary(project.Payload!),
                ["range"] = range,
                ["sections"] = new[]
                {
                    new Dictionary<string, object?> { ["title"] = "Highlights", ["items"] = new[] { "Review bounded GitLab context before publishing release notes." } },
                    new Dictionary<string, object?> { ["title"] = "Governance", ["items"] = new[] { "This capability drafts content only and does not create a GitLab release." } },
                },
            },
        });
    }

    public static Dictionary<string, object?> GitLab(string method, string path, string token, Dictionary<string, object?>? body)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), $"{ApiBase()}{path}");
        request.Headers.Accept.ParseAdd("application/json");
        request.Headers.UserAgent.ParseAdd("anip-gitlab-fronting-showcase");
        request.Headers.Add("PRIVATE-TOKEN", token);
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        var response = Http.Send(request);
        var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
        var payload = ParseGitLabPayload(text);
        if (!response.IsSuccessStatusCode) return new Dictionary<string, object?> { ["error"] = "gitlab_http_error", ["status"] = (int)response.StatusCode, ["detail"] = payload };
        return payload;
    }

    private static ProjectContext ProjectMetadata(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var project = ProjectId(parameters);
        if (!ProjectAllowed(project)) return new ProjectContext(project, null, Restricted(capability, plan, project));
        var payload = GitLab("GET", $"/projects/{Uri.EscapeDataString(project)}", token, null);
        if (payload.ContainsKey("error")) return new ProjectContext(project, null, Result(capability, plan, "backend_error", new() { ["gitlab_error"] = payload }));
        return new ProjectContext(project, payload, null);
    }

    private static Dictionary<string, object?> WritePreview(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string action, string path, Dictionary<string, object?> body, Dictionary<string, object?> projectPayload) =>
        Result(capability, plan, "prepared", new()
        {
            ["approval_required"] = true,
            ["mutation_performed"] = false,
            ["gitlab_action"] = action,
            ["gitlab_metadata"] = ProjectSummary(projectPayload),
            ["gitlab_request"] = new Dictionary<string, object?> { ["method"] = "POST", ["path"] = path, ["body"] = body },
            ["note"] = "Prepared a GitLab request payload. No GitLab mutation was performed.",
        });

    private static Dictionary<string, object?> ProjectSummary(Dictionary<string, object?> payload) =>
        new() { ["id"] = payload.GetValueOrDefault("id"), ["path_with_namespace"] = payload.GetValueOrDefault("path_with_namespace"), ["default_branch"] = payload.GetValueOrDefault("default_branch"), ["visibility"] = payload.GetValueOrDefault("visibility"), ["web_url"] = payload.GetValueOrDefault("web_url") };

    private static Dictionary<string, object?> Result(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string status, Dictionary<string, object?> extra)
    {
        var result = new Dictionary<string, object?> { ["execution_status"] = status, ["capability_id"] = capability.GetValueOrDefault("capability_id"), ["selected_backend"] = plan.GetValueOrDefault("selected_binding"), ["semantic_input"] = plan.GetValueOrDefault("semantic_input"), ["backend_input_contract"] = plan.GetValueOrDefault("backend_input_contract") };
        foreach (var item in extra) result[item.Key] = item.Value;
        return result;
    }

    private static Dictionary<string, object?> Restricted(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string project) =>
        Result(capability, plan, "restricted", new() { ["project_id"] = project, ["reason"] = "GitLab project is outside the configured ANIP project policy." });

    private static string ProjectId(Dictionary<string, object?> parameters)
    {
        var explicitId = Text(parameters.GetValueOrDefault("project_id"));
        if (!string.IsNullOrWhiteSpace(explicitId)) return explicitId;
        var ns = Text(parameters.GetValueOrDefault("namespace")).Trim('/');
        var project = Text(parameters.GetValueOrDefault("project")).Trim('/');
        return !string.IsNullOrWhiteSpace(ns) && !string.IsNullOrWhiteSpace(project) ? $"{ns}/{project}" : "";
    }

    private static bool ProjectAllowed(string project)
    {
        var key = project.ToLowerInvariant();
        var blocked = CsvEnv("ANIP_GITLAB_BLOCKED_PROJECTS");
        var allowed = CsvEnv("ANIP_GITLAB_ALLOWED_PROJECTS");
        return !blocked.Contains(key) && (allowed.Count == 0 || allowed.Contains(key));
    }

    private static bool MutationEnabled(InvocationContext context) =>
        Environment.GetEnvironmentVariable("ANIP_GITLAB_ALLOW_MUTATION") == "true" && !string.IsNullOrWhiteSpace(context?.ApprovalGrant);

    private static string ApiBase()
    {
        var raw = Environment.GetEnvironmentVariable("GITLAB_API_BASE") ?? "https://gitlab.com/api/v4";
        return raw.TrimEnd('/');
    }

    private static Dictionary<string, object?> ParseGitLabPayload(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return new();
        var trimmed = text.TrimStart();
        if (trimmed.StartsWith("[", StringComparison.Ordinal)) return new() { ["items"] = JsonSerializer.Deserialize<JsonElement>(text) };
        return JsonSerializer.Deserialize<Dictionary<string, object?>>(text) ?? new();
    }

    private static List<JsonElement> JsonList(object? value)
    {
        var result = new List<JsonElement>();
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray()) result.Add(item);
        }
        return result;
    }

    private static Dictionary<string, object?> ObjectMap(object? value)
    {
        if (value is Dictionary<string, object?> dict) return dict;
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Object)
        {
            return JsonSerializer.Deserialize<Dictionary<string, object?>>(element.GetRawText()) ?? new();
        }
        return new();
    }

    private static object? Get(JsonElement element, string key) => element.TryGetProperty(key, out var value) ? value.ValueKind == JsonValueKind.String ? value.GetString() : value.ToString() : null;
    private static string FirstNonEmpty(params string[] values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    private static int BoundedLimit(object? value, int defaultValue, int maximum) => int.TryParse(Text(value), out var parsed) ? Math.Max(1, Math.Min(parsed, maximum)) : defaultValue;
    private static string Text(object? value) => value is null ? "" : value.ToString()!.Trim();
    private static List<string> CsvEnv(string name) => (Environment.GetEnvironmentVariable(name) ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Select(item => item.ToLowerInvariant()).Distinct().ToList();
    private static List<string> StringList(object? value) => value is IEnumerable<object?> items ? items.Select(Text).Where(item => item.Length > 0).Distinct().ToList() : value is string text ? text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Distinct().ToList() : [];

    private sealed record ProjectContext(string Id, Dictionary<string, object?>? Payload, Dictionary<string, object?>? Error);
}
