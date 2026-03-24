package stdioapi

import (
	"encoding/json"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// newTestService creates a service with an echo capability for testing.
func newTestService(t *testing.T) *service.Service {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID: "test-stdio-service",
		Capabilities: []service.CapabilityDef{
			{
				Declaration: core.CapabilityDeclaration{
					Name:            "echo",
					Description:     "Echoes input back",
					ContractVersion: "1.0",
					Inputs: []core.CapabilityInput{
						{Name: "message", Type: "string", Required: false},
					},
					Output: core.CapabilityOutput{
						Type:   "object",
						Fields: []string{"echo"},
					},
					SideEffect: core.SideEffect{
						Type:           "read",
						RollbackWindow: "not_applicable",
					},
					MinimumScope:  []string{"echo"},
					ResponseModes: []string{"unary"},
				},
				Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
					msg, _ := params["message"].(string)
					if msg == "" {
						msg = "hello"
					}
					return map[string]any{"echo": msg}, nil
				},
			},
		},
		Storage: ":memory:",
		Trust:   "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-api-key" {
				return "human:tester@example.com", true
			}
			return "", false
		},
		RetentionIntervalSeconds: -1, // disable background retention
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	return svc
}

// issueTestToken issues a token via API key auth and returns the JWT string.
func issueTestToken(t *testing.T, svc *service.Service) string {
	t.Helper()
	resp, err := svc.IssueToken("human:tester@example.com", core.TokenRequest{
		Subject:    "human:tester@example.com",
		Scope:      []string{"echo"},
		Capability: "echo",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected token to be issued")
	}
	return resp.Token
}

// dispatch is a test helper that calls HandleRequest and returns the responses.
func dispatch(t *testing.T, srv *Server, method string, params map[string]any) []any {
	t.Helper()
	var rawParams json.RawMessage
	if params != nil {
		data, _ := json.Marshal(params)
		rawParams = data
	}
	req := request{
		JSONRPC: "2.0",
		ID:      json.RawMessage(`1`),
		Method:  method,
		Params:  rawParams,
	}
	return srv.HandleRequest(req)
}

// expectSuccess extracts the result from a single success response.
func expectSuccess(t *testing.T, messages []any) map[string]any {
	t.Helper()
	if len(messages) != 1 {
		t.Fatalf("expected 1 message, got %d", len(messages))
	}
	resp, ok := messages[0].(response)
	if !ok {
		t.Fatalf("expected response, got %T", messages[0])
	}
	if resp.Error != nil {
		t.Fatalf("unexpected error: code=%d message=%s", resp.Error.Code, resp.Error.Message)
	}
	// Convert result to map.
	data, _ := json.Marshal(resp.Result)
	var result map[string]any
	json.Unmarshal(data, &result)
	return result
}

// expectError extracts the error from a single error response.
func expectError(t *testing.T, messages []any, expectedCode int) *rpcError {
	t.Helper()
	if len(messages) != 1 {
		t.Fatalf("expected 1 message, got %d", len(messages))
	}
	resp, ok := messages[0].(response)
	if !ok {
		t.Fatalf("expected response, got %T", messages[0])
	}
	if resp.Error == nil {
		t.Fatal("expected error response, got success")
	}
	if resp.Error.Code != expectedCode {
		t.Fatalf("expected error code %d, got %d (message: %s)", expectedCode, resp.Error.Code, resp.Error.Message)
	}
	return resp.Error
}

func TestDiscovery(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.discovery", nil))

	disc, ok := result["anip_discovery"].(map[string]any)
	if !ok {
		t.Fatal("expected anip_discovery object in result")
	}
	if disc["protocol"] != core.ProtocolVersion {
		t.Fatalf("expected protocol %q, got %v", core.ProtocolVersion, disc["protocol"])
	}
	caps, ok := disc["capabilities"].(map[string]any)
	if !ok {
		t.Fatal("expected capabilities map")
	}
	if _, ok := caps["echo"]; !ok {
		t.Fatal("expected echo capability in discovery")
	}
}

func TestManifest(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.manifest", nil))

	if result["manifest"] == nil {
		t.Fatal("expected manifest in result")
	}
	if result["signature"] == nil {
		t.Fatal("expected signature in result")
	}
}

func TestJWKS(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.jwks", nil))

	if result["keys"] == nil {
		t.Fatal("expected keys in JWKS result")
	}
}

func TestTokensIssue(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.tokens.issue", map[string]any{
		"auth": map[string]any{
			"bearer": "test-api-key",
		},
		"subject":    "human:tester@example.com",
		"scope":      []string{"echo"},
		"capability": "echo",
	}))

	if result["issued"] != true {
		t.Fatal("expected issued=true")
	}
	if result["token"] == nil || result["token"] == "" {
		t.Fatal("expected non-empty token")
	}
	if result["token_id"] == nil || result["token_id"] == "" {
		t.Fatal("expected non-empty token_id")
	}
}

