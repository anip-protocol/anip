package core

import (
	"encoding/json"
	"testing"
)

func grantPolicy() GrantPolicy {
	return GrantPolicy{
		AllowedGrantTypes: []string{GrantTypeOneTime, GrantTypeSessionBound},
		DefaultGrantType:  GrantTypeOneTime,
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
}

func composedDecl() CapabilityDeclaration {
	return CapabilityDeclaration{
		Name:            "at_risk_account_enrichment_summary",
		Description:     "Composed example",
		ContractVersion: "1.0",
		Inputs:          []CapabilityInput{},
		Output:          CapabilityOutput{Type: "enriched", Fields: []string{"count", "accounts"}},
		SideEffect:      SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope:    []string{"gtm.read"},
		Kind:            CapabilityKindComposed,
		Composition: &Composition{
			AuthorityBoundary: AuthorityBoundarySameService,
			Steps: []CompositionStep{
				{ID: "select", Capability: "select_at_risk", EmptyResultSource: true},
				{ID: "enrich", Capability: "enrich_accounts"},
			},
			InputMapping: map[string]map[string]string{
				"select": {"quarter": "$.input.quarter"},
				"enrich": {"accounts": "$.steps.select.output.accounts"},
			},
			OutputMapping: map[string]string{
				"count":    "$.steps.enrich.output.count",
				"accounts": "$.steps.enrich.output.accounts",
			},
			EmptyResultPolicy: EmptyResultPolicyReturnSuccessNoResults,
			EmptyResultOutput: map[string]any{"count": 0, "accounts": []any{}},
			FailurePolicy: FailurePolicy{
				ChildClarification:    FailurePolicyOutcomePropagate,
				ChildDenial:           FailurePolicyOutcomePropagate,
				ChildApprovalRequired: FailurePolicyOutcomePropagate,
				ChildError:            FailurePolicyOutcomeFailParent,
			},
			AuditPolicy: AuditPolicy{RecordChildInvocations: true, ParentTaskLineage: true},
		},
	}
}

func grant() ApprovalGrant {
	return ApprovalGrant{
		GrantID:                  "grant_test",
		ApprovalRequestID:        "apr_test",
		GrantType:                GrantTypeOneTime,
		Capability:               "finance.transfer_funds",
		Scope:                    []string{"finance.write"},
		ApprovedParametersDigest: "sha256:params",
		PreviewDigest:            "sha256:preview",
		Requester:                map[string]any{"principal": "u1"},
		Approver:                 map[string]any{"principal": "u2"},
		IssuedAt:                 "2026-01-01T00:00:00Z",
		ExpiresAt:                "2026-01-01T00:15:00Z",
		MaxUses:                  1,
		UseCount:                 0,
		Signature:                "sig_test",
	}
}

func roundTrip[T any](t *testing.T, v T) T {
	t.Helper()
	data, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var out T
	if err := json.Unmarshal(data, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	return out
}

func TestCapabilityKindAtomicDefaultEmpty(t *testing.T) {
	d := CapabilityDeclaration{
		Name:         "cap",
		Description:  "d",
		Inputs:       []CapabilityInput{},
		Output:       CapabilityOutput{Type: "x", Fields: []string{}},
		SideEffect:   SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope: []string{"s"},
	}
	d2 := roundTrip(t, d)
	if d2.Kind != "" {
		t.Errorf("expected empty Kind (atomic-default), got %q", d2.Kind)
	}
	if d2.Composition != nil {
		t.Errorf("expected nil Composition, got %+v", d2.Composition)
	}
}

func TestComposedDeclarationRoundTrip(t *testing.T) {
	d := composedDecl()
	d2 := roundTrip(t, d)
	if d2.Kind != CapabilityKindComposed {
		t.Errorf("expected composed, got %q", d2.Kind)
	}
	if d2.Composition == nil {
		t.Fatal("expected non-nil composition")
	}
	if !d2.Composition.Steps[0].EmptyResultSource {
		t.Error("expected step[0].EmptyResultSource=true")
	}
	if d2.Composition.Steps[1].EmptyResultSource {
		t.Error("expected step[1].EmptyResultSource=false")
	}
	if d2.Composition.EmptyResultPolicy != EmptyResultPolicyReturnSuccessNoResults {
		t.Errorf("policy mismatch: %q", d2.Composition.EmptyResultPolicy)
	}
	if d2.Composition.FailurePolicy.ChildError != FailurePolicyOutcomeFailParent {
		t.Errorf("child_error policy mismatch")
	}
}

func TestApprovalGrantOneTimeRoundTrip(t *testing.T) {
	g := grant()
	g2 := roundTrip(t, g)
	if g2.ApprovalRequestID != "apr_test" {
		t.Errorf("approval_request_id mismatch: %q", g2.ApprovalRequestID)
	}
	if g2.GrantType != GrantTypeOneTime {
		t.Errorf("grant_type mismatch: %q", g2.GrantType)
	}
	if g2.SessionID != "" {
		t.Errorf("expected empty session_id, got %q", g2.SessionID)
	}
}

func TestApprovalGrantSessionBoundRoundTrip(t *testing.T) {
	g := grant()
	g.GrantType = GrantTypeSessionBound
	g.SessionID = "sess_1"
	g.MaxUses = 5
	g2 := roundTrip(t, g)
	if g2.GrantType != GrantTypeSessionBound {
		t.Errorf("grant_type mismatch")
	}
	if g2.SessionID != "sess_1" {
		t.Errorf("session_id mismatch: %q", g2.SessionID)
	}
	if g2.MaxUses != 5 {
		t.Errorf("max_uses mismatch: %d", g2.MaxUses)
	}
}

func TestApprovalRequestPendingRoundTrip(t *testing.T) {
	r := ApprovalRequest{
		ApprovalRequestID:         "apr_test",
		Capability:                "cap",
		Scope:                     []string{"s"},
		Requester:                 map[string]any{"principal": "u1"},
		Preview:                   map[string]any{"k": "v"},
		PreviewDigest:             "d2",
		RequestedParameters:       map[string]any{"k": "v"},
		RequestedParametersDigest: "d1",
		GrantPolicy:               grantPolicy(),
		Status:                    ApprovalRequestStatusPending,
		CreatedAt:                 "2026-01-01T00:00:00Z",
		ExpiresAt:                 "2026-01-01T00:15:00Z",
	}
	r2 := roundTrip(t, r)
	if r2.Status != ApprovalRequestStatusPending {
		t.Errorf("status mismatch")
	}
	if r2.Approver != nil {
		t.Errorf("expected nil approver, got %+v", r2.Approver)
	}
}

func TestApprovalRequestExpiredHasNoApprover(t *testing.T) {
	r := ApprovalRequest{
		ApprovalRequestID:         "apr_test",
		Capability:                "cap",
		Scope:                     []string{"s"},
		Requester:                 map[string]any{"principal": "u1"},
		Preview:                   map[string]any{},
		PreviewDigest:             "d2",
		RequestedParameters:       map[string]any{},
		RequestedParametersDigest: "d1",
		GrantPolicy:               grantPolicy(),
		Status:                    ApprovalRequestStatusExpired,
		DecidedAt:                 "2026-01-01T00:15:01Z",
		CreatedAt:                 "2026-01-01T00:00:00Z",
		ExpiresAt:                 "2026-01-01T00:15:00Z",
	}
	r2 := roundTrip(t, r)
	if r2.Status != ApprovalRequestStatusExpired {
		t.Errorf("status mismatch")
	}
	if r2.Approver != nil {
		t.Errorf("expired request must have nil approver, got %+v", r2.Approver)
	}
	if r2.DecidedAt == "" {
		t.Errorf("expected decided_at to be set")
	}
}

func TestANIPErrorWithApprovalRequiredMetadata(t *testing.T) {
	e := &ANIPError{
		ErrorType: "approval_required",
		Detail:    "needs approval",
		Resolution: &Resolution{
			Action:        "contact_service_owner",
			RecoveryClass: "terminal",
		},
		ApprovalRequired: &ApprovalRequiredMetadata{
			ApprovalRequestID:         "apr_test",
			PreviewDigest:             "d2",
			RequestedParametersDigest: "d1",
			GrantPolicy:               grantPolicy(),
		},
	}
	data, err := json.Marshal(e)
	if err != nil {
		t.Fatal(err)
	}
	var e2 ANIPError
	if err := json.Unmarshal(data, &e2); err != nil {
		t.Fatal(err)
	}
	if e2.ApprovalRequired == nil {
		t.Fatal("expected approval_required metadata")
	}
	if e2.ApprovalRequired.ApprovalRequestID != "apr_test" {
		t.Errorf("approval_request_id mismatch")
	}
}

func TestInvokeRequestApprovalGrantRoundTrip(t *testing.T) {
	r := InvokeRequest{Token: "jwt", ApprovalGrant: "grant_test"}
	r2 := roundTrip(t, r)
	if r2.ApprovalGrant != "grant_test" {
		t.Errorf("approval_grant mismatch: %q", r2.ApprovalGrant)
	}
}

func TestGrantPolicyValidate_Valid(t *testing.T) {
	p := grantPolicy()
	if err := p.Validate(); err != nil {
		t.Errorf("expected valid policy, got error: %v", err)
	}
}

func TestGrantPolicyValidate_DefaultNotInAllowed(t *testing.T) {
	p := GrantPolicy{
		AllowedGrantTypes: []string{GrantTypeOneTime},
		DefaultGrantType:  GrantTypeSessionBound, // not in AllowedGrantTypes
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
	err := p.Validate()
	if err == nil {
		t.Fatal("expected validation error, got nil")
	}
	pve, ok := err.(*PolicyValidationError)
	if !ok {
		t.Fatalf("expected *PolicyValidationError, got %T", err)
	}
	if pve.Field != "default_grant_type" {
		t.Errorf("expected Field=default_grant_type, got %q", pve.Field)
	}
}

func TestGrantPolicyValidate_EmptyAllowed(t *testing.T) {
	p := GrantPolicy{
		AllowedGrantTypes: nil,
		DefaultGrantType:  GrantTypeOneTime,
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
	if err := p.Validate(); err == nil {
		t.Error("expected validation error for empty AllowedGrantTypes")
	}
}

func TestGrantPolicyValidate_EmptyDefault(t *testing.T) {
	p := GrantPolicy{
		AllowedGrantTypes: []string{GrantTypeOneTime},
		DefaultGrantType:  "",
		ExpiresInSeconds:  900,
		MaxUses:           1,
	}
	if err := p.Validate(); err == nil {
		t.Error("expected validation error for empty DefaultGrantType")
	}
}

func TestIssueApprovalGrantRequestResponseRoundTrip(t *testing.T) {
	req := IssueApprovalGrantRequest{
		ApprovalRequestID: "apr_test",
		GrantType:         GrantTypeOneTime,
		ExpiresInSeconds:  600,
		MaxUses:           1,
	}
	req2 := roundTrip(t, req)
	if req2.GrantType != GrantTypeOneTime {
		t.Errorf("grant_type mismatch")
	}
	// SPEC.md §4.9: response IS the signed grant — no wrapper.
	resp := IssueApprovalGrantResponse(grant())
	resp2 := roundTrip(t, resp)
	if resp2.GrantID != "grant_test" {
		t.Errorf("grant_id mismatch")
	}
}
