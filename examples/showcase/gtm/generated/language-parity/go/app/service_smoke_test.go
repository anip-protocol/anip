package app

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"generated/gtm-pipeline-q2-review/generated"
)

func issueToken(t *testing.T, ts *httptest.Server, capabilityID string, scope []string) string {
	t.Helper()
	body := map[string]any{
		"capability": capabilityID,
		"scope": scope,
	}
	bodyBytes, _ := json.Marshal(body)
	req, _ := http.NewRequest(http.MethodPost, ts.URL+"/anip/tokens", bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer dev-admin-key")
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("token request failed: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 from token endpoint, got %d", resp.StatusCode)
	}
	var payload map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&payload)
	token, _ := payload["token"].(string)
	if token == "" {
		t.Fatal("expected token in response")
	}
	return token
}

func TestGeneratedServiceDiscoveryAndInvoke(t *testing.T) {
	svc, err := NewService()
	if err != nil {
		t.Fatalf("NewService: %v", err)
	}
	defer svc.Shutdown()
	ts := httptest.NewServer(NewMux(svc))
	defer ts.Close()

	discoveryResp, err := http.Get(ts.URL + "/.well-known/anip")
	if err != nil {
		t.Fatalf("discovery request failed: %v", err)
	}
	defer discoveryResp.Body.Close()
	if discoveryResp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 from discovery, got %d", discoveryResp.StatusCode)
	}

	capability := generated.GeneratedCapabilityMetadata[0]
	token := issueToken(t, ts, capability.CapabilityID, capability.MinimumScope)
	body := map[string]any{
		"parameters": capability.SampleParameters,
	}
	bodyBytes, _ := json.Marshal(body)
	req, _ := http.NewRequest(http.MethodPost, ts.URL+"/anip/invoke/"+capability.CapabilityID, bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("invoke request failed: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 from invoke, got %d", resp.StatusCode)
	}
	var payload struct {
		Success bool `json:"success"`
		Result map[string]any `json:"result"`
	}
	_ = json.NewDecoder(resp.Body).Decode(&payload)
	if !payload.Success {
		t.Fatal("expected successful invoke response")
	}
	if payload.Result["execution_status"] == nil {
		t.Fatal("expected execution_status in invoke response")
	}
}
