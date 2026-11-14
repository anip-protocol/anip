// The streaming path runs the unary pre-handler checks (SPEC.md §6.3: the
// checks are "the same ... for unary and streaming invocations"). Each case
// sends the same request through Invoke and through InvokeStream, against a
// capability that supports both response modes, and compares the answers.

package service

import (
	"fmt"
	"reflect"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

type streamParityFixture struct {
	svc     *Service
	handled *atomic.Int32
}

// newStreamParityService registers stream_book (estimated cost, a quote
// binding with max_age, a grant policy) and stream_capped (a cost_ceiling
// control requirement). Both support unary and streaming.
func newStreamParityService(t *testing.T, hooks *ObservabilityHooks) streamParityFixture {
	t.Helper()
	handled := &atomic.Int32{}
	handler := func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
		handled.Add(1)
		return map[string]any{"ok": true}, nil
	}
	book := core.CapabilityDeclaration{
		Name:        "stream_book",
		Description: "Book with streamed progress",
		Inputs: []core.CapabilityInput{
			{Name: "flight_number", Type: "string", Required: true},
			{Name: "quote_id", Type: "object", Required: false},
		},
		Output:       core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
		SideEffect:   core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
		MinimumScope: []string{"travel.book"},
		Cost: &core.Cost{
			Certainty: "estimated",
			Financial: &core.FinancialCost{Currency: "USD"},
		},
		RequiresBinding: []core.BindingRequirement{{Type: "quote", Field: "quote_id", SourceCapability: "search_flights", MaxAge: "PT15M"}},
		ResponseModes:   []string{"unary", "streaming"},
		GrantPolicy:     defaultGrantPolicy(),
	}
	capped := core.CapabilityDeclaration{
		Name:                "stream_capped",
		Description:         "Needs a budget",
		Inputs:              []core.CapabilityInput{{Name: "flight_number", Type: "string", Required: true}},
		Output:              core.CapabilityOutput{Type: "object", Fields: []string{"ok"}},
		SideEffect:          core.SideEffect{Type: "write", RollbackWindow: "PT1H"},
		MinimumScope:        []string{"travel.book"},
		ControlRequirements: []core.ControlRequirement{{Type: "cost_ceiling", Enforcement: "reject"}},
		ResponseModes:       []string{"unary", "streaming"},
	}
	svc := New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{
			{Declaration: book, Handler: handler},
			{Declaration: capped, Handler: handler},
		},
		Storage: ":memory:",
		Trust:   "signed",
		Hooks:   hooks,
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	return streamParityFixture{svc: svc, handled: handled}
}

func streamBookParams() map[string]any {
	return map[string]any{
		"flight_number": "AA100",
		"quote_id":      map[string]any{"id": "qt-1", "price": float64(420), "issued_at": float64(time.Now().Unix())},
	}
}

type streamParityCase struct {
	row        int
	name       string
	capability string
	want       string
	token      func(t *testing.T, svc *Service) *core.DelegationToken
	params     func() map[string]any
	opts       InvokeOpts
	audited    bool // the unary path writes an audit entry for this refusal
}

