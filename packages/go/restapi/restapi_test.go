package restapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func floatPtr(f float64) *float64 { return &f }

// testCapabilities returns two test capabilities: greet (read) and book (write).
func testCapabilities() []service.CapabilityDef {
	return []service.CapabilityDef{
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "greet",
				Description:     "Greet a person",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "name", Type: "string", Required: true, Description: "Person to greet"},
					{Name: "count", Type: "integer", Required: false, Default: 1, Description: "Repeat count"},
					{Name: "loud", Type: "boolean", Required: false, Description: "Shout the greeting"},
				},
				Output: core.CapabilityOutput{
					Type:   "object",
					Fields: []string{"greeting"},
				},
				SideEffect: core.SideEffect{
					Type:           "read",
					RollbackWindow: "not_applicable",
				},
				MinimumScope:  []string{"greet"},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				name, _ := params["name"].(string)
				if name == "" {
					name = "World"
				}
				return map[string]any{
					"greeting": "Hello, " + name + "!",
				}, nil
			},
		},
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "book",
				Description:     "Book a reservation",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "item", Type: "string", Required: true, Description: "Item to book"},
					{Name: "quantity", Type: "integer", Required: false, Default: 1, Description: "Number of items"},
				},
				Output: core.CapabilityOutput{
					Type:   "object",
					Fields: []string{"booking_id", "item"},
				},
				SideEffect: core.SideEffect{
					Type:           "irreversible",
					RollbackWindow: "none",
				},
				MinimumScope: []string{"book"},
				Cost: &core.Cost{
					Certainty: "estimated",
					Financial: &core.FinancialCost{
						Currency: "USD",
						RangeMin: floatPtr(10),
						RangeMax: floatPtr(100),
					},
				},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				item, _ := params["item"].(string)
				return map[string]any{
					"booking_id": "BK-999",
					"item":       item,
				}, nil
			},
		},
	}
}

func newTestService(t *testing.T) *service.Service {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID:    "test-rest-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Trust:        "signed",
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
	return svc
}

func newHTTPTestServer(t *testing.T, opts *RestOptions) *httptest.Server {
	t.Helper()
	svc := newTestService(t)
	mux := http.NewServeMux()
	MountANIPRest(mux, svc, opts)
	ts := httptest.NewServer(mux)
	t.Cleanup(ts.Close)
	return ts
}

func newGinTestServer(t *testing.T, opts *RestOptions) *httptest.Server {
	t.Helper()
	svc := newTestService(t)
	gin.SetMode(gin.TestMode)
	router := gin.New()
	MountANIPRestGin(router, svc, opts)
	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)
	return ts
}

// --- OpenAPI Spec Generation ---

func TestGenerateOpenAPISpec(t *testing.T) {
	svc := newTestService(t)
	routes := GenerateRoutes(svc, nil)
	spec := GenerateOpenAPISpec("test-rest-service", routes)

	// Check top-level fields.
	if spec["openapi"] != "3.1.0" {
		t.Fatalf("expected openapi=3.1.0, got %v", spec["openapi"])
	}

	info, _ := spec["info"].(map[string]any)
	if info == nil {
		t.Fatal("missing info")
	}

	paths, _ := spec["paths"].(map[string]any)
	if paths == nil {
		t.Fatal("missing paths")
	}

	// Greet should be GET at /api/greet
	greetPath, ok := paths["/api/greet"]
	if !ok {
		t.Fatal("missing /api/greet path")
	}
	greetOp, _ := greetPath.(map[string]any)["get"].(map[string]any)
	if greetOp == nil {
		t.Fatal("greet should be a GET route")
	}
	if greetOp["operationId"] != "greet" {
		t.Fatalf("expected operationId=greet, got %v", greetOp["operationId"])
	}
	// Should have query parameters, not request body
	if _, ok := greetOp["parameters"]; !ok {
		t.Fatal("GET route should have parameters")
	}
	if _, ok := greetOp["requestBody"]; ok {
		t.Fatal("GET route should not have requestBody")
	}

	// Book should be POST at /api/book
	bookPath, ok := paths["/api/book"]
	if !ok {
		t.Fatal("missing /api/book path")
	}
	bookOp, _ := bookPath.(map[string]any)["post"].(map[string]any)
	if bookOp == nil {
		t.Fatal("book should be a POST route")
	}
	// Should have request body, not query parameters
	if _, ok := bookOp["requestBody"]; !ok {
		t.Fatal("POST route should have requestBody")
	}
	if _, ok := bookOp["parameters"]; ok {
		t.Fatal("POST route should not have parameters")
	}

	// Check ANIP extensions
	if bookOp["x-anip-financial"] != true {
		t.Fatalf("expected x-anip-financial=true for book, got %v", bookOp["x-anip-financial"])
	}
	if greetOp["x-anip-side-effect"] != "read" {
		t.Fatalf("expected x-anip-side-effect=read for greet, got %v", greetOp["x-anip-side-effect"])
	}

	// Check components
	components, _ := spec["components"].(map[string]any)
	if components == nil {
		t.Fatal("missing components")
	}
	schemas, _ := components["schemas"].(map[string]any)
	if schemas == nil {
		t.Fatal("missing schemas")
	}
	if _, ok := schemas["ANIPResponse"]; !ok {
		t.Fatal("missing ANIPResponse schema")
	}
	if _, ok := schemas["ANIPFailure"]; !ok {
		t.Fatal("missing ANIPFailure schema")
	}

	// Check security
	security, _ := spec["security"].([]map[string]any)
	if len(security) == 0 {
		t.Fatal("missing security")
	}
}

