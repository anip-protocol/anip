// Parameter validation against declared inputs (SPEC.md §6.3 "Parameter
// Validation", §4.1 "Inputs"). Mirrors conformance/test_input_validation.py
// at the service layer, plus the in-memory value forms only Go callers and
// Go transports produce.

package service

import (
	"encoding/json"
	"math"
	"math/big"
	"reflect"
	"sync/atomic"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

func validationDecl() *core.CapabilityDeclaration {
	return &core.CapabilityDeclaration{
		Name: "book_flight",
		Inputs: []core.CapabilityInput{
			{Name: "flight_number", Type: "string", Required: true},
			{Name: "date", Type: "date", Required: true},
			{Name: "passengers", Type: "integer", Required: false, Default: 1},
			{Name: "quote_id", Type: "object", Required: false},
			{Name: "price_cap", Type: "number", Required: false},
			{Name: "flexible", Type: "boolean", Required: false},
			{Name: "tags", Type: "array", Required: false},
			{Name: "cabin", Type: "String", Required: false}, // not a primitive name: case-sensitive
		},
	}
}

func validParams() map[string]any {
	return map[string]any{"flight_number": "AA100", "date": "2026-03-10"}
}

func TestValidateDeclaredInputsAcceptsValidParameters(t *testing.T) {
	type custom struct{ A int }
	cases := map[string]map[string]any{
		"required only":                validParams(),
		"optional null":                {"flight_number": "AA100", "date": "2026-03-10", "passengers": nil, "quote_id": nil},
		"integer as float64":           {"flight_number": "AA100", "date": "2026-03-10", "passengers": float64(5)},
		"integer as integral float":    {"flight_number": "AA100", "date": "2026-03-10", "passengers": 5.0},
		"integer as 1e2":               {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1e2},
		"integer as int":               {"flight_number": "AA100", "date": "2026-03-10", "passengers": 5},
		"integer as int64":             {"flight_number": "AA100", "date": "2026-03-10", "passengers": int64(5)},
		"integer as uint8":             {"flight_number": "AA100", "date": "2026-03-10", "passengers": uint8(5)},
		"integer as float32":           {"flight_number": "AA100", "date": "2026-03-10", "passengers": float32(5)},
		"integer as json.Number":       {"flight_number": "AA100", "date": "2026-03-10", "passengers": json.Number("5")},
		"integer as json.Number 5.0":   {"flight_number": "AA100", "date": "2026-03-10", "passengers": json.Number("5.0")},
		"integer as json.Number 1e2":   {"flight_number": "AA100", "date": "2026-03-10", "passengers": json.Number("1e2")},
		"integer beyond 2^63":          {"flight_number": "AA100", "date": "2026-03-10", "passengers": json.Number("123456789012345678901234567890")},
		"integer as big.Int":           {"flight_number": "AA100", "date": "2026-03-10", "passengers": new(big.Int).Lsh(big.NewInt(1), 80)},
		"integer as large float":       {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1e300},
		"number as float":              {"flight_number": "AA100", "date": "2026-03-10", "price_cap": 1.5},
		"number as int":                {"flight_number": "AA100", "date": "2026-03-10", "price_cap": 2},
		"number as json.Number":        {"flight_number": "AA100", "date": "2026-03-10", "price_cap": json.Number("1.5")},
		"boolean":                      {"flight_number": "AA100", "date": "2026-03-10", "flexible": false},
		"array as []any":               {"flight_number": "AA100", "date": "2026-03-10", "tags": []any{"a"}},
		"array as []string":            {"flight_number": "AA100", "date": "2026-03-10", "tags": []string{"a"}},
		"array as []map":               {"flight_number": "AA100", "date": "2026-03-10", "tags": []map[string]any{{"a": 1}}},
		"array empty":                  {"flight_number": "AA100", "date": "2026-03-10", "tags": []any{}},
		"object as map[string]any":     {"flight_number": "AA100", "date": "2026-03-10", "quote_id": map[string]any{"id": "q"}},
		"object as map[string]string":  {"flight_number": "AA100", "date": "2026-03-10", "quote_id": map[string]string{"id": "q"}},
		"object as struct":             {"flight_number": "AA100", "date": "2026-03-10", "quote_id": custom{A: 1}},
		"object as struct pointer":     {"flight_number": "AA100", "date": "2026-03-10", "quote_id": &custom{A: 1}},
		"domain type is not checked":   {"flight_number": "AA100", "date": true},
		"domain type as number":        {"flight_number": "AA100", "date": 20260310},
		"type name is case-sensitive":  {"flight_number": "AA100", "date": "2026-03-10", "cabin": 7},
		"undeclared parameter":         {"flight_number": "AA100", "date": "2026-03-10", "seat": 12, "extra": map[string]any{}},
		"empty string is still string": {"flight_number": "", "date": "2026-03-10"},
	}
	for name, params := range cases {
		t.Run(name, func(t *testing.T) {
			before := len(params)
			if err := validateDeclaredInputs("book_flight", validationDecl(), params); err != nil {
				t.Fatalf("expected the parameters to be accepted, got %v", err)
			}
			if len(params) != before {
				t.Fatalf("validation changed the parameters: %#v", params)
			}
		})
	}
}

func TestValidateDeclaredInputsRefusals(t *testing.T) {
	var nilPtr *struct{}
	cases := []struct {
		name   string
		params map[string]any
		detail string
	}{
		{"nil parameters", nil,
			"book_flight is missing required input(s): flight_number, date"},
		{"empty parameters", map[string]any{},
			"book_flight is missing required input(s): flight_number, date"},
		{"one missing", map[string]any{"date": "2026-03-10"},
			"book_flight is missing required input(s): flight_number"},
		{"null is missing", map[string]any{"flight_number": nil, "date": "2026-03-10"},
			"book_flight is missing required input(s): flight_number"},
		{"nil pointer is missing", map[string]any{"flight_number": "AA100", "date": nilPtr},
			"book_flight is missing required input(s): date"},
		{"missing wins over wrong type", map[string]any{"date": "2026-03-10", "passengers": "two"},
			"book_flight is missing required input(s): flight_number"},
		{"string got number", map[string]any{"flight_number": 12345, "date": "2026-03-10"},
			"book_flight has invalid input(s): 'flight_number' must be string, got number"},
		{"string got boolean", map[string]any{"flight_number": true, "date": "2026-03-10"},
			"book_flight has invalid input(s): 'flight_number' must be string, got boolean"},
		{"string got array", map[string]any{"flight_number": []any{"AA100"}, "date": "2026-03-10"},
			"book_flight has invalid input(s): 'flight_number' must be string, got array"},
		{"string got object", map[string]any{"flight_number": map[string]any{}, "date": "2026-03-10"},
			"book_flight has invalid input(s): 'flight_number' must be string, got object"},
		{"string got json.Number", map[string]any{"flight_number": json.Number("7"), "date": "2026-03-10"},
			"book_flight has invalid input(s): 'flight_number' must be string, got number"},
		{"integer got string", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": "5"},
			"book_flight has invalid input(s): 'passengers' must be integer, got string"},
		{"integer got fraction", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": 1.5},
			"book_flight has invalid input(s): 'passengers' must be integer, got number"},
		{"integer got json.Number fraction", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": json.Number("1.5")},
			"book_flight has invalid input(s): 'passengers' must be integer, got number"},
		{"integer got NaN", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": math.NaN()},
			"book_flight has invalid input(s): 'passengers' must be integer, got number"},
		{"integer got infinity", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": math.Inf(1)},
			"book_flight has invalid input(s): 'passengers' must be integer, got number"},
		{"integer got true", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": true},
			"book_flight has invalid input(s): 'passengers' must be integer, got boolean"},
		{"integer got false", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": false},
			"book_flight has invalid input(s): 'passengers' must be integer, got boolean"},
		{"integer got array", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": []any{1}},
			"book_flight has invalid input(s): 'passengers' must be integer, got array"},
		{"integer got object", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "passengers": map[string]any{"n": 1}},
			"book_flight has invalid input(s): 'passengers' must be integer, got object"},
		{"number got string", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "price_cap": "1.5"},
			"book_flight has invalid input(s): 'price_cap' must be number, got string"},
		{"number got boolean", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "price_cap": true},
			"book_flight has invalid input(s): 'price_cap' must be number, got boolean"},
		{"boolean got number", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "flexible": 1},
			"book_flight has invalid input(s): 'flexible' must be boolean, got number"},
		{"boolean got string", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "flexible": "true"},
			"book_flight has invalid input(s): 'flexible' must be boolean, got string"},
		{"array got object", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "tags": map[string]any{}},
			"book_flight has invalid input(s): 'tags' must be array, got object"},
		{"array got string", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "tags": "a,b"},
			"book_flight has invalid input(s): 'tags' must be array, got string"},
		{"object got array", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "quote_id": []any{}},
			"book_flight has invalid input(s): 'quote_id' must be object, got array"},
		{"object got string", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "quote_id": "qt-1"},
			"book_flight has invalid input(s): 'quote_id' must be object, got string"},
		{"every wrong input, declaration order", map[string]any{"flight_number": "AA100", "date": "2026-03-10", "quote_id": []any{}, "passengers": "two", "flexible": 0},
			"book_flight has invalid input(s): 'passengers' must be integer, got string; 'quote_id' must be object, got array; 'flexible' must be boolean, got number"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			err := validateDeclaredInputs("book_flight", validationDecl(), tc.params)
			if err == nil {
				t.Fatalf("expected a refusal with detail %q", tc.detail)
			}
			if err.ErrorType != core.FailureInvalidParameters {
				t.Fatalf("failure type = %q, want invalid_parameters", err.ErrorType)
			}
			if err.Detail != tc.detail {
				t.Fatalf("detail =\n  %q\nwant\n  %q", err.Detail, tc.detail)
			}
			want := &core.Resolution{
				Action:        "retry_now",
				RecoveryClass: "retry_now",
				Requires:      "parameters that match the capability's declared inputs",
			}
			if !reflect.DeepEqual(err.Resolution, want) {
				t.Fatalf("resolution = %#v, want %#v", err.Resolution, want)
			}
			if err.Retry {
				t.Fatal("retry must be false: the same request cannot succeed")
			}
		})
	}
}

