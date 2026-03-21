package ginapi

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

func init() {
	gin.SetMode(gin.TestMode)
}

// testCapabilities returns two test capabilities for Gin handler tests.
func testCapabilities() []service.CapabilityDef {
	return []service.CapabilityDef{
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "search_flights",
				Description:     "Search for available flights",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "origin", Type: "airport_code", Required: true},
					{Name: "destination", Type: "airport_code", Required: true},
					{Name: "date", Type: "date", Required: true},
				},
				Output: core.CapabilityOutput{
					Type:   "object",
					Fields: []string{"flights", "count"},
				},
				SideEffect: core.SideEffect{
					Type:           "read",
					RollbackWindow: "not_applicable",
				},
				MinimumScope:  []string{"travel.search"},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				return map[string]any{
					"flights": []map[string]any{
						{
							"flight_number":  "AA100",
							"departure_time": "08:00",
							"arrival_time":   "10:30",
							"price":          420,
							"currency":       "USD",
							"stops":          0,
						},
					},
					"count": 1,
				}, nil
			},
		},
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "book_flight",
				Description:     "Book a specific flight",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "flight_number", Type: "string", Required: true},
					{Name: "date", Type: "date", Required: true},
					{Name: "passengers", Type: "integer", Required: false, Default: 1},
				},
				Output: core.CapabilityOutput{
					Type:   "object",
					Fields: []string{"booking_id", "flight_number", "total_cost"},
				},
				SideEffect: core.SideEffect{
					Type:           "irreversible",
					RollbackWindow: "none",
				},
				MinimumScope: []string{"travel.book"},
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
				Requires: []core.CapabilityRequirement{
					{Capability: "search_flights", Reason: "Must search before booking"},
				},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				ctx.SetCostActual(&core.CostActual{
					Financial: map[string]any{
						"currency": "USD",
						"amount":   280.00,
					},
				})
				return map[string]any{
					"booking_id":    "BK-12345",
					"flight_number": params["flight_number"],
					"total_cost":    280.00,
				}, nil
			},
		},
	}
}

func newTestServer(t *testing.T) (*httptest.Server, *service.Service) {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID:    "test-service",
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

	router := gin.New()
	MountANIPGin(router, svc)
	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)
	return ts, svc
}

