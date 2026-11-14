package host

import (
	"errors"
	"os"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// Principals the 0.2.0 runtime policy bindings select, and one they do not.
const (
	githubDrafterPrincipal        = "human:local-dev|actor_id=release_notes_drafter"
	githubIssueRequesterPrincipal = "human:local-dev|actor_id=issue_requester"
	githubNoBindingDetail         = "No runtime policy binding matches the current actor for this capability."
)

func TestGitHubGeneratedHandlerApprovedIssueCreate(t *testing.T) {
	owner, repo := os.Getenv("GITHUB_OWNER"), os.Getenv("GITHUB_REPO")
	if os.Getenv("GITHUB_TOKEN") == "" || owner == "" || repo == "" {
		t.Skip("GitHub credentials are not configured")
	}
	if os.Getenv("ANIP_GITHUB_ALLOWED_REPOS") == "" {
		t.Setenv("ANIP_GITHUB_ALLOWED_REPOS", owner+"/"+repo)
	}
	capability := githubCapabilityDefForTest(t, "github.issue.prepare")
	params := map[string]any{
		"owner": owner,
		"repo":  repo,
		"title": "ANIP approved GitHub Go issue at " + time.Now().Format(time.RFC3339),
		"body":  "Created by explicit ANIP GitHub Go generated-handler smoke.",
	}

	// release_notes_drafter may prepare issues: without a grant it gets a preview.
	preview, err := capability.Handler(githubTestContext(githubDrafterPrincipal, ""), params)
	if err != nil {
		t.Fatal(err)
	}
	if preview["execution_status"] != "prepared" || preview["mutation_performed"] != false {
		t.Fatalf("expected safe issue preview without grant, got %#v", preview)
	}

	// issue_requester's binding requires approval: no grant, no adapter call.
	_, err = capability.Handler(githubTestContext(githubIssueRequesterPrincipal, ""), params)
	githubExpectRefusal(t, err, "approval_required", "")

	if os.Getenv("ANIP_GITHUB_ALLOW_MUTATION") != "true" {
		return
	}
	// The runtime sets ApprovalGrant only after validating the grant.
	result, err := capability.Handler(githubTestContext(githubIssueRequesterPrincipal, "grant_live_go_github_smoke"), params)
	if err != nil {
		t.Fatal(err)
	}
	if result["execution_status"] != "completed" || result["mutation_performed"] != true {
		t.Fatalf("expected approved issue creation, got %#v", result)
	}
	created, ok := result["created_issue"].(map[string]any)
	if !ok || created["number"] == nil {
		t.Fatalf("expected created issue number, got %#v", result)
	}
}

// The generated policy refuses a principal no binding selects before the
// backend adapter runs, so this needs no GitHub credentials.
func TestGitHubGeneratedHandlerRefusesUnboundActors(t *testing.T) {
	capability := githubCapabilityDefForTest(t, "github.issue.prepare")
	params := map[string]any{"owner": "anip-smoke", "repo": "sandbox", "title": "Refused", "body": "Never reaches GitHub."}
	for _, principal := range []string{
		"human:local-dev",
		"human:local-dev|actor_id=github_fronting_consumer",
	} {
		_, err := capability.Handler(githubTestContext(principal, "grant_live_go_github_smoke"), params)
		githubExpectRefusal(t, err, "denied", githubNoBindingDetail)
	}
}

func githubTestContext(principal string, approvalGrant string) *service.InvocationContext {
	return &service.InvocationContext{
		RootPrincipal: principal,
		Subject:       "agent:github-live-smoke",
		Scopes:        []string{"github.issue.prepare"},
		InvocationID:  "inv-test",
		ApprovalGrant: approvalGrant,
	}
}

func githubExpectRefusal(t *testing.T, err error, failureType string, detail string) {
	t.Helper()
	var anipErr *core.ANIPError
	if !errors.As(err, &anipErr) || anipErr.ErrorType != failureType {
		t.Fatalf("expected %s, got %#v", failureType, err)
	}
	if detail != "" && anipErr.Detail != detail {
		t.Fatalf("expected detail %q, got %q", detail, anipErr.Detail)
	}
}

func githubCapabilityDefForTest(t *testing.T, capabilityID string) service.CapabilityDef {
	t.Helper()
	for _, capability := range GeneratedCapabilities {
		if capability.Declaration.Name == capabilityID {
			return capability
		}
	}
	t.Fatalf("missing capability %s", capabilityID)
	return service.CapabilityDef{}
}
