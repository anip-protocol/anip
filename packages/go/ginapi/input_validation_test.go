// Parameter validation over HTTP (SPEC.md §6.3 "Parameter Validation"): a
// missing or wrong-typed declared input is refused with invalid_parameters,
// HTTP 400, on the unary and the streaming path.

package ginapi

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// newValidationTestServer serves one capability that supports both response
// modes and declares a required string, an optional integer and a domain type.
func newValidationTestServer(t *testing.T) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	handled := &atomic.Int32{}
	svc := service.New(service.Config{
		ServiceID: "test-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "watch_fares",
				Description:     "Watch fares on a route",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "route", Type: "string", Required: true},
					{Name: "limit", Type: "integer", Required: false, Default: 10},
					{Name: "date", Type: "date", Required: false},
				},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"count"}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"travel.search"},
				ResponseModes: []string{"unary", "streaming"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				handled.Add(1)
				return map[string]any{"count": 0, "limit": params["limit"]}, nil
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

func postInvoke(t *testing.T, ts *httptest.Server, jwt, capability, body string) (*http.Response, map[string]any) {
	t.Helper()
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/"+capability, strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
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
	return resp, data
}

// assertInvalidParametersResponse checks the status and the failure object.
// nullMembers is true where the binding writes the resolution's optional
// members as null (refusals reported through httputil.FailureResponse).
func assertInvalidParametersResponse(t *testing.T, resp *http.Response, data map[string]any, detail string, nullMembers bool) {
	t.Helper()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (%v)", resp.StatusCode, data)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Fatalf("Content-Type = %q, want application/json", ct)
	}
	if data["success"] != false {
		t.Fatalf("expected success=false, got %v", data)
	}
	if _, has := data["result"]; has {
		t.Fatalf("a refused invocation carries a result: %v", data)
	}
	resolution := map[string]any{
		"action":         "retry_now",
		"recovery_class": "retry_now",
		"requires":       "parameters that match the capability's declared inputs",
	}
	if nullMembers {
		resolution["grantable_by"] = nil
		resolution["estimated_availability"] = nil
	}
	want := map[string]any{
		"type":       "invalid_parameters",
		"detail":     detail,
		"resolution": resolution,
		"retry":      false,
	}
	if !reflect.DeepEqual(data["failure"], want) {
		t.Fatalf("failure =\n  %#v\nwant\n  %#v", data["failure"], want)
	}
}

