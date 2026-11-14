using Anip.Core;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};
using Xunit;

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class NotionLiveBackendAdapterTests
{
    // Principals the 0.2.0 runtime policy bindings select.
    private const string Reviewer = "human:local-dev|actor_id=notion_governance_reviewer";
    private const string Requester = "human:local-dev|actor_id=governed_notion_requester";
    private const string NoBindingDetail = "No runtime policy binding matches the current actor for this capability.";

    [Fact]
    public void ExecutesLiveReadsAndPreparedPreviewsWithoutMutation()
    {
        if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("NOTION_TOKEN"))) return;
        var workspaceScope = Env("NOTION_WORKSPACE_SCOPE");
        var parentId = Env("NOTION_PARENT_PAGE_ID");
        var databaseId = Env("NOTION_DATABASE_ID");

        var searchParams = new Dictionary<string, object?> { ["workspace_scope"] = workspaceScope, ["query"] = "ANIP", ["limit"] = 5 };
        var search = BackendAdapter.Default(Capability("notion.workspace.search_context"), Plan(searchParams), searchParams, null!);
        Assert.True(Equals("completed", search["execution_status"]), $"Search failed: {System.Text.Json.JsonSerializer.Serialize(search)}");

        var queryParams = new Dictionary<string, object?> { ["database_id"] = databaseId, ["limit"] = 5 };
        var query = BackendAdapter.Default(Capability("notion.database.query_context"), Plan(queryParams), queryParams, null!);
        Assert.True(Equals("completed", query["execution_status"]), $"Query failed: {System.Text.Json.JsonSerializer.Serialize(query)}");

        var createParams = new Dictionary<string, object?> { ["parent_id"] = parentId, ["title"] = "ANIP Notion C# preview", ["content_summary"] = "Preview only" };
        var create = BackendAdapter.Default(Capability("notion.page.create.prepare"), Plan(createParams), createParams, null!);
        Assert.Equal("prepared", create["execution_status"]);
        Assert.Equal(false, create["mutation_performed"]);
    }

    [Fact]
    public void GeneratedHandlerStopsWithoutApprovalAndCreatesWithGrant()
    {
        if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("NOTION_TOKEN"))) return;
        var parentId = Env("NOTION_PARENT_PAGE_ID");
        var capability = PageCreateCapability();
        var parameters = new Dictionary<string, object?> { ["parent_id"] = parentId, ["title"] = $"ANIP approved Notion C# page at {DateTimeOffset.UtcNow:O}", ["content_summary"] = "Created by explicit ANIP Notion C# generated-handler smoke." };

        // notion_governance_reviewer may create pages: without a grant it gets a preview.
        var preview = capability.Handler(Context(Reviewer, null), parameters);
        Assert.Equal("prepared", preview["execution_status"]);
        Assert.Equal(false, preview["mutation_performed"]);

        // governed_notion_requester's binding requires approval: no grant, no adapter call.
        var approval = Assert.Throws<AnipError>(() => capability.Handler(Context(Requester, null), parameters));
        Assert.Equal("approval_required", approval.ErrorType);

        if (Environment.GetEnvironmentVariable("ANIP_NOTION_ALLOW_MUTATION") == "true")
        {
            // The runtime sets the approval grant only after validating it.
            var created = capability.Handler(Context(Requester, "grant_live_csharp_notion_smoke"), parameters);
            Assert.Equal("completed", created["execution_status"]);
            Assert.Equal(true, created["mutation_performed"]);
            Assert.NotNull(((Dictionary<string, object?>)created["created_page"]!)["id"]);
        }
    }

    // The generated policy refuses a principal no binding selects before the
    // backend adapter runs, so this needs no Notion credentials.
    [Theory]
    [InlineData("human:local-dev")]
    [InlineData("human:local-dev|actor_id=notion_fronting_consumer")]
    public void GeneratedHandlerRefusesUnboundActors(string principal)
    {
        var parameters = new Dictionary<string, object?> { ["parent_id"] = "11111111-1111-4111-8111-111111111111", ["title"] = "Refused", ["content_summary"] = "Never reaches Notion." };
        var error = Assert.Throws<AnipError>(() => PageCreateCapability().Handler(Context(principal, "grant_live_csharp_notion_smoke"), parameters));
        Assert.Equal("denied", error.ErrorType);
        Assert.Equal(NoBindingDetail, error.Detail);
    }

    private static Anip.Service.CapabilityDef PageCreateCapability() =>
        GeneratedCapabilities.CreateAll(BackendAdapter.Default).First(item => item.Declaration.Name == "notion.page.create.prepare");

    private static string Env(string name) => Environment.GetEnvironmentVariable(name) ?? "";

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
        subject: "agent:notion-live-smoke",
        scopes: ["notion.page.create.prepare"],
        delegationChain: [],
        invocationId: "inv-test",
        clientReferenceId: null,
        taskId: null,
        parentInvocationId: null,
        emitProgress: _ => true,
        approvalGrant: grantId);
}

