package mcpapi

import (
	"encoding/json"
	"strings"
	"testing"

	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func floatPtr(f float64) *float64 { return &f }

// --- Test capabilities ---

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
					{Name: "date", Type: "date", Required: false, Description: "Booking date"},
					{Name: "airport", Type: "airport_code", Required: false, Description: "Airport code"},
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
				Requires: []core.CapabilityRequirement{
					{Capability: "greet", Reason: "Must greet first"},
				},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				item, _ := params["item"].(string)
				return map[string]any{
					"booking_id": "bk-123",
					"item":       item,
				}, nil
			},
		},
	}
}

func newTestService(t *testing.T) *service.Service {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID:    "test-mcp-service",
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

// --- Translation tests ---

func TestCapabilityToInputSchema_BasicTypes(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Inputs: []core.CapabilityInput{
			{Name: "name", Type: "string", Required: true, Description: "A name"},
			{Name: "count", Type: "integer", Required: false, Default: 1, Description: "Count"},
			{Name: "ratio", Type: "number", Required: false, Description: "Ratio"},
			{Name: "active", Type: "boolean", Required: true, Description: "Active"},
			{Name: "travel_date", Type: "date", Required: false, Description: "Travel date"},
			{Name: "origin", Type: "airport_code", Required: false, Description: "Airport"},
		},
	}

	schema := CapabilityToInputSchema(decl)

	if schema["type"] != "object" {
		t.Errorf("expected type=object, got %v", schema["type"])
	}

	props := schema["properties"].(map[string]any)

	// Check string
	nameProp := props["name"].(map[string]any)
	if nameProp["type"] != "string" {
		t.Errorf("name: expected type=string, got %v", nameProp["type"])
	}

	// Check integer
	countProp := props["count"].(map[string]any)
	if countProp["type"] != "integer" {
		t.Errorf("count: expected type=integer, got %v", countProp["type"])
	}
	if countProp["default"] != 1 {
		t.Errorf("count: expected default=1, got %v", countProp["default"])
	}

	// Check number
	ratioProp := props["ratio"].(map[string]any)
	if ratioProp["type"] != "number" {
		t.Errorf("ratio: expected type=number, got %v", ratioProp["type"])
	}

	// Check boolean
	activeProp := props["active"].(map[string]any)
	if activeProp["type"] != "boolean" {
		t.Errorf("active: expected type=boolean, got %v", activeProp["type"])
	}

	// Check date → string with format
	dateProp := props["travel_date"].(map[string]any)
	if dateProp["type"] != "string" {
		t.Errorf("travel_date: expected type=string, got %v", dateProp["type"])
	}
	if dateProp["format"] != "date" {
		t.Errorf("travel_date: expected format=date, got %v", dateProp["format"])
	}

	// Check airport_code → string
	airportProp := props["origin"].(map[string]any)
	if airportProp["type"] != "string" {
		t.Errorf("origin: expected type=string, got %v", airportProp["type"])
	}

	// Check required
	required := schema["required"].([]string)
	if len(required) != 2 {
		t.Fatalf("expected 2 required fields, got %d", len(required))
	}
	expectedRequired := map[string]bool{"name": true, "active": true}
	for _, r := range required {
		if !expectedRequired[r] {
			t.Errorf("unexpected required field: %s", r)
		}
	}
}

func TestCapabilityToInputSchema_NoRequired(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Inputs: []core.CapabilityInput{
			{Name: "optional_field", Type: "string", Required: false},
		},
	}

	schema := CapabilityToInputSchema(decl)
	if _, hasRequired := schema["required"]; hasRequired {
		t.Error("expected no required field when no inputs are required")
	}
}

func TestEnrichDescription_ReadOnly(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Description: "Look up a thing",
		SideEffect:  core.SideEffect{Type: "read"},
		MinimumScope: []string{"read"},
	}

	desc := EnrichDescription(decl)
	if !strings.Contains(desc, "Read-only, no side effects.") {
		t.Errorf("expected read-only annotation, got: %s", desc)
	}
	if !strings.Contains(desc, "Delegation scope: read.") {
		t.Errorf("expected scope annotation, got: %s", desc)
	}
}

