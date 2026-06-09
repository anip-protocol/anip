package host

import (
	"os"
	"strings"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/service"
)

func TestGitLabGeneratedHandlerApprovedIssueCreate(t *testing.T) {
	project := gitlabProjectForTest()
	if os.Getenv("GITLAB_TOKEN") == "" || project == "" {
		t.Skip("GitLab credentials are not configured")
	}
	if os.Getenv("ANIP_GITLAB_ALLOWED_PROJECTS") == "" {
		t.Setenv("ANIP_GITLAB_ALLOWED_PROJECTS", project)
	}
	capability := gitlabCapabilityDefForTest(t, "gitlab.issue.prepare")
	params := map[string]any{
		"project_id": project,
		"namespace": gitlabNamespaceForTest(project),
		"project": gitlabProjectNameForTest(project),
		"title": "ANIP approved GitLab Go issue at " + time.Now().Format(time.RFC3339),
		"body": "Created by explicit ANIP GitLab Go generated-handler smoke.",
	}

	preview, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=gitlab_fronting_consumer",
		Subject: "agent:gitlab-live-smoke",
		Scopes: []string{"gitlab.issue.prepare"},
		InvocationID: "inv-test",
	}, map[string]any{"project_id": project, "namespace": params["namespace"], "project": params["project"], "title": params["title"], "body": params["body"], "request_execution_approval": true})
	if err != nil {
		t.Fatal(err)
	}
	if preview["execution_status"] != "prepared" || preview["mutation_performed"] != false {
		t.Fatalf("expected safe issue preview without grant, got %#v", preview)
	}

	if os.Getenv("ANIP_GITLAB_ALLOW_MUTATION") != "true" {
		return
	}
	result, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=gitlab_fronting_consumer",
		Subject: "agent:gitlab-live-smoke",
		Scopes: []string{"gitlab.issue.prepare"},
		InvocationID: "inv-test",
		ApprovalGrant: "grant_live_go_gitlab_smoke",
	}, params)
	if err != nil {
		t.Fatal(err)
	}
	if result["execution_status"] != "completed" || result["mutation_performed"] != true {
		t.Fatalf("expected approved issue creation, got %#v", result)
	}
	created, ok := result["created_issue"].(map[string]any)
	if !ok || created["iid"] == nil {
		t.Fatalf("expected created issue iid, got %#v", result)
	}
}

func gitlabProjectForTest() string {
	if project := os.Getenv("GITLAB_PROJECT_ID"); project != "" {
		return project
	}
	namespace, project := os.Getenv("GITLAB_NAMESPACE"), os.Getenv("GITLAB_PROJECT")
	if namespace != "" && project != "" {
		return namespace + "/" + project
	}
	return ""
}

func gitlabNamespaceForTest(project string) string {
	if namespace := os.Getenv("GITLAB_NAMESPACE"); namespace != "" {
		return namespace
	}
	parts := strings.SplitN(project, "/", 2)
	if len(parts) == 2 {
		return parts[0]
	}
	return ""
}

func gitlabProjectNameForTest(project string) string {
	if name := os.Getenv("GITLAB_PROJECT"); name != "" {
		return name
	}
	parts := strings.SplitN(project, "/", 2)
	if len(parts) == 2 {
		return parts[1]
	}
	return ""
}

func gitlabCapabilityDefForTest(t *testing.T, capabilityID string) service.CapabilityDef {
	t.Helper()
	for _, capability := range GeneratedCapabilities {
		if capability.Declaration.Name == capabilityID {
			return capability
		}
	}
	t.Fatalf("missing capability %s", capabilityID)
	return service.CapabilityDef{}
}
