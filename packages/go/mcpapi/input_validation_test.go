// Parameter validation through the MCP adapter (SPEC.md §6.3): a refused
// invocation is a tool error (isError) that carries the failure, not a
// successful tool result.

package mcpapi

import (
	"context"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/mark3labs/mcp-go/mcp"
)

func assertInvalidParametersToolError(t *testing.T, isError bool, text, detail string) {
	t.Helper()
	if !isError {
		t.Fatalf("expected a tool error, got a successful result: %s", text)
	}
	want := strings.Join([]string{
		"FAILED: invalid_parameters",
		"Detail: " + detail,
		"Resolution: retry_now",
		"Requires: parameters that match the capability's declared inputs",
		"Retryable: no",
	}, "\n")
	if text != want {
		t.Fatalf("tool error text =\n%s\nwant\n%s", text, want)
	}
}

func TestInvokeWithMountCredentials_InvalidParameters(t *testing.T) {
	svc := newTestService(t)
	creds := &McpCredentials{APIKey: "test-api-key", Scope: []string{"greet"}, Subject: "adapter:mcp-test"}

	result := InvokeWithMountCredentials(svc, "greet", map[string]any{"count": 2}, creds)
	assertInvalidParametersToolError(t, result.IsError, result.Text, "greet is missing required input(s): name")

	result = InvokeWithMountCredentials(svc, "greet", nil, creds)
	assertInvalidParametersToolError(t, result.IsError, result.Text, "greet is missing required input(s): name")

	result = InvokeWithMountCredentials(svc, "greet", map[string]any{"name": "Alice", "count": "two", "loud": 1}, creds)
	assertInvalidParametersToolError(t, result.IsError, result.Text,
		"greet has invalid input(s): 'count' must be integer, got string; 'loud' must be boolean, got number")

	// Control: valid arguments, with the integer written as 2.0.
	result = InvokeWithMountCredentials(svc, "greet", map[string]any{"name": "Alice", "count": 2.0}, creds)
	if result.IsError || !strings.Contains(result.Text, "Hello, Alice!") {
		t.Fatalf("control: expected the greeting, got isError=%v %s", result.IsError, result.Text)
	}
}

func TestHTTP_CallToolWithInvalidParameters(t *testing.T) {
	plainURL, _ := startHTTPTestServer(t)

	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Any("/mcp", gin.WrapH(newStreamableHTTPServer(newHTTPTestService(t), true)))
	ginServer := httptest.NewServer(router)
	t.Cleanup(ginServer.Close)

	for name, url := range map[string]string{"net/http": plainURL, "gin": ginServer.URL + "/mcp"} {
		t.Run(name, func(t *testing.T) {
			c := mcpClient(t, url, "test-api-key")
			initReq := mcp.InitializeRequest{}
			initReq.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
			initReq.Params.ClientInfo = mcp.Implementation{Name: "test-client", Version: "0.1.0"}
			if _, err := c.Initialize(context.Background(), initReq); err != nil {
				t.Fatalf("Initialize: %v", err)
			}

			callReq := mcp.CallToolRequest{}
			callReq.Params.Name = "greet"
			callReq.Params.Arguments = map[string]any{}
			result, err := c.CallTool(context.Background(), callReq)
			if err != nil {
				t.Fatalf("CallTool: %v", err)
			}
			assertInvalidParametersToolError(t, result.IsError, extractTextContent(t, result), "greet is missing required input(s): name")

			callReq.Params.Arguments = map[string]any{"name": 7}
			result, err = c.CallTool(context.Background(), callReq)
			if err != nil {
				t.Fatalf("CallTool: %v", err)
			}
			assertInvalidParametersToolError(t, result.IsError, extractTextContent(t, result), "greet has invalid input(s): 'name' must be string, got number")
		})
	}
}
