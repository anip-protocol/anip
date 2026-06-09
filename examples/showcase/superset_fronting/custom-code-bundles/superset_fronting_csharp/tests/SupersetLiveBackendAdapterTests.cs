using Anip.Service;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};
using Xunit;

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public sealed class SupersetLiveBackendAdapterTests
{
    [Fact]
    public void ExecutesLiveDiscoveryAndPreparedPreviewsWithoutMutation()
    {
        if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("SUPERSET_BASE_URL")) ||
            (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("SUPERSET_ACCESS_TOKEN")) &&
             (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("SUPERSET_USERNAME")) || string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("SUPERSET_PASSWORD")))))
        {
            return;
        }

        var workspaceScope = string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("SUPERSET_WORKSPACE_SCOPE")) ? "local" : Environment.GetEnvironmentVariable("SUPERSET_WORKSPACE_SCOPE")!;
        var discovery = Invoke("superset.analytics.discover_context", new() { ["workspace_scope"] = workspaceScope, ["query"] = "birth", ["limit"] = 5 });
        Assert.Equal("completed", discovery["execution_status"]);

        var chart = Invoke("superset.chart.preview.create", new() { ["dataset_ref"] = "1", ["metric"] = "count", ["visualization_type"] = "bar", ["title"] = "ANIP C# preview chart" });
        Assert.Equal("prepared", chart["execution_status"]);
        Assert.Equal(false, chart["mutation_performed"]);
        Assert.Equal(false, ((Dictionary<string, object?>)((Dictionary<string, object?>)chart["superset_request"]!)["body"]!)["save_chart"]);

        var dataset = Invoke("superset.dataset.draft.prepare", new() { ["database_ref"] = "1", ["dataset_purpose"] = "ANIP smoke", ["query_intent"] = "Count records by category" });
        Assert.Equal("prepared", dataset["execution_status"]);
        Assert.Equal(false, dataset["mutation_performed"]);
    }

    private static Dictionary<string, object?> Invoke(string capabilityId, Dictionary<string, object?> parameters)
    {
        var capability = GeneratedCapabilities.CreateAll(BackendAdapter.Default).Single(item => item.Declaration.Name == capabilityId);
        return capability.Handler(new InvocationContext(
            null!,
            "human:local-dev|actor_id=superset_fronting_consumer",
            "agent:superset-live-smoke",
            [capabilityId],
            [],
            "inv-test",
            null,
            null,
            null,
            _ => true), parameters);
    }
}
