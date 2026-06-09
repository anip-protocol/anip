package host

import (
	"os"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/service"
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
		"repo": repo,
		"title": "ANIP approved GitHub Go issue at " + time.Now().Format(time.RFC3339),
		"body": "Created by explicit ANIP GitHub Go generated-handler smoke.",
	}

	preview, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=github_fronting_consumer",
		Subject: "agent:github-live-smoke",
		Scopes: []string{"github.issue.prepare"},
		InvocationID: "inv-test",
	}, map[string]any{ "owner": owner, "repo": repo, "title": params["title"], "body": params["body"], "request_execution_approval": true })
	if err != nil {
		t.Fatal(err)
	}
	if preview["execution_status"] != "prepared" || preview["mutation_performed"] != false {
		t.Fatalf("expected safe issue preview without grant, got %#v", preview)
	}

	if os.Getenv("ANIP_GITHUB_ALLOW_MUTATION") != "true" {
		return
	}
	result, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=github_fronting_consumer",
		Subject: "agent:github-live-smoke",
		Scopes: []string{"github.issue.prepare"},
		InvocationID: "inv-test",
		ApprovalGrant: "grant_live_go_github_smoke",
	}, params)
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
