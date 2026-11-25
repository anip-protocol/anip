// Parameter validation over stdio JSON-RPC (SPEC.md §6.3): the refusal is in
// the response message. A unary invocation answers the invoke response with
// success=false; a streaming invocation, refused before the stream opens,
// answers a JSON-RPC error whose data is the failure.

package stdioapi

import (
	"encoding/json"
	"reflect"
	"sync/atomic"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func newValidationStdioServer(t *testing.T) (*Server, string, *atomic.Int32) {
	t.Helper()
	handled := &atomic.Int32{}
	svc := service.New(service.Config{
		ServiceID: "test-stdio-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "watch_fares",
				Description:     "Watch fares on a route",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "route", Type: "string", Required: true},
					{Name: "limit", Type: "integer", Required: false},
				},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"count"}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"travel.search"},
				ResponseModes: []string{"unary", "streaming"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				handled.Add(1)
				return map[string]any{"count": 0}, nil
			},
		}},
		Storage:                  ":memory:",
		Trust:                    "signed",
		RetentionIntervalSeconds: -1,
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	resp, err := svc.IssueToken("human:tester@example.com", core.TokenRequest{
		Subject:    "human:tester@example.com",
		Scope:      []string{"travel.search"},
		Capability: "watch_fares",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	return NewServer(svc), resp.Token, handled
}

func invalidParametersFailureJSON(detail string) map[string]any {
	return map[string]any{
		"type":   "invalid_parameters",
		"detail": detail,
		"resolution": map[string]any{
			"action":         "retry_now",
			"recovery_class": "retry_now",
			"requires":       "parameters that match the capability's declared inputs",
		},
		"retry": false,
	}
}

func TestInvokeInvalidParametersUnary(t *testing.T) {
	srv, jwt, handled := newValidationStdioServer(t)

	cases := []struct {
		name       string
		parameters any
		detail     string
	}{
		{"missing", map[string]any{}, "watch_fares is missing required input(s): route"},
		{"absent parameters", nil, "watch_fares is missing required input(s): route"},
		{"wrong type", map[string]any{"route": "SEA-SFO", "limit": 1.5}, "watch_fares has invalid input(s): 'limit' must be integer, got number"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			params := map[string]any{"auth": map[string]any{"bearer": jwt}, "capability": "watch_fares"}
			if tc.parameters != nil {
				params["parameters"] = tc.parameters
			}
			result := expectSuccess(t, dispatch(t, srv, "anip.invoke", params))
			if result["success"] != false || result["result"] != nil {
				t.Fatalf("expected a refusal without a result, got %v", result)
			}
			if want := invalidParametersFailureJSON(tc.detail); !reflect.DeepEqual(result["failure"], want) {
				t.Fatalf("failure =\n  %#v\nwant\n  %#v", result["failure"], want)
			}
			if id, _ := result["invocation_id"].(string); id == "" {
				t.Fatalf("no invocation_id on the refusal: %v", result)
			}
		})
	}
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

func TestInvokeInvalidParametersStreaming(t *testing.T) {
	srv, jwt, handled := newValidationStdioServer(t)

	messages := dispatch(t, srv, "anip.invoke", map[string]any{
		"auth":       map[string]any{"bearer": jwt},
		"capability": "watch_fares",
		"parameters": map[string]any{"limit": 3},
		"stream":     true,
	})
	rpcErr := expectError(t, messages, codeInternalError)
	raw, _ := json.Marshal(rpcErr.Data)
	var data map[string]any
	json.Unmarshal(raw, &data)
	if want := invalidParametersFailureJSON("watch_fares is missing required input(s): route"); !reflect.DeepEqual(data, want) {
		t.Fatalf("error data =\n  %#v\nwant\n  %#v", data, want)
	}
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}

	// Control: valid parameters stream to a completed result.
	messages = dispatch(t, srv, "anip.invoke", map[string]any{
		"auth":       map[string]any{"bearer": jwt},
		"capability": "watch_fares",
		"parameters": map[string]any{"route": "SEA-SFO", "limit": 3},
		"stream":     true,
	})
	final, ok := messages[len(messages)-1].(response)
	if !ok || final.Error != nil {
		t.Fatalf("control: expected a final response, got %#v", messages[len(messages)-1])
	}
	if handled.Load() != 1 {
		t.Fatal("control: the handler did not run")
	}
}
