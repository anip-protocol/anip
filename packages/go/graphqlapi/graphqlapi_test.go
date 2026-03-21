package graphqlapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/graphql-go/graphql"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// noopResolverFactory returns a no-op resolver factory for SDL-only tests.
func noopResolverFactory(capName string) graphql.FieldResolveFn {
	return func(p graphql.ResolveParams) (any, error) {
		return nil, nil
	}
}

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
				Name:            "book_flight",
				Description:     "Book a flight reservation",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "destination", Type: "string", Required: true, Description: "Destination city"},
					{Name: "num_passengers", Type: "integer", Required: false, Description: "Number of passengers"},
				},
				Output: core.CapabilityOutput{
					Type:   "object",
					Fields: []string{"booking_id", "destination"},
				},
				SideEffect: core.SideEffect{
					Type:           "irreversible",
					RollbackWindow: "none",
				},
				MinimumScope: []string{"book"},
				Cost: &core.Cost{
					Certainty: "estimated",
					Financial: map[string]any{
						"currency": "USD",
						"estimated_range": map[string]any{
							"min": 280,
							"max": 500,
						},
					},
				},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				dest, _ := params["destination"].(string)
				return map[string]any{
					"booking_id":  "BK-123",
					"destination": dest,
				}, nil
			},
		},
	}
}

func newTestService(t *testing.T) *service.Service {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID:    "test-graphql-service",
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

func newHTTPTestServer(t *testing.T, opts *GraphQLOptions) *httptest.Server {
	t.Helper()
	svc := newTestService(t)
	mux := http.NewServeMux()
	MountANIPGraphQL(mux, svc, opts)
	ts := httptest.NewServer(mux)
	t.Cleanup(ts.Close)
	return ts
}

func newGinTestServer(t *testing.T, opts *GraphQLOptions) *httptest.Server {
	t.Helper()
	svc := newTestService(t)
	gin.SetMode(gin.TestMode)
	router := gin.New()
	MountANIPGraphQLGin(router, svc, opts)
	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)
	return ts
}

func postGraphQL(t *testing.T, url string, query string, authHeader string) map[string]any {
	t.Helper()
	body, _ := json.Marshal(map[string]any{"query": query})
	req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if authHeader != "" {
		req.Header.Set("Authorization", authHeader)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected status 200, got %d", resp.StatusCode)
	}

	var result map[string]any
	json.NewDecoder(resp.Body).Decode(&result)
	return result
}

// --- SDL Generation ---

func TestSDLGenerationHasQueryAndMutation(t *testing.T) {
	svc := newTestService(t)
	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema error: %v", err)
	}

	if !strings.Contains(sdl, "type Query {") {
		t.Fatal("SDL missing Query type")
	}
	if !strings.Contains(sdl, "type Mutation {") {
		t.Fatal("SDL missing Mutation type")
	}
}

func TestSDLGenerationCamelCaseFieldNames(t *testing.T) {
	svc := newTestService(t)
	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema error: %v", err)
	}

	// "book_flight" should become "bookFlight" in SDL
	if !strings.Contains(sdl, "bookFlight") {
		t.Fatalf("SDL should contain camelCase field 'bookFlight', got:\n%s", sdl)
	}
	// "greet" stays as "greet"
	if !strings.Contains(sdl, "greet") {
		t.Fatalf("SDL should contain field 'greet'")
	}
	// Args should be camelCase: "num_passengers" -> "numPassengers"
	if !strings.Contains(sdl, "numPassengers") {
		t.Fatalf("SDL should contain camelCase arg 'numPassengers', got:\n%s", sdl)
	}
}

func TestSDLGenerationDirectives(t *testing.T) {
	svc := newTestService(t)
	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema error: %v", err)
	}

	if !strings.Contains(sdl, "@anipSideEffect") {
		t.Fatal("SDL missing @anipSideEffect directive")
	}
	if !strings.Contains(sdl, "@anipCost") {
		t.Fatal("SDL missing @anipCost directive")
	}
	if !strings.Contains(sdl, "@anipScope") {
		t.Fatal("SDL missing @anipScope directive")
	}
	if !strings.Contains(sdl, "directive @anipRequires") {
		t.Fatal("SDL missing @anipRequires directive declaration")
	}
}

