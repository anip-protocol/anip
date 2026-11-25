package mcpapi

import (
	"reflect"
	"sort"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func onMissingReportDecl() core.CapabilityDeclaration {
	clarify := core.ResolutionBehaviorClarify
	return core.CapabilityDeclaration{
		Name:            "region_report",
		Description:     "Report for a region",
		ContractVersion: "1.0",
		Inputs: []core.CapabilityInput{
			{Name: "region", Type: "string", Required: true, Description: "Region",
				Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify, OnMissing: &clarify}},
			{Name: "quarter", Type: "string", Required: true, Description: "Quarter",
				Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify}},
			{Name: "currency", Type: "string", Required: true, Description: "Currency"},
			{Name: "notes", Type: "string", Required: false, Description: "Notes"},
		},
		Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
		SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope:  []string{"report"},
		ResponseModes: []string{"unary"},
	}
}

// SPEC.md §4.10 / §6.3: an input that declares resolution.on_missing is left
// to the service when absent, so the tool schema does not demand it.
func TestCapabilityToInputSchema_OnMissingInputIsNotRequired(t *testing.T) {
	decl := onMissingReportDecl()
	schema := CapabilityToInputSchema(&decl)
	required, _ := schema["required"].([]string)
	sort.Strings(required)
	if want := []string{"currency", "quarter"}; !reflect.DeepEqual(required, want) {
		t.Fatalf("required = %v, want %v", required, want)
	}
	if _, ok := schema["properties"].(map[string]any)["region"]; !ok {
		t.Fatal("the on_missing input must still be a property of the schema")
	}
}

func TestInvoke_MissingOnMissingInputReachesTheCapability(t *testing.T) {
	var calls []map[string]any
	svc := service.New(service.Config{
		ServiceID: "test-mcp-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: onMissingReportDecl(),
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				calls = append(calls, params)
				return map[string]any{"ok": true}, nil
			},
		}},
		Storage: ":memory:",
		Trust:   "signed",
		Authenticate: func(bearer string) (string, bool) {
			return "human:test@example.com", bearer == "test-api-key"
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	creds := &McpCredentials{APIKey: "test-api-key", Scope: []string{"report"}, Subject: "adapter:mcp-test"}

	result := InvokeWithMountCredentials(svc, "region_report", map[string]any{"quarter": "Q1", "currency": "USD"}, creds)
	if result.IsError || len(calls) != 1 {
		t.Fatalf("expected the capability to run, got isError=%v %s (calls %v)", result.IsError, result.Text, calls)
	}

	result = InvokeWithMountCredentials(svc, "region_report", map[string]any{"region": "eu", "currency": "USD"}, creds)
	if !result.IsError || !strings.Contains(result.Text, "region_report is missing required input(s): quarter") || len(calls) != 1 {
		t.Fatalf("a resolution without on_missing leaves the input required, got isError=%v %s", result.IsError, result.Text)
	}
}

// The service checks array and object inputs against the JSON type (SPEC.md
// §6.3), so the tool schema asks for that type, not for a string.
func TestCapabilityToInputSchema_ArrayAndObjectTypes(t *testing.T) {
	decl := &core.CapabilityDeclaration{Inputs: []core.CapabilityInput{
		{Name: "tags", Type: "array", Required: true},
		{Name: "quote_id", Type: "object", Required: false},
		{Name: "cohort", Type: "cohort_reference", Required: false},
	}}
	props := CapabilityToInputSchema(decl)["properties"].(map[string]any)
	for name, want := range map[string]string{"tags": "array", "quote_id": "object", "cohort": "string"} {
		if got := props[name].(map[string]any)["type"]; got != want {
			t.Errorf("%s: schema type = %v, want %q", name, got, want)
		}
	}
}
