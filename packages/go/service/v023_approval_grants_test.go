// Approval request creation + grant issuance + continuation tests (v0.23
// §4.7–§4.9).
//
// Mirrors anip-service/tests/test_v023_approval_grants.py and the TS
// equivalent in packages/typescript/service/tests/v023-approval-grants.test.ts.

package service

import (
	"errors"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

// --- Helpers --------------------------------------------------------------

func defaultGrantPolicy() *core.GrantPolicy {
	return &core.GrantPolicy{
		AllowedGrantTypes: []string{core.GrantTypeOneTime, core.GrantTypeSessionBound},
		DefaultGrantType:  core.GrantTypeOneTime,
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
}

func approvalRequiredCapability(grantPolicy *core.GrantPolicy) CapabilityDef {
	if grantPolicy == nil {
		grantPolicy = defaultGrantPolicy()
	}
	decl := core.CapabilityDeclaration{
		Name:        "transfer_funds",
		Description: "High-value transfer",
		Inputs: []core.CapabilityInput{
			{Name: "amount", Type: "number", Required: true},
			{Name: "to_account", Type: "string", Required: true},
		},
		Output:       core.CapabilityOutput{Type: "transfer_confirmation", Fields: []string{"transfer_id"}},
		SideEffect:   core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
		MinimumScope: []string{"finance.write"},
		GrantPolicy:  grantPolicy,
	}
	return CapabilityDef{
		Declaration: decl,
		Handler: func(ctx *InvocationContext, params map[string]any) (map[string]any, error) {
			amount, _ := params["amount"].(float64)
			if amount == 0 {
				if i, ok := params["amount"].(int); ok {
					amount = float64(i)
				}
			}
			if amount > 10000 {
				return nil, &core.ANIPError{
					ErrorType: FailureApprovalRequired,
					Detail:    "transfer_funds requires approval for amounts above $10000",
					// No pre-built ApprovalRequiredMetadata: the runtime
					// auto-materialises a fresh ApprovalRequest from the
					// capability declaration's grant_policy.
				}
			}
			return map[string]any{"transfer_id": "tx-1234"}, nil
		},
	}
}

func newApprovalService(t *testing.T) *Service {
	t.Helper()
	return newApprovalServiceWithCapability(t, approvalRequiredCapability(nil))
}

func newApprovalServiceWithCapability(t *testing.T, cap CapabilityDef) *Service {
	t.Helper()
	svc := New(Config{
		ServiceID:    "test-finance",
		Capabilities: []CapabilityDef{cap},
		Storage:      ":memory:",
		Trust:        "signed",
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	return svc
}

func issueResolvedToken(t *testing.T, svc *Service, opts ...func(*core.TokenRequest)) *core.DelegationToken {
	t.Helper()
	req := core.TokenRequest{
		Subject:    "human:samir@example.com",
		Scope:      []string{"finance.write"},
		Capability: "transfer_funds",
		TTLHours:   1,
	}
	for _, o := range opts {
		o(&req)
	}
	resp, err := svc.IssueToken("human:samir@example.com", req)
	if err != nil {
		t.Fatalf("IssueToken: %v", err)
	}
	tok, err := svc.ResolveBearerToken(resp.Token)
	if err != nil {
		t.Fatalf("ResolveBearerToken: %v", err)
	}
	return tok
}

func withScope(scope ...string) func(*core.TokenRequest) {
	return func(r *core.TokenRequest) { r.Scope = scope }
}

func withSession(sessionID string) func(*core.TokenRequest) {
	return func(r *core.TokenRequest) { r.SessionID = sessionID }
}

func triggerApproval(t *testing.T, svc *Service, token *core.DelegationToken) string {
	t.Helper()
	result, err := svc.Invoke("transfer_funds", token, map[string]any{
		"amount":     50000,
		"to_account": "acct-2",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if success, _ := result["success"].(bool); success {
		t.Fatalf("expected approval_required failure, got success=%v", result)
	}
	failure, _ := result["failure"].(map[string]any)
	meta, _ := failure["approval_required"].(*core.ApprovalRequiredMetadata)
	if meta == nil {
		// In the response shape after JSON round-trip the type would be
		// map[string]any; here it's the struct because we never marshalled.
		if m, ok := failure["approval_required"].(map[string]any); ok {
			id, _ := m["approval_request_id"].(string)
			return id
		}
		t.Fatalf("missing approval_required metadata in failure: %#v", failure)
	}
	return meta.ApprovalRequestID
}

// --- ApprovalRequest creation --------------------------------------------

func TestApprovalRequestCreation_HandlerRaiseCreatesPersistentRequest(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	result, err := svc.Invoke("transfer_funds", token, map[string]any{
		"amount":     50000,
		"to_account": "acct-2",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if success, _ := result["success"].(bool); success {
		t.Fatalf("expected failure, got %+v", result)
	}
	failure, _ := result["failure"].(map[string]any)
	if got, _ := failure["type"].(string); got != FailureApprovalRequired {
		t.Errorf("failure.type = %q, want approval_required", got)
	}
	meta, _ := failure["approval_required"].(*core.ApprovalRequiredMetadata)
	if meta == nil {
		t.Fatalf("approval_required metadata missing: %+v", failure)
	}
	if !strings.HasPrefix(meta.ApprovalRequestID, "apr_") {
		t.Errorf("ApprovalRequestID = %q, want apr_*", meta.ApprovalRequestID)
	}
	if !strings.HasPrefix(meta.PreviewDigest, "sha256:") {
		t.Errorf("PreviewDigest = %q", meta.PreviewDigest)
	}
	if !strings.HasPrefix(meta.RequestedParametersDigest, "sha256:") {
		t.Errorf("RequestedParametersDigest = %q", meta.RequestedParametersDigest)
	}
	if meta.GrantPolicy.ExpiresInSeconds != 900 {
		t.Errorf("ExpiresInSeconds = %d", meta.GrantPolicy.ExpiresInSeconds)
	}
	stored, err := svc.storage.GetApprovalRequest(meta.ApprovalRequestID)
	if err != nil {
		t.Fatalf("GetApprovalRequest: %v", err)
	}
	if stored == nil {
		t.Fatal("approval_request not persisted")
	}
	if stored.Status != core.ApprovalRequestStatusPending {
		t.Errorf("Status = %q, want pending", stored.Status)
	}
	if stored.Capability != "transfer_funds" {
		t.Errorf("Capability = %q", stored.Capability)
	}
	// Persisted parameters/preview match the invocation params.
	if stored.RequestedParameters["amount"].(float64) != 50000 {
		t.Errorf("RequestedParameters.amount = %v", stored.RequestedParameters["amount"])
	}
}

func TestApprovalRequestCreation_NoApprovalUnderThreshold(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	result, err := svc.Invoke("transfer_funds", token, map[string]any{
		"amount":     5000,
		"to_account": "acct-2",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	if success, _ := result["success"].(bool); !success {
		t.Fatalf("expected success=true, got %+v", result)
	}
	res, _ := result["result"].(map[string]any)
	if res["transfer_id"] != "tx-1234" {
		t.Errorf("transfer_id = %v", res["transfer_id"])
	}
}

// --- IssueApprovalGrant SPI ----------------------------------------------

func TestIssueApprovalGrant_HappyPathOneTime(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"principal": "manager_456"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	if !strings.HasPrefix(grant.GrantID, "grant_") {
		t.Errorf("GrantID = %q", grant.GrantID)
	}
	if grant.ApprovalRequestID != requestID {
		t.Errorf("ApprovalRequestID = %q", grant.ApprovalRequestID)
	}
	if grant.GrantType != core.GrantTypeOneTime {
		t.Errorf("GrantType = %q", grant.GrantType)
	}
	if grant.MaxUses != 1 {
		t.Errorf("MaxUses = %d, want 1", grant.MaxUses)
	}
	if grant.UseCount != 0 {
		t.Errorf("UseCount = %d, want 0", grant.UseCount)
	}
	if grant.Capability != "transfer_funds" {
		t.Errorf("Capability = %q", grant.Capability)
	}
	if len(grant.Scope) != 1 || grant.Scope[0] != "finance.write" {
		t.Errorf("Scope = %v", grant.Scope)
	}
	if grant.SessionID != "" {
		t.Errorf("SessionID = %q, want empty for one_time", grant.SessionID)
	}
	if grant.Signature == "" {
		t.Error("Signature is empty")
	}
	stored, _ := svc.storage.GetApprovalRequest(requestID)
	if stored.Status != core.ApprovalRequestStatusApproved {
		t.Errorf("approval_request.Status = %q", stored.Status)
	}
	if stored.Approver["principal"] != "manager_456" {
		t.Errorf("Approver = %v", stored.Approver)
	}
	if stored.DecidedAt == "" {
		t.Error("DecidedAt is empty")
	}
}

func TestIssueApprovalGrant_HappyPathSessionBound(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeSessionBound, map[string]any{"principal": "manager_456"}, IssueApprovalGrantOpts{
		SessionID: "sess-X",
	})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	if grant.GrantType != core.GrantTypeSessionBound {
		t.Errorf("GrantType = %q", grant.GrantType)
	}
	if grant.SessionID != "sess-X" {
		t.Errorf("SessionID = %q", grant.SessionID)
	}
}

func TestIssueApprovalGrant_UnknownRequestID(t *testing.T) {
	svc := newApprovalService(t)
	_, err := svc.IssueApprovalGrant("apr_does_not_exist", core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err == nil {
		t.Fatal("expected error for unknown request id")
	}
	var anipErr *core.ANIPError
	if !errors.As(err, &anipErr) {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	if anipErr.ErrorType != FailureApprovalRequestNotFound {
		t.Errorf("ErrorType = %q", anipErr.ErrorType)
	}
}

func TestIssueApprovalGrant_AlreadyDecided(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	if _, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u1"}, IssueApprovalGrantOpts{}); err != nil {
		t.Fatalf("first IssueApprovalGrant: %v", err)
	}
	_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u2"}, IssueApprovalGrantOpts{})
	if err == nil {
		t.Fatal("expected error on second issuance")
	}
	var anipErr *core.ANIPError
	if !errors.As(err, &anipErr) {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	if anipErr.ErrorType != FailureApprovalRequestAlreadyDone {
		t.Errorf("ErrorType = %q", anipErr.ErrorType)
	}
}

func TestIssueApprovalGrant_TypeNotInPolicy(t *testing.T) {
	policy := &core.GrantPolicy{
		AllowedGrantTypes: []string{core.GrantTypeOneTime},
		DefaultGrantType:  core.GrantTypeOneTime,
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
	svc := newApprovalServiceWithCapability(t, approvalRequiredCapability(policy))
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeSessionBound, map[string]any{"p": "u"}, IssueApprovalGrantOpts{
		SessionID: "s1",
	})
	if err == nil {
		t.Fatal("expected error")
	}
	var anipErr *core.ANIPError
	if !errors.As(err, &anipErr) {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	if anipErr.ErrorType != FailureGrantTypeNotAllowed {
		t.Errorf("ErrorType = %q, want grant_type_not_allowed_by_policy", anipErr.ErrorType)
	}
}

func TestIssueApprovalGrant_SessionBoundRequiresSessionID(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeSessionBound, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err == nil {
		t.Fatal("expected error when session_id missing")
	}
	var anipErr *core.ANIPError
	if !errors.As(err, &anipErr) {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	if anipErr.ErrorType != FailureGrantTypeNotAllowed {
		t.Errorf("ErrorType = %q", anipErr.ErrorType)
	}
}

func TestIssueApprovalGrant_OneTimeRejectsSessionID(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{
		SessionID: "s1",
	})
	if err == nil {
		t.Fatal("expected error when one_time carries session_id")
	}
}

func TestIssueApprovalGrant_ClampsExpiresInSecondsToPolicy(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	huge := 999999
	_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{
		ExpiresInSeconds: &huge,
	})
	if err == nil {
		t.Fatal("expected error when expires_in_seconds exceeds policy")
	}
}

func TestIssueApprovalGrant_ClampsMaxUsesToPolicyForSessionBound(t *testing.T) {
	policy := &core.GrantPolicy{
		AllowedGrantTypes: []string{core.GrantTypeSessionBound},
		DefaultGrantType:  core.GrantTypeSessionBound,
		ExpiresInSeconds:  900,
		MaxUses:           2,
	}
	svc := newApprovalServiceWithCapability(t, approvalRequiredCapability(policy))
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	huge := 99
	_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeSessionBound, map[string]any{"p": "u"}, IssueApprovalGrantOpts{
		SessionID: "s1",
		MaxUses:   &huge,
	})
	if err == nil {
		t.Fatal("expected error when max_uses exceeds policy")
	}
}

func TestIssueApprovalGrant_CapabilityScopeCopiedFromRequest(t *testing.T) {
	// SPEC.md §4.9 step 8: grant fields MUST come from the approval_request,
	// not from caller args.
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	request, err := svc.storage.GetApprovalRequest(requestID)
	if err != nil {
		t.Fatalf("GetApprovalRequest: %v", err)
	}
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	if grant.Capability != request.Capability {
		t.Errorf("Capability copy mismatch: %q vs %q", grant.Capability, request.Capability)
	}
	if len(grant.Scope) != len(request.Scope) {
		t.Fatalf("Scope length mismatch")
	}
	for i := range grant.Scope {
		if grant.Scope[i] != request.Scope[i] {
			t.Errorf("Scope[%d] = %q, want %q", i, grant.Scope[i], request.Scope[i])
		}
	}
	if grant.ApprovedParametersDigest != request.RequestedParametersDigest {
		t.Errorf("ApprovedParametersDigest = %q, want %q", grant.ApprovedParametersDigest, request.RequestedParametersDigest)
	}
	if grant.PreviewDigest != request.PreviewDigest {
		t.Errorf("PreviewDigest mismatch")
	}
	if grant.Requester["principal"] != request.Requester["principal"] {
		t.Errorf("Requester mismatch: %v vs %v", grant.Requester, request.Requester)
	}
}

// --- ValidateContinuationGrant ------------------------------------------

func TestValidateContinuationGrant_CapabilityMismatch(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	g, fail := ValidateContinuationGrant(svc.storage, svc.keys, grant.GrantID,
		"some_other_capability",
		map[string]any{"amount": 50000, "to_account": "acct-2"},
		token.Scope, "", utcNowISO())
	if g != nil {
		t.Error("expected grant=nil")
	}
	if fail != FailureGrantCapabilityMismatch {
		t.Errorf("fail = %q, want grant_capability_mismatch", fail)
	}
}

func TestValidateContinuationGrant_ScopeMismatch(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	g, fail := ValidateContinuationGrant(svc.storage, svc.keys, grant.GrantID,
		"transfer_funds",
		map[string]any{"amount": 50000, "to_account": "acct-2"},
		[]string{"other.scope"}, "", utcNowISO())
	if g != nil {
		t.Error("expected grant=nil")
	}
	if fail != FailureGrantScopeMismatch {
		t.Errorf("fail = %q, want grant_scope_mismatch", fail)
	}
	_ = token
}

func TestValidateContinuationGrant_ParamDrift(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	g, fail := ValidateContinuationGrant(svc.storage, svc.keys, grant.GrantID,
		"transfer_funds",
		map[string]any{"amount": 99999, "to_account": "y"},
		token.Scope, "", utcNowISO())
	if g != nil {
		t.Error("expected grant=nil")
	}
	if fail != FailureGrantParamDrift {
		t.Errorf("fail = %q, want grant_param_drift", fail)
	}
}

func TestValidateContinuationGrant_Expired(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime, map[string]any{"p": "u"}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	// Use a "now" that's after the grant's expiry to trigger grant_expired.
	g, fail := ValidateContinuationGrant(svc.storage, svc.keys, grant.GrantID,
		"transfer_funds",
		map[string]any{"amount": 50000, "to_account": "acct-2"},
		token.Scope, "", utcInISO(99999))
	if g != nil {
		t.Error("expected grant=nil")
	}
	if fail != FailureGrantExpired {
		t.Errorf("fail = %q, want grant_expired", fail)
	}
}

func TestValidateContinuationGrant_SessionMismatch(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	grant, err := svc.IssueApprovalGrant(requestID, core.GrantTypeSessionBound, map[string]any{"p": "u"}, IssueApprovalGrantOpts{
		SessionID: "sess-A",
	})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	g, fail := ValidateContinuationGrant(svc.storage, svc.keys, grant.GrantID,
		"transfer_funds",
		map[string]any{"amount": 50000, "to_account": "acct-2"},
		token.Scope, "sess-B", utcNowISO())
	if g != nil {
		t.Error("expected grant=nil")
	}
	if fail != FailureGrantSessionInvalid {
		t.Errorf("fail = %q, want grant_session_invalid", fail)
	}
}

// --- Audit linkage --------------------------------------------------------

func TestAuditLinkage_FullChainReconstructible(t *testing.T) {
	// SPEC.md §4.9: every approval flow must be reconstructible from audit
	// entries via parent_invocation_id → approval_request_id → grant_id →
	// continuation_invocation_id.
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)

	first, err := svc.Invoke("transfer_funds", token, map[string]any{
		"amount":     50000,
		"to_account": "acct-2",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke 1: %v", err)
	}
	firstInvocationID, _ := first["invocation_id"].(string)
	failure, _ := first["failure"].(map[string]any)
	meta, _ := failure["approval_required"].(*core.ApprovalRequiredMetadata)
	if meta == nil {
		t.Fatalf("missing approval_required metadata")
	}
	approvalRequestID := meta.ApprovalRequestID

	grant, err := svc.IssueApprovalGrant(approvalRequestID, core.GrantTypeOneTime, map[string]any{
		"principal":      "manager_456",
		"root_principal": "human:samir@example.com",
	}, IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}
	grantID := grant.GrantID

	token2 := issueResolvedToken(t, svc)
	cont, err := svc.Invoke("transfer_funds", token2, map[string]any{
		"amount":     50000,
		"to_account": "acct-2",
	}, InvokeOpts{ApprovalGrant: grantID})
	if err != nil {
		t.Fatalf("Invoke continuation: %v", err)
	}
	continuationInvocationID, _ := cont["invocation_id"].(string)

	allEntries, err := svc.storage.QueryAuditEntries(server.AuditFilters{Limit: 200})
	if err != nil {
		t.Fatalf("QueryAuditEntries: %v", err)
	}

	// 3a. Original failure carries approval_request_id.
	var failureEntry *core.AuditEntry
	for i := range allEntries {
		e := &allEntries[i]
		if e.InvocationID == firstInvocationID && e.FailureType == FailureApprovalRequired {
			failureEntry = e
			break
		}
	}
	if failureEntry == nil {
		t.Fatal("no audit entry carries failure_type=approval_required for first invocation")
	}
	if failureEntry.ApprovalRequestID != approvalRequestID {
		t.Errorf("failure entry approval_request_id = %q, want %q", failureEntry.ApprovalRequestID, approvalRequestID)
	}

	// 3b. approval_request_created event with parent_invocation_id pointing
	// to the original invocation.
	var requestCreated []core.AuditEntry
	for _, e := range allEntries {
		if e.EntryType == "approval_request_created" && e.ApprovalRequestID == approvalRequestID {
			requestCreated = append(requestCreated, e)
		}
	}
	if len(requestCreated) != 1 {
		t.Fatalf("expected 1 approval_request_created entry, got %d", len(requestCreated))
	}
	if requestCreated[0].ParentInvocationID != firstInvocationID {
		t.Errorf("approval_request_created.parent_invocation_id = %q, want %q",
			requestCreated[0].ParentInvocationID, firstInvocationID)
	}

	// 3b'. Persisted ApprovalRequest carries parent_invocation_id = the
	// invocation that raised approval_required (SPEC.md §4.7 line 916).
	persisted, err := svc.storage.GetApprovalRequest(approvalRequestID)
	if err != nil {
		t.Fatalf("GetApprovalRequest: %v", err)
	}
	if persisted == nil {
		t.Fatal("approval_request not persisted")
	}
	if persisted.ParentInvocationID != firstInvocationID {
		t.Errorf("ApprovalRequest.parent_invocation_id = %q, want %q",
			persisted.ParentInvocationID, firstInvocationID)
	}

	// 3c. approval_grant_issued event links request_id ↔ grant_id.
	var grantIssued []core.AuditEntry
	for _, e := range allEntries {
		if e.EntryType == "approval_grant_issued" && e.ApprovalGrantID == grantID {
			grantIssued = append(grantIssued, e)
		}
	}
	if len(grantIssued) != 1 {
		t.Fatalf("expected 1 approval_grant_issued entry, got %d", len(grantIssued))
	}
	if grantIssued[0].ApprovalRequestID != approvalRequestID {
		t.Errorf("approval_grant_issued.approval_request_id = %q", grantIssued[0].ApprovalRequestID)
	}

	// 3d. Continuation audit entry references the grant.
	matched := false
	for _, e := range allEntries {
		if e.InvocationID == continuationInvocationID && e.ApprovalGrantID == grantID {
			matched = true
			break
		}
	}
	if !matched {
		t.Errorf("no continuation entry references grant_id=%q", grantID)
	}
}

// --- Concurrent issuance --------------------------------------------------

func TestConcurrentIssueApprovalGrant_OnlyOneSucceeds(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	requestID := triggerApproval(t, svc, token)
	const n = 5
	var wg sync.WaitGroup
	var successes int32
	rejections := make([]string, n)
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			_, err := svc.IssueApprovalGrant(requestID, core.GrantTypeOneTime,
				map[string]any{"p": fmt.Sprintf("u%d", idx)},
				IssueApprovalGrantOpts{})
			if err == nil {
				atomic.AddInt32(&successes, 1)
				return
			}
			var anipErr *core.ANIPError
			if errors.As(err, &anipErr) {
				rejections[idx] = anipErr.ErrorType
			} else {
				rejections[idx] = err.Error()
			}
		}(i)
	}
	wg.Wait()
	if got := atomic.LoadInt32(&successes); got != 1 {
		t.Errorf("successes = %d, want 1", got)
	}
	rejected := 0
	for i, r := range rejections {
		if r == "" {
			continue
		}
		rejected++
		if r != FailureApprovalRequestAlreadyDone {
			t.Errorf("rejection[%d] = %q, want %q", i, r, FailureApprovalRequestAlreadyDone)
		}
	}
	if rejected != n-1 {
		t.Errorf("rejections = %d, want %d", rejected, n-1)
	}
	stored, _ := svc.storage.GetApprovalRequest(requestID)
	if stored.Status != core.ApprovalRequestStatusApproved {
		t.Errorf("stored.Status = %q", stored.Status)
	}
}
