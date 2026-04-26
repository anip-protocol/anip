// Gin endpoint tests for POST /anip/approval_grants (v0.23 §4.9).
//
// Mirrors the httpapi/v023_approval_grants_test.go suite — same content,
// shape, and coverage, but exercising the Gin router.

package ginapi

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// --- v0.23 helpers --------------------------------------------------------

func transferFundsCapability() service.CapabilityDef {
	decl := core.CapabilityDeclaration{
		Name:        "transfer_funds",
		Description: "High-value transfer",
		Inputs: []core.CapabilityInput{
			{Name: "amount", Type: "number", Required: true},
			{Name: "to_account", Type: "string", Required: true},
		},
		Output:       core.CapabilityOutput{Type: "x", Fields: []string{"transfer_id"}},
		SideEffect:   core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
		MinimumScope: []string{"finance.write"},
		GrantPolicy: &core.GrantPolicy{
			AllowedGrantTypes: []string{core.GrantTypeOneTime, core.GrantTypeSessionBound},
			DefaultGrantType:  core.GrantTypeOneTime,
			ExpiresInSeconds:  900,
			MaxUses:           1,
		},
	}
	return service.CapabilityDef{
		Declaration: decl,
		Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
			amount, _ := params["amount"].(float64)
			if amount > 10000 {
				return nil, &core.ANIPError{
					ErrorType: "approval_required",
					Detail:    "needs approval",
				}
			}
			return map[string]any{"transfer_id": "tx"}, nil
		},
	}
}

func newApprovalGinServer(t *testing.T) *httptest.Server {
	t.Helper()
	gin.SetMode(gin.TestMode)
	svc := service.New(service.Config{
		ServiceID:    "test-fin",
		Capabilities: []service.CapabilityDef{transferFundsCapability()},
		Storage:      ":memory:",
		Trust:        "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-api-key" {
				return "human:samir@example.com", true
			}
			return "", false
		},
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Service.Start: %v", err)
	}
	t.Cleanup(func() { svc.Shutdown() })
	router := gin.New()
	MountANIPGin(router, svc)
	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)
	return ts
}

func issueApprovalTokenGin(t *testing.T, ts *httptest.Server, scope []string, sessionID string) string {
	t.Helper()
	body := map[string]any{
		"subject":    "human:samir@example.com",
		"scope":      scope,
		"capability": "transfer_funds",
		"ttl_hours":  1,
	}
	if sessionID != "" {
		body["session_id"] = sessionID
	}
	bodyBytes, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", ts.URL+"/anip/tokens", bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer test-api-key")
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("token request: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		raw, _ := io.ReadAll(resp.Body)
		t.Fatalf("token status %d: %s", resp.StatusCode, raw)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	tok, _ := data["token"].(string)
	if tok == "" {
		t.Fatal("empty token in response")
	}
	return tok
}

func triggerApprovalGin(t *testing.T, ts *httptest.Server, token string) string {
	t.Helper()
	body := `{"parameters": {"amount": 50000, "to_account": "x"}}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/transfer_funds", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("invoke: %v", err)
	}
	defer resp.Body.Close()
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure == nil {
		t.Fatalf("expected failure: %#v", data)
	}
	meta, _ := failure["approval_required"].(map[string]any)
	if meta == nil {
		t.Fatalf("missing approval_required: %#v", failure)
	}
	id, _ := meta["approval_request_id"].(string)
	return id
}

// --- happy path ----------------------------------------------------------

func TestV023ApprovalGrantsGinHappyPath(t *testing.T) {
	ts := newApprovalGinServer(t)
	token := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	requestID := triggerApprovalGin(t, ts, token)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")

	body := map[string]any{
		"approval_request_id": requestID,
		"grant_type":          core.GrantTypeOneTime,
	}
	bb, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(bb))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		raw, _ := io.ReadAll(resp.Body)
		t.Fatalf("status = %d, body=%s", resp.StatusCode, raw)
	}
	var grant map[string]any
	json.NewDecoder(resp.Body).Decode(&grant)
	if grant["approval_request_id"] != requestID {
		t.Errorf("approval_request_id = %v", grant["approval_request_id"])
	}
	if grant["grant_type"] != "one_time" {
		t.Errorf("grant_type = %v", grant["grant_type"])
	}
	if mu, _ := grant["max_uses"].(float64); mu != 1 {
		t.Errorf("max_uses = %v", grant["max_uses"])
	}
	if uc, _ := grant["use_count"].(float64); uc != 0 {
		t.Errorf("use_count = %v", grant["use_count"])
	}
	if sig, _ := grant["signature"].(string); sig == "" {
		t.Error("signature empty")
	}
}

func TestV023ApprovalGrantsGinUnauthorizedWithoutToken(t *testing.T) {
	ts := newApprovalGinServer(t)
	body := `{"approval_request_id": "apr_x", "grant_type": "one_time"}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 401 {
		t.Fatalf("status = %d, want 401", resp.StatusCode)
	}
}

