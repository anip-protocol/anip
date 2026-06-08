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
        InvocationContext _context)
    {
        var unresolved = StringList(plan.GetValueOrDefault("unresolved_required_backend_inputs"));
        if (unresolved.Count > 0)
        {
            return Result(capability, plan, "backend_input_incomplete", new() { ["unresolved_required_backend_inputs"] = unresolved });
        }

        var config = JiraConfig.Read();
        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "jira.backlog.search_context" => SearchBacklog(capability, plan, parameters, config),
            "jira.issue.get_context" => GetIssueContext(capability, plan, parameters, config),
            "jira.release_notes.prepare" => PrepareReleaseNotes(capability, plan, parameters, config),
            "jira.incident_bug.prepare" => PrepareIssueCreate(capability, plan, parameters, "Bug"),
            "jira.story.prepare" => PrepareIssueCreate(capability, plan, parameters, "Story"),
            "jira.subtask.prepare" => PrepareSubtask(capability, plan, parameters, config),
            "jira.customer_escalation.comment.prepare" => Preview(capability, plan, "add_comment", new() { ["method"] = "POST", ["path"] = $"/rest/api/3/issue/{Text(parameters.GetValueOrDefault("issue_key"))}/comment", ["body"] = new Dictionary<string, object?> { ["body"] = Adf($"[{Text(parameters.GetValueOrDefault("comment_purpose"))}] {Text(parameters.GetValueOrDefault("context"))}"), ["visibility"] = FirstNonEmpty(Text(parameters.GetValueOrDefault("visibility")), "internal") } }, new() { ["issue_key"] = parameters.GetValueOrDefault("issue_key"), ["visibility"] = FirstNonEmpty(Text(parameters.GetValueOrDefault("visibility")), "internal"), ["comment_purpose"] = parameters.GetValueOrDefault("comment_purpose") }),
            "jira.workflow_transition.request" => Preview(capability, plan, "transition_issue", new() { ["method"] = "POST", ["path"] = $"/rest/api/3/issue/{Text(parameters.GetValueOrDefault("issue_key"))}/transitions", ["body"] = new Dictionary<string, object?> { ["transition"] = new Dictionary<string, object?> { ["id"] = parameters.GetValueOrDefault("target_status") } } }, new() { ["issue_key"] = parameters.GetValueOrDefault("issue_key"), ["target_status"] = parameters.GetValueOrDefault("target_status") }),
            "jira.sprint_move.request" => Preview(capability, plan, "move_issues_to_sprint", new() { ["method"] = "POST", ["path"] = $"/rest/agile/1.0/sprint/{Text(parameters.GetValueOrDefault("target_sprint"))}/issue", ["body"] = new Dictionary<string, object?> { ["issues"] = ListValue(parameters.GetValueOrDefault("issue_keys")) } }, new() { ["issue_keys"] = ListValue(parameters.GetValueOrDefault("issue_keys")), ["target_sprint"] = parameters.GetValueOrDefault("target_sprint") }),
            "jira.assignee_change.request" => Preview(capability, plan, "assign_issue", new() { ["method"] = "PUT", ["path"] = $"/rest/api/3/issue/{Text(parameters.GetValueOrDefault("issue_key"))}/assignee", ["body"] = new Dictionary<string, object?> { ["accountId"] = parameters.GetValueOrDefault("assignee_ref") } }, new() { ["issue_key"] = parameters.GetValueOrDefault("issue_key"), ["assignee_ref"] = parameters.GetValueOrDefault("assignee_ref") }),
            "jira.issue_link.request" => Preview(capability, plan, "link_issues", new() { ["method"] = "POST", ["path"] = "/rest/api/3/issueLink", ["body"] = new Dictionary<string, object?> { ["type"] = new Dictionary<string, object?> { ["name"] = parameters.GetValueOrDefault("link_type") }, ["inwardIssue"] = new Dictionary<string, object?> { ["key"] = parameters.GetValueOrDefault("source_issue_key") }, ["outwardIssue"] = new Dictionary<string, object?> { ["key"] = parameters.GetValueOrDefault("target_issue_key") }, ["comment"] = new Dictionary<string, object?> { ["body"] = Adf(parameters.GetValueOrDefault("reason")) } } }, new() { ["requested_link_type"] = parameters.GetValueOrDefault("link_type") }),
            _ => Result(capability, plan, "backend_execution_stub", new() { ["note"] = "No Jira custom handler is registered for this capability." }),
        };
    }

    private static Dictionary<string, object?> SearchBacklog(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, JiraConfig? config)
    {
        var jql = IssueQuery(Text(parameters.GetValueOrDefault("project_key")), Text(parameters.GetValueOrDefault("query")));
        if (!string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("issue_type")))) jql += $" AND issuetype = \"{SafeJql(parameters.GetValueOrDefault("issue_type"))}\"";
        if (!string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("status")))) jql += $" AND status = \"{SafeJql(parameters.GetValueOrDefault("status"))}\"";
        if (config is null) return Result(capability, plan, "backend_not_configured", new() { ["jql_preview"] = jql });
        var payload = SearchIssues(config, jql, BoundedLimit(parameters.GetValueOrDefault("limit"), 25, 50), "summary,status,issuetype,project,assignee,priority");
        if (payload.ContainsKey("error")) return BackendError(capability, plan, payload);
        var issues = IssueSummaries(payload.GetValueOrDefault("issues"));
        return Result(capability, plan, "completed", new() { ["jql"] = jql, ["result"] = new Dictionary<string, object?> { ["issues"] = issues, ["count"] = issues.Count, ["is_last"] = payload.GetValueOrDefault("isLast") } });
    }

    private static Dictionary<string, object?> GetIssueContext(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, JiraConfig? config)
    {
        var issueKey = Text(parameters.GetValueOrDefault("issue_key"));
        if (config is null) return Result(capability, plan, "backend_not_configured", new() { ["path_preview"] = $"/rest/api/3/issue/{issueKey}" });
        var payload = Jira(config, "GET", $"/rest/api/3/issue/{Uri.EscapeDataString(issueKey)}", new() { ["fields"] = "summary,status,issuetype,project,assignee,priority,description" });
        if (payload.ContainsKey("error")) return BackendError(capability, plan, payload);
        return Result(capability, plan, "completed", new() { ["result"] = IssueSummary(payload) });
    }

    private static Dictionary<string, object?> PrepareReleaseNotes(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, JiraConfig? config)
    {
        var releaseRef = Text(parameters.GetValueOrDefault("release_ref"));
        var audience = FirstNonEmpty(Text(parameters.GetValueOrDefault("audience")), "internal");
        var jql = releaseRef.Equals("unversioned", StringComparison.OrdinalIgnoreCase)
            ? $"project = \"{SafeJql(parameters.GetValueOrDefault("project_key"))}\" AND fixVersion is EMPTY"
            : $"project = \"{SafeJql(parameters.GetValueOrDefault("project_key"))}\" AND fixVersion = \"{SafeJql(releaseRef)}\"";
        if (!string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("issue_query")))) jql += $" AND text ~ \"{SafeJql(parameters.GetValueOrDefault("issue_query"))}\"";
        jql += " ORDER BY priority DESC, updated DESC";
        var issues = new List<Dictionary<string, object?>>();
        if (config is not null)
        {
            var payload = SearchIssues(config, jql, BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50), "summary,status,issuetype,project");
            if (payload.ContainsKey("error")) return BackendError(capability, plan, payload);
            issues = IssueSummaries(payload.GetValueOrDefault("issues"));
        }
        return Result(capability, plan, "prepared", new() { ["jql"] = jql, ["result"] = new Dictionary<string, object?> { ["audience"] = audience, ["issue_count"] = issues.Count, ["issues"] = issues, ["draft"] = ReleaseDraft(audience, releaseRef, issues) }, ["note"] = "Prepared release notes only. No Jira mutation or publication was performed." });
    }

    private static Dictionary<string, object?> PrepareIssueCreate(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string issueType)
    {
        var fields = new Dictionary<string, object?> { ["project"] = new Dictionary<string, object?> { ["key"] = parameters.GetValueOrDefault("project_key") }, ["issuetype"] = new Dictionary<string, object?> { ["name"] = issueType }, ["summary"] = Text(parameters.GetValueOrDefault("summary")) };
        if (Text(capability.GetValueOrDefault("capability_id")) == "jira.incident_bug.prepare")
        {
            fields["description"] = Adf(parameters.GetValueOrDefault("description"));
            fields["priority"] = new Dictionary<string, object?> { ["name"] = PriorityForSeverity(parameters.GetValueOrDefault("severity")) };
        }
        else
        {
            fields["description"] = Adf($"Acceptance criteria:\n{Text(parameters.GetValueOrDefault("acceptance_criteria"))}");
            if (!string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("priority")))) fields["priority"] = new Dictionary<string, object?> { ["name"] = Capitalize(Text(parameters.GetValueOrDefault("priority"))) };
        }
        var labels = Labels(parameters.GetValueOrDefault("labels"));
        if (labels.Count > 0) fields["labels"] = labels;
        return Preview(capability, plan, "create_issue", new() { ["method"] = "POST", ["path"] = "/rest/api/3/issue", ["body"] = new Dictionary<string, object?> { ["fields"] = fields } }, new() { ["project_key"] = parameters.GetValueOrDefault("project_key"), ["requested_issue_type"] = issueType });
    }

    private static Dictionary<string, object?> PrepareSubtask(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, JiraConfig? config)
    {
        var parentIssueKey = Text(parameters.GetValueOrDefault("parent_issue_key"));
        var fields = new Dictionary<string, object?> { ["parent"] = new Dictionary<string, object?> { ["key"] = parentIssueKey }, ["issuetype"] = new Dictionary<string, object?> { ["name"] = "Sub-task" }, ["summary"] = Text(parameters.GetValueOrDefault("summary")), ["description"] = Adf(parameters.GetValueOrDefault("description")) };
        if (config is not null)
        {
            var parent = Jira(config, "GET", $"/rest/api/3/issue/{Uri.EscapeDataString(parentIssueKey)}", new() { ["fields"] = "project" });
            var projectKey = Nested(parent, "fields", "project", "key");
            if (!string.IsNullOrWhiteSpace(projectKey)) fields["project"] = new Dictionary<string, object?> { ["key"] = projectKey };
            if (!string.IsNullOrWhiteSpace(Text(parent.GetValueOrDefault("id")))) fields["parent"] = new Dictionary<string, object?> { ["id"] = parent.GetValueOrDefault("id") };
        }
        return Preview(capability, plan, "create_subtask", new() { ["method"] = "POST", ["path"] = "/rest/api/3/issue", ["body"] = new Dictionary<string, object?> { ["fields"] = fields } }, new() { ["parent_issue_key"] = parentIssueKey });
    }

    private static Dictionary<string, object?> Preview(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string action, Dictionary<string, object?> request, Dictionary<string, object?> metadata) =>
        Result(capability, plan, "prepared", new() { ["approval_required"] = Text(capability.GetValueOrDefault("operation_type")) == "approval_gated" || Text(capability.GetValueOrDefault("execution_posture")) == "prepare_only", ["mutation_performed"] = false, ["jira_action"] = action, ["jira_request_preview"] = request, ["jira_metadata"] = metadata, ["note"] = "Prepared a governed Jira request preview. No Jira mutation was performed." });

    private static Dictionary<string, object?> Result(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string status, Dictionary<string, object?> extra)
    {
        var result = new Dictionary<string, object?> { ["execution_status"] = status, ["capability_id"] = capability.GetValueOrDefault("capability_id"), ["selected_backend"] = plan.GetValueOrDefault("selected_binding"), ["semantic_input"] = plan.GetValueOrDefault("semantic_input"), ["backend_input_contract"] = plan.GetValueOrDefault("backend_input_contract") };
        foreach (var item in extra) result[item.Key] = item.Value;
        return result;
    }

    private static Dictionary<string, object?> BackendError(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> payload) =>
        Result(capability, plan, "backend_error", new() { ["jira_error"] = payload });

    public static Dictionary<string, object?> Jira(JiraConfig config, string method, string path, Dictionary<string, string> query, Dictionary<string, object?>? body = null)
    {
        var uri = new UriBuilder(config.BaseUrl + path);
        uri.Query = string.Join("&", query.Select(item => $"{Uri.EscapeDataString(item.Key)}={Uri.EscapeDataString(item.Value)}"));
        using var request = new HttpRequestMessage(new HttpMethod(method), uri.Uri);
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        request.Headers.Authorization = new AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{config.Email}:{config.Token}")));
        if (body is not null) request.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        var response = Http.Send(request);
        var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
        var payload = string.IsNullOrWhiteSpace(text) ? new Dictionary<string, object?>() : JsonSerializer.Deserialize<Dictionary<string, object?>>(text)!;
        if (!response.IsSuccessStatusCode) return new Dictionary<string, object?> { ["error"] = "jira_http_error", ["status"] = (int)response.StatusCode, ["detail"] = payload };
        return payload;
    }

    private static Dictionary<string, object?> SearchIssues(JiraConfig config, string jql, int limit, string fields) =>
        Jira(config, "GET", "/rest/api/3/search/jql", new() { ["jql"] = jql, ["maxResults"] = limit.ToString(), ["fields"] = fields });

    private static string IssueQuery(string projectKey, string query)
    {
        var jql = $"project = \"{SafeJql(projectKey)}\"";
        if (!string.IsNullOrWhiteSpace(query)) jql += $" AND text ~ \"{SafeJql(query)}\"";
        return jql + " ORDER BY updated DESC";
    }

    private static Dictionary<string, object?> IssueSummary(Dictionary<string, object?> issue) => new()
    {
        ["key"] = issue.GetValueOrDefault("key"),
        ["summary"] = Nested(issue, "fields", "summary"),
        ["status"] = Nested(issue, "fields", "status", "name"),
        ["issue_type"] = Nested(issue, "fields", "issuetype", "name"),
        ["project_key"] = Nested(issue, "fields", "project", "key"),
        ["assignee"] = Nested(issue, "fields", "assignee", "displayName"),
        ["priority"] = Nested(issue, "fields", "priority", "name"),
    };

    private static List<Dictionary<string, object?>> IssueSummaries(object? value)
    {
        var result = new List<Dictionary<string, object?>>();
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray()) result.Add(IssueSummary(JsonSerializer.Deserialize<Dictionary<string, object?>>(item.GetRawText())!));
        }
        return result;
    }

    private static Dictionary<string, object?> Adf(object? value) => new() { ["type"] = "doc", ["version"] = 1, ["content"] = new object[] { new Dictionary<string, object?> { ["type"] = "paragraph", ["content"] = new object[] { new Dictionary<string, object?> { ["type"] = "text", ["text"] = Text(value) } } } } };

    private static string ReleaseDraft(string audience, string releaseRef, List<Dictionary<string, object?>> issues)
    {
        var heading = $"Release {releaseRef} notes for {audience}";
        if (issues.Count == 0) return heading + "\n\nNo matching Jira issues were returned for the bounded query.";
        return string.Join("\n", new[] { heading, "" }.Concat(issues.Select(issue => $"- {issue.GetValueOrDefault("key")}: {issue.GetValueOrDefault("summary")} ({issue.GetValueOrDefault("status")})")));
    }

    private static int BoundedLimit(object? value, int defaultValue, int maximum) => int.TryParse(Text(value), out var parsed) ? Math.Max(1, Math.Min(parsed, maximum)) : defaultValue;
    private static string SafeJql(object? value) => Text(value).Replace("\\", "\\\\").Replace("\"", "\\\"");
    private static string Text(object? value) => value is null ? "" : value.ToString()!.Trim();
    private static string FirstNonEmpty(params string[] values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    private static string Capitalize(string value) => string.IsNullOrWhiteSpace(value) ? value : char.ToUpperInvariant(value[0]) + value[1..];
    private static string PriorityForSeverity(object? value) => Text(value).ToLowerInvariant() switch { "sev1" or "sev2" => "High", "sev4" => "Low", _ => "Medium" };

    private static List<string> StringList(object? value) => value is IEnumerable<object?> items ? items.Select(Text).Where(item => item.Length > 0).ToList() : [];
    private static List<string> ListValue(object? value) => value is IEnumerable<object?> items ? items.Select(Text).Where(item => item.Length > 0).Distinct().ToList() : Text(value).Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Distinct().ToList();
    private static List<string> Labels(object? value) => ListValue(value).Select(item => System.Text.RegularExpressions.Regex.Replace(item.ToLowerInvariant(), "[^a-z0-9_.-]+", "-").Trim('-')).Where(item => item.Length > 0).ToList();

    private static string Nested(Dictionary<string, object?> value, params string[] path)
    {
        object? current = value;
        foreach (var key in path)
        {
            if (current is JsonElement element && element.ValueKind == JsonValueKind.Object)
            {
                if (!element.TryGetProperty(key, out var property)) return "";
                current = property.ValueKind == JsonValueKind.String ? property.GetString() : property;
                continue;
            }
            if (current is not Dictionary<string, object?> record || !record.TryGetValue(key, out current)) return "";
        }
        return Text(current);
    }

    public sealed record JiraConfig(string BaseUrl, string Email, string Token)
    {
        public static JiraConfig? Read()
        {
            var baseUrl = Environment.GetEnvironmentVariable("JIRA_BASE_URL")?.TrimEnd('/') ?? "";
            var email = Environment.GetEnvironmentVariable("JIRA_EMAIL") ?? "";
            var token = Environment.GetEnvironmentVariable("JIRA_API_TOKEN") ?? "";
            return string.IsNullOrWhiteSpace(baseUrl) || string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(token) ? null : new JiraConfig(baseUrl, email, token);
        }
    }
}
