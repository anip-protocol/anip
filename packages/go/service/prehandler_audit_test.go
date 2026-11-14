package service

import (
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

// SPEC.md §6.3: every refusal made before the handler is audited. Budget,
// binding and control-requirement refusals are recorded like scope,
// purpose and parameter refusals, on unary and streaming invocations.


type prehandlerCase struct {
	name     string
	decl     func(*core.CapabilityDeclaration)
	params   map[string]any
	budget   *core.Budget
	expected string
}

func prehandlerCases() []prehandlerCase {
	now := float64(time.Now().Unix())
	estimated := func(d *core.CapabilityDeclaration) {
		d.Cost = &core.Cost{Certainty: "estimated", Financial: &core.FinancialCost{Currency: "USD", RangeMin: floatPtr(100), RangeMax: floatPtr(500)}}
		d.RequiresBinding = []core.BindingRequirement{{Type: "quote", Field: "quote", MaxAge: "PT15M"}}
	}
	fixed := func(d *core.CapabilityDeclaration) {
		d.Cost = &core.Cost{Certainty: "fixed", Financial: &core.FinancialCost{Currency: "USD", Amount: floatPtr(500)}}
	}
	return []prehandlerCase{
		{"budget_exceeded fixed", fixed, map[string]any{}, &core.Budget{Currency: "USD", MaxAmount: 1}, core.FailureBudgetExceeded},
		{"budget_exceeded bound", estimated, map[string]any{"quote": map[string]any{"price": 420.0, "issued_at": now}}, &core.Budget{Currency: "USD", MaxAmount: 100}, core.FailureBudgetExceeded},
		{"budget_currency_mismatch", fixed, map[string]any{}, &core.Budget{Currency: "EUR", MaxAmount: 1000}, core.FailureBudgetCurrencyMismatch},
		{"budget_not_enforceable", estimated, map[string]any{"quote": map[string]any{"issued_at": now}}, &core.Budget{Currency: "USD", MaxAmount: 1000}, core.FailureBudgetNotEnforceable},
		{"binding_missing", estimated, map[string]any{}, nil, core.FailureBindingMissing},
		{"binding_stale", estimated, map[string]any{"quote": map[string]any{"price": 420.0, "issued_at": now - 86400}}, nil, core.FailureBindingStale},
		{"control requirement", func(d *core.CapabilityDeclaration) {
			d.ControlRequirements = []core.ControlRequirement{{Type: "cost_ceiling", Enforcement: "reject"}}
		}, map[string]any{}, nil, core.FailureControlRequirementUnsatisfied},
	}
}

func newPrehandlerService(t *testing.T, tc prehandlerCase) (*Service, *core.DelegationToken, *int) {
	t.Helper()
	calls := 0
	decl := core.CapabilityDeclaration{
		Name:          "book",
		Description:   "book",
		Inputs:        []core.CapabilityInput{{Name: "quote", Type: "object", Required: false}},
		Output:        core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
		SideEffect:    core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
		MinimumScope:  []string{"book"},
		ResponseModes: []string{"unary", "streaming"},
	}
	tc.decl(&decl)
	svc := New(Config{
		ServiceID: "test-prehandler-audit",
		Capabilities: []CapabilityDef{{
			Declaration: decl,
			Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
				calls++
				return map[string]any{"ok": true}, nil
			},
		}},
		Storage: ":memory:",
		Trust:   "signed",
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject: "human:test@example.com", Scope: []string{"book"}, Capability: "book", TTLHours: 1,
	})
	if err != nil {
		t.Fatalf("IssueToken: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken: %v", err)
	}
	return svc, token, &calls
}

func assertOneRefusalAudited(t *testing.T, svc *Service, token *core.DelegationToken, filters server.AuditFilters, expected string) {
	t.Helper()
	audit, err := svc.QueryAudit(token, filters)
	if err != nil {
		t.Fatalf("QueryAudit: %v", err)
	}
	if len(audit.Entries) != 1 {
		t.Fatalf("expected one audit entry for the %s refusal, got %d", expected, len(audit.Entries))
	}
	e := audit.Entries[0]
	if e.Success || e.FailureType != expected {
		t.Fatalf("audit entry = success %v failure_type %q, want a %s failure", e.Success, e.FailureType, expected)
	}
	if want := ClassifyEvent("irreversible", false, expected); e.EventClass != want {
		t.Fatalf("event_class = %q, want %q", e.EventClass, want)
	}
}

func TestRefusalsBeforeTheHandlerAreAudited(t *testing.T) {
	for _, tc := range prehandlerCases() {
		t.Run(tc.name+"/unary", func(t *testing.T) {
			svc, token, calls := newPrehandlerService(t, tc)
			result, err := svc.Invoke("book", token, tc.params, InvokeOpts{Budget: tc.budget})
			if err != nil {
				t.Fatalf("Invoke: %v", err)
			}
			failure, _ := result["failure"].(map[string]any)
			if result["success"] != false || failure["type"] != tc.expected {
				t.Fatalf("expected %s, got %#v", tc.expected, result)
			}
			if resolution, ok := failure["resolution"].(map[string]any); !ok || resolution["action"] == nil || resolution["recovery_class"] == nil {
				t.Fatalf("the %s failure has no complete resolution: %#v", tc.expected, failure)
			}
			if *calls != 0 {
				t.Fatal("the handler ran")
			}
			assertOneRefusalAudited(t, svc, token, server.AuditFilters{InvocationID: result["invocation_id"].(string)}, tc.expected)
		})
		t.Run(tc.name+"/streaming", func(t *testing.T) {
			svc, token, calls := newPrehandlerService(t, tc)
			sr, err := svc.InvokeStream("book", token, tc.params, InvokeOpts{Budget: tc.budget, Stream: true, ClientReferenceID: "ref-stream"})
			if sr != nil {
				t.Fatal("a stream was opened for a refused invocation")
			}
			anipErr, ok := err.(*core.ANIPError)
			if !ok || anipErr.ErrorType != tc.expected {
				t.Fatalf("expected %s, got %T %v", tc.expected, err, err)
			}
			if *calls != 0 {
				t.Fatal("the handler ran")
			}
			assertOneRefusalAudited(t, svc, token, server.AuditFilters{ClientReferenceID: "ref-stream"}, tc.expected)
		})
	}
}