// --- Invoke pipeline ------------------------------------------------------

type validationFixture struct {
	svc      *Service
	handled  *atomic.Int32
	streamed *atomic.Int32
}

// newValidationService has one unary capability with a binding, a budget cost
// and a grant policy (so every earlier pipeline stage can be provoked), and
// one streaming capability.
func newValidationService(t *testing.T, hooks *ObservabilityHooks) validationFixture {
	t.Helper()
	handled := &atomic.Int32{}
	streamed := &atomic.Int32{}
	book := CapabilityDef{
		Declaration: core.CapabilityDeclaration{
			Name:        "book_flight",
			Description: "Book a flight",
			Inputs: []core.CapabilityInput{
				{Name: "flight_number", Type: "string", Required: true},
				{Name: "date", Type: "date", Required: true},
				{Name: "passengers", Type: "integer", Required: true, Default: 1},
				{Name: "quote_id", Type: "object", Required: false},
			},
			Output:       core.CapabilityOutput{Type: "object", Fields: []string{"booking_id"}},
			SideEffect:   core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
			MinimumScope: []string{"travel.book"},
			Cost: &core.Cost{
				Certainty: "estimated",
				Financial: &core.FinancialCost{Currency: "USD"},
			},
			RequiresBinding: []core.BindingRequirement{{Type: "quote", Field: "quote_id", SourceCapability: "search_flights"}},
			ResponseModes:   []string{"unary"},
			GrantPolicy:     defaultGrantPolicy(),
		},
		Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
			handled.Add(1)
			if n, _ := params["passengers"].(float64); n >= 5 && ctx.ApprovalGrant == "" {
				return nil, &core.ANIPError{ErrorType: FailureApprovalRequired, Detail: "group bookings need approval"}
			}
			return map[string]any{"booking_id": "BK-1", "seen": params}, nil
		},
	}
	watch := CapabilityDef{
		Declaration: core.CapabilityDeclaration{
			Name:        "watch_fares",
			Description: "Stream fare changes",
			Inputs: []core.CapabilityInput{
				{Name: "route", Type: "string", Required: true},
				{Name: "limit", Type: "integer", Required: false},
			},
			Output:        core.CapabilityOutput{Type: "object", Fields: []string{"count"}},
			SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
			MinimumScope:  []string{"travel.search"},
			ResponseModes: []string{"unary", "streaming"},
			GrantPolicy:   defaultGrantPolicy(),
		},
		Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
			streamed.Add(1)
			return map[string]any{"count": 0}, nil
		},
	}
	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: []CapabilityDef{book, watch},
		Storage:      ":memory:",
		Trust:        "signed",
		Hooks:        hooks,
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	return validationFixture{svc: svc, handled: handled, streamed: streamed}
}

