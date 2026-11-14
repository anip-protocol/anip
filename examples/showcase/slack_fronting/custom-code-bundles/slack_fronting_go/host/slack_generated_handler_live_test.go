package host

import (
	"errors"
	"os"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// Package 0.2.1 binds every capability to the collaborator actor
// (allow_with_limits) and requires approval nowhere.
const (
	slackCollaboratorPrincipal = "human:local-dev|actor_id=collaborator"
	slackNoBindingDetail       = "No runtime policy binding matches the current actor for this capability."
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

	// Without a grant the collaborator gets a preview; nothing is posted.
	preview, err := capability.Handler(slackTestContext(slackCollaboratorPrincipal, ""), params)
	if err != nil {
		t.Fatal(err)
	}
	if preview["execution_status"] != "prepared" || preview["mutation_performed"] != false {
		t.Fatalf("expected announcement preview without grant, got %#v", preview)
	}

	if os.Getenv("ANIP_SLACK_ALLOW_SEND") != "true" {
		return
	}
	// The runtime sets ApprovalGrant only after validating the grant.
	result, err := capability.Handler(slackTestContext(slackCollaboratorPrincipal, "grant_live_go_handler_smoke"), params)
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

// The generated policy refuses a principal no binding selects before the
// backend adapter runs, so this needs no Slack credentials.
func TestSlackGeneratedHandlerRefusesUnboundActors(t *testing.T) {
	capability := capabilityDefForTest(t, "slack.announcement.request")
	params := map[string]any{"channel_id": "C0SMOKE01", "announcement": "Refused", "audience": "test"}
	for _, principal := range []string{
		"human:local-dev",
		"human:local-dev|actor_id=slack_requester",
	} {
		_, err := capability.Handler(slackTestContext(principal, "grant_live_go_handler_smoke"), params)
		var anipErr *core.ANIPError
		if !errors.As(err, &anipErr) || anipErr.ErrorType != "denied" || anipErr.Detail != slackNoBindingDetail {
			t.Fatalf("%s: expected denied (%s), got %#v", principal, slackNoBindingDetail, err)
		}
	}
}

func slackTestContext(principal string, approvalGrant string) *service.InvocationContext {
	return &service.InvocationContext{
		RootPrincipal: principal,
		Subject:       "agent:slack-live-smoke",
		Scopes:        []string{"slack.announcement.request"},
		InvocationID:  "inv-test",
		ApprovalGrant: approvalGrant,
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
