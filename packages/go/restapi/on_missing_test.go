package restapi

import (
	"net/http"
	"net/http/httptest"
	"reflect"
	"sort"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// SPEC.md §4.10 / §6.3: an input that declares resolution.on_missing is left
// to the service when absent, so the OpenAPI document does not demand it and
// a call without it reaches the capability.
func TestOnMissingInputIsNotRequiredByOpenAPIAndReachesTheCapability(t *testing.T) {
	clarify := core.ResolutionBehaviorClarify
	inputs := []core.CapabilityInput{
		{Name: "region", Type: "string", Required: true,
			Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify, OnMissing: &clarify}},
		{Name: "quarter", Type: "string", Required: true,
			Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify}},
		{Name: "currency", Type: "string", Required: true},
	}
	decl := func(name, sideEffect string) core.CapabilityDeclaration {
		return core.CapabilityDeclaration{
			Name: name, Description: name, ContractVersion: "1.0", Inputs: inputs,
			Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
			SideEffect:    core.SideEffect{Type: sideEffect, RollbackWindow: "not_applicable"},
			MinimumScope:  []string{"report"},
			ResponseModes: []string{"unary"},
		}
	}
	calls := 0
	handler := func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
		calls++
		return map[string]any{"ok": true}, nil
	}
	svc := service.New(service.Config{
		ServiceID: "test-rest-service",
		Capabilities: []service.CapabilityDef{
			{Declaration: decl("region_report", "read"), Handler: handler},
			{Declaration: decl("region_update", "write"), Handler: handler},
		},
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

	spec := GenerateOpenAPISpec("test-rest-service", GenerateRoutes(svc, nil))
	paths := spec["paths"].(map[string]any)

	get := paths["/api/region_report"].(map[string]any)["get"].(map[string]any)
	demanded := map[string]bool{}
	for _, parameter := range get["parameters"].([]map[string]any) {
		demanded[parameter["name"].(string)] = parameter["required"].(bool)
	}
	if want := map[string]bool{"region": false, "quarter": true, "currency": true}; !reflect.DeepEqual(demanded, want) {
		t.Fatalf("query parameters required = %v, want %v", demanded, want)
	}

	post := paths["/api/region_update"].(map[string]any)["post"].(map[string]any)
	schema := post["requestBody"].(map[string]any)["content"].(map[string]any)["application/json"].(map[string]any)["schema"].(map[string]any)
	required, _ := schema["required"].([]string)
	sort.Strings(required)
	if want := []string{"currency", "quarter"}; !reflect.DeepEqual(required, want) {
		t.Fatalf("request body required = %v, want %v", required, want)
	}

	mux := http.NewServeMux()
	MountANIPRest(mux, svc, nil)
	plain := httptest.NewServer(mux)
	t.Cleanup(plain.Close)
	gin.SetMode(gin.TestMode)
	router := gin.New()
	MountANIPRestGin(router, svc, nil)
	ginServer := httptest.NewServer(router)
	t.Cleanup(ginServer.Close)

	for name, ts := range map[string]*httptest.Server{"net/http": plain, "gin": ginServer} {
		t.Run(name, func(t *testing.T) {
			before := calls
			status, data := restCall(t, "GET", ts.URL+"/api/region_report?quarter=Q1&currency=USD", "")
			if status != 200 || data["success"] != true {
				t.Fatalf("GET without the on_missing input: got %d %v", status, data)
			}
			status, data = restCall(t, "POST", ts.URL+"/api/region_update", `{"quarter": "Q1", "currency": "USD"}`)
			if status != 200 || data["success"] != true {
				t.Fatalf("POST without the on_missing input: got %d %v", status, data)
			}
			if calls != before+2 {
				t.Fatalf("the capabilities ran %d times, want 2", calls-before)
			}
			status, data = restCall(t, "GET", ts.URL+"/api/region_report?region=eu&currency=USD", "")
			assertRestInvalidParameters(t, status, data, "region_report is missing required input(s): quarter")
		})
	}
}