func TestSDLGenerationSharedTypes(t *testing.T) {
	svc := newTestService(t)
	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema error: %v", err)
	}

	for _, typeName := range []string{"CostActual", "FinancialCost", "ANIPFailure", "Resolution", "scalar JSON"} {
		if !strings.Contains(sdl, typeName) {
			t.Fatalf("SDL missing shared type %q", typeName)
		}
	}
}

func TestSDLGenerationResultTypes(t *testing.T) {
	svc := newTestService(t)
	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema error: %v", err)
	}

	// "greet" -> "GreetResult"
	if !strings.Contains(sdl, "type GreetResult") {
		t.Fatal("SDL missing GreetResult type")
	}
	// "book_flight" -> "BookFlightResult"
	if !strings.Contains(sdl, "type BookFlightResult") {
		t.Fatal("SDL missing BookFlightResult type")
	}
}

func TestSDLQueryMutationSeparation(t *testing.T) {
	svc := newTestService(t)
	_, sdl, err := BuildSchema(svc, noopResolverFactory)
	if err != nil {
		t.Fatalf("BuildSchema error: %v", err)
	}

	// "greet" (side_effect=read) should be in Query
	queryIdx := strings.Index(sdl, "type Query {")
	mutationIdx := strings.Index(sdl, "type Mutation {")
	greetIdx := strings.Index(sdl, "  greet")
	bookFlightIdx := strings.Index(sdl, "  bookFlight")

	if greetIdx < queryIdx || greetIdx > mutationIdx {
		t.Fatal("greet should be in Query section")
	}
	if bookFlightIdx < mutationIdx {
		t.Fatal("bookFlight should be in Mutation section")
	}
}

// --- Case conversion ---

func TestToCamelCase(t *testing.T) {
	tests := []struct{ input, expected string }{
		{"search_flights", "searchFlights"},
		{"greet", "greet"},
		{"book_flight", "bookFlight"},
		{"num_passengers", "numPassengers"},
		{"a_b_c", "aBC"},
	}
	for _, tc := range tests {
		got := ToCamelCase(tc.input)
		if got != tc.expected {
			t.Errorf("ToCamelCase(%q) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}

func TestToSnakeCase(t *testing.T) {
	tests := []struct{ input, expected string }{
		{"searchFlights", "search_flights"},
		{"greet", "greet"},
		{"bookFlight", "book_flight"},
		{"numPassengers", "num_passengers"},
	}
	for _, tc := range tests {
		got := ToSnakeCase(tc.input)
		if got != tc.expected {
			t.Errorf("ToSnakeCase(%q) = %q, want %q", tc.input, got, tc.expected)
		}
	}
}

// --- HTTP Mount Tests ---

func TestHTTPQueryWithAuth(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`{ greet(name: "Alice") { success result } }`,
		"Bearer test-api-key",
	)

	data, _ := result["data"].(map[string]any)
	if data == nil {
		t.Fatalf("expected data in response, got: %v", result)
	}
	greet, _ := data["greet"].(map[string]any)
	if greet == nil {
		t.Fatalf("expected greet in data, got: %v", data)
	}
	if greet["success"] != true {
		t.Fatalf("expected success=true, got %v", greet["success"])
	}
	resultMap, _ := greet["result"].(map[string]any)
	if resultMap == nil {
		t.Fatalf("expected result map, got %v", greet["result"])
	}
	greeting, _ := resultMap["greeting"].(string)
	if !strings.Contains(greeting, "Alice") {
		t.Fatalf("expected greeting to contain Alice, got %q", greeting)
	}
}

func TestHTTPMutationWithAuth(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`mutation { bookFlight(destination: "Paris") { success result } }`,
		"Bearer test-api-key",
	)

	data, _ := result["data"].(map[string]any)
	if data == nil {
		t.Fatalf("expected data in response, got: %v", result)
	}
	book, _ := data["bookFlight"].(map[string]any)
	if book == nil {
		t.Fatalf("expected bookFlight in data, got: %v", data)
	}
	if book["success"] != true {
		t.Fatalf("expected success=true, got %v", book["success"])
	}
	resultMap, _ := book["result"].(map[string]any)
	if resultMap == nil {
		t.Fatalf("expected result map, got %v", book["result"])
	}
	if resultMap["booking_id"] != "BK-123" {
		t.Fatalf("expected booking_id=BK-123, got %v", resultMap["booking_id"])
	}
	if resultMap["destination"] != "Paris" {
		t.Fatalf("expected destination=Paris, got %v", resultMap["destination"])
	}
}

func TestHTTPQueryWithoutAuth(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`{ greet(name: "Alice") { success failure { type detail } } }`,
		"", // no auth
	)

	data, _ := result["data"].(map[string]any)
	if data == nil {
		t.Fatalf("expected data in response, got: %v", result)
	}
	greet, _ := data["greet"].(map[string]any)
	if greet == nil {
		t.Fatalf("expected greet in data, got: %v", data)
	}
	if greet["success"] != false {
		t.Fatalf("expected success=false, got %v", greet["success"])
	}
	failure, _ := greet["failure"].(map[string]any)
	if failure == nil {
		t.Fatalf("expected failure in result, got: %v", greet)
	}
	if failure["type"] != core.FailureAuthRequired {
		t.Fatalf("expected failure type=%q, got %v", core.FailureAuthRequired, failure["type"])
	}
}

func TestHTTPQueryInvalidJWT(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`{ greet(name: "Alice") { success failure { type detail } } }`,
		"Bearer garbage-not-a-jwt-or-api-key",
	)

	data, _ := result["data"].(map[string]any)
	if data == nil {
		t.Fatalf("expected data in response, got: %v", result)
	}
	greet, _ := data["greet"].(map[string]any)
	if greet == nil {
		t.Fatalf("expected greet in data, got: %v", data)
	}
	if greet["success"] != false {
		t.Fatalf("expected success=false, got %v", greet["success"])
	}
	failure, _ := greet["failure"].(map[string]any)
	if failure == nil {
		t.Fatalf("expected failure in result, got: %v", greet)
	}
	if failure["type"] != core.FailureInvalidToken {
		t.Fatalf("expected failure type=%q, got %v", core.FailureInvalidToken, failure["type"])
	}
}

