using Xunit;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class GitLabLiveBackendAdapterTests
{
    [Fact]
    public void ExecutesLiveReadsAndPreparedPreviewsWithoutMutation()
    {
        var token = Environment.GetEnvironmentVariable("GITLAB_TOKEN");
        var project = ProjectId();
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(project)) return;

        var searchParams = new Dictionary<string, object?> { ["project_id"] = project, ["query"] = "ANIP", ["limit"] = 5 };
        var search = BackendAdapter.Default(Capability("gitlab.project.search_context"), Plan(searchParams), searchParams, null!);
        Assert.Equal("completed", search["execution_status"]);

        var issueParams = new Dictionary<string, object?> { ["project_id"] = project, ["title"] = "ANIP GitLab C# preview", ["body"] = "Preview only" };
        var issue = BackendAdapter.Default(Capability("gitlab.issue.prepare"), Plan(issueParams), issueParams, null!);
        Assert.Equal("prepared", issue["execution_status"]);
        Assert.Equal(false, issue["mutation_performed"]);

        var notesParams = new Dictionary<string, object?> { ["project_id"] = project, ["range"] = "HEAD", ["audience"] = "internal" };
        var notes = BackendAdapter.Default(Capability("gitlab.release_notes.prepare"), Plan(notesParams), notesParams, null!);
        Assert.Equal("completed", notes["execution_status"]);
    }

    [Fact]
    public void GeneratedHandlerStopsWithoutApprovalAndCreatesWithGrant()
    {
        var token = Environment.GetEnvironmentVariable("GITLAB_TOKEN");
        var project = ProjectId();
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(project)) return;

        var capability = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
            .First(item => item.Declaration.Name == "gitlab.issue.prepare");
        var parameters = new Dictionary<string, object?> { ["project_id"] = project, ["namespace"] = Namespace(project), ["project"] = ProjectName(project), ["title"] = $"ANIP approved GitLab C# issue at {DateTimeOffset.UtcNow:O}", ["body"] = "Created by explicit ANIP GitLab C# generated-handler smoke." };

        var requestApproval = new Dictionary<string, object?>(parameters) { ["request_execution_approval"] = true };
        var preview = capability.Handler(ApprovalContext(null), requestApproval);
        Assert.Equal("prepared", preview["execution_status"]);
        Assert.Equal(false, preview["mutation_performed"]);

        if (Environment.GetEnvironmentVariable("ANIP_GITLAB_ALLOW_MUTATION") == "true")
        {
            var created = capability.Handler(ApprovalContext("grant_live_csharp_gitlab_smoke"), parameters);
            Assert.Equal("completed", created["execution_status"]);
            Assert.Equal(true, created["mutation_performed"]);
            Assert.NotNull(((Dictionary<string, object?>)created["created_issue"]!)["iid"]);
        }
    }

    private static string ProjectId()
    {
        var explicitId = Environment.GetEnvironmentVariable("GITLAB_PROJECT_ID");
        if (!string.IsNullOrWhiteSpace(explicitId)) return explicitId;
        var ns = Environment.GetEnvironmentVariable("GITLAB_NAMESPACE");
        var project = Environment.GetEnvironmentVariable("GITLAB_PROJECT");
        return !string.IsNullOrWhiteSpace(ns) && !string.IsNullOrWhiteSpace(project) ? $"{ns}/{project}" : "";
    }

    private static string Namespace(string projectId)
    {
        var explicitValue = Environment.GetEnvironmentVariable("GITLAB_NAMESPACE");
        if (!string.IsNullOrWhiteSpace(explicitValue)) return explicitValue;
        var parts = projectId.Split('/', 2);
        return parts.Length == 2 ? parts[0] : "";
    }

    private static string ProjectName(string projectId)
    {
        var explicitValue = Environment.GetEnvironmentVariable("GITLAB_PROJECT");
        if (!string.IsNullOrWhiteSpace(explicitValue)) return explicitValue;
        var parts = projectId.Split('/', 2);
        return parts.Length == 2 ? parts[1] : "";
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

    private static Anip.Service.InvocationContext ApprovalContext(string? grantId) => new(
        token: null!,
        rootPrincipal: "human:local-dev|actor_id=gitlab_fronting_consumer",
        subject: "agent:gitlab-live-smoke",
        scopes: ["gitlab.issue.prepare"],
        delegationChain: [],
        invocationId: "inv-test",
        clientReferenceId: null,
        taskId: null,
        parentInvocationId: null,
        emitProgress: _ => true,
        approvalGrant: grantId);
}