func TestEnrichDescription_Irreversible(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Description: "Delete everything",
		SideEffect:  core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
	}

	desc := EnrichDescription(decl)
	if !strings.Contains(desc, "WARNING: IRREVERSIBLE") {
		t.Errorf("expected irreversible warning, got: %s", desc)
	}
	if !strings.Contains(desc, "No rollback window.") {
		t.Errorf("expected no rollback window, got: %s", desc)
	}
}

func TestEnrichDescription_WriteWithRollback(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Description: "Update record",
		SideEffect:  core.SideEffect{Type: "write", RollbackWindow: "PT24H"},
	}

	desc := EnrichDescription(decl)
	if !strings.Contains(desc, "Reversible within PT24H.") {
		t.Errorf("expected rollback window annotation, got: %s", desc)
	}
}

func TestEnrichDescription_Cost(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Description: "Book a flight",
		SideEffect:  core.SideEffect{Type: "write"},
		Cost: &core.Cost{
			Certainty: "estimated",
			Financial: &core.FinancialCost{
				Currency: "USD",
				RangeMin: floatPtr(100),
				RangeMax: floatPtr(500),
			},
		},
	}

	desc := EnrichDescription(decl)
	if !strings.Contains(desc, "Estimated cost: USD 100-500.") {
		t.Errorf("expected cost annotation, got: %s", desc)
	}
}

func TestEnrichDescription_FixedCost(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Description: "Check status",
		SideEffect:  core.SideEffect{Type: "read"},
		Cost: &core.Cost{
			Certainty: "fixed",
			Financial: &core.FinancialCost{
				Currency: "EUR",
				Amount:   floatPtr(5.0),
			},
		},
	}

	desc := EnrichDescription(decl)
	if !strings.Contains(desc, "Cost: EUR 5") {
		t.Errorf("expected fixed cost annotation, got: %s", desc)
	}
}

func TestEnrichDescription_Prerequisites(t *testing.T) {
	decl := &core.CapabilityDeclaration{
		Description: "Execute action",
		SideEffect:  core.SideEffect{Type: "write"},
		Requires: []core.CapabilityRequirement{
			{Capability: "prepare"},
			{Capability: "validate"},
		},
	}

	desc := EnrichDescription(decl)
	if !strings.Contains(desc, "Requires calling first: prepare, validate.") {
		t.Errorf("expected prerequisites annotation, got: %s", desc)
	}
}

// --- TranslateResponse tests ---

func TestTranslateResponse_Success(t *testing.T) {
	response := map[string]any{
		"success": true,
		"result": map[string]any{
			"greeting": "Hello, Alice!",
		},
	}

	result := TranslateResponse(response)
	if result.IsError {
		t.Error("expected success, got error")
	}

	// Should be pretty-printed JSON
	var parsed map[string]any
	if err := json.Unmarshal([]byte(result.Text), &parsed); err != nil {
		t.Errorf("expected valid JSON, got: %s", result.Text)
	}
	if parsed["greeting"] != "Hello, Alice!" {
		t.Errorf("expected greeting, got: %v", parsed)
	}
}

func TestTranslateResponse_SuccessWithCost(t *testing.T) {
	response := map[string]any{
		"success": true,
		"result": map[string]any{
			"booking": "confirmed",
		},
		"cost_actual": map[string]any{
			"financial": map[string]any{
				"amount":   42.50,
				"currency": "USD",
			},
		},
	}

	result := TranslateResponse(response)
	if result.IsError {
		t.Error("expected success, got error")
	}
	if !strings.Contains(result.Text, "[Cost: USD 42.5]") {
		t.Errorf("expected cost annotation, got: %s", result.Text)
	}
}