func TestHTTPSchemaEndpoint(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/schema.graphql")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	ct := resp.Header.Get("Content-Type")
	if !strings.Contains(ct, "text/plain") {
		t.Fatalf("expected Content-Type text/plain, got %q", ct)
	}

	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	sdl := buf.String()

	if !strings.Contains(sdl, "type Query") {
		t.Fatal("SDL should contain type Query")
	}
	if !strings.Contains(sdl, "@anipSideEffect") {
		t.Fatal("SDL should contain @anipSideEffect")
	}
}

func TestHTTPPlayground(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/graphql")
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

	if !strings.Contains(body, "ANIP GraphQL Playground") {
		t.Fatal("expected playground HTML")
	}
}

// --- Gin Mount Tests ---

func TestGinQueryWithAuth(t *testing.T) {
	ts := newGinTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`{ greet(name: "Bob") { success result } }`,
		"Bearer test-api-key",
	)

	data, _ := result["data"].(map[string]any)
	if data == nil {
		t.Fatalf("expected data in response, got: %v", result)
	}
	greet, _ := data["greet"].(map[string]any)
	if greet == nil {
		t.Fatalf("expected greet in data, got: %v", data)
	}
	if greet["success"] != true {
		t.Fatalf("expected success=true, got %v", greet["success"])
	}
	resultMap, _ := greet["result"].(map[string]any)
	greeting, _ := resultMap["greeting"].(string)
	if !strings.Contains(greeting, "Bob") {
		t.Fatalf("expected greeting to contain Bob, got %q", greeting)
	}
}

func TestGinMutationWithAuth(t *testing.T) {
	ts := newGinTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`mutation { bookFlight(destination: "Tokyo") { success result } }`,
		"Bearer test-api-key",
	)

	data, _ := result["data"].(map[string]any)
	if data == nil {
		t.Fatalf("expected data in response, got: %v", result)
	}
	book, _ := data["bookFlight"].(map[string]any)
	if book == nil {
		t.Fatalf("expected bookFlight in data, got: %v", data)
	}
	if book["success"] != true {
		t.Fatalf("expected success=true, got %v", book["success"])
	}
}

