// Parameter validation through the REST adapter (SPEC.md §6.3): the adapter
// invokes through the service, so a missing or wrong-typed declared input is
// answered with invalid_parameters and HTTP 400 on both mounts.

package restapi

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

func restServers(t *testing.T) map[string]*httptest.Server {
	t.Helper()
	return map[string]*httptest.Server{
		"net/http": newHTTPTestServer(t, nil),
		"gin":      newGinTestServer(t, nil),
	}
}

func restCall(t *testing.T, method, url, body string) (int, map[string]any) {
	t.Helper()
	var reader io.Reader
	if body != "" {
		reader = strings.NewReader(body)
	}
	req, _ := http.NewRequest(method, url, reader)
	req.Header.Set("Authorization", "Bearer test-api-key")
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
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

func assertRestInvalidParameters(t *testing.T, status int, data map[string]any, detail string) {
	t.Helper()
	if status != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (%v)", status, data)
	}
	if _, has := data["result"]; has || data["success"] != false {
		t.Fatalf("expected a refusal without a result, got %v", data)
	}
	want := map[string]any{
		"type":   "invalid_parameters",
		"detail": detail,
		"resolution": map[string]any{
			"action":         "retry_now",
			"recovery_class": "retry_now",
			"requires":       "parameters that match the capability's declared inputs",
		},
		"retry": false,
	}
	if !reflect.DeepEqual(data["failure"], want) {
		t.Fatalf("failure =\n  %#v\nwant\n  %#v", data["failure"], want)
	}
	if id, _ := data["invocation_id"].(string); !strings.HasPrefix(id, "inv-") {
		t.Fatalf("no invocation_id on the refusal: %v", data)
	}
}

func TestRestMissingRequiredInputIsInvalidParameters(t *testing.T) {
	for name, ts := range restServers(t) {
		t.Run(name, func(t *testing.T) {
			status, data := restCall(t, "GET", ts.URL+"/api/greet?count=2", "")
			assertRestInvalidParameters(t, status, data, "greet is missing required input(s): name")

			status, data = restCall(t, "POST", ts.URL+"/api/book", `{"quantity": 2}`)
			assertRestInvalidParameters(t, status, data, "book is missing required input(s): item")

			status, data = restCall(t, "POST", ts.URL+"/api/book", `{"parameters": {"item": null}}`)
			assertRestInvalidParameters(t, status, data, "book is missing required input(s): item")
		})
	}
}

func TestRestWrongTypedInputIsInvalidParameters(t *testing.T) {
	for name, ts := range restServers(t) {
		t.Run(name, func(t *testing.T) {
			// A query value that is not a number stays a string.
			status, data := restCall(t, "GET", ts.URL+"/api/greet?name=Bob&count=many", "")
			assertRestInvalidParameters(t, status, data, "greet has invalid input(s): 'count' must be integer, got string")

			status, data = restCall(t, "POST", ts.URL+"/api/book", `{"item": 7, "quantity": 1.5}`)
			assertRestInvalidParameters(t, status, data,
				"book has invalid input(s): 'item' must be string, got number; 'quantity' must be integer, got number")

			// Control: typed query values and an integral float are accepted.
			status, data = restCall(t, "GET", ts.URL+"/api/greet?name=Bob&count=3&loud=true", "")
			if status != 200 || data["success"] != true {
				t.Fatalf("control GET: got %d %v", status, data)
			}
			status, data = restCall(t, "POST", ts.URL+"/api/book", `{"item": "flight", "quantity": 2.0}`)
			if status != 200 || data["success"] != true {
				t.Fatalf("control POST: got %d %v", status, data)
			}
		})
	}
}

// A body that is not JSON is invalid_parameters with the same recovery
// guidance: correct the request and send it again.
func TestRestBodyThatIsNotJSONIsInvalidParameters(t *testing.T) {
	for name, ts := range restServers(t) {
		t.Run(name, func(t *testing.T) {
			status, data := restCall(t, "POST", ts.URL+"/api/book", `{"item": `)
			if status != http.StatusBadRequest || data["success"] != false {
				t.Fatalf("got %d %v, want 400 and a failure", status, data)
			}
			failure, _ := data["failure"].(map[string]any)
			resolution, _ := failure["resolution"].(map[string]any)
			if failure["type"] != "invalid_parameters" || failure["retry"] != false ||
				resolution["action"] != "retry_now" || resolution["recovery_class"] != "retry_now" {
				t.Fatalf("unexpected failure: %v", failure)
			}
		})
	}
}