func bookParams() map[string]any {
	return map[string]any{
		"flight_number": "AA100",
		"date":          "2026-03-10",
		"passengers":    float64(1),
		"quote_id":      map[string]any{"id": "qt-1", "price": float64(420)},
	}
}

func bookToken(t *testing.T, svc *Service, opts ...func(*core.TokenRequest)) *core.DelegationToken {
	t.Helper()
	base := []func(*core.TokenRequest){func(r *core.TokenRequest) {
		r.Scope = []string{"travel.book"}
		r.Capability = "book_flight"
	}}
	return issueResolvedToken(t, svc, append(base, opts...)...)
}

func assertInvalidParameters(t *testing.T, result map[string]any, wantDetail string) map[string]any {
	t.Helper()
	if result["success"] != false {
		t.Fatalf("expected a refusal, got %#v", result)
	}
	if _, has := result["result"]; has {
		t.Fatalf("a refused invocation carries a result: %#v", result)
	}
	failure, _ := result["failure"].(map[string]any)
	want := map[string]any{
		"type":   "invalid_parameters",
		"detail": wantDetail,
		"resolution": map[string]any{
			"action":         "retry_now",
			"recovery_class": "retry_now",
			"requires":       "parameters that match the capability's declared inputs",
		},
		"retry": false,
	}
	if !reflect.DeepEqual(failure, want) {
		t.Fatalf("failure =\n  %#v\nwant\n  %#v", failure, want)
	}
	if id, _ := result["invocation_id"].(string); id == "" {
		t.Fatalf("no invocation_id on the refusal: %#v", result)
	}
	return failure
}

func auditEntryFor(t *testing.T, svc *Service, token *core.DelegationToken, invocationID string) core.AuditEntry {
	t.Helper()
	audit, err := svc.QueryAudit(token, server.AuditFilters{InvocationID: invocationID})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(audit.Entries) != 1 {
		t.Fatalf("expected one audit entry for %s, got %d", invocationID, len(audit.Entries))
	}
	return audit.Entries[0]
}

func TestInvokeRefusesMissingRequiredInput(t *testing.T) {
	var completed []bool
	fx := newValidationService(t, &ObservabilityHooks{
		OnInvokeComplete: func(invocationID, capability string, success bool, durationMs int64) {
			completed = append(completed, success)
		},
	})
	token := bookToken(t, fx.svc)
	params := bookParams()
	delete(params, "flight_number")
	delete(params, "date")

	result, err := fx.svc.Invoke("book_flight", token, params, InvokeOpts{
		ClientReferenceID:  "ref-1",
		TaskID:             token.Purpose.TaskID,
		ParentInvocationID: "inv-000000000000",
		UpstreamService:    "upstream",
	})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	assertInvalidParameters(t, result, "book_flight is missing required input(s): flight_number, date")
	if fx.handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
	for key, want := range map[string]string{
		"client_reference_id":  "ref-1",
		"task_id":              token.Purpose.TaskID,
		"parent_invocation_id": "inv-000000000000",
		"upstream_service":     "upstream",
	} {
		if result[key] != want {
			t.Fatalf("%s = %#v, want %q", key, result[key], want)
		}
	}

	entry := auditEntryFor(t, fx.svc, token, result["invocation_id"].(string))
	if entry.Success || entry.FailureType != core.FailureInvalidParameters || entry.Capability != "book_flight" {
		t.Fatalf("unexpected audit entry: success=%v failure_type=%q capability=%q", entry.Success, entry.FailureType, entry.Capability)
	}
	if entry.ClientReferenceID != "ref-1" || entry.TaskID != token.Purpose.TaskID || entry.TaskID == "" || entry.ParentInvocationID != "inv-000000000000" || entry.UpstreamService != "upstream" {
		t.Fatalf("audit entry lost the lineage fields: %#v", entry)
	}
	if len(completed) != 1 || completed[0] {
		t.Fatalf("OnInvokeComplete = %v, want one call with success=false", completed)
	}
}

