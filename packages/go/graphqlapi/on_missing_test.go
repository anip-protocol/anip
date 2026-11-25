package graphqlapi

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// SPEC.md §4.10 / §6.3: an input that declares resolution.on_missing is left
// to the service when absent, so the schema does not make it non-null.
func TestOnMissingInputIsNullableInTheSchemaAndReachesTheCapability(t *testing.T) {
	clarify := core.ResolutionBehaviorClarify
	var calls []map[string]any
	svc := service.New(service.Config{
		ServiceID: "test-graphql-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "region_report",
				Description:     "Report for a region",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "region", Type: "string", Required: true,
						Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify, OnMissing: &clarify}},
					{Name: "quarter", Type: "string", Required: true,
						Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify}},
				},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"report"},
				ResponseModes: []string{"unary"},
			},
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

	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema: %v", err)
	}
	if !strings.Contains(sdl, "regionReport(region: String, quarter: String!)") {
		t.Fatalf("the SDL should make only quarter non-null:\n%s", sdl)
	}

	mux := http.NewServeMux()
	MountANIPGraphQL(mux, svc, nil)
	plain := httptest.NewServer(mux)
	t.Cleanup(plain.Close)
	gin.SetMode(gin.TestMode)
	router := gin.New()
	MountANIPGraphQLGin(router, svc, nil)
	ginServer := httptest.NewServer(router)
	t.Cleanup(ginServer.Close)

	for name, ts := range map[string]*httptest.Server{"net/http": plain, "gin": ginServer} {
		t.Run(name, func(t *testing.T) {
			before := len(calls)
			result := postGraphQL(t, ts.URL+"/graphql",
				`{ regionReport(quarter: "Q1") { success failure { type detail } } }`, "Bearer test-api-key")
			data, _ := result["data"].(map[string]any)
			field, _ := data["regionReport"].(map[string]any)
			if result["errors"] != nil || field["success"] != true {
				t.Fatalf("expected the capability to run, got %v", result)
			}
			if len(calls) != before+1 {
				t.Fatalf("the capability ran %d times, want 1", len(calls)-before)
			}
			if _, has := calls[len(calls)-1]["region"]; has {
				t.Fatalf("the absent argument must not be passed as a parameter: %v", calls[len(calls)-1])
			}

			// A resolution without on_missing leaves the argument non-null.
			result = postGraphQL(t, ts.URL+"/graphql",
				`{ regionReport(region: "eu") { success } }`, "Bearer test-api-key")
			if errs, _ := result["errors"].([]any); len(errs) == 0 {
				t.Fatalf("expected a GraphQL error for the missing non-null argument, got %v", result)
			}
			if len(calls) != before+1 {
				t.Fatal("the capability ran for an invalid GraphQL request")
			}
		})
	}
}
