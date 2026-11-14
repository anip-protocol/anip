package stdioapi

import (
	"encoding/json"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// SPEC.md §4.8: a continuation supplies approval_grant on anip.invoke, and
// stdio carries it with the same validation as HTTP.

func newApprovalStdio(t *testing.T) (*Server, *service.Service, string) {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID: "test-stdio-approvals",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:          "transfer",
				Description:   "Transfer funds",
				Inputs:        []core.CapabilityInput{{Name: "amount", Type: "number", Required: true}},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"transferred"}},
				SideEffect:    core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
				MinimumScope:  []string{"finance.write"},
				ResponseModes: []string{"unary", "streaming"},
				GrantPolicy: &core.GrantPolicy{
					AllowedGrantTypes: []string{"one_time"}, DefaultGrantType: "one_time",
					ExpiresInSeconds: 900, MaxUses: 1,
				},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				amount, _ := params["amount"].(float64)
				if amount > 1000 && ctx.ApprovalGrant == "" {
					return nil, &core.ANIPError{ErrorType: "approval_required", Detail: "transfers above 1000 need approval"}
				}
				return map[string]any{"transferred": amount}, nil
			},
		}},
		Storage:                  ":memory:",
		Trust:                    "signed",
		RetentionIntervalSeconds: -1,
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	resp, err := svc.IssueToken("human:tester@example.com", core.TokenRequest{
		Subject: "human:tester@example.com", Scope: []string{"finance.write"}, Capability: "transfer",
	})
	if err != nil {
		t.Fatalf("IssueToken: %v", err)
	}
	return NewServer(svc), svc, resp.Token
}

// invokeTransfer returns the failure type of the call, or "" on success.
func invokeTransfer(t *testing.T, srv *Server, token string, extra map[string]any) (string, map[string]any) {
	t.Helper()
	params := map[string]any{
		"auth": map[string]any{"bearer": token}, "capability": "transfer",
		"parameters": map[string]any{"amount": 5000},
	}
	for k, v := range extra {
		params[k] = v
	}
	messages := dispatch(t, srv, "anip.invoke", params)
	last, ok := messages[len(messages)-1].(response)
	if !ok {
		t.Fatalf("expected a response, got %T", messages[len(messages)-1])
	}
	// A refusal made before the handler of a streaming call is a JSON-RPC
	// error carrying the failure.
	if last.Error != nil {
		data, _ := last.Error.Data.(map[string]any)
		failureType, _ := data["type"].(string)
		return failureType, nil
	}
	raw, _ := json.Marshal(last.Result)
	var result map[string]any
	json.Unmarshal(raw, &result)
	if result["success"] == true {
		return "", result
	}
	failure, _ := result["failure"].(map[string]any)
	failureType, _ := failure["type"].(string)
	return failureType, result
}

func TestInvokeCarriesApprovalGrant(t *testing.T) {
	srv, svc, token := newApprovalStdio(t)
	failureType, first := invokeTransfer(t, srv, token, nil)
	if failureType != "approval_required" {
		t.Fatalf("expected approval_required, got %q %v", failureType, first)
	}
	meta := first["failure"].(map[string]any)["approval_required"].(map[string]any)
	grant, err := svc.IssueApprovalGrant(meta["approval_request_id"].(string), core.GrantTypeOneTime,
		map[string]any{"principal": "human:approver@example.com"}, service.IssueApprovalGrantOpts{})
	if err != nil {
		t.Fatalf("IssueApprovalGrant: %v", err)
	}

	failureType, result := invokeTransfer(t, srv, token, map[string]any{"approval_grant": grant.GrantID})
	if failureType != "" {
		t.Fatalf("the continuation was refused: %q", failureType)
	}
	if result["result"].(map[string]any)["transferred"] != float64(5000) {
		t.Fatalf("unexpected result %v", result)
	}
	if again, _ := invokeTransfer(t, srv, token, map[string]any{"approval_grant": grant.GrantID}); again != "grant_consumed" {
		t.Fatalf("a spent grant answered %q, want grant_consumed", again)
	}
}

func TestInvokeBlankApprovalGrantIsNotFound(t *testing.T) {
	for _, stream := range []bool{false, true} {
		for _, grant := range []any{"", "   ", 7} {
			srv, _, token := newApprovalStdio(t)
			failureType, _ := invokeTransfer(t, srv, token, map[string]any{"approval_grant": grant, "stream": stream})
			if failureType != "grant_not_found" {
				t.Errorf("stream=%v approval_grant=%#v: got %q, want grant_not_found", stream, grant, failureType)
			}
		}
	}
}

func TestInvokeNullApprovalGrantIsNoGrant(t *testing.T) {
	srv, _, token := newApprovalStdio(t)
	if failureType, _ := invokeTransfer(t, srv, token, map[string]any{"approval_grant": nil}); failureType != "approval_required" {
		t.Fatalf("got %q, want approval_required", failureType)
	}
}