// issueToken is a test helper that issues a JWT via the /anip/tokens endpoint.
func issueToken(t *testing.T, ts *httptest.Server, scope []string, capability string) string {
	t.Helper()
	body := map[string]any{
		"scope":      scope,
		"capability": capability,
	}
	bodyBytes, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", ts.URL+"/anip/tokens", bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("token request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("token issuance returned %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	token, _ := data["token"].(string)
	if token == "" {
		t.Fatal("empty token in response")
	}
	return token
}

// --- Discovery Tests ---

func TestDiscoveryReturns200(t *testing.T) {
	ts, _ := newTestServer(t)
	resp, err := http.Get(ts.URL + "/.well-known/anip")
	if err != nil {
		t.Fatalf("GET /.well-known/anip error: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)

	discovery, ok := data["anip_discovery"].(map[string]any)
	if !ok {
		t.Fatal("missing anip_discovery key")
	}

	requiredFields := []string{"protocol", "compliance", "base_url", "profile", "auth",
		"capabilities", "endpoints", "trust_level"}
	for _, field := range requiredFields {
		if _, ok := discovery[field]; !ok {
			t.Fatalf("missing required field: %s", field)
		}
	}
}

func TestDiscoveryCapabilitiesNonEmpty(t *testing.T) {
	ts, _ := newTestServer(t)
	resp, err := http.Get(ts.URL + "/.well-known/anip")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	discovery := data["anip_discovery"].(map[string]any)
	caps := discovery["capabilities"].(map[string]any)
	if len(caps) == 0 {
		t.Fatal("expected non-empty capabilities")
	}
}

// --- JWKS Tests ---

func TestJWKSReturnsKeys(t *testing.T) {
	ts, _ := newTestServer(t)
	resp, err := http.Get(ts.URL + "/.well-known/jwks.json")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	keys, ok := data["keys"].([]any)
	if !ok || len(keys) == 0 {
		t.Fatal("expected non-empty keys array")
	}

	// Verify EC keys.
	for _, k := range keys {
		key, _ := k.(map[string]any)
		if key["kty"] != "EC" {
			t.Fatalf("expected kty=EC, got %v", key["kty"])
		}
		if key["crv"] != "P-256" {
			t.Fatalf("expected crv=P-256, got %v", key["crv"])
		}
	}
}

// --- Manifest Tests ---

func TestManifestHasSignature(t *testing.T) {
	ts, _ := newTestServer(t)
	resp, err := http.Get(ts.URL + "/anip/manifest")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	sig := resp.Header.Get("X-ANIP-Signature")
	if sig == "" {
		t.Fatal("missing X-ANIP-Signature header")
	}

	// Verify it's a detached JWS (3 parts, empty middle).
	parts := strings.SplitN(sig, ".", 3)
	if len(parts) != 3 {
		t.Fatalf("expected 3 parts in JWS, got %d", len(parts))
	}
	if parts[1] != "" {
		t.Fatal("expected empty payload in detached JWS")
	}

	// Verify body is valid JSON with capabilities.
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if _, ok := data["capabilities"]; !ok {
		t.Fatal("manifest missing capabilities")
	}
}

// --- Token Tests ---

func TestTokenIssuanceWithValidKey(t *testing.T) {
	ts, _ := newTestServer(t)

	body := `{"scope": ["travel.search"], "capability": "search_flights"}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/tokens", strings.NewReader(body))
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
	if data["issued"] != true {
		t.Fatal("expected issued=true")
	}
	if _, ok := data["token"]; !ok {
		t.Fatal("missing token")
	}
	if _, ok := data["token_id"]; !ok {
		t.Fatal("missing token_id")
	}
	if _, ok := data["expires"]; !ok {
		t.Fatal("missing expires")
	}
}

func TestTokenIssuanceWithoutAuth(t *testing.T) {
	ts, _ := newTestServer(t)

	body := `{"scope": ["travel.search"]}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/tokens", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

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
	resolution, _ := failure["resolution"].(map[string]any)
	if resolution["action"] != "provide_api_key" {
		t.Fatalf("expected resolution.action='provide_api_key', got %v", resolution["action"])
	}
}

// --- Invoke Tests ---

func TestInvokeWithValidJWT(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	body := `{"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
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
		t.Fatal("expected success=true")
	}
	invID, _ := data["invocation_id"].(string)
	if !strings.HasPrefix(invID, "inv-") {
		t.Fatalf("expected invocation_id starting with 'inv-', got %q", invID)
	}
}

func TestInvokeWithoutAuth(t *testing.T) {
	ts, _ := newTestServer(t)

	body := `{"parameters": {}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")

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
	resolution, _ := failure["resolution"].(map[string]any)
	if resolution["action"] != "obtain_delegation_token" {
		t.Fatalf("expected resolution.action='obtain_delegation_token', got %v", resolution["action"])
	}
}

func TestInvokeWithGarbageJWT(t *testing.T) {
	ts, _ := newTestServer(t)

	body := `{"parameters": {}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer garbage-not-a-jwt")
	req.Header.Set("Content-Type", "application/json")

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

func TestInvokeMissingVsInvalidTokenDistinct(t *testing.T) {
	ts, _ := newTestServer(t)

	// Missing auth.
	body := `{"parameters": {}}`
	req1, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req1.Header.Set("Content-Type", "application/json")
	resp1, _ := http.DefaultClient.Do(req1)
	defer resp1.Body.Close()
	var data1 map[string]any
	json.NewDecoder(resp1.Body).Decode(&data1)
	failure1, _ := data1["failure"].(map[string]any)
	type1, _ := failure1["type"].(string)

	// Invalid token.
	req2, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req2.Header.Set("Authorization", "Bearer garbage-not-a-jwt")
	req2.Header.Set("Content-Type", "application/json")
	resp2, _ := http.DefaultClient.Do(req2)
	defer resp2.Body.Close()
	var data2 map[string]any
	json.NewDecoder(resp2.Body).Decode(&data2)
	failure2, _ := data2["failure"].(map[string]any)
	type2, _ := failure2["type"].(string)

	if type1 == type2 {
		t.Fatalf("missing auth and invalid token should have different types, both returned %q", type1)
	}
}

func TestInvokeUnknownCapability(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	body := `{"parameters": {}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/nonexistent_capability_xyz", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 404 {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != false {
		t.Fatal("expected success=false")
	}
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureUnknownCapability {
		t.Fatalf("expected type=%q, got %v", core.FailureUnknownCapability, failure["type"])
	}
}

func TestInvokeClientReferenceIDEchoed(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	body := `{"parameters": {}, "client_reference_id": "my-ref-123"}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	clientRef, _ := data["client_reference_id"].(string)
	if clientRef != "my-ref-123" {
		t.Fatalf("expected client_reference_id='my-ref-123', got %q", clientRef)
	}
}

func TestInvokeFailureHasRequiredFields(t *testing.T) {
	ts, _ := newTestServer(t)

	body := `{"parameters": {}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer garbage-not-a-jwt")
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)

	requiredFields := []string{"type", "detail", "resolution", "retry"}
	for _, field := range requiredFields {
		if _, ok := failure[field]; !ok {
			t.Fatalf("failure missing required field: %s", field)
		}
	}
	// retry must be a boolean
	if _, ok := failure["retry"].(bool); !ok {
		t.Fatal("failure.retry must be a boolean")
	}
}

// --- Permissions Tests ---

func TestPermissionsAvailableAndRestricted(t *testing.T) {
	ts, _ := newTestServer(t)
	// Token with only search scope.
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	req, _ := http.NewRequest("POST", ts.URL+"/anip/permissions", nil)
	req.Header.Set("Authorization", "Bearer "+jwt)

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
	available, _ := data["available"].([]any)
	restricted, _ := data["restricted"].([]any)
	denied, _ := data["denied"].([]any)

	if available == nil {
		t.Fatal("missing available field")
	}
	if restricted == nil {
		t.Fatal("missing restricted field")
	}
	if denied == nil {
		t.Fatal("missing denied field")
	}

	// search_flights should be available.
	foundAvailable := false
	for _, a := range available {
		entry, _ := a.(map[string]any)
		if entry["capability"] == "search_flights" {
			foundAvailable = true
			break
		}
	}
	if !foundAvailable {
		t.Fatal("expected search_flights to be available")
	}

	// book_flight should be restricted (requires travel.book).
	foundRestricted := false
	for _, r := range restricted {
		entry, _ := r.(map[string]any)
		if entry["capability"] == "book_flight" {
			foundRestricted = true
			if _, ok := entry["reason"]; !ok {
				t.Fatal("restricted entry missing reason")
			}
			break
		}
	}
	if !foundRestricted {
		t.Fatal("expected book_flight to be restricted")
	}
}

func TestPermissionsUnauthenticated(t *testing.T) {
	ts, _ := newTestServer(t)

	req, _ := http.NewRequest("POST", ts.URL+"/anip/permissions", nil)
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
}

// --- Audit Tests ---

func TestAuditReturnsEntries(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	// Invoke to generate an audit entry.
	body := `{"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}}`
	invokeReq, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	invokeReq.Header.Set("Authorization", "Bearer "+jwt)
	invokeReq.Header.Set("Content-Type", "application/json")
	invokeResp, _ := http.DefaultClient.Do(invokeReq)
	invokeResp.Body.Close()

	// Query audit.
	auditReq, _ := http.NewRequest("POST", ts.URL+"/anip/audit", nil)
	auditReq.Header.Set("Authorization", "Bearer "+jwt)
	resp, err := http.DefaultClient.Do(auditReq)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	entries, _ := data["entries"].([]any)
	if len(entries) == 0 {
		t.Fatal("expected at least one audit entry")
	}

	count, _ := data["count"].(float64)
	if int(count) != len(entries) {
		t.Fatalf("expected count=%d, got %d", len(entries), int(count))
	}
}

func TestAuditUnauthenticated(t *testing.T) {
	ts, _ := newTestServer(t)

	req, _ := http.NewRequest("POST", ts.URL+"/anip/audit", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 401 {
		t.Fatalf("expected 401, got %d", resp.StatusCode)
	}
}

func TestAuditFilterByCapability(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	// Invoke first.
	body := `{"parameters": {}}`
	invokeReq, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	invokeReq.Header.Set("Authorization", "Bearer "+jwt)
	invokeReq.Header.Set("Content-Type", "application/json")
	invokeResp, _ := http.DefaultClient.Do(invokeReq)
	invokeResp.Body.Close()

	// Query with capability filter.
	auditReq, _ := http.NewRequest("POST", ts.URL+"/anip/audit?capability=search_flights", nil)
	auditReq.Header.Set("Authorization", "Bearer "+jwt)
	resp, err := http.DefaultClient.Do(auditReq)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	capFilter, _ := data["capability_filter"].(string)
	if capFilter != "search_flights" {
		t.Fatalf("expected capability_filter='search_flights', got %q", capFilter)
	}
}

// --- Checkpoint Tests ---

func TestCheckpointsListReturns200(t *testing.T) {
	ts, _ := newTestServer(t)
	resp, err := http.Get(ts.URL + "/anip/checkpoints")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	checkpoints, ok := data["checkpoints"].([]any)
	if !ok {
		t.Fatal("missing or invalid checkpoints field")
	}
	// Initially empty list is fine.
	_ = checkpoints
}

func TestCheckpointNotFound(t *testing.T) {
	ts, _ := newTestServer(t)
	resp, err := http.Get(ts.URL + "/anip/checkpoints/nonexistent_cp_id_xyz")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 404 {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}
}

// --- Scope Mismatch Test ---

func TestInvokeScopeMismatch(t *testing.T) {
	ts, _ := newTestServer(t)
	// Issue token with only search scope, try to invoke book_flight.
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	body := `{"parameters": {"flight_number": "AA100", "date": "2026-03-10"}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/book_flight", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != false {
		t.Fatal("expected success=false for scope mismatch")
	}
}

// --- Full-scope Permissions Test ---

func TestPermissionsFullScope(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search", "travel.book"}, "search_flights")

	req, _ := http.NewRequest("POST", ts.URL+"/anip/permissions", nil)
	req.Header.Set("Authorization", "Bearer "+jwt)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	available, _ := data["available"].([]any)
	if len(available) != 2 {
		t.Fatalf("expected 2 available with full scope, got %d", len(available))
	}
}

// --- Cost Signaling Test ---

func TestInvokeFinancialCapabilityCostActual(t *testing.T) {
	ts, _ := newTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search", "travel.book"}, "book_flight")

	body := `{"parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/book_flight", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
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
		t.Fatal("expected success=true")
	}
	if _, ok := data["cost_actual"]; !ok {
		t.Fatal("expected cost_actual in response for financial capability")
	}
}

// --- SSE Streaming Tests ---

func newStreamingTestServer(t *testing.T) (*httptest.Server, *service.Service) {
	t.Helper()
	caps := append(testCapabilities(), streamingTestCapabilities()...)
	svc := service.New(service.Config{
		ServiceID:    "test-service",
		Capabilities: caps,
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

	router := gin.New()
	MountANIPGin(router, svc)
	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)
	return ts, svc
}

func streamingTestCapabilities() []service.CapabilityDef {
	return []service.CapabilityDef{
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "stream_search",
				Description:     "Search with streaming progress",
				ContractVersion: "1.0",
				SideEffect:      core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:    []string{"travel.search"},
				ResponseModes:   []string{"unary", "streaming"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				ctx.EmitProgress(map[string]any{"step": 1, "status": "searching"})
				ctx.EmitProgress(map[string]any{"step": 2, "status": "filtering"})
				return map[string]any{"flights": []string{"AA100"}, "count": 1}, nil
			},
		},
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "stream_fail",
				Description:     "Streaming capability that fails",
				ContractVersion: "1.0",
				SideEffect:      core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:    []string{"travel.search"},
				ResponseModes:   []string{"streaming"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				ctx.EmitProgress(map[string]any{"step": 1, "status": "starting"})
				return nil, core.NewANIPError(core.FailureUnavailable, "service temporarily unavailable")
			},
		},
	}
}

// parseSSEEvents parses SSE-formatted text into event type/data pairs.
func parseSSEEvents(body string) []struct {
	Type string
	Data string
} {
	var events []struct {
		Type string
		Data string
	}
	lines := strings.Split(body, "\n")
	var currentType, currentData string
	for _, line := range lines {
		if strings.HasPrefix(line, "event: ") {
			currentType = strings.TrimPrefix(line, "event: ")
		} else if strings.HasPrefix(line, "data: ") {
			currentData = strings.TrimPrefix(line, "data: ")
		} else if line == "" && currentType != "" {
			events = append(events, struct {
				Type string
				Data string
			}{currentType, currentData})
			currentType = ""
			currentData = ""
		}
	}
	return events
}

func TestSSEStreamingSuccess(t *testing.T) {
	ts, _ := newStreamingTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "stream_search")

	body := `{"parameters": {}, "stream": true}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/stream_search", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request error: %v", err)
	}
	defer resp.Body.Close()

	// Check SSE headers.
	if ct := resp.Header.Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("expected Content-Type 'text/event-stream', got %q", ct)
	}

	// Read the full body.
	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	bodyStr := buf.String()

	events := parseSSEEvents(bodyStr)
	if len(events) != 3 {
		t.Fatalf("expected 3 SSE events, got %d. Body:\n%s", len(events), bodyStr)
	}

	// First two should be progress.
	if events[0].Type != "progress" {
		t.Fatalf("expected event 0 type 'progress', got %q", events[0].Type)
	}
	if events[1].Type != "progress" {
		t.Fatalf("expected event 1 type 'progress', got %q", events[1].Type)
	}

	// Last should be completed.
	if events[2].Type != "completed" {
		t.Fatalf("expected event 2 type 'completed', got %q", events[2].Type)
	}

	// Parse completed data.
	var completedData map[string]any
	if err := json.Unmarshal([]byte(events[2].Data), &completedData); err != nil {
		t.Fatalf("failed to parse completed data: %v", err)
	}
	if completedData["success"] != true {
		t.Fatal("expected completed event success=true")
	}
	if _, ok := completedData["invocation_id"]; !ok {
		t.Fatal("completed event missing invocation_id")
	}
	if _, ok := completedData["timestamp"]; !ok {
		t.Fatal("completed event missing timestamp")
	}

	// Parse first progress data.
	var progressData map[string]any
	if err := json.Unmarshal([]byte(events[0].Data), &progressData); err != nil {
		t.Fatalf("failed to parse progress data: %v", err)
	}
	payload, _ := progressData["payload"].(map[string]any)
	if payload == nil {
		t.Fatal("progress event missing payload")
	}
}

func TestSSEStreamingFailure(t *testing.T) {
	ts, _ := newStreamingTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "stream_fail")

	body := `{"parameters": {}, "stream": true}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/stream_fail", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request error: %v", err)
	}
	defer resp.Body.Close()

	if ct := resp.Header.Get("Content-Type"); ct != "text/event-stream" {
		t.Fatalf("expected Content-Type 'text/event-stream', got %q", ct)
	}

	var buf bytes.Buffer
	buf.ReadFrom(resp.Body)
	bodyStr := buf.String()

	events := parseSSEEvents(bodyStr)
	if len(events) != 2 {
		t.Fatalf("expected 2 SSE events, got %d. Body:\n%s", len(events), bodyStr)
	}

	if events[0].Type != "progress" {
		t.Fatalf("expected event 0 type 'progress', got %q", events[0].Type)
	}
	if events[1].Type != "failed" {
		t.Fatalf("expected event 1 type 'failed', got %q", events[1].Type)
	}

	var failedData map[string]any
	if err := json.Unmarshal([]byte(events[1].Data), &failedData); err != nil {
		t.Fatalf("failed to parse failed data: %v", err)
	}
	if failedData["success"] != false {
		t.Fatal("expected failed event success=false")
	}
	failure, _ := failedData["failure"].(map[string]any)
	if failure == nil {
		t.Fatal("failed event missing failure")
	}
	if failure["type"] != core.FailureUnavailable {
		t.Fatalf("expected failure type %q, got %v", core.FailureUnavailable, failure["type"])
	}
}

func TestSSEStreamingNotSupportedReturnsJSON(t *testing.T) {
	ts, _ := newStreamingTestServer(t)
	jwt := issueToken(t, ts, []string{"travel.search"}, "search_flights")

	// Request streaming on a unary-only capability.
	body := `{"parameters": {}, "stream": true}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/search_flights", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request error: %v", err)
	}
	defer resp.Body.Close()

	// Should return JSON error, not SSE.
	ct := resp.Header.Get("Content-Type")
	if !strings.HasPrefix(ct, "application/json") {
		t.Fatalf("expected Content-Type starting with 'application/json', got %q", ct)
	}

	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	if data["success"] != false {
		t.Fatal("expected success=false")
	}
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureStreamingNotSupported {
		t.Fatalf("expected failure type %q, got %v", core.FailureStreamingNotSupported, failure["type"])
	}
}
