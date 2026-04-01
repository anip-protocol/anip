package core

import (
	"encoding/json"
	"regexp"
	"testing"
)

func TestGenerateInvocationID(t *testing.T) {
	id := GenerateInvocationID()
	matched, err := regexp.MatchString(`^inv-[0-9a-f]{12}$`, id)
	if err != nil {
		t.Fatal(err)
	}
	if !matched {
		t.Errorf("invocation ID %q does not match pattern inv-[0-9a-f]{12}", id)
	}

	// Each call should generate a unique ID.
	id2 := GenerateInvocationID()
	if id == id2 {
		t.Errorf("two invocation IDs should be unique, both were %q", id)
	}
}

func TestANIPErrorImplementsError(t *testing.T) {
	var err error = NewANIPError(FailureInvalidToken, "token is invalid")
	if err.Error() != "invalid_token: token is invalid" {
		t.Errorf("unexpected error string: %q", err.Error())
	}
}

func TestANIPErrorBuilder(t *testing.T) {
	e := NewANIPError(FailureScopeInsufficient, "missing scope").
		WithResolution("request_broader_scope").
		WithRetry()

	if e.ErrorType != FailureScopeInsufficient {
		t.Errorf("expected type %q, got %q", FailureScopeInsufficient, e.ErrorType)
	}
	if e.Resolution == nil {
		t.Fatal("expected resolution to be non-nil")
	}
	if e.Resolution.Action != "request_broader_scope" {
		t.Errorf("expected action %q, got %q", "request_broader_scope", e.Resolution.Action)
	}
	if !e.Retry {
		t.Error("expected retry to be true")
	}
}

func TestFailureStatusCode(t *testing.T) {
	tests := []struct {
		failureType string
		expected    int
	}{
		{FailureAuthRequired, 401},
		{FailureInvalidToken, 401},
		{FailureTokenExpired, 401},
		{FailureScopeInsufficient, 403},
		{FailureBudgetExceeded, 403},
		{FailurePurposeMismatch, 403},
		{FailureUnknownCapability, 404},
		{FailureNotFound, 404},
		{FailureUnavailable, 409},
		{FailureConcurrentLock, 409},
		{FailureInternalError, 500},
		{"some_unknown_type", 400},
	}

	for _, tc := range tests {
		got := FailureStatusCode(tc.failureType)
		if got != tc.expected {
			t.Errorf("FailureStatusCode(%q) = %d, want %d", tc.failureType, got, tc.expected)
		}
	}
}

func TestCapabilityDeclarationJSON(t *testing.T) {
	cap := CapabilityDeclaration{
		Name:            "search_flights",
		Description:     "Search for flights",
		ContractVersion: "1.0",
		Inputs: []CapabilityInput{
			{Name: "origin", Type: "airport_code", Required: true, Description: "Departure airport"},
			{Name: "destination", Type: "airport_code", Required: true, Description: "Arrival airport"},
			{Name: "date", Type: "date", Required: true, Description: "Travel date"},
		},
		Output: CapabilityOutput{
			Type:   "object",
			Fields: []string{"flights", "count"},
		},
		SideEffect: SideEffect{
			Type:           "read",
			RollbackWindow: "not_applicable",
		},
		MinimumScope:  []string{"travel.search"},
		ResponseModes: []string{"unary"},
	}

	data, err := json.Marshal(cap)
	if err != nil {
		t.Fatal(err)
	}

	var decoded CapabilityDeclaration
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatal(err)
	}

	if decoded.Name != "search_flights" {
		t.Errorf("expected name %q, got %q", "search_flights", decoded.Name)
	}
	if len(decoded.Inputs) != 3 {
		t.Errorf("expected 3 inputs, got %d", len(decoded.Inputs))
	}
	if decoded.SideEffect.Type != "read" {
		t.Errorf("expected side_effect.type %q, got %q", "read", decoded.SideEffect.Type)
	}
	if len(decoded.MinimumScope) != 1 || decoded.MinimumScope[0] != "travel.search" {
		t.Errorf("expected minimum_scope [travel.search], got %v", decoded.MinimumScope)
	}

	// Verify JSON field names are snake_case.
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	if _, ok := raw["contract_version"]; !ok {
		t.Error("expected JSON field 'contract_version'")
	}
	if _, ok := raw["side_effect"]; !ok {
		t.Error("expected JSON field 'side_effect'")
	}
	if _, ok := raw["minimum_scope"]; !ok {
		t.Error("expected JSON field 'minimum_scope'")
	}
	if _, ok := raw["response_modes"]; !ok {
		t.Error("expected JSON field 'response_modes'")
	}
}

func TestDelegationTokenJSON(t *testing.T) {
	token := DelegationToken{
		TokenID:       "anip-abc123def456",
		Issuer:        "anip-flight-service",
		Subject:       "agent:demo-agent",
		Scope:         []string{"travel.search", "travel.book"},
		Purpose:       Purpose{Capability: "search_flights", Parameters: map[string]any{}, TaskID: "task-001"},
		Expires:       "2026-03-20T12:00:00Z",
		Constraints:   DelegationConstraints{MaxDelegationDepth: 3, ConcurrentBranches: "allowed"},
		RootPrincipal: "human:samir@example.com",
	}

	data, err := json.Marshal(token)
	if err != nil {
		t.Fatal(err)
	}

	var decoded DelegationToken
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatal(err)
	}

	if decoded.TokenID != "anip-abc123def456" {
		t.Errorf("expected token_id %q, got %q", "anip-abc123def456", decoded.TokenID)
	}
	if decoded.RootPrincipal != "human:samir@example.com" {
		t.Errorf("expected root_principal %q, got %q", "human:samir@example.com", decoded.RootPrincipal)
	}
	if decoded.Constraints.MaxDelegationDepth != 3 {
		t.Errorf("expected max_delegation_depth 3, got %d", decoded.Constraints.MaxDelegationDepth)
	}
	if decoded.Purpose.Capability != "search_flights" {
		t.Errorf("expected purpose.capability %q, got %q", "search_flights", decoded.Purpose.Capability)
	}

	// Verify JSON field names.
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	if _, ok := raw["token_id"]; !ok {
		t.Error("expected JSON field 'token_id'")
	}
	if _, ok := raw["root_principal"]; !ok {
		t.Error("expected JSON field 'root_principal'")
	}
}

