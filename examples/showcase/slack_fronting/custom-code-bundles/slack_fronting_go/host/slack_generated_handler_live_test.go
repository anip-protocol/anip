package host

import (
	"os"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func TestSlackGeneratedHandlerApprovedSend(t *testing.T) {
	channelID := os.Getenv("SLACK_CHANNEL_ID")
	if os.Getenv("SLACK_BOT_TOKEN") == "" || channelID == "" {
		t.Skip("Slack credentials are not configured")
	}
	if os.Getenv("ANIP_SLACK_ALLOWED_CHANNELS") == "" {
		t.Setenv("ANIP_SLACK_ALLOWED_CHANNELS", channelID)
	}
	capability := capabilityDefForTest(t, "slack.announcement.request")
	params := map[string]any{"channel_id": channelID, "announcement": "ANIP approved Slack Go generated handler post", "audience": "test"}

	_, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=slack_requester",
		Subject:       "agent:slack-live-smoke",
		Scopes:        []string{"slack.announcement.request"},
		InvocationID:  "inv-test",
	}, params)
	if anipErr, ok := err.(*core.ANIPError); !ok || anipErr.ErrorType != "approval_required" {
		t.Fatalf("expected approval_required without grant, got %#v", err)
	}

	if os.Getenv("ANIP_SLACK_ALLOW_SEND") != "true" {
		return
	}
	result, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=slack_requester",
		Subject:       "agent:slack-live-smoke",
		Scopes:        []string{"slack.announcement.request"},
		InvocationID:  "inv-test",
		ApprovalGrant: "grant_live_go_handler_smoke",
	}, params)
	if err != nil {
		t.Fatal(err)
	}
	if result["execution_status"] != "completed" || result["mutation_performed"] != true {
		t.Fatalf("expected approved send completed, got %#v", result)
	}
	posted, ok := result["posted_message"].(map[string]any)
	if !ok || posted["ts"] == "" {
		t.Fatalf("expected posted message timestamp, got %#v", result)
	}
}

func capabilityDefForTest(t *testing.T, capabilityID string) service.CapabilityDef {
	t.Helper()
	for _, capability := range GeneratedCapabilities {
		if capability.Declaration.Name == capabilityID {
			return capability
		}
	}
	t.Fatalf("missing capability %s", capabilityID)
	return service.CapabilityDef{}
}