// --- Route Generation ---

func TestGenerateRoutes(t *testing.T) {
	svc := newTestService(t)
	routes := GenerateRoutes(svc, nil)

	if len(routes) != 2 {
		t.Fatalf("expected 2 routes, got %d", len(routes))
	}

	// Find routes by name (map iteration is non-deterministic)
	routeMap := make(map[string]RESTRoute)
	for _, r := range routes {
		routeMap[r.CapabilityName] = r
	}

	greet, ok := routeMap["greet"]
	if !ok {
		t.Fatal("missing greet route")
	}
	if greet.Method != "GET" {
		t.Fatalf("expected greet method=GET, got %s", greet.Method)
	}
	if greet.Path != "/api/greet" {
		t.Fatalf("expected greet path=/api/greet, got %s", greet.Path)
	}

	book, ok := routeMap["book"]
	if !ok {
		t.Fatal("missing book route")
	}
	if book.Method != "POST" {
		t.Fatalf("expected book method=POST, got %s", book.Method)
	}
	if book.Path != "/api/book" {
		t.Fatalf("expected book path=/api/book, got %s", book.Path)
	}
}

func TestRouteOverrides(t *testing.T) {
	svc := newTestService(t)
	overrides := map[string]RouteOverride{
		"greet": {Path: "/v2/hello", Method: "POST"},
		"book":  {Path: "/v2/reserve"},
	}
	routes := GenerateRoutes(svc, overrides)

	routeMap := make(map[string]RESTRoute)
	for _, r := range routes {
		routeMap[r.CapabilityName] = r
	}

	greet := routeMap["greet"]
	if greet.Path != "/v2/hello" {
		t.Fatalf("expected overridden path=/v2/hello, got %s", greet.Path)
	}
	if greet.Method != "POST" {
		t.Fatalf("expected overridden method=POST, got %s", greet.Method)
	}

	book := routeMap["book"]
	if book.Path != "/v2/reserve" {
		t.Fatalf("expected overridden path=/v2/reserve, got %s", book.Path)
	}
	// Method should remain POST (default for non-read)
	if book.Method != "POST" {
		t.Fatalf("expected method=POST, got %s", book.Method)
	}
}

// --- HTTP Mount Tests ---

func TestHTTPGetReadCapabilityWithAPIKey(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
	result, _ := data["result"].(map[string]any)
	greeting, _ := result["greeting"].(string)
	if !strings.Contains(greeting, "Alice") {
		t.Fatalf("expected greeting to contain Alice, got %q", greeting)
	}
}