func TestGinQueryWithoutAuth(t *testing.T) {
	ts := newGinTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`{ greet(name: "Alice") { success failure { type detail } } }`,
		"", // no auth
	)

	data, _ := result["data"].(map[string]any)
	greet, _ := data["greet"].(map[string]any)
	if greet["success"] != false {
		t.Fatalf("expected success=false, got %v", greet["success"])
	}
	failure, _ := greet["failure"].(map[string]any)
	if failure["type"] != core.FailureAuthRequired {
		t.Fatalf("expected failure type=%q, got %v", core.FailureAuthRequired, failure["type"])
	}
}

func TestGinQueryInvalidJWT(t *testing.T) {
	ts := newGinTestServer(t, nil)

	result := postGraphQL(t, ts.URL+"/graphql",
		`{ greet(name: "Alice") { success failure { type detail } } }`,
		"Bearer garbage-not-a-jwt-or-api-key",
	)

	data, _ := result["data"].(map[string]any)
	greet, _ := data["greet"].(map[string]any)
	if greet["success"] != false {
		t.Fatalf("expected success=false, got %v", greet["success"])
	}
	failure, _ := greet["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidToken {
		t.Fatalf("expected failure type=%q, got %v", core.FailureInvalidToken, failure["type"])
	}
}

func TestGinSchemaEndpoint(t *testing.T) {
	ts := newGinTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/schema.graphql")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	sdl := buf.String()

	if !strings.Contains(sdl, "type Query") {
		t.Fatal("SDL should contain type Query")
	}
}

func TestGinPlayground(t *testing.T) {
	ts := newGinTestServer(t, nil)

	resp, err := http.Get(ts.URL + "/graphql")
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

	if !strings.Contains(body, "ANIP GraphQL Playground") {
		t.Fatal("expected playground HTML")
	}
}

// --- Response Mapping ---

func TestBuildGraphQLResponse(t *testing.T) {
	// Success case
	result := BuildGraphQLResponse(map[string]any{
		"success": true,
		"result":  map[string]any{"greeting": "Hello"},
		"cost_actual": map[string]any{
			"financial":              map[string]any{"amount": 1.5, "currency": "USD"},
			"variance_from_estimate": "under",
		},
	})

	if result["success"] != true {
		t.Fatal("expected success=true")
	}
	costActual, _ := result["costActual"].(map[string]any)
	if costActual == nil {
		t.Fatal("expected costActual")
	}
	if costActual["varianceFromEstimate"] != "under" {
		t.Fatalf("expected varianceFromEstimate=under, got %v", costActual["varianceFromEstimate"])
	}

	// Failure case
	result = BuildGraphQLResponse(map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   "authentication_required",
			"detail": "No token",
			"resolution": map[string]any{
				"action":      "provide_credentials",
				"grantable_by": "admin",
			},
			"retry": true,
		},
	})

	if result["success"] != false {
		t.Fatal("expected success=false")
	}
	failure, _ := result["failure"].(map[string]any)
	if failure == nil {
		t.Fatal("expected failure")
	}
	resolution, _ := failure["resolution"].(map[string]any)
	if resolution == nil {
		t.Fatal("expected resolution")
	}
	if resolution["grantableBy"] != "admin" {
		t.Fatalf("expected grantableBy=admin, got %v", resolution["grantableBy"])
	}
}

// --- HTTP always returns 200 ---

func TestHTTPAlwaysReturns200(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	// Even with no auth, GraphQL always returns 200
	body, _ := json.Marshal(map[string]any{
		"query": `{ greet(name: "Alice") { success failure { type } } }`,
	})
	req, _ := http.NewRequest("POST", ts.URL+"/graphql", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	// No auth header

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("GraphQL should always return 200, got %d", resp.StatusCode)
	}
}

// --- Args conversion ---

func TestArgsCamelToSnakeConversion(t *testing.T) {
	ts := newHTTPTestServer(t, nil)

	// "numPassengers" in GraphQL should become "num_passengers" for ANIP
	result := postGraphQL(t, ts.URL+"/graphql",
		`mutation { bookFlight(destination: "London", numPassengers: 3) { success result } }`,
		"Bearer test-api-key",
	)

	data, _ := result["data"].(map[string]any)
	book, _ := data["bookFlight"].(map[string]any)
	if book["success"] != true {
		t.Fatalf("expected success=true, got %v (full result: %v)", book["success"], result)
	}
}
