package host

import (
	"os"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/service"
)

func TestNotionGeneratedHandlerApprovedPageCreate(t *testing.T) {
	parentID := os.Getenv("NOTION_PARENT_PAGE_ID")
	if os.Getenv("NOTION_TOKEN") == "" || parentID == "" {
		t.Skip("Notion credentials are not configured")
	}
	t.Setenv("ANIP_NOTION_ALLOWED_PARENTS", parentID)
	capability := capabilityDefForTest(t, "notion.page.create.prepare")
	params := map[string]any{"parent_id": parentID, "title": "ANIP approved Notion Go page "+time.Now().Format(time.RFC3339), "content_summary": "Created by explicit ANIP Notion Go generated-handler smoke."}

	preview, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=notion_fronting_consumer",
		Subject:       "agent:notion-live-smoke",
		Scopes:        []string{"notion.page.create.prepare"},
		InvocationID:  "inv-test",
	}, params)
	if err != nil {
		t.Fatal(err)
	}
	if preview["execution_status"] != "prepared" || preview["approval_required"] != true || preview["mutation_performed"] != false {
		t.Fatalf("expected prepared approval preview without grant, got %#v", preview)
	}

	if os.Getenv("ANIP_NOTION_ALLOW_MUTATION") != "true" {
		return
	}
	result, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=notion_fronting_consumer",
		Subject:       "agent:notion-live-smoke",
		Scopes:        []string{"notion.page.create.prepare"},
		InvocationID:  "inv-test",
		ApprovalGrant: "grant_live_go_notion_smoke",
	}, params)
	if err != nil {
		t.Fatal(err)
	}
	if result["execution_status"] != "completed" || result["mutation_performed"] != true {
		t.Fatalf("expected approved page create completed, got %#v", result)
	}
	created, ok := result["created_page"].(map[string]any)
	if !ok || created["id"] == "" {
		t.Fatalf("expected created page id, got %#v", result)
	}
}

func TestNotionGeneratedHandlerLiveDatabaseQuery(t *testing.T) {
	databaseID := os.Getenv("NOTION_DATABASE_ID")
	dataSourceID := os.Getenv("NOTION_DATA_SOURCE_ID")
	if os.Getenv("NOTION_TOKEN") == "" || databaseID == "" || dataSourceID == "" {
		t.Skip("Notion database credentials are not configured")
	}
	t.Setenv("ANIP_NOTION_ALLOWED_DATABASES", databaseID)
	t.Setenv("ANIP_NOTION_ALLOWED_DATA_SOURCES", dataSourceID)
	capability := capabilityDefForTest(t, "notion.database.query_context")

	result, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=notion_fronting_consumer",
		Subject:       "agent:notion-live-smoke",
		Scopes:        []string{"notion.database.query_context"},
		InvocationID:  "inv-test",
	}, map[string]any{"database_id": databaseID, "limit": 5})
	if err != nil {
		t.Fatal(err)
	}
	if result["execution_status"] != "completed" {
		t.Fatalf("expected completed database query, got %#v", result)
	}
	payload, ok := result["result"].(map[string]any)
	if !ok || payload["database_id"] != databaseID || payload["data_source_id"] != dataSourceID {
		t.Fatalf("expected database and data source ids in result, got %#v", result)
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
