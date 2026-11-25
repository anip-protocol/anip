package restapi

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"reflect"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// The service checks a supplied value against a declared primitive type
// (SPEC.md §6.3), so the OpenAPI document asks for that type and a GET reads
// a query value as the JSON value its declared type calls for.
func TestConvertQueryValue(t *testing.T) {
	cases := []struct {
		value, declared string
		want            any
	}{
		{"3", "integer", 3.0},
		{"3.0", "integer", 3.0},
		{"1e2", "integer", 100.0},
		{"-7", "integer", -7.0},
		{"2.5", "number", 2.5},
		{"many", "integer", "many"},
		{"0x10", "integer", "0x10"},
		{"NaN", "number", "NaN"},
		{"Infinity", "number", "Infinity"},
		{" 3", "integer", " 3"},
		{"", "integer", ""},
		{"true", "boolean", true},
		{"false", "boolean", false},
		{"yes", "boolean", "yes"},
		{`["a","b"]`, "array", []any{"a", "b"}},
		{`{"id":"qt-1","price":420}`, "object", map[string]any{"id": "qt-1", "price": 420.0}},
		{"a,b", "array", "a,b"},
		{"qt-1", "object", "qt-1"},
		{"SEA", "string", "SEA"},
		{"123", "string", "123"},
		{"2026-03-10", "date", "2026-03-10"},
		{"123", "", "123"},
	}
	for _, tc := range cases {
		if got := convertQueryValue(tc.value, tc.declared); !reflect.DeepEqual(got, tc.want) {
			t.Errorf("convertQueryValue(%q, %q) = %#v, want %#v", tc.value, tc.declared, got, tc.want)
		}
	}
}

func TestOpenAPINamesArrayAndObjectTypes(t *testing.T) {
	for declared, want := range map[string]string{
		"string": "string", "integer": "integer", "number": "number", "boolean": "boolean",
		"array": "array", "object": "object", "date": "string", "airport_code": "string", "cohort": "string",
	} {
		if got := mapType(declared); got != want {
			t.Errorf("mapType(%q) = %q, want %q", declared, got, want)
		}
	}
}

func TestRestGetCarriesArrayAndObjectInputsAsJSONText(t *testing.T) {
	var seen map[string]any
	svc := service.New(service.Config{
		ServiceID: "test-rest-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name: "find", Description: "find", ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "tags", Type: "array", Required: true},
					{Name: "filter", Type: "object", Required: false},
					{Name: "exact", Type: "boolean", Required: false},
				},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"find"},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				seen = params
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
			query := url.Values{"tags": {`["a","b"]`}, "filter": {`{"stops":0}`}, "exact": {"false"}}
			status, data := restCall(t, "GET", ts.URL+"/api/find?"+query.Encode(), "")
			if status != 200 || data["success"] != true {
				t.Fatalf("got %d %v", status, data)
			}
			want := map[string]any{"tags": []any{"a", "b"}, "filter": map[string]any{"stops": 0.0}, "exact": false}
			if !reflect.DeepEqual(seen, want) {
				t.Fatalf("the handler saw %#v, want %#v", seen, want)
			}

			// Values that cannot be read as the declared type stay strings and are refused by name.
			query = url.Values{"tags": {"a,b"}, "exact": {"yes"}}
			status, data = restCall(t, "GET", ts.URL+"/api/find?"+query.Encode(), "")
			assertRestInvalidParameters(t, status, data,
				"find has invalid input(s): 'tags' must be array, got string; 'exact' must be boolean, got string")
		})
	}
}
