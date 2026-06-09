using Xunit;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class JiraLiveBackendAdapterTests
{
    [Fact]
    public void ExecutesLiveReadsAndPreparedPreviewsWithoutMutation()
    {
        var config = BackendAdapter.JiraConfig.Read();
        if (config is null) return;

        var projects = BackendAdapter.Jira(config, "GET", "/rest/api/3/project/search", new() { ["maxResults"] = "1" });
        var projectKey = FirstString((System.Text.Json.JsonElement)projects["values"]!);
        var issuesPayload = BackendAdapter.Jira(config, "GET", "/rest/api/3/search/jql", new() { ["jql"] = $"project = {projectKey} ORDER BY updated DESC", ["maxResults"] = "2", ["fields"] = "summary,status,issuetype,project" });
        var issues = (System.Text.Json.JsonElement)issuesPayload["issues"]!;
        Assert.True(issues.GetArrayLength() > 0);
        var issueKey = issues[0].GetProperty("key").GetString()!;
        var secondIssueKey = issues.GetArrayLength() > 1 ? issues[1].GetProperty("key").GetString()! : issueKey;

        var search = BackendAdapter.Default(Capability("jira.backlog.search_context"), Plan(new() { ["project_key"] = projectKey, ["query"] = "test", ["limit"] = 5 }), new() { ["project_key"] = projectKey, ["query"] = "test", ["limit"] = 5 }, null!);
        Assert.Equal("completed", search["execution_status"]);
        var issue = BackendAdapter.Default(Capability("jira.issue.get_context"), Plan(new() { ["issue_key"] = issueKey, ["include_comments"] = true }), new() { ["issue_key"] = issueKey, ["include_comments"] = true }, null!);
        Assert.Equal("completed", issue["execution_status"]);

        var previews = new Dictionary<string, Dictionary<string, object?>>
        {
            ["jira.incident_bug.prepare"] = new() { ["project_key"] = projectKey, ["summary"] = "ANIP smoke bug", ["description"] = "Preview only", ["severity"] = "sev3", ["labels"] = new object[] { "anip-smoke" } },
            ["jira.story.prepare"] = new() { ["project_key"] = projectKey, ["summary"] = "ANIP smoke story", ["acceptance_criteria"] = new object[] { "Given ANIP", "Then no mutation" }, ["priority"] = "medium" },
            ["jira.subtask.prepare"] = new() { ["parent_issue_key"] = issueKey, ["summary"] = "ANIP smoke subtask", ["description"] = "Preview only" },
            ["jira.customer_escalation.comment.prepare"] = new() { ["issue_key"] = issueKey, ["comment_purpose"] = "triage_update", ["context"] = "Preview only", ["visibility"] = "internal" },
            ["jira.workflow_transition.request"] = new() { ["issue_key"] = issueKey, ["target_status"] = "To Do", ["reason"] = "Preview only", ["comment"] = "Preview only" },
            ["jira.sprint_move.request"] = new() { ["issue_keys"] = new object[] { issueKey }, ["target_sprint"] = "preview-sprint", ["reason"] = "Preview only" },
            ["jira.assignee_change.request"] = new() { ["issue_key"] = issueKey, ["assignee_ref"] = "preview-account-id", ["reason"] = "Preview only" },
            ["jira.issue_link.request"] = new() { ["source_issue_key"] = issueKey, ["target_issue_key"] = secondIssueKey, ["link_type"] = "Relates", ["reason"] = "Preview only" },
        };

        foreach (var item in previews)
        {
            var result = BackendAdapter.Default(Capability(item.Key), Plan(item.Value), item.Value, null!);
            Assert.Equal("prepared", result["execution_status"]);
            Assert.Equal(false, result["mutation_performed"]);
        }
    }

    private static Dictionary<string, object?> Capability(string id) => GeneratedRuntimeTarget.Capabilities.First(item => item["capability_id"]?.ToString() == id);

    private static Dictionary<string, object?> Plan(Dictionary<string, object?> parameters) => new()
    {
        ["selected_binding"] = null,
        ["semantic_input"] = parameters,
        ["adapter_input"] = parameters,
        ["backend_input_contract"] = new Dictionary<string, object?> { ["mode"] = "explicit", ["required"] = Array.Empty<string>(), ["optional"] = Array.Empty<string>() },
        ["unresolved_required_backend_inputs"] = Array.Empty<string>(),
    };

    private static string FirstString(System.Text.Json.JsonElement values) => values[0].GetProperty("key").GetString()!;
}
