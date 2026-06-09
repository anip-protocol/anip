package host

import (
	"os"
	"testing"

	"github.com/anip-protocol/anip/packages/go/service"
)

func TestSupersetGeneratedHandlerLiveSmoke(t *testing.T) {
	if os.Getenv("SUPERSET_BASE_URL") == "" || (os.Getenv("SUPERSET_ACCESS_TOKEN") == "" && (os.Getenv("SUPERSET_USERNAME") == "" || os.Getenv("SUPERSET_PASSWORD") == "")) {
		t.Skip("Superset credentials are not configured")
	}
	workspaceScope := firstNonEmpty(os.Getenv("SUPERSET_WORKSPACE_SCOPE"), "local")
	if os.Getenv("ANIP_SUPERSET_ALLOWED_WORKSPACES") == "" {
		t.Setenv("ANIP_SUPERSET_ALLOWED_WORKSPACES", workspaceScope)
	}

	discovery := invokeForTest(t, "superset.analytics.discover_context", map[string]any{"workspace_scope": workspaceScope, "query": "birth", "limit": 5})
	if discovery["execution_status"] != "completed" {
		t.Fatalf("expected discovery completed, got %#v", discovery)
	}

	chart := invokeForTest(t, "superset.chart.preview.create", map[string]any{"dataset_ref": "1", "metric": "count", "visualization_type": "bar", "title": "ANIP Go preview chart"})
	if chart["execution_status"] != "prepared" || chart["mutation_performed"] != false {
		t.Fatalf("expected chart preview without mutation, got %#v", chart)
	}
	request := chart["superset_request"].(map[string]any)
	body := request["body"].(map[string]any)
	if body["save_chart"] != false {
		t.Fatalf("expected save_chart=false, got %#v", chart)
	}

	dataset := invokeForTest(t, "superset.dataset.draft.prepare", map[string]any{"database_ref": "1", "dataset_purpose": "ANIP smoke", "query_intent": "Count records by category"})
	if dataset["execution_status"] != "prepared" || dataset["mutation_performed"] != false {
		t.Fatalf("expected dataset draft without mutation, got %#v", dataset)
	}
}

func invokeForTest(t *testing.T, capabilityID string, params map[string]any) map[string]any {
	t.Helper()
	capability := capabilityDefForTest(t, capabilityID)
	result, err := capability.Handler(&service.InvocationContext{
		RootPrincipal: "human:local-dev|actor_id=superset_fronting_consumer",
		Subject:       "agent:superset-live-smoke",
		Scopes:        []string{capabilityID},
		InvocationID:  "inv-test",
	}, params)
	if err != nil {
		t.Fatal(err)
	}
	return result
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