func TestTranslateResponse_Failure(t *testing.T) {
	response := map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   "scope_insufficient",
			"detail": "Missing 'admin' scope",
			"retry":  false,
			"resolution": map[string]any{
				"action":   "Request admin scope from principal",
				"requires": "admin:write",
			},
		},
	}

	result := TranslateResponse(response)
	if !result.IsError {
		t.Error("expected error, got success")
	}
	if !strings.Contains(result.Text, "FAILED: scope_insufficient") {
		t.Errorf("expected failure type, got: %s", result.Text)
	}
	if !strings.Contains(result.Text, "Detail: Missing 'admin' scope") {
		t.Errorf("expected detail, got: %s", result.Text)
	}
	if !strings.Contains(result.Text, "Resolution: Request admin scope from principal") {
		t.Errorf("expected resolution, got: %s", result.Text)
	}
	if !strings.Contains(result.Text, "Requires: admin:write") {
		t.Errorf("expected requires, got: %s", result.Text)
	}
	if !strings.Contains(result.Text, "Retryable: no") {
		t.Errorf("expected retryable: no, got: %s", result.Text)
	}
}

func TestTranslateResponse_FailureRetryable(t *testing.T) {
	response := map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   "unavailable",
			"detail": "Service temporarily unavailable",
			"retry":  true,
		},
	}

	result := TranslateResponse(response)
	if !result.IsError {
		t.Error("expected error, got success")
	}
	if !strings.Contains(result.Text, "Retryable: yes") {
		t.Errorf("expected retryable: yes, got: %s", result.Text)
	}
}

func TestTranslateResponse_FailureNilFailure(t *testing.T) {
	response := map[string]any{
		"success": false,
	}

	result := TranslateResponse(response)
	if !result.IsError {
		t.Error("expected error, got success")
	}
	if !strings.Contains(result.Text, "FAILED: unknown") {
		t.Errorf("expected unknown failure, got: %s", result.Text)
	}
}

// --- InvokeWithMountCredentials tests ---

func TestInvokeWithMountCredentials_ValidCredentials(t *testing.T) {
	svc := newTestService(t)

	creds := &McpCredentials{
		APIKey:  "test-api-key",
		Scope:   []string{"greet"},
		Subject: "adapter:mcp-test",
	}

	result := InvokeWithMountCredentials(svc, "greet", map[string]any{
		"name": "Alice",
	}, creds)

	if result.IsError {
		t.Errorf("expected success, got error: %s", result.Text)
	}
	if !strings.Contains(result.Text, "Hello, Alice!") {
		t.Errorf("expected greeting, got: %s", result.Text)
	}
}

func TestInvokeWithMountCredentials_InvalidCredentials(t *testing.T) {
	svc := newTestService(t)

	creds := &McpCredentials{
		APIKey:  "bad-key",
		Scope:   []string{"greet"},
		Subject: "adapter:mcp-test",
	}

	result := InvokeWithMountCredentials(svc, "greet", map[string]any{
		"name": "Alice",
	}, creds)

	if !result.IsError {
		t.Error("expected error for invalid credentials")
	}
	if !strings.Contains(result.Text, "authentication_required") {
		t.Errorf("expected authentication_required, got: %s", result.Text)
	}
}

func TestInvokeWithMountCredentials_ScopeNarrowing(t *testing.T) {
	svc := newTestService(t)

	// Provide broad scope including both greet and book
	creds := &McpCredentials{
		APIKey:  "test-api-key",
		Scope:   []string{"greet", "book", "admin"},
		Subject: "adapter:mcp-test",
	}

	// Invoking greet should narrow scope to just "greet"
	result := InvokeWithMountCredentials(svc, "greet", map[string]any{
		"name": "Bob",
	}, creds)

	if result.IsError {
		t.Errorf("expected success, got error: %s", result.Text)
	}
	if !strings.Contains(result.Text, "Hello, Bob!") {
		t.Errorf("expected greeting, got: %s", result.Text)
	}
}

func TestInvokeWithMountCredentials_UnknownCapability(t *testing.T) {
	svc := newTestService(t)

	creds := &McpCredentials{
		APIKey:  "test-api-key",
		Scope:   []string{"*"},
		Subject: "adapter:mcp-test",
	}

	result := InvokeWithMountCredentials(svc, "nonexistent", map[string]any{}, creds)

	if !result.IsError {
		t.Error("expected error for unknown capability")
	}
	if !strings.Contains(result.Text, "unknown_capability") || !strings.Contains(result.Text, "FAILED") {
		t.Errorf("expected unknown_capability failure, got: %s", result.Text)
	}
}

