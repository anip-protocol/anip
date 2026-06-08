using Xunit;
using Anip.Core;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class SlackLiveBackendAdapterTests
{
    [Fact]
    public void ExecutesLiveReadsAndPreparedPreviewsWithoutMutation()
    {
        var token = Environment.GetEnvironmentVariable("SLACK_BOT_TOKEN");
        var channelId = Environment.GetEnvironmentVariable("SLACK_CHANNEL_ID");
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(channelId)) return;

        var history = BackendAdapter.Slack(token, "conversations.history", new() { ["channel"] = channelId, ["limit"] = 1 });
        Assert.True(IsOk(history["ok"]));
        var threadTs = "";
        if (history["messages"] is System.Text.Json.JsonElement messages && messages.GetArrayLength() > 0)
        {
            var first = messages[0];
            threadTs = first.TryGetProperty("thread_ts", out var thread) ? thread.GetString() ?? "" : first.GetProperty("ts").GetString() ?? "";
        }

        var context = BackendAdapter.Default(Capability("slack.channel.read_context"), Plan(new() { ["channel_id"] = channelId, ["limit"] = 5 }), new() { ["channel_id"] = channelId, ["limit"] = 5 }, null!);
        Assert.Equal("completed", context["execution_status"]);
        if (!string.IsNullOrWhiteSpace(threadTs))
        {
            var thread = BackendAdapter.Default(Capability("slack.thread.summarize"), Plan(new() { ["channel_id"] = channelId, ["thread_ts"] = threadTs, ["limit"] = 10 }), new() { ["channel_id"] = channelId, ["thread_ts"] = threadTs, ["limit"] = 10 }, null!);
            Assert.Equal("completed", thread["execution_status"]);
        }

        var previews = new Dictionary<string, Dictionary<string, object?>>
        {
            ["slack.message.prepare"] = new() { ["channel_id"] = channelId, ["text"] = "ANIP Slack C# smoke preview" },
            ["slack.incident_update.prepare"] = new() { ["channel_id"] = channelId, ["incident_id"] = "INC-123", ["status"] = "monitoring", ["summary"] = "Preview only", ["next_update_time"] = "in 30 minutes" },
            ["slack.announcement.request"] = new() { ["channel_id"] = channelId, ["announcement"] = "Preview governed announcement only", ["audience"] = "internal" },
        };

        foreach (var item in previews)
        {
            var result = BackendAdapter.Default(Capability(item.Key), Plan(item.Value), item.Value, null!);
            Assert.Equal("prepared", result["execution_status"]);
            Assert.Equal(false, result["mutation_performed"]);
        }

        if (Environment.GetEnvironmentVariable("ANIP_SLACK_ALLOW_SEND") == "true")
        {
            var parameters = new Dictionary<string, object?> { ["channel_id"] = channelId, ["text"] = "ANIP approved Slack C# post" };
            var sent = BackendAdapter.Default(Capability("slack.message.prepare"), Plan(parameters), parameters, ApprovalContext("grant_live_csharp_smoke"));
            Assert.Equal("completed", sent["execution_status"]);
            Assert.Equal(true, sent["mutation_performed"]);
            Assert.False(string.IsNullOrWhiteSpace(((Dictionary<string, object?>)sent["posted_message"]!)["ts"]?.ToString()));
        }
    }

    [Fact]
    public void GeneratedHandlerStopsWithoutApprovalAndSendsWithGrant()
    {
        var token = Environment.GetEnvironmentVariable("SLACK_BOT_TOKEN");
        var channelId = Environment.GetEnvironmentVariable("SLACK_CHANNEL_ID");
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(channelId)) return;

        var capability = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
            .First(item => item.Declaration.Name == "slack.announcement.request");
        var parameters = new Dictionary<string, object?> { ["channel_id"] = channelId, ["announcement"] = "ANIP approved Slack C# generated handler post", ["audience"] = "test" };

        var error = Assert.Throws<AnipError>(() => capability.Handler(ApprovalContext(null), parameters));
        Assert.Equal("approval_required", error.ErrorType);

        if (Environment.GetEnvironmentVariable("ANIP_SLACK_ALLOW_SEND") == "true")
        {
            var sent = capability.Handler(ApprovalContext("grant_live_csharp_handler_smoke"), parameters);
            Assert.Equal("completed", sent["execution_status"]);
            Assert.Equal(true, sent["mutation_performed"]);
            Assert.False(string.IsNullOrWhiteSpace(((Dictionary<string, object?>)sent["posted_message"]!)["ts"]?.ToString()));
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

    private static bool IsOk(object? value) =>
        value is bool ok ? ok : value is System.Text.Json.JsonElement element && element.ValueKind == System.Text.Json.JsonValueKind.True;

    private static Anip.Service.InvocationContext ApprovalContext(string? grantId) => new(
        token: null!,
        rootPrincipal: "human:local-dev|actor_id=slack_requester",
        subject: "agent:slack-live-smoke",
        scopes: ["slack.message.prepare", "slack.announcement.request"],
        delegationChain: [],
        invocationId: "inv-test",
        clientReferenceId: null,
        taskId: null,
        parentInvocationId: null,
        emitProgress: _ => true,
        approvalGrant: grantId);
}