func TestInvokeResponseJSON(t *testing.T) {
	// Success response.
	resp := InvokeResponse{
		Success:      true,
		InvocationID: "inv-aabbccddeeff",
		Result:       map[string]any{"flights": []any{}, "count": float64(0)},
	}

	data, err := json.Marshal(resp)
	if err != nil {
		t.Fatal(err)
	}

	var decoded InvokeResponse
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatal(err)
	}

	if !decoded.Success {
		t.Error("expected success to be true")
	}
	if decoded.InvocationID != "inv-aabbccddeeff" {
		t.Errorf("expected invocation_id %q, got %q", "inv-aabbccddeeff", decoded.InvocationID)
	}

	// Failure response.
	failResp := InvokeResponse{
		Success:      false,
		InvocationID: "inv-112233445566",
		Failure:      NewANIPError(FailureUnknownCapability, "not found"),
	}

	data, err = json.Marshal(failResp)
	if err != nil {
		t.Fatal(err)
	}

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}

	if _, ok := raw["invocation_id"]; !ok {
		t.Error("expected JSON field 'invocation_id'")
	}
	failure, ok := raw["failure"].(map[string]any)
	if !ok {
		t.Fatal("expected failure to be a map")
	}
	if failure["type"] != FailureUnknownCapability {
		t.Errorf("expected failure type %q, got %q", FailureUnknownCapability, failure["type"])
	}
}

func TestANIPErrorJSON(t *testing.T) {
	e := NewANIPError(FailureScopeInsufficient, "missing travel.book")
	e.Resolution = &Resolution{
		Action:      "request_broader_scope",
		Requires:    "delegation.scope += travel.book",
		GrantableBy: "human:samir@example.com",
	}
	e.Retry = true

	data, err := json.Marshal(e)
	if err != nil {
		t.Fatal(err)
	}

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}

	if raw["type"] != FailureScopeInsufficient {
		t.Errorf("expected type %q, got %v", FailureScopeInsufficient, raw["type"])
	}
	if raw["detail"] != "missing travel.book" {
		t.Errorf("expected detail %q, got %v", "missing travel.book", raw["detail"])
	}
	if raw["retry"] != true {
		t.Errorf("expected retry true, got %v", raw["retry"])
	}

	resolution, ok := raw["resolution"].(map[string]any)
	if !ok {
		t.Fatal("expected resolution to be a map")
	}
	if resolution["action"] != "request_broader_scope" {
		t.Errorf("expected resolution.action %q, got %v", "request_broader_scope", resolution["action"])
	}
	if resolution["grantable_by"] != "human:samir@example.com" {
		t.Errorf("expected resolution.grantable_by %q, got %v", "human:samir@example.com", resolution["grantable_by"])
	}
}

func TestProtocolVersion(t *testing.T) {
	// Intentionally hardcoded — this is the one place that verifies the constant value.
	// Update this when bumping the protocol version.
	if ProtocolVersion != "anip/0.15" {
		t.Errorf("expected protocol version %q, got %q", "anip/0.15", ProtocolVersion)
	}
}

func TestCheckpointJSON(t *testing.T) {
	cp := Checkpoint{
		Version:      "1.0",
		ServiceID:    "anip-flight-service",
		CheckpointID: "chk-001",
		Range:        map[string]int{"first_sequence": 1, "last_sequence": 10},
		MerkleRoot:   "sha256:abc123",
		Timestamp:    "2026-03-20T12:00:00Z",
		EntryCount:   10,
	}

	data, err := json.Marshal(cp)
	if err != nil {
		t.Fatal(err)
	}

	var decoded Checkpoint
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatal(err)
	}

	if decoded.CheckpointID != "chk-001" {
		t.Errorf("expected checkpoint_id %q, got %q", "chk-001", decoded.CheckpointID)
	}
	if decoded.Range["first_sequence"] != 1 {
		t.Errorf("expected range.first_sequence 1, got %d", decoded.Range["first_sequence"])
	}
	if decoded.EntryCount != 10 {
		t.Errorf("expected entry_count 10, got %d", decoded.EntryCount)
	}

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}
	if _, ok := raw["checkpoint_id"]; !ok {
		t.Error("expected JSON field 'checkpoint_id'")
	}
	if _, ok := raw["merkle_root"]; !ok {
		t.Error("expected JSON field 'merkle_root'")
	}
	if _, ok := raw["entry_count"]; !ok {
		t.Error("expected JSON field 'entry_count'")
	}
}

func TestTokenResponseJSON(t *testing.T) {
	resp := TokenResponse{
		Issued:  true,
		TokenID: "anip-abc123",
		Token:   "eyJ...",
		Expires: "2026-03-20T14:00:00Z",
	}

	data, err := json.Marshal(resp)
	if err != nil {
		t.Fatal(err)
	}

	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatal(err)
	}

	if raw["issued"] != true {
		t.Errorf("expected issued true, got %v", raw["issued"])
	}
	if _, ok := raw["token_id"]; !ok {
		t.Error("expected JSON field 'token_id'")
	}
}
