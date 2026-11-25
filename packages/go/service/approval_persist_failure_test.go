package service

import (
	"errors"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

// failingApprovalStorage refuses to persist approval requests.
type failingApprovalStorage struct {
	server.Storage
}

func (failingApprovalStorage) StoreApprovalRequest(*core.ApprovalRequest) error {
	return errors.New("disk full")
}

// SPEC.md §4.7: when the ApprovalRequest cannot be persisted the failure is
// service_unavailable (HTTP 503 by the §6.3 table), not approval_required.
func TestApprovalRequestPersistFailureIsServiceUnavailable(t *testing.T) {
	svc := newApprovalService(t)
	token := issueResolvedToken(t, svc)
	svc.storage = failingApprovalStorage{Storage: svc.storage}

	result, err := svc.Invoke("transfer_funds", token, map[string]any{
		"amount":     50000,
		"to_account": "acct-2",
	}, InvokeOpts{})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	failure, _ := result["failure"].(map[string]any)
	if failure["type"] != "service_unavailable" {
		t.Fatalf("failure type = %v, want service_unavailable (%#v)", failure["type"], failure)
	}
	if core.FailureStatusCode(failure["type"].(string)) != 503 {
		t.Fatalf("service_unavailable must map to HTTP 503")
	}
	if _, has := failure["approval_required"]; has {
		t.Fatalf("no approval request exists, yet the failure carries approval metadata: %#v", failure)
	}
	resolution, _ := failure["resolution"].(map[string]any)
	if resolution["action"] != "wait_and_retry" || resolution["recovery_class"] != "wait_then_retry" {
		t.Fatalf("resolution = %#v, want wait_and_retry / wait_then_retry", resolution)
	}

	entry := auditEntryFor(t, svc, token, result["invocation_id"].(string))
	if entry.Success || entry.FailureType != core.FailureServiceUnavailable || entry.ApprovalRequestID != "" {
		t.Fatalf("unexpected audit entry: success=%v failure_type=%q approval_request_id=%q",
			entry.Success, entry.FailureType, entry.ApprovalRequestID)
	}
}