func TestHTTPPostWriteCapabilityWithAPIKey(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	body := `{"item": "flight", "quantity": 2}`
	req, _ := http.NewRequest("POST", ts.URL+"/api/book", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
	result, _ := data["result"].(map[string]any)
	if result["booking_id"] != "BK-999" {
		t.Fatalf("expected booking_id=BK-999, got %v", result["booking_id"])
	}
}

func TestHTTPMissingAuth401(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 401 {
		t.Fatalf("expected 401, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != false {
		t.Fatal("expected success=false")
	}
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureAuthRequired {
		t.Fatalf("expected type=%q, got %v", core.FailureAuthRequired, failure["type"])
	}
}

func TestHTTPInvalidJWT401(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer garbage-not-a-jwt-or-api-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 401 {
		t.Fatalf("expected 401, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != false {
		t.Fatal("expected success=false")
	}
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidToken {
		t.Fatalf("expected type=%q, got %v", core.FailureInvalidToken, failure["type"])
	}
}

func TestHTTPOpenAPIEndpoint(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/rest/openapi.json")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var spec map[string]any
	json.NewDecoder(resp.Body).Decode(&spec)
	if spec["openapi"] != "3.1.0" {
		t.Fatalf("expected openapi=3.1.0, got %v", spec["openapi"])
	}
	paths, _ := spec["paths"].(map[string]any)
	if paths == nil || len(paths) == 0 {
		t.Fatal("expected non-empty paths")
	}
}

func TestHTTPDocsEndpoint(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/rest/docs")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	ct := resp.Header.Get("Content-Type")
	if !strings.Contains(ct, "text/html") {
		t.Fatalf("expected Content-Type text/html, got %q", ct)
	}

	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	body := buf.String()
	if !strings.Contains(body, "swagger-ui") {
		t.Fatal("expected Swagger UI HTML")
	}
}

func TestHTTPRouteOverrides(t *testing.T) {
	ts := newHTTPTestServer(t, &RestOptions{
		Routes: map[string]RouteOverride{
			"greet": {Path: "/v2/hello", Method: "POST"},
		},
	})

	// Original path should not work (404)
	req1, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req1.Header.Set("Authorization", "Bearer test-api-key")
	resp1, _ := http.DefaultClient.Do(req1)
	resp1.Body.Close()
	if resp1.StatusCode == 200 {
		t.Fatal("expected original path to not work with override")
	}

	// Overridden path should work
	body := `{"name": "Alice"}`
	req2, _ := http.NewRequest("POST", ts.URL+"/v2/hello", strings.NewReader(body))
	req2.Header.Set("Authorization", "Bearer test-api-key")
	req2.Header.Set("Content-Type", "application/json")
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		t.Fatal(err)
	}
	defer resp2.Body.Close()

	if resp2.StatusCode != 200 {
		t.Fatalf("expected 200 for overridden route, got %d", resp2.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp2.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
}

func TestHTTPQueryParamTypeConversion(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Bob&count=3&loud=true", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
}

func TestHTTPClientReferenceID(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("X-Client-Reference-Id", "ref-123")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	clientRef, _ := data["client_reference_id"].(string)
	if clientRef != "ref-123" {
		t.Fatalf("expected client_reference_id=ref-123, got %q", clientRef)
	}
}

// --- Gin Mount Tests ---

func TestGinGetReadCapabilityWithAPIKey(t *testing.T) {
	ts := newGinTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
	result, _ := data["result"].(map[string]any)
	greeting, _ := result["greeting"].(string)
	if !strings.Contains(greeting, "Alice") {
		t.Fatalf("expected greeting to contain Alice, got %q", greeting)
	}
}

func TestGinPostWriteCapabilityWithAPIKey(t *testing.T) {
	ts := newGinTestServer(t, nil)

	body := `{"item": "hotel", "quantity": 1}`
	req, _ := http.NewRequest("POST", ts.URL+"/api/book", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
}

func TestGinMissingAuth401(t *testing.T) {
	ts := newGinTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 401 {
		t.Fatalf("expected 401, got %d", resp.StatusCode)
	}
}

func TestGinInvalidJWT401(t *testing.T) {
	ts := newGinTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer garbage-not-a-jwt-or-api-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 401 {
		t.Fatalf("expected 401, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidToken {
		t.Fatalf("expected type=%q, got %v", core.FailureInvalidToken, failure["type"])
	}
}

func TestGinOpenAPIEndpoint(t *testing.T) {
	ts := newGinTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/rest/openapi.json")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var spec map[string]any
	json.NewDecoder(resp.Body).Decode(&spec)
	if spec["openapi"] != "3.1.0" {
		t.Fatalf("expected openapi=3.1.0, got %v", spec["openapi"])
	}
}

func TestGinDocsEndpoint(t *testing.T) {
	ts := newGinTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/rest/docs")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	body := buf.String()
	if !strings.Contains(body, "swagger-ui") {
		t.Fatal("expected Swagger UI HTML")
	}
}

func TestGinRouteOverrides(t *testing.T) {
	ts := newGinTestServer(t, &RestOptions{
		Routes: map[string]RouteOverride{
			"greet": {Path: "/v2/hello", Method: "POST"},
		},
	})

	// Overridden path should work
	body := `{"name": "Alice"}`
	req, _ := http.NewRequest("POST", ts.URL+"/v2/hello", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
}

func TestGinClientReferenceID(t *testing.T) {
	ts := newGinTestServer(t, nil)

	req, _ := http.NewRequest("GET", ts.URL+"/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("X-Client-Reference-Id", "gin-ref-456")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	clientRef, _ := data["client_reference_id"].(string)
	if clientRef != "gin-ref-456" {
		t.Fatalf("expected client_reference_id=gin-ref-456, got %q", clientRef)
	}
}

// --- Prefix Tests ---

func TestHTTPPrefix(t *testing.T) {
	ts := newHTTPTestServer(t, &RestOptions{Prefix: "/v1"})

	// Should work with prefix
	req, _ := http.NewRequest("GET", ts.URL+"/v1/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200 with prefix, got %d", resp.StatusCode)
	}

	// OpenAPI should also be prefixed
	resp2, err := http.Get(ts.URL + "/v1/rest/openapi.json")
	if err != nil {
		t.Fatal(err)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != 200 {
		t.Fatalf("expected 200 for prefixed openapi, got %d", resp2.StatusCode)
	}
}

func TestGinPrefix(t *testing.T) {
	ts := newGinTestServer(t, &RestOptions{Prefix: "/v1"})

	req, _ := http.NewRequest("GET", ts.URL+"/v1/api/greet?name=Alice", nil)
	req.Header.Set("Authorization", "Bearer test-api-key")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200 with prefix, got %d", resp.StatusCode)
	}
}

// --- POST body with parameters wrapper ---

func TestHTTPPostWithParametersWrapper(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	body := `{"parameters": {"item": "car"}}`
	req, _ := http.NewRequest("POST", ts.URL+"/api/book", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != true {
		t.Fatalf("expected success=true, got %v", data["success"])
	}
	result, _ := data["result"].(map[string]any)
	if result["item"] != "car" {
		t.Fatalf("expected item=car, got %v", result["item"])
	}
}
