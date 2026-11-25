// One HTTP status per failure type (SPEC.md §6.3 "HTTP Status Codes"), and a
// request body that is not JSON is invalid_parameters after the credential
// check.

package httpapi

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// statusTable is SPEC.md §6.3; core.FailureStatusCode is tested against the
// same rows in packages/go/core.
var statusTable = map[string]int{
	"invalid_parameters": 400, "streaming_not_supported": 400, "approval_required": 400,
	"grant_not_found": 400, "grant_capability_mismatch": 400, "grant_scope_mismatch": 400,
	"grant_param_drift": 400, "grant_session_invalid": 400, "grant_type_not_allowed_by_policy": 400,
	"authentication_required": 401, "invalid_token": 401, "token_expired": 401, "token_not_registered": 401,
	"scope_insufficient": 403, "insufficient_authority": 403, "purpose_mismatch": 403,
	"scope_escalation": 403, "constraint_escalation": 403, "broken_delegation_chain": 403,
	"delegation_depth_exceeded": 403, "parent_token_expired": 403, "budget_exceeded": 403,
	"budget_currency_mismatch": 403, "budget_not_enforceable": 403, "binding_missing": 403,
	"binding_stale": 403, "control_requirement_unsatisfied": 403, "approver_not_authorized": 403,
	"unknown_capability": 404, "not_found": 404, "approval_request_not_found": 404,
	"grant_consumed": 409, "grant_expired": 409, "approval_request_already_decided": 409,
	"approval_request_expired": 409, "concurrent_lock": 409, "concurrent_request_rejected": 409,
	"unavailable":         409,
	"internal_error":      500,
	"service_unavailable": 503,
	// not in the table: 400
	"seat_unavailable": 400,
}

// newStatusTestServer serves a capability whose handler fails with the
// failure type named in its input.
func newStatusTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID: "test-service",
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
	return ts
}

func TestInvokeAnswersTheTableStatusForEveryFailureType(t *testing.T) {
	ts := newStatusTestServer(t)
	jwt := issueToken(t, ts, []string{"test"}, "fail_with")

	for failureType, want := range statusTable {
		if failureType == "approval_required" {
			continue // the runtime materialises an approval request for it; covered by the approval tests
		}
		body, _ := json.Marshal(map[string]any{"parameters": map[string]any{"failure_type": failureType}})
		resp, data := postInvoke(t, ts, jwt, "fail_with", string(body))
		failure, _ := data["failure"].(map[string]any)
		if failure["type"] != failureType {
			t.Errorf("%s: the response carries failure type %v", failureType, failure["type"])
			continue
		}
		if resp.StatusCode != want {
			t.Errorf("%s: status = %d, want %d", failureType, resp.StatusCode, want)
		}
	}
}

func postRaw(t *testing.T, url, bearer, body string) (int, map[string]any) {
	t.Helper()
	req, _ := http.NewRequest("POST", url, strings.NewReader(body))
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	var data map[string]any
	if err := json.Unmarshal(raw, &data); err != nil {
		t.Fatalf("status %d, body is not a JSON object: %q", resp.StatusCode, raw)
	}
	return resp.StatusCode, data
}

func assertBodyIsNotJSONFailure(t *testing.T, status int, data map[string]any) {
	t.Helper()
	failure, _ := data["failure"].(map[string]any)
	resolution, _ := failure["resolution"].(map[string]any)
	if status != 400 || data["success"] != false || failure["type"] != "invalid_parameters" {
		t.Fatalf("got %d %v, want 400 invalid_parameters", status, data)
	}
	if failure["retry"] != false || resolution["action"] != "retry_now" || resolution["recovery_class"] != "retry_now" {
		t.Fatalf("want retry=false and the retry_now resolution, got %v", failure)
	}
	if detail, _ := failure["detail"].(string); detail == "" {
		t.Fatalf("no detail: %v", failure)
	}
}

func assertAuthenticationRequired(t *testing.T, status int, data map[string]any) {
	t.Helper()
	failure, _ := data["failure"].(map[string]any)
	if status != 401 || failure["type"] != "authentication_required" {
		t.Fatalf("got %d %v, want 401 authentication_required", status, data)
	}
}

// Bodies that are not JSON, and JSON that is not an object.
var notAJSONObject = map[string]string{
	"truncated":  `{"parameters": `,
	"not json":   `parameters=1`,
	"empty":      ``,
	"json array": `[1, 2]`,
	"json text":  `"parameters"`,
}

func TestInvokeBodyThatIsNotJSONIsInvalidParameters(t *testing.T) {
	ts := newStatusTestServer(t)
	jwt := issueToken(t, ts, []string{"test"}, "fail_with")

	for name, body := range notAJSONObject {
		t.Run(name, func(t *testing.T) {
			status, data := postRaw(t, ts.URL+"/anip/invoke/fail_with", jwt, body)
			assertBodyIsNotJSONFailure(t, status, data)

			// The credential is checked first.
			status, data = postRaw(t, ts.URL+"/anip/invoke/fail_with", "", body)
			assertAuthenticationRequired(t, status, data)
			status, data = postRaw(t, ts.URL+"/anip/invoke/fail_with", "not-a-token", body)
			if failure, _ := data["failure"].(map[string]any); status != 401 || failure["type"] != "invalid_token" {
				t.Fatalf("got %d %v, want 401 invalid_token", status, data)
			}
		})
	}
}

func TestTokenRequestBodyThatIsNotJSONIsInvalidParameters(t *testing.T) {
	ts := newStatusTestServer(t)

	for name, body := range notAJSONObject {
		t.Run(name, func(t *testing.T) {
			status, data := postRaw(t, ts.URL+"/anip/tokens", "test-api-key", body)
			assertBodyIsNotJSONFailure(t, status, data)

			// The credential is checked first.
			status, data = postRaw(t, ts.URL+"/anip/tokens", "", body)
			assertAuthenticationRequired(t, status, data)
			status, data = postRaw(t, ts.URL+"/anip/tokens", "unknown-key", body)
			assertAuthenticationRequired(t, status, data)
		})
	}
}
