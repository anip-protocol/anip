package host

import (
	"errors"
	"os"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// Principals the 0.2.0 runtime policy bindings select.
const (
	notionReviewerPrincipal  = "human:local-dev|actor_id=notion_governance_reviewer"
	notionRequesterPrincipal = "human:local-dev|actor_id=governed_notion_requester"
	notionNoBindingDetail    = "No runtime policy binding matches the current actor for this capability."
)

func TestNotionGeneratedHandlerApprovedPageCreate(t *testing.T) {
	parentID := os.Getenv("NOTION_PARENT_PAGE_ID")
	if os.Getenv("NOTION_TOKEN") == "" || parentID == "" {
		t.Skip("Notion credentials are not configured")
	}
	t.Setenv("ANIP_NOTION_ALLOWED_PARENTS", parentID)
	capability := capabilityDefForTest(t, "notion.page.create.prepare")
	params := map[string]any{"parent_id": parentID, "title": "ANIP approved Notion Go page " + time.Now().Format(time.RFC3339), "content_summary": "Created by explicit ANIP Notion Go generated-handler smoke."}

	// notion_governance_reviewer may create pages: without a grant it gets a preview.
	preview, err := capability.Handler(notionTestContext(notionReviewerPrincipal, "notion.page.create.prepare", ""), params)
	if err != nil {
		t.Fatal(err)
	}
	if preview["execution_status"] != "prepared" || preview["approval_required"] != true || preview["mutation_performed"] != false {
		t.Fatalf("expected prepared approval preview without grant, got %#v", preview)
	}

	// governed_notion_requester's binding requires approval: no grant, no adapter call.
	_, err = capability.Handler(notionTestContext(notionRequesterPrincipal, "notion.page.create.prepare", ""), params)
	var anipErr *core.ANIPError
	if !errors.As(err, &anipErr) || anipErr.ErrorType != "approval_required" {
		t.Fatalf("expected approval_required without grant, got %#v", err)
	}

	if os.Getenv("ANIP_NOTION_ALLOW_MUTATION") != "true" {
		return
	}
	// The runtime sets ApprovalGrant only after validating the grant.
	result, err := capability.Handler(notionTestContext(notionRequesterPrincipal, "notion.page.create.prepare", "grant_live_go_notion_smoke"), params)
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

	result, err := capability.Handler(notionTestContext(notionReviewerPrincipal, "notion.database.query_context", ""), map[string]any{"database_id": databaseID, "limit": 5})
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

// The generated policy refuses a principal no binding selects before the
// backend adapter runs, so this needs no Notion credentials.
func TestNotionGeneratedHandlerRefusesUnboundActors(t *testing.T) {
	capability := capabilityDefForTest(t, "notion.page.create.prepare")
	params := map[string]any{"parent_id": "11111111-1111-4111-8111-111111111111", "title": "Refused", "content_summary": "Never reaches Notion."}
	for _, principal := range []string{
		"human:local-dev",
		"human:local-dev|actor_id=notion_fronting_consumer",
	} {
		_, err := capability.Handler(notionTestContext(principal, "notion.page.create.prepare", "grant_live_go_notion_smoke"), params)
		var anipErr *core.ANIPError
		if !errors.As(err, &anipErr) || anipErr.ErrorType != "denied" || anipErr.Detail != notionNoBindingDetail {
			t.Fatalf("%s: expected denied (%s), got %#v", principal, notionNoBindingDetail, err)
		}
	}
}

func notionTestContext(principal string, capabilityID string, approvalGrant string) *service.InvocationContext {
	return &service.InvocationContext{
		RootPrincipal: principal,
		Subject:       "agent:notion-live-smoke",
		Scopes:        []string{capabilityID},
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
