package mcpapi

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/client/transport"
	"github.com/mark3labs/mcp-go/mcp"

	"github.com/anip-protocol/anip/packages/go/service"
)

// newHTTPTestService creates a test service without calling Start (the mount
// functions call Start themselves).
func newHTTPTestService(t *testing.T) *service.Service {
	t.Helper()
	svc := service.New(service.Config{
		ServiceID:    "test-mcp-http-service",
		Capabilities: testCapabilities(),
		Storage:      ":memory:",
		Trust:        "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-api-key" {
				return "human:test@example.com", true
			}
			return "", false
		},
	})
	t.Cleanup(func() { svc.Shutdown() })
	return svc
}

// startHTTPTestServer creates a StreamableHTTPServer backed by a test service and
// returns the httptest.Server URL. It uses the raw newStreamableHTTPServer helper
// (same as MountAnipMcpHTTP uses internally) to avoid dealing with ServeMux path
// routing in tests.
func startHTTPTestServer(t *testing.T) (string, *service.Service) {
	t.Helper()
	svc := newHTTPTestService(t)
	if err := svc.Start(); err != nil {
		t.Fatalf("svc.Start(): %v", err)
	}

	httpServer := newStreamableHTTPServer(svc, true)
	ts := httptest.NewServer(httpServer)
	t.Cleanup(ts.Close)
	return ts.URL, svc
}

// mcpClient creates an MCP StreamableHTTP client pointed at url with optional
// auth header.
func mcpClient(t *testing.T, url string, bearer string) *client.Client {
	t.Helper()
	var opts []transport.StreamableHTTPCOption
	if bearer != "" {
		opts = append(opts, transport.WithHTTPHeaders(map[string]string{
			"Authorization": "Bearer " + bearer,
		}))
	}
	c, err := client.NewStreamableHttpClient(url, opts...)
	if err != nil {
		t.Fatalf("NewStreamableHttpClient: %v", err)
	}
	t.Cleanup(func() { c.Close() })

	ctx := context.Background()
	if err := c.Start(ctx); err != nil {
		t.Fatalf("client.Start: %v", err)
	}
	return c
}

// --- net/http tests ---

func TestHTTP_InitializeAndListTools(t *testing.T) {
	url, _ := startHTTPTestServer(t)

	c := mcpClient(t, url, "test-api-key")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	toolsResult, err := c.ListTools(context.Background(), mcp.ListToolsRequest{})
	if err != nil {
		t.Fatalf("ListTools: %v", err)
	}

	if len(toolsResult.Tools) != 2 {
		t.Fatalf("expected 2 tools, got %d", len(toolsResult.Tools))
	}

	found := make(map[string]bool)
	for _, tool := range toolsResult.Tools {
		found[tool.Name] = true
	}
	if !found["greet"] || !found["book"] {
		t.Errorf("expected greet and book tools, got: %v", found)
	}
}

func TestHTTP_CallToolWithValidAPIKey(t *testing.T) {
	url, _ := startHTTPTestServer(t)

	c := mcpClient(t, url, "test-api-key")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	callReq := mcp.CallToolRequest{}
	callReq.Params.Name = "greet"
	callReq.Params.Arguments = map[string]any{"name": "Alice"}

	result, err := c.CallTool(context.Background(), callReq)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}

	if result.IsError {
		t.Fatalf("expected success, got error: %v", result.Content)
	}

	text := extractTextContent(t, result)
	if !strings.Contains(text, "Hello, Alice!") {
		t.Errorf("expected greeting, got: %s", text)
	}
}

func TestHTTP_CallToolWithoutAuth(t *testing.T) {
	url, _ := startHTTPTestServer(t)

	// No bearer token
	c := mcpClient(t, url, "")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	callReq := mcp.CallToolRequest{}
	callReq.Params.Name = "greet"
	callReq.Params.Arguments = map[string]any{"name": "Alice"}

	result, err := c.CallTool(context.Background(), callReq)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}

	if !result.IsError {
		t.Fatal("expected error for unauthenticated call")
	}

	text := extractTextContent(t, result)
	if !strings.Contains(text, "authentication_required") {
		t.Errorf("expected authentication_required, got: %s", text)
	}
}

func TestHTTP_CallToolWithInvalidAPIKey(t *testing.T) {
	url, _ := startHTTPTestServer(t)

	c := mcpClient(t, url, "bad-key")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	callReq := mcp.CallToolRequest{}
	callReq.Params.Name = "greet"
	callReq.Params.Arguments = map[string]any{"name": "Alice"}

	result, err := c.CallTool(context.Background(), callReq)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}

	if !result.IsError {
		t.Fatal("expected error for invalid API key")
	}

	text := extractTextContent(t, result)
	if !strings.Contains(text, "FAILED") {
		t.Errorf("expected FAILED in error text, got: %s", text)
	}
}

// --- Gin tests ---

