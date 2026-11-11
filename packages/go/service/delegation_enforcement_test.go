// Delegation enforcement (SPEC.md §3.2, §6.3 and the behavioral-conformance
// list). Mirrors the Python reference in anip_server/delegation.py and the
// cross-runtime suite in conformance/test_delegation.py.
//
//   - Purpose binding: "a token issued for book_flight cannot invoke
//     search_flights", even when its scope would cover both.
//   - Only the holder of a token (its subject) may delegate from it.
//   - A delegated token cannot widen its parent's scope or scope budget.
//   - Chains deeper than max_delegation_depth are rejected.
//
// Composed capabilities (§4.6) must still work under those rules: each child
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

// --- Delegated issuance ----------------------------------------------------

func startedTestService(t *testing.T) *Service {
	t.Helper()
	svc := newTestService()
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	return svc
}

func issueRoot(t *testing.T, svc *Service, principal string, scope []string) core.TokenResponse {
	t.Helper()
	resp, err := svc.IssueToken(principal, core.TokenRequest{Scope: scope, Capability: "search_flights"})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	return resp
}

func expectIssuanceFailure(t *testing.T, err error, wantType string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected issuance to fail with %q, but a token was issued", wantType)
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected *core.ANIPError, got %T: %v", err, err)
	}
	if anipErr.ErrorType != wantType {
		t.Fatalf("expected failure type %q, got %q (%s)", wantType, anipErr.ErrorType, anipErr.Detail)
	}
}

func TestIssueTokenAllowsHolderToDelegateWithinScope(t *testing.T) {
	svc := startedTestService(t)
	root := issueRoot(t, svc, "human:test@example.com", []string{"travel.search", "travel.book"})

	child, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject:     "agent:helper",
		Scope:       []string{"travel.search"},
		Capability:  "search_flights",
		ParentToken: root.TokenID,
	})
	if err != nil {
		t.Fatalf("delegating within scope failed: %v", err)
	}
	token, err := svc.ResolveBearerToken(child.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}
	if token.Parent != root.TokenID || token.RootPrincipal != "human:test@example.com" {
		t.Fatalf("unexpected child token lineage: parent=%q root_principal=%q", token.Parent, token.RootPrincipal)
	}
}

func TestIssueTokenRejectsDelegationByNonHolder(t *testing.T) {
	svc := startedTestService(t)
	// The token is held by the human principal (default subject).
	root := issueRoot(t, svc, "human:test@example.com", []string{"travel.search"})

	_, err := svc.IssueToken("agent:someone-else", core.TokenRequest{
		Scope:       []string{"travel.search"},
		Capability:  "search_flights",
		ParentToken: root.TokenID,
	})

	expectIssuanceFailure(t, err, "insufficient_authority")
}

func TestIssueTokenRejectsScopeWidening(t *testing.T) {
	svc := startedTestService(t)
	root := issueRoot(t, svc, "human:test@example.com", []string{"travel.search"})

	_, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Scope:       []string{"travel.search", "travel.book"},
		Capability:  "book_flight",
		ParentToken: root.TokenID,
	})

	expectIssuanceFailure(t, err, core.FailureScopeEscalation)
}