// --- NarrowScope tests ---

func TestNarrowScope(t *testing.T) {
	tests := []struct {
		name       string
		mountScope []string
		minScope   []string
		expected   []string
	}{
		{
			name:       "empty minimum scope returns full scope",
			mountScope: []string{"greet", "book"},
			minScope:   nil,
			expected:   []string{"greet", "book"},
		},
		{
			name:       "narrows to matching entries",
			mountScope: []string{"greet", "book", "admin"},
			minScope:   []string{"greet"},
			expected:   []string{"greet"},
		},
		{
			name:       "matches base of qualified scope",
			mountScope: []string{"greet:read", "book:write"},
			minScope:   []string{"greet"},
			expected:   []string{"greet:read"},
		},
		{
			name:       "no match returns full scope",
			mountScope: []string{"admin"},
			minScope:   []string{"greet"},
			expected:   []string{"admin"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := NarrowScope(tt.mountScope, tt.minScope)
			if len(got) != len(tt.expected) {
				t.Errorf("NarrowScope(%v, %v) = %v, want %v", tt.mountScope, tt.minScope, got, tt.expected)
				return
			}
			for i, v := range got {
				if v != tt.expected[i] {
					t.Errorf("NarrowScope(%v, %v)[%d] = %v, want %v", tt.mountScope, tt.minScope, i, v, tt.expected[i])
				}
			}
		})
	}
}

// --- MountAnipMCP tests ---

func TestMountAnipMCP_RequiresCredentials(t *testing.T) {
	svc := newTestService(t)
	mcpSrv := mcpserver.NewMCPServer("test", "0.1.0")

	_, err := MountAnipMCP(mcpSrv, svc, nil)
	if err == nil {
		t.Fatal("expected error when credentials are nil")
	}
	if !strings.Contains(err.Error(), "requires credentials") {
		t.Errorf("expected credentials error, got: %s", err.Error())
	}

	_, err = MountAnipMCP(mcpSrv, svc, &MountOptions{})
	if err == nil {
		t.Fatal("expected error when credentials are nil in options")
	}
}

func TestMountAnipMCP_RegistersTools(t *testing.T) {
	svc := newTestService(t)
	mcpSrv := mcpserver.NewMCPServer("test", "0.1.0")

	lifecycle, err := MountAnipMCP(mcpSrv, svc, &MountOptions{
		Credentials: &McpCredentials{
			APIKey:  "test-api-key",
			Scope:   []string{"greet", "book"},
			Subject: "adapter:mcp-test",
		},
	})
	if err != nil {
		t.Fatalf("MountAnipMCP error: %v", err)
	}
	defer lifecycle.Shutdown()

	// Verify tool names are registered
	names := ToolNames(svc)
	if len(names) != 2 {
		t.Fatalf("expected 2 tools, got %d", len(names))
	}

	found := make(map[string]bool)
	for _, name := range names {
		found[name] = true
	}
	if !found["greet"] || !found["book"] {
		t.Errorf("expected greet and book tools, got: %v", names)
	}
}

func TestMountAnipMCP_EnrichDescriptionsDefault(t *testing.T) {
	svc := newTestService(t)

	// Check that enriched description for the "greet" capability includes metadata
	decl := svc.GetCapabilityDeclaration("greet")
	desc := EnrichDescription(decl)

	if !strings.Contains(desc, "Read-only, no side effects.") {
		t.Errorf("expected enriched description, got: %s", desc)
	}
	if !strings.Contains(desc, "Delegation scope: greet.") {
		t.Errorf("expected scope in description, got: %s", desc)
	}
}

func TestMountAnipMCP_EnrichDescriptionsDisabled(t *testing.T) {
	svc := newTestService(t)

	// When enrichment is disabled, description should be the raw declaration description
	decl := svc.GetCapabilityDeclaration("greet")
	rawDesc := decl.Description

	if rawDesc != "Greet a person" {
		t.Errorf("expected raw description 'Greet a person', got: %s", rawDesc)
	}
}