func auditEntryByInvocation(t *testing.T, ts *httptest.Server, jwt, invocationID string) map[string]any {
	t.Helper()
	req, _ := http.NewRequest("POST", ts.URL+"/anip/audit?invocation_id="+invocationID, nil)
	req.Header.Set("Authorization", "Bearer "+jwt)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var data struct {
		Entries []map[string]any `json:"entries"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("audit response: %v", err)
	}
	if len(data.Entries) != 1 {
		t.Fatalf("expected one audit entry for %s, got %d", invocationID, len(data.Entries))
	}
	return data.Entries[0]
}

func TestInvokeMissingRequiredInputIsInvalidParameters(t *testing.T) {
	ts, handled := newValidationTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "watch_fares")

	bodies := map[string]string{
		"empty parameters":  `{"parameters": {}, "client_reference_id": "ref-1"}`,
		"null parameters":   `{"parameters": null, "client_reference_id": "ref-1"}`,
		"absent parameters": `{"client_reference_id": "ref-1"}`,
		"null value":        `{"parameters": {"route": null, "limit": 5}, "client_reference_id": "ref-1"}`,
	}
	for name, body := range bodies {
		t.Run(name, func(t *testing.T) {
			resp, data := postInvoke(t, ts, jwt, "watch_fares", body)
			assertInvalidParametersResponse(t, resp, data, "watch_fares is missing required input(s): route", false)
			if data["client_reference_id"] != "ref-1" {
				t.Fatalf("client_reference_id not echoed: %v", data)
			}
			invocationID, _ := data["invocation_id"].(string)
			if !strings.HasPrefix(invocationID, "inv-") {
				t.Fatalf("no invocation_id on the refusal: %v", data)
			}
			entry := auditEntryByInvocation(t, ts, jwt, invocationID)
			if entry["success"] != false || entry["failure_type"] != "invalid_parameters" {
				t.Fatalf("unexpected audit entry: %v", entry)
			}
		})
	}
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

func TestInvokeWrongTypedInputIsInvalidParameters(t *testing.T) {
	ts, handled := newValidationTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "watch_fares")

	resp, data := postInvoke(t, ts, jwt, "watch_fares", `{"parameters": {"route": 7, "limit": 1.5, "date": true}}`)
	assertInvalidParametersResponse(t, resp, data,
		"watch_fares has invalid input(s): 'route' must be string, got number; 'limit' must be integer, got number", false)
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}

	// 5.0 is the integer 5; a domain-typed input and an undeclared one are not checked.
	resp, data = postInvoke(t, ts, jwt, "watch_fares", `{"parameters": {"route": "SEA-SFO", "limit": 5.0, "date": true, "extra": [1]}}`)
	if resp.StatusCode != 200 || data["success"] != true {
		t.Fatalf("expected 200 success, got %d %v", resp.StatusCode, data)
	}
	if handled.Load() != 1 {
		t.Fatalf("the handler ran %d times, want 1", handled.Load())
	}
}

// A streaming invocation with invalid parameters is refused before the stream
// opens: this binding answers JSON with the mapped status, as it does for the
// other refusals made before the handler.
func TestStreamInvokeInvalidParametersIsJSON400(t *testing.T) {
	ts, handled := newValidationTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "watch_fares")

	resp, data := postInvoke(t, ts, jwt, "watch_fares", `{"parameters": {}, "stream": true}`)
	assertInvalidParametersResponse(t, resp, data, "watch_fares is missing required input(s): route", true)

	resp, data = postInvoke(t, ts, jwt, "watch_fares", `{"parameters": {"route": "SEA-SFO", "limit": "ten"}, "stream": true}`)
	assertInvalidParametersResponse(t, resp, data, "watch_fares has invalid input(s): 'limit' must be integer, got string", true)

	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}

	// Control: the same capability streams when the parameters are valid.
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/watch_fares", strings.NewReader(`{"parameters": {"route": "SEA-SFO"}, "stream": true}`))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")
	streamResp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer streamResp.Body.Close()
	raw, _ := io.ReadAll(streamResp.Body)
	if streamResp.StatusCode != 200 || !strings.HasPrefix(streamResp.Header.Get("Content-Type"), "text/event-stream") {
		t.Fatalf("control: expected an SSE stream, got %d %q %q", streamResp.StatusCode, streamResp.Header.Get("Content-Type"), raw)
	}
	if !strings.Contains(string(raw), "event: completed") {
		t.Fatalf("control: no completed event: %q", raw)
	}
}

// invalid_parameters carries the retry_now resolution at every endpoint that
// returns it: here a grant request that fails schema validation, and one that
// is not JSON (SPEC.md §4.9 step 2).
func TestApprovalGrantsInvalidRequestHasRetryNowResolution(t *testing.T) {
	ts, _ := newValidationTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "watch_fares")

	for name, body := range map[string]string{
		"schema":   `{"grant_type": "one_time"}`,
		"not json": `{"approval_request_id": `,
	} {
		t.Run(name, func(t *testing.T) {
			req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
			req.Header.Set("Authorization", "Bearer "+jwt)
			req.Header.Set("Content-Type", "application/json")
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				t.Fatal(err)
			}
			defer resp.Body.Close()
			var data map[string]any
			json.NewDecoder(resp.Body).Decode(&data)
			failure, _ := data["failure"].(map[string]any)
			resolution, _ := failure["resolution"].(map[string]any)
			if resp.StatusCode != 400 || failure["type"] != "invalid_parameters" || failure["retry"] != false {
				t.Fatalf("got %d %v, want 400 invalid_parameters retry=false", resp.StatusCode, data)
			}
			if resolution["action"] != "retry_now" || resolution["recovery_class"] != "retry_now" {
				t.Fatalf("resolution = %v, want retry_now / retry_now", resolution)
			}
		})
	}
}

// SPEC.md §6.3: a `parameters` value that is neither an object nor null does
// not match the request schema and is refused, like a body that is not JSON.
func TestInvokeParametersThatAreNotAnObjectAreInvalidParameters(t *testing.T) {
	ts, handled := newValidationTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "watch_fares")

	cases := map[string]string{
		"array":   `["LHR-JFK"]`,
		"string":  `"LHR-JFK"`,
		"number":  `1.5`,
		"boolean": `true`,
	}
	for received, value := range cases {
		t.Run(received, func(t *testing.T) {
			resp, data := postInvoke(t, ts, jwt, "watch_fares", `{"parameters": `+value+`}`)
			failure, _ := data["failure"].(map[string]any)
			resolution, _ := failure["resolution"].(map[string]any)
			if resp.StatusCode != http.StatusBadRequest || failure["type"] != "invalid_parameters" {
				t.Fatalf("status %d, failure %v", resp.StatusCode, failure)
			}
			if want := "watch_fares parameters must be an object, got " + received; failure["detail"] != want {
				t.Fatalf("detail = %q, want %q", failure["detail"], want)
			}
			if resolution["action"] != "retry_now" || resolution["recovery_class"] != "retry_now" ||
				resolution["requires"] != "parameters that match the capability's declared inputs" {
				t.Fatalf("resolution = %v", resolution)
			}
			if failure["retry"] != false {
				t.Fatalf("retry = %v, want false", failure["retry"])
			}
		})
	}
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

// stream: true on a capability that only supports unary: a JSON failure whose
// resolution sends the caller back to the manifest, as the other runtimes do.
func TestStreamingNotSupportedResolutionIsCheckManifest(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	resp, data := postInvoke(t, ts, jwt, "search_flights",
		`{"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}, "stream": true}`)

	failure, _ := data["failure"].(map[string]any)
	resolution, _ := failure["resolution"].(map[string]any)
	if resp.StatusCode != http.StatusBadRequest || failure["type"] != "streaming_not_supported" {
		t.Fatalf("status %d, failure %v", resp.StatusCode, failure)
	}
	if resolution["action"] != "check_manifest" || resolution["recovery_class"] != "revalidate_then_retry" {
		t.Fatalf("resolution = %v", resolution)
	}
}

func postForText(t *testing.T, ts *httptest.Server, jwt, capability, body string) string {
	t.Helper()
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/"+capability, strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	return string(raw)
}