func streamParityCases() []streamParityCase {
	tokenFor := func(capability string, scope []string, budget *core.Budget) func(*testing.T, *Service) *core.DelegationToken {
		return func(t *testing.T, svc *Service) *core.DelegationToken {
			return issueResolvedToken(t, svc, func(r *core.TokenRequest) {
				r.Scope = scope
				r.Capability = capability
				r.Budget = budget
			})
		}
	}
	bookToken := tokenFor("stream_book", []string{"travel.book"}, nil)
	without := func(field string) func() map[string]any {
		return func() map[string]any {
			p := streamBookParams()
			delete(p, field)
			return p
		}
	}
	return []streamParityCase{
		{row: 1, name: "budget exceeded", capability: "stream_book", want: core.FailureBudgetExceeded,
			token:  tokenFor("stream_book", []string{"travel.book"}, &core.Budget{Currency: "USD", MaxAmount: 1}),
			params: streamBookParams, audited: true},
		{row: 2, name: "budget_not_enforceable", capability: "stream_book", want: core.FailureBudgetNotEnforceable,
			token: tokenFor("stream_book", []string{"travel.book"}, &core.Budget{Currency: "USD", MaxAmount: 100000}),
			params: func() map[string]any {
				p := streamBookParams()
				delete(p["quote_id"].(map[string]any), "price")
				return p
			}, audited: true},
		{row: 3, name: "binding_missing", capability: "stream_book", want: core.FailureBindingMissing,
			token: bookToken, params: without("quote_id"), audited: true},
		{row: 4, name: "binding_stale", capability: "stream_book", want: core.FailureBindingStale,
			token: bookToken,
			params: func() map[string]any {
				p := streamBookParams()
				p["quote_id"].(map[string]any)["issued_at"] = float64(time.Now().Add(-400 * 24 * time.Hour).Unix())
				return p
			}, audited: true},
		{row: 5, name: "control requirement unsatisfied", capability: "stream_capped", want: core.FailureControlRequirementUnsatisfied,
			token:  tokenFor("stream_capped", []string{"travel.book"}, nil),
			params: func() map[string]any { return map[string]any{"flight_number": "AA100"} }, audited: true},
		{row: 6, name: "purpose mismatch", capability: "stream_book", want: core.FailurePurposeMismatch,
			token:  tokenFor("stream_capped", []string{"travel.book"}, nil),
			params: streamBookParams, audited: true},
		{row: 7, name: "insufficient scope", capability: "stream_book", want: core.FailureScopeInsufficient,
			token:  tokenFor("stream_book", []string{"travel.search"}, nil),
			params: streamBookParams, audited: true},
		{row: 8, name: "blank approval grant", capability: "stream_book", want: FailureGrantNotFound,
			token: bookToken, params: streamBookParams,
			opts: InvokeOpts{ApprovalGrant: "", ApprovalGrantSupplied: true}, audited: true},
		{row: 9, name: "unknown approval grant", capability: "stream_book", want: FailureGrantNotFound,
			token: bookToken, params: streamBookParams,
			opts: InvokeOpts{ApprovalGrant: "grant_000000000000", ApprovalGrantSupplied: true}, audited: true},
		{row: 10, name: "parameter validation", capability: "stream_book", want: core.FailureInvalidParameters,
			token: bookToken, params: without("flight_number"), audited: true},
	}
}

// streamOutcome describes what InvokeStream did with a request.
func streamOutcome(t *testing.T, fx streamParityFixture, tc streamParityCase, token *core.DelegationToken, clientRef string) (failure *core.ANIPError, description string) {
	t.Helper()
	before := fx.handled.Load()
	opts := tc.opts
	opts.Stream = true
	opts.ClientReferenceID = clientRef
	sr, err := fx.svc.InvokeStream(tc.capability, token, tc.params(), opts)
	if err != nil {
		anipErr, ok := err.(*core.ANIPError)
		if !ok {
			return nil, fmt.Sprintf("error that is not an ANIP failure: %v", err)
		}
		if fx.handled.Load() != before {
			return anipErr, "refused with " + anipErr.ErrorType + " but the handler ran"
		}
		return anipErr, "refused with " + anipErr.ErrorType
	}
	var last StreamEvent
	for event := range sr.Events {
		last = event
	}
	if fx.handled.Load() != before {
		return nil, "handler ran (stream ended with a " + last.Type + " event)"
	}
	return nil, "stream opened, terminal event " + last.Type + ", handler did not run"
}

