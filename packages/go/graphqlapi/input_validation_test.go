// Parameter validation through the GraphQL adapter (SPEC.md §6.3). GraphQL
// convention applies: HTTP 200, the ANIP failure in the field's result.
//
// GraphQL's own type system refuses most invalid calls before the resolver
// runs (a missing non-null argument, a string where Int is declared) and
// reports them in the top-level "errors" member. What reaches the service is
// a value of the JSON scalar, which carries array, object and domain-typed
// inputs: there the service check answers invalid_parameters.

package graphqlapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"sync/atomic"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func newValidationGraphQLServers(t *testing.T) (map[string]*httptest.Server, *atomic.Int32) {
	t.Helper()
	handled := &atomic.Int32{}
	svc := service.New(service.Config{
		ServiceID: "test-graphql-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "price_quote",
				Description:     "Price a quote",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "quote", Type: "object", Required: true},
					{Name: "tags", Type: "array", Required: false},
					{Name: "seats", Type: "integer", Required: false},
				},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"quote"},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				handled.Add(1)
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
		t.Fatalf("Service.Start() error: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })

	mux := http.NewServeMux()
	MountANIPGraphQL(mux, svc, nil)
	httpServer := httptest.NewServer(mux)
	t.Cleanup(httpServer.Close)

	gin.SetMode(gin.TestMode)
	router := gin.New()
	MountANIPGraphQLGin(router, svc, nil)
	ginServer := httptest.NewServer(router)
	t.Cleanup(ginServer.Close)

	return map[string]*httptest.Server{"net/http": httpServer, "gin": ginServer}, handled
}

func postGraphQLWithVariables(t *testing.T, url, query string, variables map[string]any) map[string]any {
	t.Helper()
	body, _ := json.Marshal(map[string]any{"query": query, "variables": variables})
	req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer test-api-key")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("GraphQL answers 200, got %d", resp.StatusCode)
	}
	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		t.Fatalf("response is not JSON: %v", err)
	}
	return result
}

const priceQuoteQuery = `query($quote: JSON!, $tags: JSON, $seats: Int) {
  priceQuote(quote: $quote, tags: $tags, seats: $seats) {
    success
    result
    failure { type detail retry resolution { action recoveryClass requires } }
  }
}`

func TestGraphQLWrongTypedInputIsInvalidParameters(t *testing.T) {
	servers, handled := newValidationGraphQLServers(t)
	for name, ts := range servers {
		t.Run(name, func(t *testing.T) {
			before := handled.Load()
			result := postGraphQLWithVariables(t, ts.URL+"/graphql", priceQuoteQuery,
				map[string]any{"quote": "qt-1", "tags": map[string]any{"a": 1}, "seats": 2})
			if result["errors"] != nil {
				t.Fatalf("unexpected GraphQL errors: %v", result["errors"])
			}
			field, _ := result["data"].(map[string]any)["priceQuote"].(map[string]any)
			if field["success"] != false || field["result"] != nil {
				t.Fatalf("expected a refusal without a result, got %v", field)
			}
			want := map[string]any{
				"type":   "invalid_parameters",
				"detail": "price_quote has invalid input(s): 'quote' must be object, got string; 'tags' must be array, got object",
				"retry":  false,
				"resolution": map[string]any{
					"action":        "retry_now",
					"recoveryClass": "retry_now",
					"requires":      "parameters that match the capability's declared inputs",
				},
			}
			if !reflect.DeepEqual(field["failure"], want) {
				t.Fatalf("failure =\n  %#v\nwant\n  %#v", field["failure"], want)
			}
			if handled.Load() != before {
				t.Fatal("the handler ran for a refused invocation")
			}

			// Control: an object, an array and a GraphQL Int are accepted.
			result = postGraphQLWithVariables(t, ts.URL+"/graphql", priceQuoteQuery,
				map[string]any{"quote": map[string]any{"id": "qt-1"}, "tags": []any{"a"}, "seats": 2})
			field, _ = result["data"].(map[string]any)["priceQuote"].(map[string]any)
			if field["success"] != true {
				t.Fatalf("control: expected success, got %v", result)
			}
			if handled.Load() != before+1 {
				t.Fatal("control: the handler did not run")
			}
		})
	}
}

// A missing required argument never reaches the service: the schema declares
// it non-null, and GraphQL reports the request as invalid.
func TestGraphQLMissingRequiredArgumentIsAGraphQLError(t *testing.T) {
	servers, handled := newValidationGraphQLServers(t)
	for name, ts := range servers {
		t.Run(name, func(t *testing.T) {
			result := postGraphQLWithVariables(t, ts.URL+"/graphql",
				`{ priceQuote(seats: 2) { success failure { type } } }`, nil)
			errs, _ := result["errors"].([]any)
			if len(errs) == 0 {
				t.Fatalf("expected GraphQL errors for a missing non-null argument, got %v", result)
			}
			if handled.Load() != 0 {
				t.Fatal("the handler ran for an invalid GraphQL request")
			}
		})
	}
}
