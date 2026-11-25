// The REST adapter answers a failed invocation with the status of SPEC.md
// §6.3 "HTTP Status Codes", on both mounts.

package restapi

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func TestRestAnswersTheTableStatusForAFailedInvocation(t *testing.T) {
	svc := service.New(service.Config{
		ServiceID: "test-rest-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "fail_with",
				Description:     "Fails with the named failure type",
				ContractVersion: "1.0",
				Inputs:          []core.CapabilityInput{{Name: "failure_type", Type: "string", Required: true}},
				Output:          core.CapabilityOutput{Type: "object", Fields: []string{}},
				SideEffect:      core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:    []string{"test"},
				ResponseModes:   []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				failureType, _ := params["failure_type"].(string)
				return nil, core.NewANIPError(failureType, "provoked by the test").WithResolution("contact_service_owner")
			},
		}},
		Storage: ":memory:",
		Trust:   "signed",
		Authenticate: func(bearer string) (string, bool) {
			return "human:test@example.com", bearer == "test-api-key"
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Service.Start() error: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })

	mux := http.NewServeMux()
	MountANIPRest(mux, svc, nil)
	plain := httptest.NewServer(mux)
	t.Cleanup(plain.Close)
	gin.SetMode(gin.TestMode)
	router := gin.New()
	MountANIPRestGin(router, svc, nil)
	ginServer := httptest.NewServer(router)
	t.Cleanup(ginServer.Close)

	// One type per status of the table, the default, and the four types
	// whose status this runtime used to get wrong.
	table := map[string]int{
		"invalid_parameters": 400, "grant_param_drift": 400, "seat_unavailable": 400,
		"token_expired": 401, "token_not_registered": 401,
		"budget_exceeded": 403, "constraint_escalation": 403,
		"not_found":   404,
		"unavailable": 409, "grant_consumed": 409, "concurrent_request_rejected": 409,
		"internal_error":      500,
		"service_unavailable": 503,
	}
	for name, ts := range map[string]*httptest.Server{"net/http": plain, "gin": ginServer} {
		t.Run(name, func(t *testing.T) {
			for failureType, want := range table {
				status, data := restCall(t, "GET", ts.URL+"/api/fail_with?failure_type="+url.QueryEscape(failureType), "")
				failure, _ := data["failure"].(map[string]any)
				if failure["type"] != failureType {
					t.Errorf("%s: the response carries failure type %v", failureType, failure["type"])
					continue
				}
				if status != want {
					t.Errorf("%s: status = %d, want %d", failureType, status, want)
				}
			}
		})
	}
}
