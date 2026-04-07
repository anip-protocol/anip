package service

import (
	"strings"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

func floatPtr(f float64) *float64 { return &f }

// testCapabilities returns two test capabilities for testing.
func testCapabilities() []CapabilityDef {
	return []CapabilityDef{
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
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				return map[string]any{
					"flights": []map[string]any{
						{
							"flight_number":  "AS-100",
							"departure_time": "08:00",
							"arrival_time":   "10:30",
							"price":          280,
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
					Financial: &core.FinancialCost{
						Currency: "USD",
						RangeMin: floatPtr(280),
						RangeMax: floatPtr(500),
					},
				},
				Requires: []core.CapabilityRequirement{
					{Capability: "search_flights", Reason: "Must search before booking"},
				},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				ctx.SetCostActual(&core.CostActual{
					Financial: &core.FinancialCost{
						Currency: "USD",
						Amount:   floatPtr(280.00),
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

// newTestService creates a test service with in-memory storage.
func newTestService() *Service {
	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Trust:        "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	return svc
}

func TestServiceLifecycle(t *testing.T) {
	svc := newTestService()

	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}

	if svc.storage == nil {
		t.Fatal("storage should be initialized after Start()")
	}
	if svc.keys == nil {
		t.Fatal("keys should be initialized after Start()")
	}

	if err := svc.Shutdown(); err != nil {
		t.Fatalf("Shutdown() error: %v", err)
	}
}

func TestAuthenticateBearer(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Valid key.
	principal, ok := svc.AuthenticateBearer("test-key")
	if !ok {
		t.Fatal("expected ok=true for valid key")
	}
	if principal != "human:test@example.com" {
		t.Fatalf("expected principal 'human:test@example.com', got %q", principal)
	}

	// Invalid key.
	_, ok = svc.AuthenticateBearer("invalid-key")
	if ok {
		t.Fatal("expected ok=false for invalid key")
	}
}

func TestTokenIssuanceAndResolution(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search", "travel.book"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
	if resp.Token == "" {
		t.Fatal("expected non-empty token")
	}
	if resp.TokenID == "" {
		t.Fatal("expected non-empty token_id")
	}
	if resp.Expires == "" {
		t.Fatal("expected non-empty expires")
	}

	// Resolve the token.
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}
	if token.Subject != "human:test@example.com" {
		t.Fatalf("expected subject 'human:test@example.com', got %q", token.Subject)
	}
	if token.RootPrincipal != "human:test@example.com" {
		t.Fatalf("expected root_principal 'human:test@example.com', got %q", token.RootPrincipal)
	}
}

func TestInvokeSuccess(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token with the right scope.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Invoke the capability.
	result, err := svc.Invoke("search_flights", token, map[string]any{
		"origin":      "SEA",
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if !success {
		t.Fatalf("expected success=true, got: %v", result)
	}

	invID, _ := result["invocation_id"].(string)
	if !strings.HasPrefix(invID, "inv-") {
		t.Fatalf("expected invocation_id starting with 'inv-', got %q", invID)
	}

	res, ok := result["result"].(map[string]any)
	if !ok {
		t.Fatal("expected result to be a map")
	}
	if _, ok := res["flights"]; !ok {
		t.Fatal("expected result to have 'flights' field")
	}
}

func TestInvokeUnknownCapability(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Invoke a non-existent capability.
	result, err := svc.Invoke("nonexistent", token, map[string]any{}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if success {
		t.Fatal("expected success=false for unknown capability")
	}

	failure, _ := result["failure"].(map[string]any)
	failType, _ := failure["type"].(string)
	if failType != core.FailureUnknownCapability {
		t.Fatalf("expected failure type %q, got %q", core.FailureUnknownCapability, failType)
	}
}

func TestInvokeScopeMismatch(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token with only search scope.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Try to invoke book_flight (requires travel.book).
	result, err := svc.Invoke("book_flight", token, map[string]any{
		"flight_number": "AS-100",
		"date":          "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if success {
		t.Fatal("expected success=false for scope mismatch")
	}

	failure, _ := result["failure"].(map[string]any)
	failType, _ := failure["type"].(string)
	if failType != core.FailureScopeInsufficient {
		t.Fatalf("expected failure type %q, got %q", core.FailureScopeInsufficient, failType)
	}
}

func TestInvokeStreamingNotSupported(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Request streaming.
	result, err := svc.Invoke("search_flights", token, map[string]any{}, InvokeOpts{Stream: true})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if success {
		t.Fatal("expected success=false for streaming request")
	}

	failure, _ := result["failure"].(map[string]any)
	failType, _ := failure["type"].(string)
	if failType != core.FailureStreamingNotSupported {
		t.Fatalf("expected failure type %q, got %q", core.FailureStreamingNotSupported, failType)
	}
}

func TestPermissionDiscovery(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token with only search scope.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	perms := svc.DiscoverPermissions(token)

	// search_flights should be available (travel.search scope matches).
	found := false
	for _, a := range perms.Available {
		if a.Capability == "search_flights" {
			found = true
			break
		}
	}
	if !found {
		t.Fatal("expected search_flights to be available")
	}

	// book_flight should be restricted (requires travel.book, only have travel.search).
	foundRestricted := false
	for _, r := range perms.Restricted {
		if r.Capability == "book_flight" {
			foundRestricted = true
			if r.GrantableBy != "human:test@example.com" {
				t.Fatalf("expected grantable_by 'human:test@example.com', got %q", r.GrantableBy)
			}
			break
		}
	}
	if !foundRestricted {
		t.Fatal("expected book_flight to be restricted")
	}
}

func TestDiscoveryDocument(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	doc := svc.GetDiscovery("http://localhost:8080")

	discovery, ok := doc["anip_discovery"].(map[string]any)
	if !ok {
		t.Fatal("expected doc to have 'anip_discovery' key")
	}

	// Check required fields.
	requiredFields := []string{
		"protocol", "compliance", "base_url", "profile", "auth",
		"capabilities", "endpoints", "trust_level",
	}
	for _, field := range requiredFields {
		if _, ok := discovery[field]; !ok {
			t.Fatalf("discovery document missing required field: %s", field)
		}
	}

	// Check protocol version.
	if protocol, _ := discovery["protocol"].(string); protocol != core.ProtocolVersion {
		t.Fatalf("expected protocol %q, got %q", core.ProtocolVersion, protocol)
	}

	// Check compliance.
	if compliance, _ := discovery["compliance"].(string); compliance != "anip-compliant" {
		t.Fatalf("expected compliance 'anip-compliant', got %q", compliance)
	}

	// Check trust_level.
	if trustLevel, _ := discovery["trust_level"].(string); trustLevel != "signed" {
		t.Fatalf("expected trust_level 'signed', got %q", trustLevel)
	}

	// Check endpoints.
	endpoints, ok := discovery["endpoints"].(map[string]any)
	if !ok {
		t.Fatal("expected endpoints to be a map")
	}
	endpointKeys := []string{"manifest", "permissions", "invoke", "tokens", "audit", "checkpoints", "jwks"}
	for _, key := range endpointKeys {
		if _, ok := endpoints[key]; !ok {
			t.Fatalf("endpoints missing key: %s", key)
		}
	}

	// Check capabilities.
	caps, ok := discovery["capabilities"].(map[string]any)
	if !ok {
		t.Fatal("expected capabilities to be a map")
	}
	if _, ok := caps["search_flights"]; !ok {
		t.Fatal("capabilities missing search_flights")
	}
	if _, ok := caps["book_flight"]; !ok {
		t.Fatal("capabilities missing book_flight")
	}

	// Check capability fields.
	searchCap, _ := caps["search_flights"].(map[string]any)
	capFields := []string{"description", "side_effect", "minimum_scope", "financial", "contract"}
	for _, field := range capFields {
		if _, ok := searchCap[field]; !ok {
			t.Fatalf("search_flights capability missing field: %s", field)
		}
	}
}

func TestGetJWKS(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	jwks := svc.GetJWKS()
	keys, ok := jwks["keys"]
	if !ok {
		t.Fatal("JWKS missing 'keys' field")
	}
	keysSlice, ok := keys.([]map[string]any)
	if !ok {
		t.Fatal("expected 'keys' to be a slice of maps")
	}
	if len(keysSlice) != 2 {
		t.Fatalf("expected 2 keys, got %d", len(keysSlice))
	}
}

func TestGetSignedManifest(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	bodyBytes, signature := svc.GetSignedManifest()
	if len(bodyBytes) == 0 {
		t.Fatal("expected non-empty manifest body")
	}
	if signature == "" {
		t.Fatal("expected non-empty signature")
	}
	// Verify it's a detached JWS (header..signature format).
	parts := strings.SplitN(signature, ".", 3)
	if len(parts) != 3 {
		t.Fatalf("expected 3 parts in signature, got %d", len(parts))
	}
	if parts[1] != "" {
		t.Fatal("expected empty payload part in detached JWS")
	}
}

func TestGetCapabilityDeclaration(t *testing.T) {
	svc := newTestService()

	decl := svc.GetCapabilityDeclaration("search_flights")
	if decl == nil {
		t.Fatal("expected non-nil declaration for search_flights")
	}
	if decl.Name != "search_flights" {
		t.Fatalf("expected name 'search_flights', got %q", decl.Name)
	}

	decl = svc.GetCapabilityDeclaration("nonexistent")
	if decl != nil {
		t.Fatal("expected nil for nonexistent capability")
	}
}

func TestAuditQuery(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token and invoke a capability to generate audit entries.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Invoke to generate an audit entry.
	_, err = svc.Invoke("search_flights", token, map[string]any{
		"origin":      "SEA",
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	// Query audit.
	auditResp, err := svc.QueryAudit(token, server.AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit() error: %v", err)
	}

	if len(auditResp.Entries) == 0 {
		t.Fatal("expected at least one audit entry after invocation")
	}

	entry := auditResp.Entries[0]
	if entry.Capability != "search_flights" {
		t.Fatalf("expected capability 'search_flights', got %q", entry.Capability)
	}
	if !entry.Success {
		t.Fatal("expected success=true in audit entry")
	}
}

func TestServiceID(t *testing.T) {
	svc := newTestService()
	if svc.ServiceID() != "test-service" {
		t.Fatalf("expected ServiceID 'test-service', got %q", svc.ServiceID())
	}
}

func TestInvokeWithClientReferenceID(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	result, err := svc.Invoke("search_flights", token, map[string]any{
		"origin":      "SEA",
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{ClientReferenceID: "my-ref-123"})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	clientRef, _ := result["client_reference_id"].(string)
	if clientRef != "my-ref-123" {
		t.Fatalf("expected client_reference_id 'my-ref-123', got %q", clientRef)
	}
}

func TestPermissionDiscoveryFullScope(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue a token with both scopes.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search", "travel.book"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	perms := svc.DiscoverPermissions(token)

	// Both should be available.
	if len(perms.Available) != 2 {
		t.Fatalf("expected 2 available capabilities, got %d", len(perms.Available))
	}
	if len(perms.Restricted) != 0 {
		t.Fatalf("expected 0 restricted capabilities, got %d", len(perms.Restricted))
	}
	if len(perms.Denied) != 0 {
		t.Fatalf("expected 0 denied capabilities, got %d", len(perms.Denied))
	}
}

func TestListCheckpoints(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Initially no checkpoints.
	cpResp, err := svc.ListCheckpoints(10)
	if err != nil {
		t.Fatalf("ListCheckpoints() error: %v", err)
	}
	if len(cpResp.Checkpoints) != 0 {
		t.Fatalf("expected 0 checkpoints initially, got %d", len(cpResp.Checkpoints))
	}
}

func TestGetCheckpointNotFound(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	_, err := svc.GetCheckpoint("nonexistent", false, 0, "")
	if err == nil {
		t.Fatal("expected error for nonexistent checkpoint")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected ANIPError, got %T: %v", err, err)
	}
	if anipErr.ErrorType != core.FailureNotFound {
		t.Fatalf("expected failure type %q, got %q", core.FailureNotFound, anipErr.ErrorType)
	}
}

func TestGetManifest(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	manifest := svc.GetManifest()

	if manifest.Protocol != core.ProtocolVersion {
		t.Fatalf("expected protocol %q, got %q", core.ProtocolVersion, manifest.Protocol)
	}

	if len(manifest.Capabilities) != 2 {
		t.Fatalf("expected 2 capabilities, got %d", len(manifest.Capabilities))
	}

	if _, ok := manifest.Capabilities["search_flights"]; !ok {
		t.Fatal("missing search_flights capability")
	}
	if _, ok := manifest.Capabilities["book_flight"]; !ok {
		t.Fatal("missing book_flight capability")
	}
}

func TestCreateCheckpointAndRetrieve(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// We need some audit entries first.
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Invoke to create audit entry.
	_, err = svc.Invoke("search_flights", token, map[string]any{
		"origin":      "SEA",
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	// Create checkpoint.
	cp, err := svc.CreateCheckpoint()
	if err != nil {
		t.Fatalf("CreateCheckpoint() error: %v", err)
	}
	if cp == nil {
		t.Fatal("expected non-nil checkpoint")
	}

	// Retrieve it.
	detail, err := svc.GetCheckpoint(cp.CheckpointID, false, 0, "")
	if err != nil {
		t.Fatalf("GetCheckpoint() error: %v", err)
	}
	if detail == nil {
		t.Fatal("expected non-nil checkpoint detail")
	}

	cpID, _ := detail.Checkpoint["checkpoint_id"].(string)
	if cpID != cp.CheckpointID {
		t.Fatalf("expected checkpoint_id %q, got %q", cp.CheckpointID, cpID)
	}

	// List checkpoints.
	cpList, err := svc.ListCheckpoints(10)
	if err != nil {
		t.Fatalf("ListCheckpoints() error: %v", err)
	}
	if len(cpList.Checkpoints) != 1 {
		t.Fatalf("expected 1 checkpoint, got %d", len(cpList.Checkpoints))
	}
}

func TestGetCheckpointConsistencyFrom(t *testing.T) {
	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "user@test.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue token and invoke to create audit entries.
	tokResp, _ := svc.IssueToken("user@test.com", core.TokenRequest{
		Subject: "agent:test", Scope: []string{"travel.search"}, Capability: "search_flights",
	})
	token, _ := svc.ResolveBearerToken(tokResp.Token)
	svc.Invoke("search_flights", token, map[string]any{"origin": "SEA", "destination": "SFO", "date": "2026-01-01"}, InvokeOpts{})

	// Create first checkpoint.
	cp1, err := svc.CreateCheckpoint()
	if err != nil || cp1 == nil {
		t.Fatalf("first CreateCheckpoint() failed: %v", err)
	}

	// Create more audit entries.
	svc.Invoke("search_flights", token, map[string]any{"origin": "LAX", "destination": "JFK", "date": "2026-01-02"}, InvokeOpts{})
	svc.Invoke("search_flights", token, map[string]any{"origin": "SFO", "destination": "SEA", "date": "2026-01-03"}, InvokeOpts{})

	// Create second checkpoint.
	cp2, err := svc.CreateCheckpoint()
	if err != nil || cp2 == nil {
		t.Fatalf("second CreateCheckpoint() failed: %v", err)
	}

	// Request checkpoint 2 with consistency proof from checkpoint 1.
	detail, err := svc.GetCheckpoint(cp2.CheckpointID, false, 0, cp1.CheckpointID)
	if err != nil {
		t.Fatalf("GetCheckpoint with consistency_from failed: %v", err)
	}
	if detail.ConsistencyProof == nil {
		t.Fatal("expected consistency_proof to be present")
	}
	proof := detail.ConsistencyProof
	if proof["old_checkpoint_id"] != cp1.CheckpointID {
		t.Errorf("expected old_checkpoint_id=%q, got %q", cp1.CheckpointID, proof["old_checkpoint_id"])
	}
	if proof["new_checkpoint_id"] != cp2.CheckpointID {
		t.Errorf("expected new_checkpoint_id=%q, got %q", cp2.CheckpointID, proof["new_checkpoint_id"])
	}
	switch p := proof["path"].(type) {
	case []string:
		if len(p) == 0 {
			t.Error("expected non-empty consistency proof path")
		}
	case []any:
		if len(p) == 0 {
			t.Error("expected non-empty consistency proof path")
		}
	default:
		t.Errorf("unexpected path type %T", proof["path"])
	}
}

func TestInvokeHandlerError(t *testing.T) {
	svc := New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{
			{
				Declaration: core.CapabilityDeclaration{
					Name:            "failing_cap",
					Description:     "Always fails",
					ContractVersion: "1.0",
					SideEffect:      core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
					MinimumScope:    []string{"test.fail"},
				},
				Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
					return nil, core.NewANIPError(core.FailureUnavailable, "service temporarily unavailable")
				},
			},
		},
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"test.fail"},
		Capability: "failing_cap",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	result, err := svc.Invoke("failing_cap", token, map[string]any{}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if success {
		t.Fatal("expected success=false")
	}

	failure, _ := result["failure"].(map[string]any)
	failType, _ := failure["type"].(string)
	if failType != core.FailureUnavailable {
		t.Fatalf("expected failure type %q, got %q", core.FailureUnavailable, failType)
	}
}

// streamingCapabilities returns capabilities that include streaming response_modes.
func streamingCapabilities() []CapabilityDef {
	return []CapabilityDef{
		{
			Declaration: core.CapabilityDeclaration{
				Name:            "stream_search",
				Description:     "Search with streaming progress",
				ContractVersion: "1.0",
				SideEffect:      core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:    []string{"travel.search"},
				ResponseModes:   []string{"unary", "streaming"},
			},
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				// Emit two progress events.
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
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				ctx.EmitProgress(map[string]any{"step": 1, "status": "starting"})
				return nil, core.NewANIPError(core.FailureUnavailable, "service temporarily unavailable")
			},
		},
	}
}

func newStreamTestService() *Service {
	allCaps := append(testCapabilities(), streamingCapabilities()...)
	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: allCaps,
		Storage:      ":memory:",
		Trust:        "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	return svc
}

func TestInvokeStreamSuccess(t *testing.T) {
	svc := newStreamTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "stream_search",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	sr, err := svc.InvokeStream("stream_search", token, map[string]any{}, InvokeOpts{ClientReferenceID: "ref-1"})
	if err != nil {
		t.Fatalf("InvokeStream() error: %v", err)
	}

	var events []StreamEvent
	timeout := time.After(5 * time.Second)
	for {
		select {
		case ev, ok := <-sr.Events:
			if !ok {
				goto done
			}
			events = append(events, ev)
		case <-timeout:
			t.Fatal("timed out waiting for stream events")
		}
	}
done:

	// Expect 2 progress events + 1 completed event.
	if len(events) != 3 {
		t.Fatalf("expected 3 events, got %d: %+v", len(events), events)
	}

	// First two should be progress events.
	if events[0].Type != "progress" {
		t.Fatalf("expected event 0 type 'progress', got %q", events[0].Type)
	}
	if events[1].Type != "progress" {
		t.Fatalf("expected event 1 type 'progress', got %q", events[1].Type)
	}

	// Check progress payload has required fields.
	payload0 := events[0].Payload
	if _, ok := payload0["invocation_id"]; !ok {
		t.Fatal("progress event missing invocation_id")
	}
	if _, ok := payload0["timestamp"]; !ok {
		t.Fatal("progress event missing timestamp")
	}
	progressData, _ := payload0["payload"].(map[string]any)
	if progressData == nil {
		t.Fatal("progress event missing payload")
	}

	// Last should be completed.
	if events[2].Type != "completed" {
		t.Fatalf("expected event 2 type 'completed', got %q", events[2].Type)
	}
	completedPayload := events[2].Payload
	if completedPayload["success"] != true {
		t.Fatal("expected completed event success=true")
	}
	if _, ok := completedPayload["result"]; !ok {
		t.Fatal("completed event missing result")
	}
	if _, ok := completedPayload["invocation_id"]; !ok {
		t.Fatal("completed event missing invocation_id")
	}
	if completedPayload["client_reference_id"] != "ref-1" {
		t.Fatalf("expected client_reference_id 'ref-1', got %v", completedPayload["client_reference_id"])
	}
}

func TestInvokeStreamHandlerError(t *testing.T) {
	svc := newStreamTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "stream_fail",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	sr, err := svc.InvokeStream("stream_fail", token, map[string]any{}, InvokeOpts{})
	if err != nil {
		t.Fatalf("InvokeStream() error: %v", err)
	}

	var events []StreamEvent
	timeout := time.After(5 * time.Second)
	for {
		select {
		case ev, ok := <-sr.Events:
			if !ok {
				goto done
			}
			events = append(events, ev)
		case <-timeout:
			t.Fatal("timed out waiting for stream events")
		}
	}
done:

	// Expect 1 progress event + 1 failed event.
	if len(events) != 2 {
		t.Fatalf("expected 2 events, got %d: %+v", len(events), events)
	}

	if events[0].Type != "progress" {
		t.Fatalf("expected event 0 type 'progress', got %q", events[0].Type)
	}

	if events[1].Type != "failed" {
		t.Fatalf("expected event 1 type 'failed', got %q", events[1].Type)
	}

	failedPayload := events[1].Payload
	if failedPayload["success"] != false {
		t.Fatal("expected failed event success=false")
	}
	failure, _ := failedPayload["failure"].(map[string]any)
	if failure == nil {
		t.Fatal("failed event missing failure")
	}
	if failure["type"] != core.FailureUnavailable {
		t.Fatalf("expected failure type %q, got %v", core.FailureUnavailable, failure["type"])
	}
}

func TestInvokeStreamUnaryOnlyCapability(t *testing.T) {
	svc := newStreamTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// InvokeStream on a unary-only capability should return an error.
	_, err = svc.InvokeStream("search_flights", token, map[string]any{}, InvokeOpts{})
	if err == nil {
		t.Fatal("expected error for streaming on unary-only capability")
	}

	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected ANIPError, got %T: %v", err, err)
	}
	if anipErr.ErrorType != core.FailureStreamingNotSupported {
		t.Fatalf("expected failure type %q, got %q", core.FailureStreamingNotSupported, anipErr.ErrorType)
	}
}

func TestEmitProgressAfterCompletion(t *testing.T) {
	var capturedEmit func(payload map[string]any) error

	svc := New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{
			{
				Declaration: core.CapabilityDeclaration{
					Name:            "capture_emit",
					Description:     "Captures EmitProgress for testing",
					ContractVersion: "1.0",
					SideEffect:      core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
					MinimumScope:    []string{"test"},
					ResponseModes:   []string{"streaming"},
				},
				Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
					capturedEmit = ctx.EmitProgress
					return map[string]any{"ok": true}, nil
				},
			},
		},
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"test"},
		Capability: "capture_emit",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}

	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	sr, err := svc.InvokeStream("capture_emit", token, map[string]any{}, InvokeOpts{})
	if err != nil {
		t.Fatalf("InvokeStream() error: %v", err)
	}

	// Drain all events.
	timeout := time.After(5 * time.Second)
	for {
		select {
		case _, ok := <-sr.Events:
			if !ok {
				goto done
			}
		case <-timeout:
			t.Fatal("timed out waiting for stream events")
		}
	}
done:

	// Now try to emit progress after stream is closed.
	if capturedEmit == nil {
		t.Fatal("capturedEmit was not set")
	}
	err = capturedEmit(map[string]any{"late": true})
	if err == nil {
		t.Fatal("expected error when calling EmitProgress after completion")
	}
	if err.Error() != "stream closed" {
		t.Fatalf("expected error 'stream closed', got %q", err.Error())
	}
}

// --- Gap 1: Input Validation Tests ---

func TestInvokeMissingRequiredParam(t *testing.T) {
	t.Skip("Input validation removed — handlers validate their own inputs, matching Python/TS")
}

func unused_TestInvokeMissingRequiredParam(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// Missing required "origin" parameter.
	result, err := svc.Invoke("search_flights", token, map[string]any{
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if success {
		t.Fatal("expected success=false for missing required parameter")
	}
	failure, _ := result["failure"].(map[string]any)
	failType, _ := failure["type"].(string)
	if failType != core.FailureInvalidParameters {
		t.Fatalf("expected failure type %q, got %q", core.FailureInvalidParameters, failType)
	}
}

func TestInvokeWrongParamType(t *testing.T) {
	t.Skip("Input validation removed — handlers validate their own inputs, matching Python/TS")
}

func unused_TestInvokeWrongParamType(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.book"},
		Capability: "book_flight",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// "passengers" should be an integer, not a bool.
	result, err := svc.Invoke("book_flight", token, map[string]any{
		"flight_number": "AS-100",
		"date":          "2026-03-10",
		"passengers":    true,
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	success, _ := result["success"].(bool)
	if success {
		t.Fatal("expected success=false for wrong parameter type")
	}
	failure, _ := result["failure"].(map[string]any)
	failType, _ := failure["type"].(string)
	if failType != core.FailureInvalidParameters {
		t.Fatalf("expected failure type %q, got %q", core.FailureInvalidParameters, failType)
	}
}

func TestInvokeStreamMissingRequiredParam(t *testing.T) {
	t.Skip("Input validation removed — handlers validate their own inputs, matching Python/TS")
}

func unused_TestInvokeStreamMissingRequiredParam(t *testing.T) {
	svc := newStreamTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// stream_search has no required inputs (no Inputs declared), so this should succeed.
	// But search_flights does -- and it's unary only. Test the stream_search which has no inputs.
	sr, err := svc.InvokeStream("stream_search", token, map[string]any{}, InvokeOpts{})
	if err != nil {
		t.Fatalf("InvokeStream() error: %v", err)
	}

	// Drain events.
	timeout := time.After(5 * time.Second)
	for {
		select {
		case _, ok := <-sr.Events:
			if !ok {
				return
			}
		case <-timeout:
			t.Fatal("timed out")
		}
	}
}

// --- Gap 3: Observability Hooks Tests ---

func TestObservabilityHooksFired(t *testing.T) {
	var invokeStartCalled, invokeCompleteCalled, scopeGranted, auditAppendCalled bool
	var invokeCapability string
	var invokeSuccess bool

	hooks := &ObservabilityHooks{
		OnInvokeStart: func(invocationID, capability, subject string) {
			invokeStartCalled = true
			invokeCapability = capability
		},
		OnInvokeComplete: func(invocationID, capability string, success bool, durationMs int64) {
			invokeCompleteCalled = true
			invokeSuccess = success
		},
		OnScopeValidation: func(capability string, granted bool) {
			scopeGranted = granted
		},
		OnAuditAppend: func(sequenceNum int, capability, invocationID string) {
			auditAppendCalled = true
		},
	}

	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Trust:        "signed",
		Hooks:        hooks,
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	_, err = svc.Invoke("search_flights", token, map[string]any{
		"origin":      "SEA",
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	if !invokeStartCalled {
		t.Error("expected OnInvokeStart to be called")
	}
	if invokeCapability != "search_flights" {
		t.Errorf("expected capability 'search_flights', got %q", invokeCapability)
	}
	if !invokeCompleteCalled {
		t.Error("expected OnInvokeComplete to be called")
	}
	if !invokeSuccess {
		t.Error("expected OnInvokeComplete success=true")
	}
	if !scopeGranted {
		t.Error("expected OnScopeValidation granted=true")
	}
	if !auditAppendCalled {
		t.Error("expected OnAuditAppend to be called")
	}
}

func TestObservabilityHooksPanicRecovery(t *testing.T) {
	hooks := &ObservabilityHooks{
		OnInvokeStart: func(invocationID, capability, subject string) {
			panic("hook panic!")
		},
	}

	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Trust:        "signed",
		Hooks:        hooks,
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      []string{"travel.search"},
		Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}

	// This should NOT panic even though the hook panics.
	result, err := svc.Invoke("search_flights", token, map[string]any{
		"origin":      "SEA",
		"destination": "SFO",
		"date":        "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}
	success, _ := result["success"].(bool)
	if !success {
		t.Fatal("expected success=true despite panicking hook")
	}
}

// --- Gap 4: Health Tests ---

func TestGetHealth(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	report := svc.GetHealth()
	if report.Status != "healthy" {
		t.Fatalf("expected status 'healthy', got %q", report.Status)
	}
	if !report.Storage.Connected {
		t.Fatal("expected storage connected=true")
	}
	if report.Storage.Type != "sqlite" {
		t.Fatalf("expected storage type 'sqlite', got %q", report.Storage.Type)
	}
	if report.Version != core.ProtocolVersion {
		t.Fatalf("expected version %q, got %q", core.ProtocolVersion, report.Version)
	}
	if report.Uptime == "" {
		t.Fatal("expected non-empty uptime")
	}
}

// --- Gap 5+6: Background Workers Tests ---

func TestRetentionAndCheckpointConfig(t *testing.T) {
	// Test that config fields are preserved.
	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Trust:        "signed",
		CheckpointPolicy: &CheckpointPolicy{
			IntervalSeconds: 30,
			MinEntries:      5,
		},
		RetentionIntervalSeconds: 120,
		Authenticate: func(bearer string) (string, bool) {
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	if svc.checkpointPolicy == nil {
		t.Fatal("expected checkpointPolicy to be set")
	}
	if svc.checkpointPolicy.IntervalSeconds != 30 {
		t.Fatalf("expected IntervalSeconds=30, got %d", svc.checkpointPolicy.IntervalSeconds)
	}
	if svc.retentionIntervalSeconds != 120 {
		t.Fatalf("expected retentionIntervalSeconds=120, got %d", svc.retentionIntervalSeconds)
	}
}

func TestShutdownIdempotent(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}

	// Calling Shutdown multiple times should not panic.
	if err := svc.Shutdown(); err != nil {
		t.Fatalf("first Shutdown() error: %v", err)
	}
	if err := svc.Shutdown(); err != nil {
		t.Fatalf("second Shutdown() error: %v", err)
	}
}

// ---------------------------------------------------------------------------
// IssueCapabilityToken
// ---------------------------------------------------------------------------

func TestIssueCapabilityToken(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueCapabilityToken(
		"human:test@example.com",
		"search_flights",
		[]string{"travel.search"},
	)
	if err != nil {
		t.Fatalf("IssueCapabilityToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
	if resp.Token == "" {
		t.Fatal("expected non-empty token")
	}
	if resp.TokenID == "" {
		t.Fatal("expected non-empty token_id")
	}

	// Resolve and verify capability binding.
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}
	if token.Subject != "human:test@example.com" {
		t.Fatalf("expected subject 'human:test@example.com', got %q", token.Subject)
	}
	if token.Purpose.Capability != "search_flights" {
		t.Fatalf("expected capability 'search_flights', got %q", token.Purpose.Capability)
	}
}

func TestIssueCapabilityTokenWithOptions(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	resp, err := svc.IssueCapabilityToken(
		"human:test@example.com",
		"search_flights",
		[]string{"travel.search"},
		WithTTL(4),
		WithPurposeParameters(map[string]any{"task_id": "task-123"}),
		WithBudget(&core.Budget{Currency: "USD", MaxAmount: 100}),
	)
	if err != nil {
		t.Fatalf("IssueCapabilityToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
	if resp.Budget == nil {
		t.Fatal("expected budget to be echoed")
	}
}

// ---------------------------------------------------------------------------
// IssueDelegatedCapabilityToken
// ---------------------------------------------------------------------------

func TestIssueDelegatedCapabilityToken(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Issue root token first.
	rootResp, err := svc.IssueCapabilityToken(
		"human:test@example.com",
		"search_flights",
		[]string{"travel.search"},
	)
	if err != nil {
		t.Fatalf("IssueCapabilityToken() error: %v", err)
	}

	// Delegate.
	resp, err := svc.IssueDelegatedCapabilityToken(
		"human:test@example.com",
		rootResp.TokenID,
		"search_flights",
		[]string{"travel.search"},
		"agent:helper",
	)
	if err != nil {
		t.Fatalf("IssueDelegatedCapabilityToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
	if resp.Token == "" {
		t.Fatal("expected non-empty token")
	}

	// Resolve and verify delegation.
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}
	if token.Subject != "agent:helper" {
		t.Errorf("expected subject %q, got %q", "agent:helper", token.Subject)
	}
	if token.Purpose.Capability != "search_flights" {
		t.Errorf("expected capability %q, got %q", "search_flights", token.Purpose.Capability)
	}
	if token.Parent != rootResp.TokenID {
		t.Errorf("expected parent %q, got %q", rootResp.TokenID, token.Parent)
	}
}

func TestIssueDelegatedCapabilityTokenScopeIsExplicit(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Root token with broader scope.
	rootResp, err := svc.IssueCapabilityToken(
		"human:test@example.com",
		"search_flights",
		[]string{"travel.search", "travel.search.read"},
	)
	if err != nil {
		t.Fatalf("IssueCapabilityToken() error: %v", err)
	}

	// Delegate with a subset scope — scope is explicit, not derived from capability.
	resp, err := svc.IssueDelegatedCapabilityToken(
		"human:test@example.com",
		rootResp.TokenID,
		"search_flights",
		[]string{"travel.search"},
		"agent:worker",
	)
	if err != nil {
		t.Fatalf("IssueDelegatedCapabilityToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
}

func TestIssueDelegatedCapabilityTokenWithOptions(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	rootResp, err := svc.IssueCapabilityToken(
		"human:test@example.com",
		"search_flights",
		[]string{"travel.search"},
	)
	if err != nil {
		t.Fatalf("IssueCapabilityToken() error: %v", err)
	}

	resp, err := svc.IssueDelegatedCapabilityToken(
		"human:test@example.com",
		rootResp.TokenID,
		"search_flights",
		[]string{"travel.search"},
		"agent:delegate",
		WithCallerClass("automated"),
		WithTTL(1),
		WithPurposeParameters(map[string]any{"task_id": "task-456"}),
		WithBudget(&core.Budget{Currency: "USD", MaxAmount: 50}),
	)
	if err != nil {
		t.Fatalf("IssueDelegatedCapabilityToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
}