func TestTokensIssueNoAuth(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.tokens.issue", nil), codeAuthError)
}

func TestTokensIssueBadKey(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.tokens.issue", map[string]any{
		"auth": map[string]any{
			"bearer": "invalid-key",
		},
		"subject":    "human:tester@example.com",
		"scope":      []string{"echo"},
		"capability": "echo",
	}), codeAuthError)
}

func TestPermissions(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	jwt := issueTestToken(t, svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.permissions", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
	}))

	if result["available"] == nil {
		t.Fatal("expected available in permissions result")
	}
}

func TestPermissionsNoAuth(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.permissions", nil), codeAuthError)
}

func TestInvoke(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	jwt := issueTestToken(t, svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.invoke", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
		"capability": "echo",
		"parameters": map[string]any{
			"message": "world",
		},
	}))

	if result["success"] != true {
		t.Fatalf("expected success=true, got %v", result["success"])
	}
	resultObj, ok := result["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected result object, got %T", result["result"])
	}
	if resultObj["echo"] != "world" {
		t.Fatalf("expected echo='world', got %v", resultObj["echo"])
	}
}

func TestInvokeNoAuth(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.invoke", map[string]any{
		"capability": "echo",
		"parameters": map[string]any{},
	}), codeAuthError)
}

func TestInvokeNoCapability(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	jwt := issueTestToken(t, svc)

	expectError(t, dispatch(t, srv, "anip.invoke", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
		"parameters": map[string]any{},
	}), codeNotFound)
}

func TestAuditQuery(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	jwt := issueTestToken(t, svc)

	// Invoke to create an audit entry first.
	dispatch(t, srv, "anip.invoke", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
		"capability": "echo",
		"parameters": map[string]any{"message": "audit-test"},
	})

	result := expectSuccess(t, dispatch(t, srv, "anip.audit.query", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
	}))

	if result["entries"] == nil {
		t.Fatal("expected entries in audit result")
	}
}

func TestAuditQueryNoAuth(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.audit.query", nil), codeAuthError)
}

func TestCheckpointsList(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	result := expectSuccess(t, dispatch(t, srv, "anip.checkpoints.list", nil))

	if result["checkpoints"] == nil {
		t.Fatal("expected checkpoints in result")
	}
}

func TestCheckpointsGet(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	// Request a non-existent checkpoint — should get not_found error.
	expectError(t, dispatch(t, srv, "anip.checkpoints.get", map[string]any{
		"id": "nonexistent-checkpoint",
	}), codeNotFound)
}

func TestCheckpointsGetNoID(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.checkpoints.get", nil), codeNotFound)
}

func TestUnknownMethod(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	expectError(t, dispatch(t, srv, "anip.nonexistent", nil), codeMethodNotFound)
}

func TestInvalidRequest(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	// Missing jsonrpc field.
	messages := srv.HandleRequest(request{
		ID:     json.RawMessage(`1`),
		Method: "anip.discovery",
	})
	expectError(t, messages, codeInvalidRequest)

	// Missing ID.
	messages = srv.HandleRequest(request{
		JSONRPC: "2.0",
		Method:  "anip.discovery",
	})
	expectError(t, messages, codeInvalidRequest)

	// Missing method.
	messages = srv.HandleRequest(request{
		JSONRPC: "2.0",
		ID:      json.RawMessage(`1`),
	})
	expectError(t, messages, codeInvalidRequest)
}

func TestParseError(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	// Feed invalid JSON.
	messages := srv.handleLine([]byte(`{not valid json`))
	expectError(t, messages, codeParseError)
}

func TestTokensIssueViaJWT(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	// First issue a token via API key to get a JWT.
	jwt := issueTestToken(t, svc)

	// Issue a sub-token using the JWT as auth (not as parent_token).
	result := expectSuccess(t, dispatch(t, srv, "anip.tokens.issue", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
		"subject":    "agent:sub-agent",
		"scope":      []string{"echo"},
		"capability": "echo",
	}))

	if result["issued"] != true {
		t.Fatal("expected issued=true for JWT-based token issuance")
	}
}

func TestInvokeDefaultMessage(t *testing.T) {
	svc := newTestService(t)
	defer svc.Shutdown()
	srv := NewServer(svc)

	jwt := issueTestToken(t, svc)

	// Invoke echo without a message param — handler defaults to "hello".
	result := expectSuccess(t, dispatch(t, srv, "anip.invoke", map[string]any{
		"auth": map[string]any{
			"bearer": jwt,
		},
		"capability": "echo",
		"parameters": map[string]any{},
	}))

	if result["success"] != true {
		t.Fatalf("expected success=true, got %v", result["success"])
	}
	resultObj, ok := result["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected result object, got %T", result["result"])
	}
	if resultObj["echo"] != "hello" {
		t.Fatalf("expected echo='hello', got %v", resultObj["echo"])
	}
}
