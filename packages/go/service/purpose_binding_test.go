// Purpose binding (SPEC.md §3.2 and the security section): a delegation token
// is bound to one capability. "A token issued for book_flight cannot invoke
// search_flights", even when its scope would cover both.
//
// Composed capabilities (§4.6) must still work under that rule: each child
// step runs with its own token, delegated from the caller's token and bound
// to the child capability, and its audit entry links back to the parent
// invocation.

package service

import (
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

func issueBoundToken(t *testing.T, svc *Service, capability string, scope []string) *core.DelegationToken {
	t.Helper()
	resp, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:    "human:test@example.com",
		Scope:      scope,
		Capability: capability,
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	token, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}
	return token
}

func failureType(t *testing.T, result map[string]any) string {
	t.Helper()
	failure, ok := result["failure"].(map[string]any)
	if !ok {
		t.Fatalf("expected a failure object, got %#v", result)
	}
	ft, _ := failure["type"].(string)
	return ft
}

func TestInvokeRejectsTokenBoundToAnotherCapability(t *testing.T) {
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// Scope covers both capabilities; the token is bound to book_flight.
	token := issueBoundToken(t, svc, "book_flight", []string{"travel.search", "travel.book"})

	result, err := svc.Invoke("search_flights", token, map[string]any{
		"origin": "SEA", "destination": "SFO", "date": "2026-03-10",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}
	if result["success"] != false {
		t.Fatalf("expected the invocation to be rejected, got %#v", result)
	}
	if got := failureType(t, result); got != core.FailurePurposeMismatch {
		t.Fatalf("expected failure type %q, got %q", core.FailurePurposeMismatch, got)
	}
	failure := result["failure"].(map[string]any)
	resolution, _ := failure["resolution"].(map[string]any)
	if resolution["action"] != "request_new_delegation" {
		t.Fatalf("expected resolution action request_new_delegation, got %#v", failure["resolution"])
	}

	// The denial is audited against the capability that was attempted.
	audit, err := svc.QueryAudit(token, server.AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit() error: %v", err)
	}
	if len(audit.Entries) != 1 {
		t.Fatalf("expected one audit entry, got %d", len(audit.Entries))
	}
	if e := audit.Entries[0]; e.Capability != "search_flights" || e.Success || e.FailureType != core.FailurePurposeMismatch {
		t.Fatalf("unexpected audit entry: capability=%q success=%v failure_type=%q", e.Capability, e.Success, e.FailureType)
	}
}

func TestInvokeStreamRejectsTokenBoundToAnotherCapability(t *testing.T) {
	svc := newStreamTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// stream_search and stream_fail share the travel.search scope.
	token := issueBoundToken(t, svc, "stream_fail", []string{"travel.search"})

	_, err := svc.InvokeStream("stream_search", token, map[string]any{}, InvokeOpts{Stream: true})
	if err == nil {
		t.Fatal("expected InvokeStream to reject a token bound to another capability")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected *core.ANIPError, got %T: %v", err, err)
	}
	if anipErr.ErrorType != core.FailurePurposeMismatch {
		t.Fatalf("expected failure type %q, got %q", core.FailurePurposeMismatch, anipErr.ErrorType)
	}
}

// newComposedTestService registers two atomic capabilities and one composed
// capability over them. The children record the token each was invoked with.
func newComposedTestService(seen map[string]*core.DelegationToken) *Service {
	selectDecl := atomicDecl("select_cap", []string{"items"})
	selectDecl.Inputs = []core.CapabilityInput{{Name: "q", Type: "string"}}
	enrichDecl := atomicDecl("enrich_cap", []string{"count", "items"})
	enrichDecl.Inputs = []core.CapabilityInput{{Name: "items", Type: "array"}}
	parentDecl := composedDecl("summary", basicComposition())
	parentDecl.Inputs = []core.CapabilityInput{{Name: "q", Type: "string"}}

	return New(Config{
		ServiceID: "test-service",
		Capabilities: []CapabilityDef{
			{
				Declaration: *selectDecl,
				Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
					seen["select_cap"] = ctx.Token
					return map[string]any{"items": []any{"a", "b"}}, nil
				},
			},
			{
				Declaration: *enrichDecl,
				Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
					seen["enrich_cap"] = ctx.Token
					items, _ := params["items"].([]any)
					return map[string]any{"count": len(items), "items": items}, nil
				},
			},
			{Declaration: *parentDecl},
		},
		Storage: ":memory:",
		Trust:   "signed",
		Authenticate: func(bearer string) (string, bool) {
			return "human:test@example.com", bearer == "test-key"
		},
	})
}

func TestComposedInvocationRunsChildrenWithChildBoundTokens(t *testing.T) {
	seen := map[string]*core.DelegationToken{}
	svc := newComposedTestService(seen)
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	token := issueBoundToken(t, svc, "summary", []string{"s"})

	result, err := svc.Invoke("summary", token, map[string]any{"q": "x"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}
	if result["success"] != true {
		t.Fatalf("expected the composed invocation to succeed, got %#v", result)
	}
	out, _ := result["result"].(map[string]any)
	if out["count"] != 2 {
		t.Fatalf("expected count=2 from the enrich step, got %#v", out)
	}
	parentInvocationID, _ := result["invocation_id"].(string)

	// Each child ran with its own token: bound to the child capability and
	// delegated from the caller's token.
	for _, child := range []string{"select_cap", "enrich_cap"} {
		childToken := seen[child]
		if childToken == nil {
			t.Fatalf("child %s was not invoked", child)
		}
		if childToken.Purpose.Capability != child {
			t.Errorf("child %s ran with a token bound to %q", child, childToken.Purpose.Capability)
		}
		if childToken.Parent != token.TokenID {
			t.Errorf("child %s token parent = %q, want the caller's token %q", child, childToken.Parent, token.TokenID)
		}
	}

	// Audit: one entry per child, linked to the parent invocation and sharing
	// its task_id (audit_policy.record_child_invocations / parent_task_lineage).
	audit, err := svc.QueryAudit(token, server.AuditFilters{})
	if err != nil {
		t.Fatalf("QueryAudit() error: %v", err)
	}
	byCapability := map[string]core.AuditEntry{}
	for _, e := range audit.Entries {
		byCapability[e.Capability] = e
	}
	parentEntry, ok := byCapability["summary"]
	if !ok {
		t.Fatalf("no audit entry for the parent; entries: %d", len(audit.Entries))
	}
	for _, child := range []string{"select_cap", "enrich_cap"} {
		e, ok := byCapability[child]
		if !ok {
			t.Fatalf("no audit entry for child %s", child)
		}
		if !e.Success {
			t.Errorf("child %s audit entry is not a success: failure_type=%q", child, e.FailureType)
		}
		if e.ParentInvocationID != parentInvocationID {
			t.Errorf("child %s parent_invocation_id = %q, want the parent invocation %q", child, e.ParentInvocationID, parentInvocationID)
		}
		if e.TaskID == "" || e.TaskID != parentEntry.TaskID {
			t.Errorf("child %s task_id = %q, want the parent's %q", child, e.TaskID, parentEntry.TaskID)
		}
	}
}
