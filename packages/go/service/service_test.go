package service

import (
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

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
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
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

	_, err := svc.GetCheckpoint("nonexistent", false, 0)
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
	detail, err := svc.GetCheckpoint(cp.CheckpointID, false, 0)
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
