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

        var token = Environment.GetEnvironmentVariable("GITHUB_TOKEN")?.Trim() ?? "";
        if (string.IsNullOrWhiteSpace(token))
        {
            return Result(capability, plan, "backend_error", new() { ["github_error"] = new Dictionary<string, object?> { ["error"] = "missing_github_token" } });
        }

        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "github.repo.search_context" => SearchRepositoryContext(capability, plan, parameters, token),
            "github.issue.prepare" => PrepareOrCreateIssue(capability, plan, parameters, token, context),
            "github.pr.comment.prepare" => PreparePullRequestComment(capability, plan, parameters, token, context),
            "github.workflow.dispatch.request" => PrepareWorkflowDispatch(capability, plan, parameters, token, context),
            "github.release_notes.prepare" => PrepareReleaseNotes(capability, plan, parameters, token),
            _ => Result(capability, plan, "backend_execution_stub", new() { ["note"] = "No GitHub custom handler is registered for this capability." }),
        };
    }

    private static Dictionary<string, object?> SearchRepositoryContext(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var owner = Text(parameters.GetValueOrDefault("owner"));
        var repo = Text(parameters.GetValueOrDefault("repo"));
        if (!RepoAllowed(owner, repo)) return Restricted(capability, plan, owner, repo);
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50);
        var query = $"repo:{owner}/{repo} {Text(parameters.GetValueOrDefault("query"))}".Trim();
        var payload = GitHub("GET", $"/search/issues?q={Uri.EscapeDataString(query)}&per_page={limit}", token, null);
        if (payload.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["github_error"] = payload });
        var items = IssueItems(payload.GetValueOrDefault("items"), limit);
        return Result(capability, plan, "completed", new() { ["github_query"] = query, ["result"] = new Dictionary<string, object?> { ["items"] = items, ["count"] = items.Count, ["total_count"] = payload.GetValueOrDefault("total_count") } });
    }

    private static Dictionary<string, object?> PrepareOrCreateIssue(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token, InvocationContext context)
    {
        var repoContext = RepoMetadata(capability, plan, parameters, token);
        if (repoContext.Error is not null) return repoContext.Error;
        var body = new Dictionary<string, object?> { ["title"] = Text(parameters.GetValueOrDefault("title")), ["body"] = Text(parameters.GetValueOrDefault("body")) };
        var labels = StringList(parameters.GetValueOrDefault("labels"));
        var assignees = StringList(parameters.GetValueOrDefault("assignees"));
        if (labels.Count > 0) body["labels"] = labels;
        if (assignees.Count > 0) body["assignees"] = assignees;
        var preview = WritePreview(capability, plan, "issues.create", $"/repos/{repoContext.Owner}/{repoContext.Repo}/issues", body, repoContext.Payload!);
        if (!MutationEnabled(context)) return preview;
        var created = GitHub("POST", $"/repos/{Uri.EscapeDataString(repoContext.Owner)}/{Uri.EscapeDataString(repoContext.Repo)}/issues", token, body);
        if (created.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["github_error"] = created;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["created_issue"] = new Dictionary<string, object?> { ["number"] = created.GetValueOrDefault("number"), ["html_url"] = created.GetValueOrDefault("html_url"), ["state"] = created.GetValueOrDefault("state") };
        preview["note"] = "Created GitHub issue after the ANIP runtime validated and reserved an approval grant.";
        return preview;
    }

    private static Dictionary<string, object?> PreparePullRequestComment(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token, InvocationContext context)
    {
        var repoContext = RepoMetadata(capability, plan, parameters, token);
        if (repoContext.Error is not null) return repoContext.Error;
        var pullNumber = Text(parameters.GetValueOrDefault("pull_number"));
        var pull = GitHub("GET", $"/repos/{Uri.EscapeDataString(repoContext.Owner)}/{Uri.EscapeDataString(repoContext.Repo)}/pulls/{Uri.EscapeDataString(pullNumber)}", token, null);
        if (pull.ContainsKey("error")) return Result(capability, plan, "backend_error", new() { ["github_error"] = pull });
        var body = new Dictionary<string, object?> { ["body"] = $"[{FirstNonEmpty(Text(parameters.GetValueOrDefault("comment_purpose")), "triage_update")}] {Text(parameters.GetValueOrDefault("context"))}".Trim() };
        var preview = WritePreview(capability, plan, "issues.createComment", $"/repos/{repoContext.Owner}/{repoContext.Repo}/issues/{pullNumber}/comments", body, repoContext.Payload!);
        preview["pull_request"] = new Dictionary<string, object?> { ["number"] = pull.GetValueOrDefault("number"), ["title"] = pull.GetValueOrDefault("title"), ["state"] = pull.GetValueOrDefault("state") };
        if (!MutationEnabled(context)) return preview;
        var posted = GitHub("POST", $"/repos/{Uri.EscapeDataString(repoContext.Owner)}/{Uri.EscapeDataString(repoContext.Repo)}/issues/{Uri.EscapeDataString(pullNumber)}/comments", token, body);
        if (posted.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["github_error"] = posted;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["posted_comment"] = new Dictionary<string, object?> { ["id"] = posted.GetValueOrDefault("id"), ["html_url"] = posted.GetValueOrDefault("html_url") };
        return preview;
    }

    private static Dictionary<string, object?> PrepareWorkflowDispatch(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token, InvocationContext context)
    {
        var repoContext = RepoMetadata(capability, plan, parameters, token);
        if (repoContext.Error is not null) return repoContext.Error;
        var workflowId = Text(parameters.GetValueOrDefault("workflow_id"));
        var body = new Dictionary<string, object?> { ["ref"] = Text(parameters.GetValueOrDefault("ref")), ["inputs"] = ObjectMap(parameters.GetValueOrDefault("inputs")) };
        var preview = WritePreview(capability, plan, "actions.createWorkflowDispatch", $"/repos/{repoContext.Owner}/{repoContext.Repo}/actions/workflows/{workflowId}/dispatches", body, repoContext.Payload!);
        if (!MutationEnabled(context)) return preview;
        var dispatched = GitHub("POST", $"/repos/{Uri.EscapeDataString(repoContext.Owner)}/{Uri.EscapeDataString(repoContext.Repo)}/actions/workflows/{Uri.EscapeDataString(workflowId)}/dispatches", token, body);
        if (dispatched.ContainsKey("error"))
        {
            preview["execution_status"] = "backend_error";
            preview["github_error"] = dispatched;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["dispatched_workflow"] = new Dictionary<string, object?> { ["workflow_id"] = workflowId, ["ref"] = body["ref"] };
        return preview;
    }

    private static Dictionary<string, object?> PrepareReleaseNotes(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var repoContext = RepoMetadata(capability, plan, parameters, token);
        if (repoContext.Error is not null) return repoContext.Error;
        var range = Text(parameters.GetValueOrDefault("range"));
        return Result(capability, plan, "completed", new()
        {
            ["result"] = new Dictionary<string, object?>
            {
                ["title"] = $"Release notes for {repoContext.Owner}/{repoContext.Repo} {range}",
                ["audience"] = FirstNonEmpty(Text(parameters.GetValueOrDefault("audience")), "internal"),
                ["repository"] = RepoSummary(repoContext.Payload!),
                ["range"] = range,
                ["sections"] = new[]
                {
                    new Dictionary<string, object?> { ["title"] = "Highlights", ["items"] = new[] { "Review bounded GitHub context before publishing release notes." } },
                    new Dictionary<string, object?> { ["title"] = "Governance", ["items"] = new[] { "This capability drafts content only and does not create a GitHub release." } },
                },
            },
            ["mutation_performed"] = false,
        });
    }

    public static Dictionary<string, object?> GitHub(string method, string path, string token, Dictionary<string, object?>? body)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), $"https://api.github.com{path}");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("anip-github-fronting-showcase");
        request.Headers.TryAddWithoutValidation("X-GitHub-Api-Version", "2022-11-28");
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        var response = Http.Send(request);
        var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
        var payload = string.IsNullOrWhiteSpace(text) ? new Dictionary<string, object?>() : JsonSerializer.Deserialize<Dictionary<string, object?>>(text)!;
        if (!response.IsSuccessStatusCode) return new Dictionary<string, object?> { ["error"] = "github_http_error", ["status"] = (int)response.StatusCode, ["detail"] = payload };
        return payload;
    }

    private static RepoContext RepoMetadata(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var owner = Text(parameters.GetValueOrDefault("owner"));
        var repo = Text(parameters.GetValueOrDefault("repo"));
        if (!RepoAllowed(owner, repo)) return new RepoContext(owner, repo, null, Restricted(capability, plan, owner, repo));
        var payload = GitHub("GET", $"/repos/{Uri.EscapeDataString(owner)}/{Uri.EscapeDataString(repo)}", token, null);
        if (payload.ContainsKey("error")) return new RepoContext(owner, repo, null, Result(capability, plan, "backend_error", new() { ["github_error"] = payload }));
        return new RepoContext(owner, repo, payload, null);
    }

    private static Dictionary<string, object?> WritePreview(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string action, string path, Dictionary<string, object?> body, Dictionary<string, object?> repoPayload) =>
        Result(capability, plan, "prepared", new()
        {
            ["approval_required"] = true,
            ["mutation_performed"] = false,
            ["github_action"] = action,
            ["github_metadata"] = RepoSummary(repoPayload),
            ["github_request"] = new Dictionary<string, object?> { ["method"] = "POST", ["path"] = path, ["body"] = body },
            ["note"] = "Prepared a GitHub request payload. No GitHub mutation was performed.",
        });

    private static Dictionary<string, object?> RepoSummary(Dictionary<string, object?> payload)
    {
        var owner = ObjectMap(payload.GetValueOrDefault("owner"));
        return new Dictionary<string, object?> { ["owner"] = owner.GetValueOrDefault("login"), ["repo"] = payload.GetValueOrDefault("name"), ["default_branch"] = payload.GetValueOrDefault("default_branch"), ["private"] = payload.GetValueOrDefault("private"), ["html_url"] = payload.GetValueOrDefault("html_url") };
    }

    private static Dictionary<string, object?> Result(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string status, Dictionary<string, object?> extra)
    {
        var result = new Dictionary<string, object?> { ["execution_status"] = status, ["capability_id"] = capability.GetValueOrDefault("capability_id"), ["selected_backend"] = plan.GetValueOrDefault("selected_binding"), ["semantic_input"] = plan.GetValueOrDefault("semantic_input"), ["backend_input_contract"] = plan.GetValueOrDefault("backend_input_contract") };
        foreach (var item in extra) result[item.Key] = item.Value;
        return result;
    }

    private static Dictionary<string, object?> Restricted(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string owner, string repo) =>
        Result(capability, plan, "restricted", new() { ["repository"] = new Dictionary<string, object?> { ["owner"] = owner, ["repo"] = repo }, ["reason"] = "GitHub repository is outside the configured ANIP repository policy." });

    private static bool RepoAllowed(string owner, string repo)
    {
        var key = $"{owner}/{repo}".ToLowerInvariant();
        var blocked = CsvEnv("ANIP_GITHUB_BLOCKED_REPOS");
        var allowed = CsvEnv("ANIP_GITHUB_ALLOWED_REPOS");
        return !blocked.Contains(key) && (allowed.Count == 0 || allowed.Contains(key));
    }

    private static bool MutationEnabled(InvocationContext context) =>
        Environment.GetEnvironmentVariable("ANIP_GITHUB_ALLOW_MUTATION") == "true" && !string.IsNullOrWhiteSpace(context?.ApprovalGrant);

    private static List<Dictionary<string, object?>> IssueItems(object? value, int limit)
    {
        var result = new List<Dictionary<string, object?>>();
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray())
            {
                if (result.Count >= limit) break;
                result.Add(new()
                {
                    ["number"] = Get(item, "number"),
                    ["title"] = Get(item, "title"),
                    ["state"] = Get(item, "state"),
                    ["html_url"] = Get(item, "html_url"),
                    ["kind"] = item.TryGetProperty("pull_request", out _) ? "pull_request" : "issue",
                });
            }
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

    private static string Get(JsonElement element, string key) => element.TryGetProperty(key, out var value) ? (value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : value.ToString()) : "";
    private static string FirstNonEmpty(params string[] values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    private static int BoundedLimit(object? value, int defaultValue, int maximum) => int.TryParse(Text(value), out var parsed) ? Math.Max(1, Math.Min(parsed, maximum)) : defaultValue;
    private static string Text(object? value) => value is null ? "" : value.ToString()!.Trim();
    private static List<string> CsvEnv(string name) => (Environment.GetEnvironmentVariable(name) ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Select(item => item.ToLowerInvariant()).Distinct().ToList();
    private static List<string> StringList(object? value) => value is IEnumerable<object?> items ? items.Select(Text).Where(item => item.Length > 0).Distinct().ToList() : value is string text ? text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Distinct().ToList() : [];

    private sealed record RepoContext(string Owner, string Repo, Dictionary<string, object?>? Payload, Dictionary<string, object?>? Error);
}
