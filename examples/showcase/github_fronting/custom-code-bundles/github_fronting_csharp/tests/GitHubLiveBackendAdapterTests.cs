using Xunit;
using Anip.Core;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class GitHubLiveBackendAdapterTests
{
    [Fact]
    public void ExecutesLiveReadsAndPreparedPreviewsWithoutMutation()
    {
        var token = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        var owner = Environment.GetEnvironmentVariable("GITHUB_OWNER");
        var repo = Environment.GetEnvironmentVariable("GITHUB_REPO");
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(owner) || string.IsNullOrWhiteSpace(repo)) return;

        var searchParams = new Dictionary<string, object?> { ["owner"] = owner, ["repo"] = repo, ["query"] = "is:issue", ["limit"] = 5 };
        var search = BackendAdapter.Default(Capability("github.repo.search_context"), Plan(searchParams), searchParams, null!);
        Assert.Equal("completed", search["execution_status"]);

        var issueParams = new Dictionary<string, object?> { ["owner"] = owner, ["repo"] = repo, ["title"] = "ANIP GitHub C# preview", ["body"] = "Preview only" };
        var issue = BackendAdapter.Default(Capability("github.issue.prepare"), Plan(issueParams), issueParams, null!);
        Assert.Equal("prepared", issue["execution_status"]);
        Assert.Equal(false, issue["mutation_performed"]);

        var notesParams = new Dictionary<string, object?> { ["owner"] = owner, ["repo"] = repo, ["range"] = "HEAD", ["audience"] = "internal" };
        var notes = BackendAdapter.Default(Capability("github.release_notes.prepare"), Plan(notesParams), notesParams, null!);
        Assert.Equal("completed", notes["execution_status"]);
    }

    [Fact]
    public void GeneratedHandlerStopsWithoutApprovalAndCreatesWithGrant()
    {
        var token = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        var owner = Environment.GetEnvironmentVariable("GITHUB_OWNER");
        var repo = Environment.GetEnvironmentVariable("GITHUB_REPO");
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(owner) || string.IsNullOrWhiteSpace(repo)) return;

        var capability = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
            .First(item => item.Declaration.Name == "github.issue.prepare");
        var parameters = new Dictionary<string, object?> { ["owner"] = owner, ["repo"] = repo, ["title"] = $"ANIP approved GitHub C# issue at {DateTimeOffset.UtcNow:O}", ["body"] = "Created by explicit ANIP GitHub C# generated-handler smoke." };

        var requestApproval = new Dictionary<string, object?>(parameters) { ["request_execution_approval"] = true };
        var preview = capability.Handler(ApprovalContext(null), requestApproval);
        Assert.Equal("prepared", preview["execution_status"]);
        Assert.Equal(false, preview["mutation_performed"]);

        if (Environment.GetEnvironmentVariable("ANIP_GITHUB_ALLOW_MUTATION") == "true")
        {
            var created = capability.Handler(ApprovalContext("grant_live_csharp_github_smoke"), parameters);
            Assert.Equal("completed", created["execution_status"]);
            Assert.Equal(true, created["mutation_performed"]);
            Assert.NotNull(((Dictionary<string, object?>)created["created_issue"]!)["number"]);
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

    private static Anip.Service.InvocationContext ApprovalContext(string? grantId) => new(
        token: null!,
        rootPrincipal: "human:local-dev|actor_id=github_fronting_consumer",
        subject: "agent:github-live-smoke",
        scopes: ["github.issue.prepare"],
        delegationChain: [],
        invocationId: "inv-test",
        clientReferenceId: null,
        taskId: null,
        parentInvocationId: null,
        emitProgress: _ => true,
        approvalGrant: grantId);
}
