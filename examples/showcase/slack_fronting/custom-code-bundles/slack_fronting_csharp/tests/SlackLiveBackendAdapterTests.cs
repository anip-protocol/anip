using Xunit;
using Anip.Core;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class SlackLiveBackendAdapterTests
{
    // Package 0.2.1 binds every capability to the collaborator actor
    // (allow_with_limits) and requires approval nowhere.
    private const string Collaborator = "human:local-dev|actor_id=collaborator";
    private const string NoBindingDetail = "No runtime policy binding matches the current actor for this capability.";

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
            var sent = BackendAdapter.Default(Capability("slack.message.prepare"), Plan(parameters), parameters, Context(Collaborator, "grant_live_csharp_smoke"));
            Assert.Equal("completed", sent["execution_status"]);
            Assert.Equal(true, sent["mutation_performed"]);
            Assert.False(string.IsNullOrWhiteSpace(((Dictionary<string, object?>)sent["posted_message"]!)["ts"]?.ToString()));
        }
    }

    [Fact]
    public void GeneratedHandlerPreviewsWithoutGrantAndSendsWithGrant()
    {
        var token = Environment.GetEnvironmentVariable("SLACK_BOT_TOKEN");
        var channelId = Environment.GetEnvironmentVariable("SLACK_CHANNEL_ID");
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(channelId)) return;

        var capability = AnnouncementCapability();
        var parameters = new Dictionary<string, object?> { ["channel_id"] = channelId, ["announcement"] = "ANIP approved Slack C# generated handler post", ["audience"] = "test" };

        // Without a grant the collaborator gets a preview; nothing is posted.
        var preview = capability.Handler(Context(Collaborator, null), parameters);
        Assert.Equal("prepared", preview["execution_status"]);
        Assert.Equal(false, preview["mutation_performed"]);

        if (Environment.GetEnvironmentVariable("ANIP_SLACK_ALLOW_SEND") == "true")
        {
            // The runtime sets the approval grant only after validating it.
            var sent = capability.Handler(Context(Collaborator, "grant_live_csharp_handler_smoke"), parameters);
            Assert.Equal("completed", sent["execution_status"]);
            Assert.Equal(true, sent["mutation_performed"]);
            Assert.False(string.IsNullOrWhiteSpace(((Dictionary<string, object?>)sent["posted_message"]!)["ts"]?.ToString()));
        }
    }

    // The generated policy refuses a principal no binding selects before the
    // backend adapter runs, so this needs no Slack credentials.
    [Theory]
    [InlineData("human:local-dev")]
    [InlineData("human:local-dev|actor_id=slack_requester")]
    public void GeneratedHandlerRefusesUnboundActors(string principal)
    {
        var parameters = new Dictionary<string, object?> { ["channel_id"] = "C0SMOKE01", ["announcement"] = "Refused", ["audience"] = "test" };
        var error = Assert.Throws<AnipError>(() => AnnouncementCapability().Handler(Context(principal, "grant_live_csharp_handler_smoke"), parameters));
        Assert.Equal("denied", error.ErrorType);
        Assert.Equal(NoBindingDetail, error.Detail);
    }

    private static Anip.Service.CapabilityDef AnnouncementCapability() =>
        GeneratedCapabilities.CreateAll(BackendAdapter.Default).First(item => item.Declaration.Name == "slack.announcement.request");

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

    private static Anip.Service.InvocationContext Context(string principal, string? grantId) => new(
        token: null!,
        rootPrincipal: principal,
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