func TestStreamingRunsTheUnaryPreHandlerChecks(t *testing.T) {
	fx := newStreamParityService(t, nil)

	// Control: the request each case is derived from succeeds on both paths.
	control := issueResolvedToken(t, fx.svc, func(r *core.TokenRequest) {
		r.Scope = []string{"travel.book"}
		r.Capability = "stream_book"
	})
	if result, _ := fx.svc.Invoke("stream_book", control, streamBookParams(), InvokeOpts{}); result["success"] != true {
		t.Fatalf("control (unary): %#v", result)
	}
	if _, outcome := streamOutcome(t, fx, streamParityCase{capability: "stream_book", params: streamBookParams}, control, "control"); outcome != "handler ran (stream ended with a completed event)" {
		t.Fatalf("control (streaming): %s", outcome)
	}

	for _, tc := range streamParityCases() {
		t.Run(fmt.Sprintf("%02d %s", tc.row, tc.name), func(t *testing.T) {
			token := tc.token(t, fx.svc)
			handledBefore := fx.handled.Load()

			// Unary: the reference answer.
			unaryOpts := tc.opts
			unaryOpts.ClientReferenceID = fmt.Sprintf("unary-%d", tc.row)
			unary, err := fx.svc.Invoke(tc.capability, token, tc.params(), unaryOpts)
			if err != nil {
				t.Fatalf("Invoke: %v", err)
			}
			unaryType := failureType(t, unary)
			if unaryType != tc.want {
				t.Fatalf("unary answered %q, the case means to provoke %q", unaryType, tc.want)
			}
			unaryFailure := unary["failure"].(map[string]any)
			unaryAudit, _ := fx.svc.QueryAudit(token, server.AuditFilters{ClientReferenceID: unaryOpts.ClientReferenceID})
			if (len(unaryAudit.Entries) == 1) != tc.audited {
				t.Fatalf("unary wrote %d audit entries; the case says audited=%v", len(unaryAudit.Entries), tc.audited)
			}

			// Streaming: the same request.
			streamRef := fmt.Sprintf("stream-%d", tc.row)
			failure, outcome := streamOutcome(t, fx, tc, token, streamRef)
			t.Logf("row %d | %s | unary: %s | streaming: %s", tc.row, tc.name, unaryType, outcome)
			if failure == nil || failure.ErrorType != unaryType {
				t.Fatalf("streaming: %s; unary refuses the same request with %s", outcome, unaryType)
			}
			if fx.handled.Load() != handledBefore {
				t.Fatalf("the handler ran (streaming: %s)", outcome)
			}

			// The same failure object, as far as an error value carries it.
			if failure.Detail != unaryFailure["detail"] {
				t.Errorf("detail differs: streaming %q, unary %q", failure.Detail, unaryFailure["detail"])
			}
			if unaryResolution, ok := unaryFailure["resolution"].(map[string]any); ok {
				if failure.Resolution == nil || failure.Resolution.Action != unaryResolution["action"] ||
					failure.Resolution.RecoveryClass != unaryResolution["recovery_class"] {
					t.Errorf("resolution differs: streaming %#v, unary %#v", failure.Resolution, unaryResolution)
				}
				if requires, _ := unaryResolution["requires"].(string); failure.Resolution != nil && failure.Resolution.Requires != requires {
					t.Errorf("resolution.requires differs: streaming %q, unary %q", failure.Resolution.Requires, requires)
				}
			} else if failure.Resolution != nil {
				t.Errorf("streaming carries a resolution the unary failure does not: %#v", failure.Resolution)
			}

			// Audited where the unary refusal is audited, with the same entry.
			streamAudit, err := fx.svc.QueryAudit(token, server.AuditFilters{ClientReferenceID: streamRef})
			if err != nil {
				t.Fatalf("QueryAudit: %v", err)
			}
			if tc.audited {
				if len(streamAudit.Entries) != 1 {
					t.Fatalf("streaming wrote %d audit entries, unary wrote 1", len(streamAudit.Entries))
				}
				got, want := streamAudit.Entries[0], unaryAudit.Entries[0]
				if got.Success || got.FailureType != want.FailureType || got.Capability != want.Capability ||
					got.ApprovalGrantID != want.ApprovalGrantID || got.InvocationID == "" {
					t.Fatalf("audit entries differ:\n  streaming %#v\n  unary     %#v", got, want)
				}
			} else if len(streamAudit.Entries) != 0 {
				t.Fatalf("streaming wrote %d audit entries, unary wrote none", len(streamAudit.Entries))
			}
		})
	}
}

