// A streaming invocation refused by a pre-handler check is answered the way
// this binding answers every refusal made before the stream opens: JSON with
// the mapped status, carrying the failure the unary path gives for the same
// request (SPEC.md §6.3).

package httpapi

import (
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func newStreamParityTestServer(t *testing.T) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	handled := &atomic.Int32{}
	amount := 10.0
	svc := service.New(service.Config{
		ServiceID: "test-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "stream_book",
				Description:     "Book with streamed progress",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "flight_number", Type: "string", Required: true},
					{Name: "quote_id", Type: "object", Required: false},
				},
				Output:          core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
				SideEffect:      core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
				MinimumScope:    []string{"travel.book"},
				Cost:            &core.Cost{Certainty: "fixed", Financial: &core.FinancialCost{Currency: "USD", Amount: &amount}},
				RequiresBinding: []core.BindingRequirement{{Type: "quote", Field: "quote_id", SourceCapability: "search_flights"}},
				ResponseModes:   []string{"unary", "streaming"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				handled.Add(1)
				return map[string]any{"ok": true}, nil
			},
		}},
		Storage: ":memory:",
		Trust:   "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-api-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Service.Start() error: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	ts := httptest.NewServer(mountForTest(svc))
	t.Cleanup(ts.Close)
	return ts, handled
}

func TestStreamInvokeRefusedByAPreHandlerCheckIsTheUnaryFailure(t *testing.T) {
	ts, handled := newStreamParityTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.book"}, "stream_book")
	quote := `"quote_id": {"id": "qt-1", "price": 10}`

	cases := []struct {
		name, body, failureType string
		status                  int
	}{
		{"budget exceeded", `{"parameters": {"flight_number": "AA100", ` + quote + `}, "budget": {"currency": "USD", "max_amount": 1}`, "budget_exceeded", 403},
		{"budget currency mismatch", `{"parameters": {"flight_number": "AA100", ` + quote + `}, "budget": {"currency": "EUR", "max_amount": 100}`, "budget_currency_mismatch", 403},
		{"binding missing", `{"parameters": {"flight_number": "AA100"}`, "binding_missing", 403},
		{"blank approval grant", `{"parameters": {"flight_number": "AA100", ` + quote + `}, "approval_grant": ""`, "grant_not_found", 400},
		{"unknown approval grant", `{"parameters": {"flight_number": "AA100", ` + quote + `}, "approval_grant": "grant_000000000000"`, "grant_not_found", 400},
		{"parameter validation", `{"parameters": {` + quote + `}`, "invalid_parameters", 400},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			unaryResp, unary := postInvoke(t, ts, jwt, "stream_book", tc.body+`}`)
			unaryFailure, _ := unary["failure"].(map[string]any)
			if unaryFailure["type"] != tc.failureType || unaryResp.StatusCode != tc.status {
				t.Fatalf("unary: got %d %v, the case means to provoke %d %s", unaryResp.StatusCode, unary, tc.status, tc.failureType)
			}

			streamResp, stream := postInvoke(t, ts, jwt, "stream_book", tc.body+`, "stream": true}`)
			if ct := streamResp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
				t.Fatalf("a refusal made before the stream opens is JSON, got Content-Type %q", ct)
			}
			streamFailure, _ := stream["failure"].(map[string]any)
			if streamResp.StatusCode != tc.status || stream["success"] != false || streamFailure["type"] != tc.failureType {
				t.Fatalf("streaming: got %d %v, unary answers %d %s", streamResp.StatusCode, stream, tc.status, tc.failureType)
			}
			if streamFailure["detail"] != unaryFailure["detail"] {
				t.Fatalf("detail differs: streaming %q, unary %q", streamFailure["detail"], unaryFailure["detail"])
			}
		})
	}
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}

	// Control: with a binding and a budget that covers the cost, both modes run the handler.
	ok := `{"parameters": {"flight_number": "AA100", ` + quote + `}, "budget": {"currency": "USD", "max_amount": 100}`
	if resp, data := postInvoke(t, ts, jwt, "stream_book", ok+`}`); resp.StatusCode != 200 || data["success"] != true {
		t.Fatalf("control (unary): got %d %v", resp.StatusCode, data)
	}
	raw := postForText(t, ts, jwt, "stream_book", ok+`, "stream": true}`)
	if !strings.Contains(raw, "event: completed") {
		t.Fatalf("control (streaming): no completed event: %q", raw)
	}
	if handled.Load() != 2 {
		t.Fatalf("control: the handler ran %d times, want 2", handled.Load())
	}
}
