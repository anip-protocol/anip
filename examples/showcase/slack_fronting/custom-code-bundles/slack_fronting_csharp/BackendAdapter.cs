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

        var token = Environment.GetEnvironmentVariable("SLACK_BOT_TOKEN")?.Trim() ?? "";
        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "slack.channel.read_context" => string.IsNullOrWhiteSpace(token)
                ? Result(capability, plan, "backend_not_configured", new() { ["missing_env"] = "SLACK_BOT_TOKEN" })
                : ReadChannel(capability, plan, parameters, token),
            "slack.thread.summarize" => string.IsNullOrWhiteSpace(token)
                ? Result(capability, plan, "backend_not_configured", new() { ["missing_env"] = "SLACK_BOT_TOKEN" })
                : ReadThread(capability, plan, parameters, token),
            "slack.message.prepare" or "slack.incident_update.prepare" or "slack.announcement.request" => PrepareOrSendMessage(capability, plan, parameters, token, _context),
            _ => Result(capability, plan, "backend_execution_stub", new() { ["note"] = "No Slack custom handler is registered for this capability." }),
        };
    }

    private static Dictionary<string, object?> ReadChannel(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var channelId = Text(parameters.GetValueOrDefault("channel_id"));
        if (!ChannelAllowed(channelId)) return Restricted(capability, plan, channelId);
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 20, 50);
        var query = Text(parameters.GetValueOrDefault("query")).ToLowerInvariant();
        var payload = Slack(token, "conversations.history", new() { ["channel"] = channelId, ["limit"] = limit });
        if (!Ok(payload)) return BackendError(capability, plan, payload);
        var messages = MessageSummaries(payload.GetValueOrDefault("messages"));
        if (!string.IsNullOrWhiteSpace(query)) messages = messages.Where(message => Text(message.GetValueOrDefault("text")).ToLowerInvariant().Contains(query)).ToList();
        if (messages.Count > limit) messages = messages.Take(limit).ToList();
        return Result(capability, plan, "completed", new() { ["result"] = new Dictionary<string, object?> { ["messages"] = messages, ["count"] = messages.Count, ["channel_id"] = channelId } });
    }

    private static Dictionary<string, object?> ReadThread(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token)
    {
        var channelId = Text(parameters.GetValueOrDefault("channel_id"));
        if (!ChannelAllowed(channelId)) return Restricted(capability, plan, channelId);
        var threadTs = Text(parameters.GetValueOrDefault("thread_ts"));
        var limit = BoundedLimit(parameters.GetValueOrDefault("limit"), 50, 100);
        var payload = Slack(token, "conversations.replies", new() { ["channel"] = channelId, ["ts"] = threadTs, ["limit"] = limit });
        if (!Ok(payload)) return BackendError(capability, plan, payload);
        var messages = MessageSummaries(payload.GetValueOrDefault("messages"));
        return Result(capability, plan, "completed", new() { ["result"] = new Dictionary<string, object?> { ["messages"] = messages, ["count"] = messages.Count, ["channel_id"] = channelId, ["thread_ts"] = threadTs } });
    }

    private static Dictionary<string, object?> PrepareOrSendMessage(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> parameters, string token, InvocationContext context)
    {
        var channelId = Text(parameters.GetValueOrDefault("channel_id"));
        if (!ChannelAllowed(channelId)) return Restricted(capability, plan, channelId);
        var body = new Dictionary<string, object?> { ["channel"] = channelId, ["text"] = MessageText(capability, parameters) };
        if (!string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("thread_ts")))) body["thread_ts"] = Text(parameters.GetValueOrDefault("thread_ts"));
        var preview = Result(capability, plan, "prepared", new()
        {
            ["approval_required"] = true,
            ["mutation_performed"] = false,
            ["slack_action"] = "chat.postMessage",
            ["post_message_request"] = new Dictionary<string, object?> { ["method"] = "POST", ["path"] = "/api/chat.postMessage", ["body"] = body },
            ["note"] = "Prepared a Slack message payload. No Slack message was sent.",
        });
        if (Environment.GetEnvironmentVariable("ANIP_SLACK_ALLOW_SEND") != "true" || string.IsNullOrWhiteSpace(context?.ApprovalGrant)) return preview;
        if (string.IsNullOrWhiteSpace(token))
        {
            preview["execution_status"] = "backend_error";
            preview["slack_error"] = new Dictionary<string, object?> { ["ok"] = false, ["error"] = "missing_slack_token" };
            return preview;
        }
        var posted = Slack(token, "chat.postMessage", body);
        if (!Ok(posted))
        {
            preview["execution_status"] = "backend_error";
            preview["slack_error"] = posted;
            return preview;
        }
        preview["execution_status"] = "completed";
        preview["approval_required"] = false;
        preview["mutation_performed"] = true;
        preview["posted_message"] = new Dictionary<string, object?> { ["channel"] = posted.GetValueOrDefault("channel"), ["ts"] = posted.GetValueOrDefault("ts") };
        preview["approval_grant_id"] = context.ApprovalGrant;
        preview["note"] = "Sent Slack message after the ANIP runtime validated and reserved an approval grant.";
        return preview;
    }

    public static Dictionary<string, object?> Slack(string token, string path, Dictionary<string, object?> body)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, $"https://slack.com/api/{path}");
        request.Headers.Accept.ParseAdd("application/json");
        request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
        request.Content = new FormUrlEncodedContent(body.Where(item => item.Value is not null).ToDictionary(item => item.Key, item => Text(item.Value)));
        var response = Http.Send(request);
        var text = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
        var payload = string.IsNullOrWhiteSpace(text) ? new Dictionary<string, object?>() : JsonSerializer.Deserialize<Dictionary<string, object?>>(text)!;
        if (!response.IsSuccessStatusCode) return new Dictionary<string, object?> { ["ok"] = false, ["error"] = "slack_http_error", ["status"] = (int)response.StatusCode, ["detail"] = payload };
        return payload;
    }

    private static string MessageText(Dictionary<string, object?> capability, Dictionary<string, object?> parameters)
    {
        return Text(capability.GetValueOrDefault("capability_id")) switch
        {
            "slack.incident_update.prepare" => string.Join("\n", new[]
            {
                $"Incident {Text(parameters.GetValueOrDefault("incident_id"))}: {Text(parameters.GetValueOrDefault("status"))}",
                Text(parameters.GetValueOrDefault("summary")),
                string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("next_update_time"))) ? "" : $"Next update: {Text(parameters.GetValueOrDefault("next_update_time"))}",
            }.Where(item => !string.IsNullOrWhiteSpace(item))),
            "slack.announcement.request" => (string.IsNullOrWhiteSpace(Text(parameters.GetValueOrDefault("audience"))) ? "" : $"[{Text(parameters.GetValueOrDefault("audience"))}] ") + Text(parameters.GetValueOrDefault("announcement")),
            _ => Text(parameters.GetValueOrDefault("text")),
        };
    }

    private static Dictionary<string, object?> Result(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string status, Dictionary<string, object?> extra)
    {
        var result = new Dictionary<string, object?> { ["execution_status"] = status, ["capability_id"] = capability.GetValueOrDefault("capability_id"), ["selected_backend"] = plan.GetValueOrDefault("selected_binding"), ["semantic_input"] = plan.GetValueOrDefault("semantic_input"), ["backend_input_contract"] = plan.GetValueOrDefault("backend_input_contract") };
        foreach (var item in extra) result[item.Key] = item.Value;
        return result;
    }

    private static Dictionary<string, object?> Restricted(Dictionary<string, object?> capability, Dictionary<string, object?> plan, string channelId) =>
        Result(capability, plan, "restricted", new() { ["channel_id"] = channelId, ["reason"] = "Slack channel is outside the configured ANIP channel policy." });

    private static Dictionary<string, object?> BackendError(Dictionary<string, object?> capability, Dictionary<string, object?> plan, Dictionary<string, object?> payload) =>
        Result(capability, plan, "backend_error", new() { ["slack_error"] = payload });

    private static bool ChannelAllowed(string channelId)
    {
        var blocked = CsvEnv("ANIP_SLACK_BLOCKED_CHANNELS");
        var allowed = CsvEnv("ANIP_SLACK_ALLOWED_CHANNELS");
        return !blocked.Contains(channelId) && (allowed.Count == 0 || allowed.Contains(channelId));
    }

    private static List<Dictionary<string, object?>> MessageSummaries(object? value)
    {
        var result = new List<Dictionary<string, object?>>();
        if (value is JsonElement element && element.ValueKind == JsonValueKind.Array)
        {
            foreach (var message in element.EnumerateArray())
            {
                result.Add(new()
                {
                    ["ts"] = Get(message, "ts"),
                    ["user"] = FirstNonEmpty(Get(message, "user"), Get(message, "bot_id")),
                    ["text"] = Get(message, "text"),
                    ["thread_ts"] = Get(message, "thread_ts"),
                });
            }
        }
        return result;
    }

    private static bool Ok(Dictionary<string, object?> payload) =>
        payload.GetValueOrDefault("ok") is bool ok ? ok : payload.GetValueOrDefault("ok") is JsonElement element && element.ValueKind == JsonValueKind.True;

    private static string Get(JsonElement element, string key) => element.TryGetProperty(key, out var value) ? (value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : value.ToString()) : "";
    private static string FirstNonEmpty(params string[] values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    private static int BoundedLimit(object? value, int defaultValue, int maximum) => int.TryParse(Text(value), out var parsed) ? Math.Max(1, Math.Min(parsed, maximum)) : defaultValue;
    private static string Text(object? value) => value is null ? "" : value.ToString()!.Trim();
    private static List<string> CsvEnv(string name) => (Environment.GetEnvironmentVariable(name) ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).Distinct().ToList();
    private static List<string> StringList(object? value) => value is IEnumerable<object?> items ? items.Select(Text).Where(item => item.Length > 0).ToList() : [];
}