func TestIssueTokenScopeNarrowingRules(t *testing.T) {
	cases := []struct {
		name        string
		parentScope []string
		childScope  []string
		wantFailure string // empty = issued
	}{
		{"same scope", []string{"travel.search"}, []string{"travel.search"}, ""},
		{"sub-scope of parent", []string{"travel"}, []string{"travel.search"}, ""},
		{"sibling scope", []string{"travel.search"}, []string{"travel.book"}, core.FailureScopeEscalation},
		{"prefix without a dot boundary", []string{"travel"}, []string{"travelogue.read"}, core.FailureScopeEscalation},
		{"keeps scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$500"}, ""},
		{"lowers scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$100"}, ""},
		{"drops scope budget", []string{"travel.book:max_$500"}, []string{"travel.book"}, core.FailureScopeEscalation},
		{"raises scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$900"}, core.FailureScopeEscalation},
		// A budget on a parent scope bounds every scope beneath it.
		{"sub-scope keeps parent budget", []string{"travel:max_$500"}, []string{"travel.book:max_$500"}, ""},
		{"sub-scope drops parent budget", []string{"travel:max_$500"}, []string{"travel.book"}, core.FailureScopeEscalation},
		{"sub-scope raises parent budget", []string{"travel:max_$500"}, []string{"travel.book:max_$900"}, core.FailureScopeEscalation},
		// A budget that is not a finite, non-negative number must fail closed:
		// NaN compares false against everything, so it would pass a naive "child > parent" check.
		{"NaN scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$NaN"}, core.FailureScopeEscalation},
		{"infinite scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$Inf"}, core.FailureScopeEscalation},
		{"negative scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$-1"}, core.FailureScopeEscalation},
		{"unparseable scope budget", []string{"travel.book:max_$500"}, []string{"travel.book:max_$lots"}, core.FailureScopeEscalation},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			svc := startedTestService(t)
			root := issueRoot(t, svc, "human:test@example.com", tc.parentScope)

			_, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
				Scope:       tc.childScope,
				Capability:  "book_flight",
				ParentToken: root.TokenID,
			})

			if tc.wantFailure == "" {
				if err != nil {
					t.Fatalf("expected the child token to be issued, got %v", err)
				}
				return
			}
			expectIssuanceFailure(t, err, tc.wantFailure)
		})
	}
}

// --- Delegation depth ------------------------------------------------------