// No grant is reserved by a streaming call that an earlier check refuses.
func TestStreamingRefusalDoesNotReserveTheGrant(t *testing.T) {
	fx := newStreamParityService(t, nil)
	token := issueResolvedToken(t, fx.svc, func(r *core.TokenRequest) {
		r.Scope = []string{"travel.book"}
		r.Capability = "stream_book"
	})
	// A real, usable grant for exactly these parameters.
	approved := streamBookParams()
	decl := fx.svc.capabilities["stream_book"].Declaration
	meta, _, err := MaterializeApprovalRequest(fx.svc.storage, &decl,
		"inv-000000000000", map[string]any{"subject": token.Subject, "root_principal": token.RootPrincipal}, approved, nil, nil)
	if err != nil {
		t.Fatalf("MaterializeApprovalRequest: %v", err)
	}
	grant, err := fx.svc.IssueApprovalGrant(meta.ApprovalRequestID, core.GrantTypeOneTime,
		map[string]any{"subject": "human:approver"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	useCount := func() int {
		stored, err := fx.svc.storage.GetGrant(grant.GrantID)
		if err != nil || stored == nil {
			t.Fatalf("GetGrant: %v %v", stored, err)
		}
		return stored.UseCount
	}

	// The binding is missing: refused before the grant is looked at.
	missingBinding := map[string]any{"flight_number": approved["flight_number"]}
	_, err = fx.svc.InvokeStream("stream_book", token, missingBinding,
		InvokeOpts{Stream: true, ApprovalGrant: grant.GrantID, ApprovalGrantSupplied: true})
	if anipErr, _ := err.(*core.ANIPError); anipErr == nil || anipErr.ErrorType != core.FailureBindingMissing {
		t.Fatalf("expected binding_missing, got %v", err)
	}
	if useCount() != 0 {
		t.Fatalf("a refused streaming call reserved the grant: use_count=%d", useCount())
	}

	// With the approved parameters the grant is still usable, once.
	sr, err := fx.svc.InvokeStream("stream_book", token, approved,
		InvokeOpts{Stream: true, ApprovalGrant: grant.GrantID, ApprovalGrantSupplied: true})
	if err != nil {
		t.Fatalf("the grant should still be usable: %v", err)
	}
	for range sr.Events {
	}
	if useCount() != 1 {
		t.Fatalf("use_count = %d after the continuation, want 1", useCount())
	}
}

// Both paths fire the same observability hooks for a refusal and for a
// completed invocation.
func TestStreamingFiresTheUnaryHooks(t *testing.T) {
	type call struct {
		Hook    string
		Success bool
	}
	var mu sync.Mutex
	var calls []call
	add := func(c call) {
		mu.Lock()
		defer mu.Unlock()
		calls = append(calls, c)
	}
	hooks := &ObservabilityHooks{
		OnInvokeStart: func(invocationID, capability, subject string) {
			add(call{Hook: "start"})
		},
		OnScopeValidation: func(capability string, granted bool) {
			add(call{Hook: "scope", Success: granted})
		},
		OnInvokeComplete: func(invocationID, capability string, success bool, durationMs int64) {
			add(call{Hook: "complete", Success: success})
		},
	}
	fx := newStreamParityService(t, hooks)
	token := issueResolvedToken(t, fx.svc, func(r *core.TokenRequest) {
		r.Scope = []string{"travel.book"}
		r.Capability = "stream_book"
	})
	record := func(run func()) []call {
		mu.Lock()
		calls = nil
		mu.Unlock()
		run()
		mu.Lock()
		defer mu.Unlock()
		return append([]call(nil), calls...)
	}
	stream := func(params map[string]any) {
		sr, err := fx.svc.InvokeStream("stream_book", token, params, InvokeOpts{Stream: true})
		if err == nil {
			for range sr.Events {
			}
		}
	}

	refusedParams := map[string]any{"flight_number": "AA100"} // binding_missing
	unaryRefused := record(func() { fx.svc.Invoke("stream_book", token, refusedParams, InvokeOpts{}) })
	streamRefused := record(func() { stream(refusedParams) })
	if !reflect.DeepEqual(streamRefused, unaryRefused) || len(unaryRefused) == 0 {
		t.Fatalf("hooks for a refusal differ:\n  streaming %v\n  unary     %v", streamRefused, unaryRefused)
	}

	unaryDone := record(func() { fx.svc.Invoke("stream_book", token, streamBookParams(), InvokeOpts{}) })
	streamDone := record(func() { stream(streamBookParams()) })
	if !reflect.DeepEqual(streamDone, unaryDone) || len(unaryDone) == 0 {
		t.Fatalf("hooks for a completed invocation differ:\n  streaming %v\n  unary     %v", streamDone, unaryDone)
	}
}