func TestHTTP_Gin_InitializeAndListTools(t *testing.T) {
	gin.SetMode(gin.TestMode)

	svc := newHTTPTestService(t)
	if err := svc.Start(); err != nil {
		t.Fatalf("svc.Start(): %v", err)
	}

	router := gin.New()
	httpServer := newStreamableHTTPServer(svc, true)
	router.Any("/mcp", gin.WrapH(httpServer))

	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)

	c := mcpClient(t, ts.URL+"/mcp", "test-api-key")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	toolsResult, err := c.ListTools(context.Background(), mcp.ListToolsRequest{})
	if err != nil {
		t.Fatalf("ListTools: %v", err)
	}

	if len(toolsResult.Tools) != 2 {
		t.Fatalf("expected 2 tools, got %d", len(toolsResult.Tools))
	}
}

func TestHTTP_Gin_CallToolWithValidAPIKey(t *testing.T) {
	gin.SetMode(gin.TestMode)

	svc := newHTTPTestService(t)
	if err := svc.Start(); err != nil {
		t.Fatalf("svc.Start(): %v", err)
	}

	router := gin.New()
	httpServer := newStreamableHTTPServer(svc, true)
	router.Any("/mcp", gin.WrapH(httpServer))

	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)

	c := mcpClient(t, ts.URL+"/mcp", "test-api-key")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	callReq := mcp.CallToolRequest{}
	callReq.Params.Name = "greet"
	callReq.Params.Arguments = map[string]any{"name": "Bob"}

	result, err := c.CallTool(context.Background(), callReq)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}

	if result.IsError {
		t.Fatalf("expected success, got error: %v", result.Content)
	}

	text := extractTextContent(t, result)
	if !strings.Contains(text, "Hello, Bob!") {
		t.Errorf("expected greeting, got: %s", text)
	}
}

func TestHTTP_Gin_CallToolWithoutAuth(t *testing.T) {
	gin.SetMode(gin.TestMode)

	svc := newHTTPTestService(t)
	if err := svc.Start(); err != nil {
		t.Fatalf("svc.Start(): %v", err)
	}

	router := gin.New()
	httpServer := newStreamableHTTPServer(svc, true)
	router.Any("/mcp", gin.WrapH(httpServer))

	ts := httptest.NewServer(router)
	t.Cleanup(ts.Close)

	c := mcpClient(t, ts.URL+"/mcp", "")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	callReq := mcp.CallToolRequest{}
	callReq.Params.Name = "greet"
	callReq.Params.Arguments = map[string]any{"name": "Alice"}

	result, err := c.CallTool(context.Background(), callReq)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}

	if !result.IsError {
		t.Fatal("expected error for unauthenticated call")
	}

	text := extractTextContent(t, result)
	if !strings.Contains(text, "authentication_required") {
		t.Errorf("expected authentication_required, got: %s", text)
	}
}

// --- MountAnipMcpHTTP integration test ---

func TestMountAnipMcpHTTP_Integration(t *testing.T) {
	svc := newHTTPTestService(t)

	mux := http.NewServeMux()
	MountAnipMcpHTTP(mux, svc, &McpHTTPOptions{
		Path: "/mcp",
	})

	ts := httptest.NewServer(mux)
	t.Cleanup(ts.Close)

	c := mcpClient(t, ts.URL+"/mcp", "test-api-key")

	initReq := mcp.InitializeRequest{}
	initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initReq.Params.ClientInfo = mcp.Implementation{
		Name:    "test-client",
		Version: "0.1.0",
	}

	_, err := c.Initialize(context.Background(), initReq)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	toolsResult, err := c.ListTools(context.Background(), mcp.ListToolsRequest{})
	if err != nil {
		t.Fatalf("ListTools: %v", err)
	}

	if len(toolsResult.Tools) != 2 {
		t.Fatalf("expected 2 tools, got %d", len(toolsResult.Tools))
	}

	callReq := mcp.CallToolRequest{}
	callReq.Params.Name = "greet"
	callReq.Params.Arguments = map[string]any{"name": "MountHTTP"}

	result, err := c.CallTool(context.Background(), callReq)
	if err != nil {
		t.Fatalf("CallTool: %v", err)
	}

	if result.IsError {
		t.Fatalf("expected success, got error: %v", result.Content)
	}

	text := extractTextContent(t, result)
	if !strings.Contains(text, "Hello, MountHTTP!") {
		t.Errorf("expected greeting, got: %s", text)
	}
}

// --- ResolveAuth unit tests ---

func TestResolveAuth_ValidAPIKey(t *testing.T) {
	svc := newTestService(t)

	token, err := ResolveAuth("test-api-key", svc, "greet")
	if err != nil {
		t.Fatalf("ResolveAuth: %v", err)
	}
	if token == nil {
		t.Fatal("expected non-nil token")
	}
}

func TestResolveAuth_InvalidBearer(t *testing.T) {
	svc := newTestService(t)

	_, err := ResolveAuth("bad-key", svc, "greet")
	if err == nil {
		t.Fatal("expected error for invalid bearer")
	}
}

// --- Helper ---

func extractTextContent(t *testing.T, result *mcp.CallToolResult) string {
	t.Helper()
	for _, c := range result.Content {
		if tc, ok := c.(mcp.TextContent); ok {
			return tc.Text
		}
	}
	t.Fatal("no text content in result")
	return ""
}