func TestV023ApprovalGrantsGinApprovalRequestNotFound(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{"approval_request_id": "apr_does_not_exist", "grant_type": "one_time"}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 404 {
		t.Fatalf("status = %d, want 404", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != "approval_request_not_found" {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinApproverNotAuthorized(t *testing.T) {
	ts := newApprovalGinServer(t)
	token := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	requestID := triggerApprovalGin(t, ts, token)
	nonApprover := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	body := map[string]any{
		"approval_request_id": requestID,
		"grant_type":          core.GrantTypeOneTime,
	}
	bb, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(bb))
	req.Header.Set("Authorization", "Bearer "+nonApprover)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 403 {
		t.Fatalf("status = %d, want 403", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != "approver_not_authorized" {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinApproverSpecificCapabilityScope(t *testing.T) {
	ts := newApprovalGinServer(t)
	token := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	requestID := triggerApprovalGin(t, ts, token)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:transfer_funds"}, "")
	body := map[string]any{
		"approval_request_id": requestID,
		"grant_type":          core.GrantTypeOneTime,
	}
	bb, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(bb))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		raw, _ := io.ReadAll(resp.Body)
		t.Fatalf("status = %d, body=%s", resp.StatusCode, raw)
	}
}

func TestV023ApprovalGrantsGinAlreadyDecidedBeforeApproverAuth(t *testing.T) {
	// SPEC.md §4.9 line 1090: state check (decided / expired) runs BEFORE
	// approver authority. A second attempt with a non-approver token still
	// reports approval_request_already_decided.
	ts := newApprovalGinServer(t)
	token := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	requestID := triggerApprovalGin(t, ts, token)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := map[string]any{
		"approval_request_id": requestID,
		"grant_type":          core.GrantTypeOneTime,
	}
	bb, _ := json.Marshal(body)
	req1, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(bb))
	req1.Header.Set("Authorization", "Bearer "+approver)
	req1.Header.Set("Content-Type", "application/json")
	resp1, _ := http.DefaultClient.Do(req1)
	resp1.Body.Close()

	nonApprover := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	req2, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(bb))
	req2.Header.Set("Authorization", "Bearer "+nonApprover)
	req2.Header.Set("Content-Type", "application/json")
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != 409 {
		t.Fatalf("status = %d, want 409", resp2.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp2.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != "approval_request_already_decided" {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinSchemaRejectsMaxUsesNegative(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{"approval_request_id": "apr_x", "grant_type": "one_time", "max_uses": -1}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 400 {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters {
		t.Errorf("type = %v", failure["type"])
	}
}

// SPEC.md §4.9: when present, max_uses must be a positive integer.
func TestV023ApprovalGrantsGinSchemaRejectsMaxUsesZero(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{"approval_request_id": "apr_x", "grant_type": "one_time", "max_uses": 0}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 400 {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinSchemaRejectsExpiresInSecondsZero(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{"approval_request_id": "apr_x", "grant_type": "one_time", "expires_in_seconds": 0}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 400 {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinSchemaRejectsStringExpiresInSeconds(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{"approval_request_id": "apr_x", "grant_type": "one_time", "expires_in_seconds": "huge"}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 400 {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinSchemaRejectsEmptySessionID(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{"approval_request_id": "apr_x", "grant_type": "session_bound"}`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 400 {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023ApprovalGrantsGinMalformedJSON(t *testing.T) {
	ts := newApprovalGinServer(t)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")
	body := `{not json`
	req, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+approver)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 400 {
		t.Fatalf("status = %d, want 400", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != core.FailureInvalidParameters {
		t.Errorf("type = %v", failure["type"])
	}
}

func TestV023DiscoveryAdvertisesApprovalGrantsEndpointGin(t *testing.T) {
	ts := newApprovalGinServer(t)
	resp, err := http.Get(ts.URL + "/.well-known/anip")
	if err != nil {
		t.Fatalf("GET /.well-known/anip: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	disc, _ := data["anip_discovery"].(map[string]any)
	endpoints, _ := disc["endpoints"].(map[string]any)
	got, _ := endpoints["approval_grants"].(string)
	if got != "/anip/approval_grants" {
		t.Errorf("endpoints.approval_grants = %q", got)
	}
}

// --- End-to-end continuation through /anip/invoke -------------------------

func TestV023InvokeWithGrantConsumesGrantGin(t *testing.T) {
	ts := newApprovalGinServer(t)
	token := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "")
	requestID := triggerApprovalGin(t, ts, token)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")

	gb, _ := json.Marshal(map[string]any{
		"approval_request_id": requestID,
		"grant_type":          core.GrantTypeOneTime,
	})
	gReq, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(gb))
	gReq.Header.Set("Authorization", "Bearer "+approver)
	gReq.Header.Set("Content-Type", "application/json")
	gResp, gErr := http.DefaultClient.Do(gReq)
	if gErr != nil {
		t.Fatalf("approval_grants: %v", gErr)
	}
	defer gResp.Body.Close()
	var grant map[string]any
	json.NewDecoder(gResp.Body).Decode(&grant)
	grantID, _ := grant["grant_id"].(string)
	if grantID == "" {
		t.Fatal("grant_id empty")
	}

	body := map[string]any{
		"parameters": map[string]any{
			"amount":     50000,
			"to_account": "x",
		},
		"approval_grant": grantID,
	}
	bb, _ := json.Marshal(body)
	req1, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/transfer_funds", bytes.NewReader(bb))
	req1.Header.Set("Authorization", "Bearer "+token)
	req1.Header.Set("Content-Type", "application/json")
	resp1, err := http.DefaultClient.Do(req1)
	if err != nil {
		t.Fatalf("invoke 1: %v", err)
	}
	resp1.Body.Close()

	req2, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/transfer_funds", bytes.NewReader(bb))
	req2.Header.Set("Authorization", "Bearer "+token)
	req2.Header.Set("Content-Type", "application/json")
	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		t.Fatalf("invoke 2: %v", err)
	}
	defer resp2.Body.Close()
	var data map[string]any
	json.NewDecoder(resp2.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != "grant_consumed" {
		t.Errorf("second invoke failure type = %v, want grant_consumed", failure["type"])
	}
}

func TestV023InvokeWithSessionBoundGrantUsesTokenSessionIDGin(t *testing.T) {
	// SPEC.md §4.8 line 1035: session_id for session_bound grant validation
	// is read from the signed token, not from caller input. Body cannot
	// impersonate a different session.
	ts := newApprovalGinServer(t)
	sessToken := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "sess-A")
	requestID := triggerApprovalGin(t, ts, sessToken)
	approver := issueApprovalTokenGin(t, ts, []string{"finance.write", "approver:*"}, "")

	gb, _ := json.Marshal(map[string]any{
		"approval_request_id": requestID,
		"grant_type":          core.GrantTypeSessionBound,
		"session_id":          "sess-A",
	})
	gReq, _ := http.NewRequest("POST", ts.URL+"/anip/approval_grants", bytes.NewReader(gb))
	gReq.Header.Set("Authorization", "Bearer "+approver)
	gReq.Header.Set("Content-Type", "application/json")
	gResp, gErr := http.DefaultClient.Do(gReq)
	if gErr != nil {
		t.Fatalf("approval_grants: %v", gErr)
	}
	defer gResp.Body.Close()
	if gResp.StatusCode != 200 {
		raw, _ := io.ReadAll(gResp.Body)
		t.Fatalf("issuance status = %d, body=%s", gResp.StatusCode, raw)
	}
	var grant map[string]any
	json.NewDecoder(gResp.Body).Decode(&grant)
	grantID, _ := grant["grant_id"].(string)

	wrongToken := issueApprovalTokenGin(t, ts, []string{"finance.write"}, "sess-B")
	body := map[string]any{
		"parameters": map[string]any{
			"amount":     50000,
			"to_account": "x",
		},
		"approval_grant": grantID,
		"session_id":     "sess-A", // MUST be ignored by the runtime
	}
	bb, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", ts.URL+"/anip/invoke/transfer_funds", bytes.NewReader(bb))
	req.Header.Set("Authorization", "Bearer "+wrongToken)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("invoke: %v", err)
	}
	defer resp.Body.Close()
	var data map[string]any
	json.NewDecoder(resp.Body).Decode(&data)
	failure, _ := data["failure"].(map[string]any)
	if failure["type"] != "grant_session_invalid" {
		t.Errorf("type = %v, want grant_session_invalid", failure["type"])
	}
}