func TestInvokeDeclaredDefaultDoesNotSatisfyRequired(t *testing.T) {
	fx := newValidationService(t, nil)
	token := bookToken(t, fx.svc)
	params := bookParams()
	delete(params, "passengers") // required: true with a default of 1

	result, err := fx.svc.Invoke("book_flight", token, params, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	assertInvalidParameters(t, result, "book_flight is missing required input(s): passengers")
	if fx.handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

func TestInvokeRefusesWrongPrimitiveType(t *testing.T) {
	fx := newValidationService(t, nil)
	token := bookToken(t, fx.svc)
	params := bookParams()
	params["passengers"] = true

	result, err := fx.svc.Invoke("book_flight", token, params, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	assertInvalidParameters(t, result, "book_flight has invalid input(s): 'passengers' must be integer, got boolean")
	if fx.handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

func TestInvokePassesValidAndUndeclaredParametersToTheHandler(t *testing.T) {
	fx := newValidationService(t, nil)
	token := bookToken(t, fx.svc)
	params := bookParams()
	params["passengers"] = 2.0
	params["date"] = true         // domain type: the handler's business
	params["seat_preference"] = 7 // undeclared

	result, err := fx.svc.Invoke("book_flight", token, params, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if result["success"] != true {
		t.Fatalf("expected success, got %#v", result)
	}
	seen := result["result"].(map[string]any)["seen"].(map[string]any)
	if seen["seat_preference"] != 7 || seen["date"] != true {
		t.Fatalf("the handler did not receive the parameters as sent: %#v", seen)
	}
}

// §6.3 "When": the check runs after delegation, budget, binding and
// control-requirement enforcement.
func TestParameterValidationRunsAfterAuthorityChecks(t *testing.T) {
	fx := newValidationService(t, nil)
	invalid := func() map[string]any {
		p := bookParams()
		p["flight_number"] = 12345
		return p
	}

	t.Run("scope", func(t *testing.T) {
		token := issueResolvedToken(t, fx.svc, func(r *core.TokenRequest) {
			r.Scope = []string{"travel.search"}
			r.Capability = "book_flight"
		})
		result, _ := fx.svc.Invoke("book_flight", token, invalid(), InvokeOpts{})
		if got := failureType(t, result); got != core.FailureScopeInsufficient {
			t.Fatalf("failure type = %q, want scope_insufficient", got)
		}
	})
	t.Run("purpose", func(t *testing.T) {
		token := issueResolvedToken(t, fx.svc, func(r *core.TokenRequest) {
			r.Scope = []string{"travel.book", "travel.search"}
			r.Capability = "watch_fares"
		})
		result, _ := fx.svc.Invoke("book_flight", token, invalid(), InvokeOpts{})
		if got := failureType(t, result); got != core.FailurePurposeMismatch {
			t.Fatalf("failure type = %q, want purpose_mismatch", got)
		}
	})
	t.Run("budget", func(t *testing.T) {
		token := bookToken(t, fx.svc, func(r *core.TokenRequest) {
			r.Budget = &core.Budget{Currency: "USD", MaxAmount: 1}
		})
		result, _ := fx.svc.Invoke("book_flight", token, invalid(), InvokeOpts{})
		if got := failureType(t, result); got != core.FailureBudgetExceeded {
			t.Fatalf("failure type = %q, want budget_exceeded", got)
		}
	})
	t.Run("binding", func(t *testing.T) {
		token := bookToken(t, fx.svc)
		params := invalid()
		delete(params, "quote_id")
		result, _ := fx.svc.Invoke("book_flight", token, params, InvokeOpts{})
		if got := failureType(t, result); got != core.FailureBindingMissing {
			t.Fatalf("failure type = %q, want binding_missing", got)
		}
	})
	if fx.handled.Load() != 0 {
		t.Fatal("a handler ran")
	}
}

// §6.3: "before an approval_grant is validated or reserved — a continuation
// with invalid parameters does not spend its grant".
func TestInvalidContinuationDoesNotSpendTheGrant(t *testing.T) {
	fx := newValidationService(t, nil)
	token := bookToken(t, fx.svc)
	approved := bookParams()
	approved["passengers"] = float64(5)

	result, err := fx.svc.Invoke("book_flight", token, approved, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if got := failureType(t, result); got != FailureApprovalRequired {
		t.Fatalf("failure type = %q, want approval_required", got)
	}
	meta := result["failure"].(map[string]any)["approval_required"].(*core.ApprovalRequiredMetadata)
	grant, err := fx.svc.IssueApprovalGrant(meta.ApprovalRequestID, core.GrantTypeOneTime,
		map[string]any{"subject": "human:approver"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	handledBefore := fx.handled.Load()

	invalid := bookParams()
	invalid["passengers"] = float64(5)
	invalid["flight_number"] = 12345
	result, err = fx.svc.Invoke("book_flight", token, invalid, InvokeOpts{ApprovalGrant: grant.GrantID, ApprovalGrantSupplied: true})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	assertInvalidParameters(t, result, "book_flight has invalid input(s): 'flight_number' must be string, got number")
	if fx.handled.Load() != handledBefore {
		t.Fatal("the handler ran for a refused continuation")
	}
	stored, err := fx.svc.storage.GetGrant(grant.GrantID)
	if err != nil || stored == nil {
		t.Fatalf("GetGrant: %v %v", stored, err)
	}
	if stored.UseCount != 0 {
		t.Fatalf("the refused continuation spent the grant: use_count=%d", stored.UseCount)
	}

	result, err = fx.svc.Invoke("book_flight", token, approved, InvokeOpts{ApprovalGrant: grant.GrantID, ApprovalGrantSupplied: true})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if result["success"] != true {
		t.Fatalf("the grant should still be usable after the refused attempt, got %#v", result)
	}
}

// A call that would have asked for approval is refused before the handler:
// no ApprovalRequest is created.
func TestInvalidCallCreatesNoApprovalRequest(t *testing.T) {
	fx := newValidationService(t, nil)
	token := bookToken(t, fx.svc)
	params := bookParams()
	params["passengers"] = float64(5)
	params["flight_number"] = 12345

	result, err := fx.svc.Invoke("book_flight", token, params, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	failure := assertInvalidParameters(t, result, "book_flight has invalid input(s): 'flight_number' must be string, got number")
	if _, has := failure["approval_required"]; has {
		t.Fatalf("a refused call carries approval metadata: %#v", failure)
	}
	audit, err := fx.svc.QueryAudit(token, server.AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	for _, entry := range audit.Entries {
		if entry.ApprovalRequestID != "" || entry.EntryType == "approval_request_created" {
			t.Fatalf("an approval request was created: %#v", entry)
		}
	}
}

// --- Streaming ------------------------------------------------------------

func watchToken(t *testing.T, svc *Service) *core.DelegationToken {
	t.Helper()
	return issueResolvedToken(t, svc, func(r *core.TokenRequest) {
		r.Scope = []string{"travel.search"}
		r.Capability = "watch_fares"
	})
}

func TestInvokeStreamRefusesInvalidParameters(t *testing.T) {
	fx := newValidationService(t, nil)
	token := watchToken(t, fx.svc)

	cases := []struct {
		name   string
		params map[string]any
		detail string
	}{
		{"missing", map[string]any{}, "watch_fares is missing required input(s): route"},
		{"nil parameters", nil, "watch_fares is missing required input(s): route"},
		{"wrong type", map[string]any{"route": "SEA-SFO", "limit": "ten"},
			"watch_fares has invalid input(s): 'limit' must be integer, got string"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			sr, err := fx.svc.InvokeStream("watch_fares", token, tc.params, InvokeOpts{Stream: true, ClientReferenceID: "ref-" + tc.name})
			if sr != nil {
				t.Fatal("a stream was opened for a refused invocation")
			}
			anipErr, ok := err.(*core.ANIPError)
			if !ok {
				t.Fatalf("expected *core.ANIPError, got %T: %v", err, err)
			}
			want := &core.ANIPError{
				ErrorType: core.FailureInvalidParameters,
				Detail:    tc.detail,
				Resolution: &core.Resolution{
					Action:        "retry_now",
					RecoveryClass: "retry_now",
					Requires:      "parameters that match the capability's declared inputs",
				},
				Retry: false,
			}
			if !reflect.DeepEqual(anipErr, want) {
				t.Fatalf("error =\n  %#v\nwant\n  %#v", anipErr, want)
			}
			audit, err := fx.svc.QueryAudit(token, server.AuditFilters{ClientReferenceID: "ref-" + tc.name})
			if err != nil {
				t.Fatalf("QueryAudit: %v", err)
			}
			if len(audit.Entries) != 1 {
				t.Fatalf("expected one audit entry, got %d", len(audit.Entries))
			}
			if e := audit.Entries[0]; e.Success || e.FailureType != core.FailureInvalidParameters || e.InvocationID == "" {
				t.Fatalf("unexpected audit entry: %#v", e)
			}
		})
	}
	if fx.streamed.Load() != 0 {
		t.Fatal("the streaming handler ran for a refused invocation")
	}
}

func TestInvokeStreamAcceptsValidParameters(t *testing.T) {
	fx := newValidationService(t, nil)
	token := watchToken(t, fx.svc)

	sr, err := fx.svc.InvokeStream("watch_fares", token, map[string]any{"route": "SEA-SFO", "limit": 10.0}, InvokeOpts{Stream: true})
	if err != nil {
		t.Fatalf("InvokeStream: %v", err)
	}
	var last StreamEvent
	for event := range sr.Events {
		last = event
	}
	if last.Type != "completed" {
		t.Fatalf("terminal event = %q, want completed: %#v", last.Type, last.Payload)
	}
}

// The streaming path validates parameters before the grant too.
func TestInvokeStreamInvalidParametersDoNotSpendTheGrant(t *testing.T) {
	fx := newValidationService(t, nil)
	token := watchToken(t, fx.svc)

	// An unknown grant with valid parameters is a grant failure ...
	_, err := fx.svc.InvokeStream("watch_fares", token, map[string]any{"route": "SEA-SFO"},
		InvokeOpts{Stream: true, ApprovalGrant: "grant_000000000000", ApprovalGrantSupplied: true})
	if anipErr, _ := err.(*core.ANIPError); anipErr == nil || anipErr.ErrorType != FailureGrantNotFound {
		t.Fatalf("control: expected grant_not_found, got %v", err)
	}
	// ... and with invalid parameters the parameters are reported first.
	_, err = fx.svc.InvokeStream("watch_fares", token, map[string]any{"route": 7},
		InvokeOpts{Stream: true, ApprovalGrant: "grant_000000000000", ApprovalGrantSupplied: true})
	if anipErr, _ := err.(*core.ANIPError); anipErr == nil || anipErr.ErrorType != core.FailureInvalidParameters {
		t.Fatalf("expected invalid_parameters before grant validation, got %v", err)
	}
}

// --- Composition ----------------------------------------------------------

// §6.3: a composed capability is checked before any child step, and each
// child step is checked against the child's declared inputs.
func TestCompositionValidatesParentAndChildInputs(t *testing.T) {
	var selectRuns, enrichRuns atomic.Int32
	selectDecl := atomicDecl("select_cap", []string{"items"})
	selectDecl.Inputs = []core.CapabilityInput{{Name: "q", Type: "string", Required: true}}
	enrichDecl := atomicDecl("enrich_cap", []string{"count", "items"})
	enrichDecl.Inputs = []core.CapabilityInput{{Name: "items", Type: "array", Required: true}}
	parentDecl := composedDecl("summary", basicComposition())
	parentDecl.Inputs = []core.CapabilityInput{{Name: "q", Type: "string", Required: true}}

	selectOutput := map[string]any{"items": []any{"a", "b"}}
	svc := New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{
			{Declaration: *selectDecl, Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				selectRuns.Add(1)
				return selectOutput, nil
			}},
			{Declaration: *enrichDecl, Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				enrichRuns.Add(1)
				return map[string]any{"count": 2, "items": params["items"]}, nil
			}},
			{Declaration: *parentDecl},
		},
		Storage: ":memory:",
		Trust:   "signed",
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer svc.Shutdown()
	token := issueBoundToken(t, svc, "summary", []string{"s"})

	// Control: valid input runs both children.
	result, err := svc.Invoke("summary", token, map[string]any{"q": "hello"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if result["success"] != true {
		t.Fatalf("control: expected success, got %#v", result)
	}
	if selectRuns.Load() != 1 || enrichRuns.Load() != 1 {
		t.Fatalf("control: children ran %d/%d times, want 1/1", selectRuns.Load(), enrichRuns.Load())
	}

	// Parent input of the wrong type: refused before any child step.
	result, err = svc.Invoke("summary", token, map[string]any{"q": 42}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	assertInvalidParameters(t, result, "summary has invalid input(s): 'q' must be string, got number")
	if selectRuns.Load() != 1 || enrichRuns.Load() != 1 {
		t.Fatalf("a child step ran for a refused parent: %d/%d", selectRuns.Load(), enrichRuns.Load())
	}

	// The first child now hands the second a string where an array is
	// declared: the second child is refused and does not run.
	selectOutput = map[string]any{"items": "not-an-array"}
	result, err = svc.Invoke("summary", token, map[string]any{"q": "hello"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if result["success"] != false {
		t.Fatalf("expected the composition to fail, got %#v", result)
	}
	if selectRuns.Load() != 2 || enrichRuns.Load() != 1 {
		t.Fatalf("children ran %d/%d times, want 2/1 (second child refused)", selectRuns.Load(), enrichRuns.Load())
	}
	audit, err := svc.QueryAudit(token, server.AuditFilters{Capability: "enrich_cap"})
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	refused := 0
	for _, entry := range audit.Entries {
		if !entry.Success && entry.FailureType == core.FailureInvalidParameters {
			refused++
		}
	}
	if refused != 1 {
		t.Fatalf("expected one invalid_parameters audit entry for the child step, got %d (%#v)", refused, audit.Entries)
	}
}

// --- invalid_parameters raised by a handler --------------------------------

// A handler that refuses a domain-typed value with invalid_parameters and
// names no resolution gets the same recovery guidance as the runtime check:
// correct the request and send it again.
func TestHandlerRaisedInvalidParametersGetsRetryNowResolution(t *testing.T) {
	refuse := func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
		return nil, core.NewANIPError(core.FailureInvalidParameters, "date must be YYYY-MM-DD")
	}
	decl := func(name string) core.CapabilityDeclaration {
		return core.CapabilityDeclaration{
			Name:          name,
			Inputs:        []core.CapabilityInput{{Name: "date", Type: "date", Required: true}},
			Output:        core.CapabilityOutput{Type: "object", Fields: []string{}},
			SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
			MinimumScope:  []string{"travel.search"},
			ResponseModes: []string{"unary", "streaming"},
		}
	}
	svc := New(Config{
		ServiceID:    "test-service",
		Capabilities: []CapabilityDef{{Declaration: decl("check_date"), Handler: refuse}},
		Storage:      ":memory:",
		Trust:        "signed",
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer svc.Shutdown()
	token := issueResolvedToken(t, svc, func(r *core.TokenRequest) {
		r.Scope = []string{"travel.search"}
		r.Capability = "check_date"
	})

	result, err := svc.Invoke("check_date", token, map[string]any{"date": "tomorrow"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	failure, _ := result["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters || failure["detail"] != "date must be YYYY-MM-DD" {
		t.Fatalf("unexpected failure: %#v", failure)
	}
	// With the default resolution the failure is the runtime's own
	// invalid_parameters: the same resolution, and retry stated and false.
	want := map[string]any{
		"action":         "retry_now",
		"recovery_class": "retry_now",
		"requires":       "parameters that match the capability's declared inputs",
	}
	if !reflect.DeepEqual(failure["resolution"], want) {
		t.Fatalf("resolution = %#v, want %#v", failure["resolution"], want)
	}
	if retry, stated := failure["retry"]; !stated || retry != false {
		t.Fatalf("retry = %#v (stated %v), want false", retry, stated)
	}

	sr, err := svc.InvokeStream("check_date", token, map[string]any{"date": "tomorrow"}, InvokeOpts{Stream: true})
	if err != nil {
		t.Fatalf("InvokeStream: %v", err)
	}
	var last StreamEvent
	for event := range sr.Events {
		last = event
	}
	streamed, _ := last.Payload["failure"].(map[string]any)
	if last.Type != "failed" || streamed["type"] != core.FailureInvalidParameters {
		t.Fatalf("expected a failed event with invalid_parameters, got %q %#v", last.Type, last.Payload)
	}
	resolution, _ := streamed["resolution"].(*core.Resolution)
	if resolution == nil || resolution.Action != "retry_now" || resolution.RecoveryClass != "retry_now" ||
		resolution.Requires != "parameters that match the capability's declared inputs" {
		t.Fatalf("streamed resolution = %#v, want the retry_now resolution", streamed["resolution"])
	}
	if streamed["retry"] != false {
		t.Fatalf("streamed retry = %#v, want false", streamed["retry"])
	}
}

// A handler that names its own resolution and retry keeps them.
func TestHandlerRaisedInvalidParametersKeepsItsOwnResolution(t *testing.T) {
	svc := New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:          "check_date",
				Inputs:        []core.CapabilityInput{{Name: "date", Type: "date", Required: true}},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"travel.search"},
				ResponseModes: []string{"unary"},
			},
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				return nil, core.NewANIPError(core.FailureInvalidParameters, "the fare table is being reloaded").
					WithResolution("wait_and_retry").WithRetry()
			},
		}},
		Storage: ":memory:",
		Trust:   "signed",
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer svc.Shutdown()
	token := issueResolvedToken(t, svc, func(r *core.TokenRequest) {
		r.Scope = []string{"travel.search"}
		r.Capability = "check_date"
	})

	result, err := svc.Invoke("check_date", token, map[string]any{"date": "2026-03-10"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	failure, _ := result["failure"].(map[string]any)
	want := map[string]any{"action": "wait_and_retry", "recovery_class": "wait_then_retry"}
	if failure["type"] != core.FailureInvalidParameters || !reflect.DeepEqual(failure["resolution"], want) {
		t.Fatalf("the handler's resolution was replaced: %#v", failure)
	}
	if retry, stated := failure["retry"]; stated && retry == false {
		t.Fatalf("the handler said the failure is retryable, the response says retry=false: %#v", failure)
	}
}

// --- Inputs that declare resolution.on_missing (SPEC.md §6.3 exception, §4.10) ---

func onMissing(behavior core.ResolutionBehavior) *core.InputResolution {
	return &core.InputResolution{Mode: core.ResolutionModeClarify, OnMissing: &behavior}
}

func onMissingDecl() *core.CapabilityDeclaration {
	deny := core.ResolutionBehaviorDeny
	return &core.CapabilityDeclaration{
		Name: "region_report",
		Inputs: []core.CapabilityInput{
			// Says what happens when the value is absent: left to the service.
			{Name: "region", Type: "string", Required: true, Resolution: onMissing(core.ResolutionBehaviorClarify)},
			// A resolution block that does not set on_missing: still required.
			{Name: "quarter", Type: "string", Required: true, Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify, OnUnresolved: &deny}},
			// No resolution block: still required.
			{Name: "currency", Type: "string", Required: true},
			{Name: "limit", Type: "integer", Required: true, Default: 10, Resolution: onMissing(core.ResolutionBehaviorUseDefault)},
		},
	}
}

func TestValidateDeclaredInputsLeavesOnMissingInputsToTheService(t *testing.T) {
	accepted := map[string]map[string]any{
		"on_missing inputs absent": {"quarter": "Q1", "currency": "USD"},
		"on_missing inputs null":   {"region": nil, "limit": nil, "quarter": "Q1", "currency": "USD"},
		"all supplied":             {"region": "eu", "limit": 5.0, "quarter": "Q1", "currency": "USD"},
	}
	for name, params := range accepted {
		t.Run(name, func(t *testing.T) {
			if err := validateDeclaredInputs("region_report", onMissingDecl(), params); err != nil {
				t.Fatalf("expected the parameters to be accepted, got %v", err)
			}
		})
	}

	refused := []struct {
		name   string
		params map[string]any
		detail string
	}{
		{"resolution without on_missing is still required", map[string]any{"currency": "USD"},
			"region_report is missing required input(s): quarter"},
		{"no resolution is still required", map[string]any{"quarter": "Q1"},
			"region_report is missing required input(s): currency"},
		{"only the inputs without on_missing are named", map[string]any{},
			"region_report is missing required input(s): quarter, currency"},
		{"a supplied on_missing value is type-checked", map[string]any{"region": 7, "limit": "ten", "quarter": "Q1", "currency": "USD"},
			"region_report has invalid input(s): 'region' must be string, got number; 'limit' must be integer, got string"},
	}
	for _, tc := range refused {
		t.Run(tc.name, func(t *testing.T) {
			err := validateDeclaredInputs("region_report", onMissingDecl(), tc.params)
			if err == nil || err.ErrorType != core.FailureInvalidParameters || err.Detail != tc.detail {
				t.Fatalf("got %v, want invalid_parameters %q", err, tc.detail)
			}
		})
	}
}

// Every one of the seven on_missing values exempts the input; a nil
// on_missing does not.
func TestValidateDeclaredInputsEveryOnMissingValue(t *testing.T) {
	behaviors := []core.ResolutionBehavior{
		core.ResolutionBehaviorClarify, core.ResolutionBehaviorUseDefault, core.ResolutionBehaviorUseActorScope,
		core.ResolutionBehaviorAppSelectOrClarify, core.ResolutionBehaviorDeny, core.ResolutionBehaviorDenyOrClarify,
		core.ResolutionBehaviorOmit,
	}
	for _, behavior := range behaviors {
		decl := &core.CapabilityDeclaration{Name: "cap", Inputs: []core.CapabilityInput{
			{Name: "scope", Type: "string", Required: true, Default: "all", Resolution: onMissing(behavior)},
		}}
		if err := validateDeclaredInputs("cap", decl, map[string]any{}); err != nil {
			t.Errorf("on_missing=%s: expected the call to go on to the handler, got %v", behavior, err)
		}
	}
	decl := &core.CapabilityDeclaration{Name: "cap", Inputs: []core.CapabilityInput{
		{Name: "scope", Type: "string", Required: true, Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify}},
	}}
	if err := validateDeclaredInputs("cap", decl, map[string]any{}); err == nil {
		t.Error("a resolution block without on_missing must leave the input required")
	}
}

// Through the pipeline, unary and streaming: the handler runs and sees the
// parameters as sent, and implements the on_missing path itself.
func TestOnMissingInputReachesTheHandler(t *testing.T) {
	var seen []map[string]any
	decl := core.CapabilityDeclaration{
		Name:        "region_report",
		Description: "Report for a region",
		Inputs: []core.CapabilityInput{
			{Name: "region", Type: "string", Required: true, Resolution: onMissing(core.ResolutionBehaviorClarify)},
			{Name: "quarter", Type: "string", Required: true, Resolution: &core.InputResolution{Mode: core.ResolutionModeClarify}},
			{Name: "currency", Type: "string", Required: true},
		},
		Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
		SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope:  []string{"report"},
		ResponseModes: []string{"unary", "streaming"},
	}
	svc := New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{{Declaration: decl, Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
			seen = append(seen, params)
			if _, ok := params["region"]; !ok {
				return nil, core.NewANIPError("clarification_required", "which region?").WithResolution("obtain_binding")
			}
			return map[string]any{"ok": true}, nil
		}}},
		Storage: ":memory:",
		Trust:   "signed",
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer svc.Shutdown()
	token := issueResolvedToken(t, svc, func(r *core.TokenRequest) {
		r.Scope = []string{"report"}
		r.Capability = "region_report"
	})

	// Unary: the handler answers through its own on_missing path.
	result, err := svc.Invoke("region_report", token, map[string]any{"quarter": "Q1", "currency": "USD"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if got := failureType(t, result); got != "clarification_required" {
		t.Fatalf("failure type = %q, want the handler's clarification_required (%#v)", got, result)
	}
	if len(seen) != 1 || len(seen[0]) != 2 {
		t.Fatalf("the handler should have run once with the parameters as sent, saw %#v", seen)
	}

	// The same input without on_missing, and one without a resolution, are refused.
	result, _ = svc.Invoke("region_report", token, map[string]any{"region": "eu", "currency": "USD"}, InvokeOpts{})
	assertInvalidParameters(t, result, "region_report is missing required input(s): quarter")
	result, _ = svc.Invoke("region_report", token, map[string]any{"region": "eu", "quarter": "Q1"}, InvokeOpts{})
	assertInvalidParameters(t, result, "region_report is missing required input(s): currency")
	// A wrong-typed value for the on_missing input is refused.
	result, _ = svc.Invoke("region_report", token, map[string]any{"region": []any{"eu"}, "quarter": "Q1", "currency": "USD"}, InvokeOpts{})
	assertInvalidParameters(t, result, "region_report has invalid input(s): 'region' must be string, got array")
	if len(seen) != 1 {
		t.Fatalf("the handler ran for a refused invocation: %#v", seen)
	}

	// Streaming: same rule.
	sr, err := svc.InvokeStream("region_report", token, map[string]any{"quarter": "Q1", "currency": "USD"}, InvokeOpts{Stream: true})
	if err != nil {
		t.Fatalf("InvokeStream: %v", err)
	}
	var last StreamEvent
	for event := range sr.Events {
		last = event
	}
	if failure, _ := last.Payload["failure"].(map[string]any); last.Type != "failed" || failure["type"] != "clarification_required" {
		t.Fatalf("expected the handler's clarification_required on the stream, got %q %#v", last.Type, last.Payload)
	}
	if len(seen) != 2 {
		t.Fatalf("the streaming handler should have run once, saw %#v", seen)
	}
	if _, err := svc.InvokeStream("region_report", token, map[string]any{"currency": "USD"}, InvokeOpts{Stream: true}); err == nil {
		t.Fatal("a missing input without on_missing must still be refused on the streaming path")
	}
}