func TestInvokeEnforcesDelegationDepth(t *testing.T) {
	svc := startedTestService(t)
	principal := "human:test@example.com"
	token := issueRoot(t, svc, principal, []string{"travel.search"})
	params := map[string]any{"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}

	invoke := func(resp core.TokenResponse) map[string]any {
		t.Helper()
		resolved, err := svc.ResolveBearerToken(resp.Token)
		if err != nil {
			t.Fatalf("ResolveBearerToken() error: %v", err)
		}
		result, err := svc.Invoke("search_flights", resolved, params, InvokeOpts{})
		if err != nil {
			t.Fatalf("Invoke() error: %v", err)
		}
		return result
	}

	// The default max_delegation_depth is 3: depths 1..3 work, depth 4 does not.
	for depth := 1; depth <= 4; depth++ {
		child, err := svc.IssueToken(principal, core.TokenRequest{
			Scope:       []string{"travel.search"},
			Capability:  "search_flights",
			ParentToken: token.TokenID,
		})
		if err != nil {
			t.Fatalf("delegation at depth %d failed at issuance: %v", depth, err)
		}
		token = child
		result := invoke(token)
		if depth <= 3 {
			if result["success"] != true {
				t.Fatalf("depth %d is within the limit but was rejected: %#v", depth, result["failure"])
			}
			continue
		}
		if result["success"] != false {
			t.Fatalf("a token at delegation depth %d was accepted (limit is 3)", depth)
		}
		if got := failureType(t, result); got != "delegation_depth_exceeded" {
			t.Fatalf("expected failure type delegation_depth_exceeded, got %q", got)
		}
	}
}

// --- Who may ask for a token ------------------------------------------------
//
// SPEC.md §6.3: root issuance authenticates with the bootstrap credential;
// delegated issuance authenticates with an existing service-issued token and
// names a parent_token. A delegation token is therefore a valid credential
// for delegating, and never for minting a fresh root token.

func TestAuthenticateIssuerAcceptsBootstrapCredentialAndTokens(t *testing.T) {
	svc := startedTestService(t)

	issuer, ok := svc.AuthenticateIssuer("test-key")
	if !ok || issuer.Principal != "human:test@example.com" || issuer.ViaToken {
		t.Fatalf("bootstrap credential: got %+v ok=%v", issuer, ok)
	}

	held, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject: "agent:helper", Scope: []string{"travel.search"}, Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	issuer, ok = svc.AuthenticateIssuer(held.Token)
	if !ok || issuer.Principal != "agent:helper" || !issuer.ViaToken {
		t.Fatalf("delegation token as credential: got %+v ok=%v", issuer, ok)
	}

	if _, ok := svc.AuthenticateIssuer("not-a-credential"); ok {
		t.Fatal("an unknown bearer value must not authenticate")
	}
}

func TestIssueTokenAsRejectsRootIssuanceWithTokenCredential(t *testing.T) {
	svc := startedTestService(t)
	held, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject: "agent:helper", Scope: []string{"travel.search"}, Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	issuer, _ := svc.AuthenticateIssuer(held.Token)

	// No parent_token: this asks for a root token, with more scope than the
	// agent was ever given.
	_, err = svc.IssueTokenAs(issuer, core.TokenRequest{
		Scope: []string{"travel.search", "travel.book"}, Capability: "book_flight",
	})

	expectIssuanceFailure(t, err, core.FailureInsufficientAuthority)
}

func TestIssueTokenAsAllowsHolderToDelegateWithTokenCredential(t *testing.T) {
	svc := startedTestService(t)
	held, err := svc.IssueToken("human:test@example.com", core.TokenRequest{
		Subject: "agent:helper", Scope: []string{"travel.search"}, Capability: "search_flights",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	issuer, _ := svc.AuthenticateIssuer(held.Token)

	child, err := svc.IssueTokenAs(issuer, core.TokenRequest{
		Subject: "agent:sub-helper", Scope: []string{"travel.search"}, Capability: "search_flights",
		ParentToken: held.TokenID,
	})
	if err != nil {
		t.Fatalf("the holder could not delegate from its own token: %v", err)
	}
	token, err := svc.ResolveBearerToken(child.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken() error: %v", err)
	}
	if token.RootPrincipal != "human:test@example.com" || token.Issuer != "agent:helper" {
		t.Fatalf("unexpected lineage: root_principal=%q issuer=%q", token.RootPrincipal, token.Issuer)
	}
}

func TestIssueTokenAsAllowsRootIssuanceWithBootstrapCredential(t *testing.T) {
	svc := startedTestService(t)
	issuer, _ := svc.AuthenticateIssuer("test-key")

	if _, err := svc.IssueTokenAs(issuer, core.TokenRequest{
		Scope: []string{"travel.search"}, Capability: "search_flights",
	}); err != nil {
		t.Fatalf("root issuance with the bootstrap credential failed: %v", err)
	}
}

// --- Composed capabilities: the child's scope comes from the caller's ------

func TestComposedInvocationCannotReachChildBeyondCallersScope(t *testing.T) {
	seen := map[string]*core.DelegationToken{}
	svc := newComposedTestService(seen)
	// The second child needs a scope the caller's token does not carry.
	enrich := svc.capabilities["enrich_cap"]
	enrich.Declaration.MinimumScope = []string{"admin"}
	svc.capabilities["enrich_cap"] = enrich
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	token := issueBoundToken(t, svc, "summary", []string{"s"})
	result, err := svc.Invoke("summary", token, map[string]any{"q": "x"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	if result["success"] != false {
		t.Fatalf("expected the composed invocation to fail, got %#v", result)
	}
	if seen["enrich_cap"] != nil {
		t.Fatal("the child handler must not run")
	}
	// Default failure_policy propagates a child denial unchanged: the caller
	// is told its token lacks the scope the step needs.
	if got := failureType(t, result); got != core.FailureScopeInsufficient {
		t.Fatalf("expected failure type %q, got %q", core.FailureScopeInsufficient, got)
	}
}

func TestComposedInvocationKeepsCallersScopeBudgetOnChildTokens(t *testing.T) {
	seen := map[string]*core.DelegationToken{}
	svc := newComposedTestService(seen)
	for _, name := range []string{"select_cap", "enrich_cap", "summary"} {
		def := svc.capabilities[name]
		def.Declaration.MinimumScope = []string{"inv.read"}
		svc.capabilities[name] = def
	}
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	defer svc.Shutdown()

	// "inv:max_$50" covers "inv.read"; the child token keeps the budget.
	token := issueBoundToken(t, svc, "summary", []string{"inv:max_$50"})
	result, err := svc.Invoke("summary", token, map[string]any{"q": "x"}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}
	if result["success"] != true {
		t.Fatalf("expected the composed invocation to succeed, got %#v", result["failure"])
	}
	child := seen["select_cap"]
	if child == nil || len(child.Scope) != 1 || child.Scope[0] != "inv.read:max_$50" {
		t.Fatalf("child token scope = %v, want [inv.read:max_$50]", child)
	}
}
