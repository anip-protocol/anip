package extensions

import (
	"os"
	"testing"

	"{{ANIP_GO_MODULE_PATH}}/generated"
)

func TestSlackLiveBackendAdapter(t *testing.T) {
	token := textEnv("SLACK_BOT_TOKEN")
	channelID := textEnv("SLACK_CHANNEL_ID")
	if token == "" || channelID == "" {
		t.Skip("Slack credentials are not configured")
	}
	if textEnv("ANIP_SLACK_ALLOWED_CHANNELS") == "" {
		t.Setenv("ANIP_SLACK_ALLOWED_CHANNELS", channelID)
	}
	history := slackPost(token, "conversations.history", map[string]any{"channel": channelID, "limit": 1})
	if history["ok"] != true {
		t.Fatalf("Slack history failed: %#v", history)
	}
	var threadTS string
	if messages, ok := history["messages"].([]any); ok && len(messages) > 0 {
		message := messages[0].(map[string]any)
		threadTS = text(firstNonNil(message["thread_ts"], message["ts"]))
	}
	context := executeForTest(t, "slack.channel.read_context", map[string]any{"channel_id": channelID, "limit": 5})
	if context["execution_status"] != "completed" {
		t.Fatalf("expected channel read completed, got %#v", context)
	}
	if threadTS != "" {
		thread := executeForTest(t, "slack.thread.summarize", map[string]any{"channel_id": channelID, "thread_ts": threadTS, "limit": 10})
		if thread["execution_status"] != "completed" {
			t.Fatalf("expected thread read completed, got %#v", thread)
		}
	}
	cases := map[string]map[string]any{
		"slack.message.prepare": {"channel_id": channelID, "text": "ANIP Slack Go smoke preview"},
		"slack.incident_update.prepare": {"channel_id": channelID, "incident_id": "INC-123", "status": "monitoring", "summary": "Preview only", "next_update_time": "in 30 minutes"},
		"slack.announcement.request": {"channel_id": channelID, "announcement": "Preview governed announcement only", "audience": "internal"},
	}
	for id, params := range cases {
		result := executeForTest(t, id, params)
		if result["execution_status"] != "prepared" || result["mutation_performed"] != false {
			t.Fatalf("%s expected prepared without mutation, got %#v", id, result)
		}
	}
	if textEnv("ANIP_SLACK_ALLOW_SEND") == "true" {
		params := map[string]any{"channel_id": channelID, "text": "ANIP approved Slack Go post"}
		result := executeForTestWithContext(t, "slack.message.prepare", params, BackendInvocationContext{ApprovalGrant: "grant_live_go_smoke"})
		if result["execution_status"] != "completed" || result["mutation_performed"] != true {
			t.Fatalf("expected approved send completed, got %#v", result)
		}
		if posted, ok := result["posted_message"].(map[string]any); !ok || text(posted["ts"]) == "" {
			t.Fatalf("expected posted message timestamp, got %#v", result)
		}
	}
}

func executeForTest(t *testing.T, capabilityID string, params map[string]any) map[string]any {
	t.Helper()
	return executeForTestWithContext(t, capabilityID, params, BackendInvocationContext{})
}

func executeForTestWithContext(t *testing.T, capabilityID string, params map[string]any, context BackendInvocationContext) map[string]any {
	t.Helper()
	capability := capabilityForTest(t, capabilityID)
	plan := generated.BackendInvocationPlan{SemanticInput: params, AdapterInput: params, BackendInputContract: generated.EffectiveBackendInputContract{Mode: "explicit"}}
	result, err := BackendAdapterInstance.Execute(capability, plan, params, context)
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func capabilityForTest(t *testing.T, capabilityID string) generated.GeneratedCapabilityRuntimeMetadata {
	t.Helper()
	for _, capability := range generated.GeneratedCapabilityMetadata {
		if capability.CapabilityID == capabilityID {
			return capability
		}
	}
	t.Fatalf("missing capability %s", capabilityID)
	return generated.GeneratedCapabilityRuntimeMetadata{}
}

func textEnv(name string) string {
	return text(getenv(name))
}

func getenv(name string) string {
	return text(os.Getenv(name))
}
