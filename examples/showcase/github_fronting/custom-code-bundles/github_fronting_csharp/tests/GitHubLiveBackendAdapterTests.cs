using Xunit;
using Anip.Core;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class GitHubLiveBackendAdapterTests
{
    // Principals the 0.2.0 runtime policy bindings select.
    private const string Drafter = "human:local-dev|actor_id=release_notes_drafter";
    private const string IssueRequester = "human:local-dev|actor_id=issue_requester";
    private const string NoBindingDetail = "No runtime policy binding matches the current actor for this capability.";

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

        var capability = IssueCapability();
        var parameters = new Dictionary<string, object?> { ["owner"] = owner, ["repo"] = repo, ["title"] = $"ANIP approved GitHub C# issue at {DateTimeOffset.UtcNow:O}", ["body"] = "Created by explicit ANIP GitHub C# generated-handler smoke." };

        // release_notes_drafter may prepare issues: without a grant it gets a preview.
        var preview = capability.Handler(Context(Drafter, null), parameters);
        Assert.Equal("prepared", preview["execution_status"]);
        Assert.Equal(false, preview["mutation_performed"]);

        // issue_requester's binding requires approval: no grant, no adapter call.
        var approval = Assert.Throws<AnipError>(() => capability.Handler(Context(IssueRequester, null), parameters));
        Assert.Equal("approval_required", approval.ErrorType);

        if (Environment.GetEnvironmentVariable("ANIP_GITHUB_ALLOW_MUTATION") == "true")
        {
            // The runtime sets the approval grant only after validating it.
            var created = capability.Handler(Context(IssueRequester, "grant_live_csharp_github_smoke"), parameters);
            Assert.Equal("completed", created["execution_status"]);
            Assert.Equal(true, created["mutation_performed"]);
            Assert.NotNull(((Dictionary<string, object?>)created["created_issue"]!)["number"]);
        }
    }

    // The generated policy refuses a principal no binding selects before the
    // backend adapter runs, so this needs no GitHub credentials.
    [Theory]
    [InlineData("human:local-dev")]
    [InlineData("human:local-dev|actor_id=github_fronting_consumer")]
    public void GeneratedHandlerRefusesUnboundActors(string principal)
    {
        var parameters = new Dictionary<string, object?> { ["owner"] = "anip-smoke", ["repo"] = "sandbox", ["title"] = "Refused", ["body"] = "Never reaches GitHub." };
        var error = Assert.Throws<AnipError>(() => IssueCapability().Handler(Context(principal, "grant_live_csharp_github_smoke"), parameters));
        Assert.Equal("denied", error.ErrorType);
        Assert.Equal(NoBindingDetail, error.Detail);
    }

    private static Anip.Service.CapabilityDef IssueCapability() =>
        GeneratedCapabilities.CreateAll(BackendAdapter.Default).First(item => item.Declaration.Name == "github.issue.prepare");

    private static Dictionary<string, object?> Capability(string id) => GeneratedRuntimeTarget.Capabilities.First(item => item["capability_id"]?.ToString() == id);

    private static Dictionary<string, object?> Plan(Dictionary<string, object?> parameters) => new()
    {
        ["selected_binding"] = null,
        ["semantic_input"] = parameters,
        ["adapter_input"] = parameters,
        ["backend_input_contract"] = new Dictionary<string, object?> { ["mode"] = "explicit", ["required"] = Array.Empty<string>(), ["optional"] = Array.Empty<string>() },
        ["unresolved_required_backend_inputs"] = Array.Empty<string>(),
    };

    private static Anip.Service.InvocationContext Context(string principal, string? grantId) => new(
        token: null!,
        rootPrincipal: principal,
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
