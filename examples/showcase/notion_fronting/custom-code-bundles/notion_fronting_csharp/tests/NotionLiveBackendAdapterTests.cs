using {{ANIP_CSHARP_ROOT_NAMESPACE}};
using Xunit;

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class NotionLiveBackendAdapterTests
{
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
        var capability = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
            .First(item => item.Declaration.Name == "notion.page.create.prepare");
        var parameters = new Dictionary<string, object?> { ["parent_id"] = parentId, ["title"] = $"ANIP approved Notion C# page at {DateTimeOffset.UtcNow:O}", ["content_summary"] = "Created by explicit ANIP Notion C# generated-handler smoke." };

        var preview = capability.Handler(ApprovalContext(null), new Dictionary<string, object?>(parameters) { ["request_execution_approval"] = true });
        Assert.Equal("prepared", preview["execution_status"]);
        Assert.Equal(false, preview["mutation_performed"]);

        if (Environment.GetEnvironmentVariable("ANIP_NOTION_ALLOW_MUTATION") == "true")
        {
            var created = capability.Handler(ApprovalContext("grant_live_csharp_notion_smoke"), parameters);
            Assert.Equal("completed", created["execution_status"]);
            Assert.Equal(true, created["mutation_performed"]);
            Assert.NotNull(((Dictionary<string, object?>)created["created_page"]!)["id"]);
        }
    }

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

    private static Anip.Service.InvocationContext ApprovalContext(string? grantId) => new(
        token: null!,
        rootPrincipal: "human:local-dev|actor_id=notion_fronting_consumer",
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

