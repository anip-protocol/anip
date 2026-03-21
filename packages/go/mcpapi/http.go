package mcpapi

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// contextKey is a private type for context keys to avoid collisions.
type contextKey string

const bearerContextKey contextKey = "anip-mcp-bearer"

func contextWithBearer(ctx context.Context, bearer string) context.Context {
	return context.WithValue(ctx, bearerContextKey, bearer)
}

func bearerFromContext(ctx context.Context) string {
	v, _ := ctx.Value(bearerContextKey).(string)
	return v
}

// McpHTTPOptions configures the MCP Streamable HTTP mount.
type McpHTTPOptions struct {
	// Path is the HTTP endpoint path. Default: "/mcp".
	Path string
	// EnrichDescriptions appends ANIP metadata to MCP tool descriptions.
	// Default: true.
	EnrichDescriptions *bool
}

func (o *McpHTTPOptions) path() string {
	if o == nil || o.Path == "" {
		return "/mcp"
	}
	return o.Path
}

func (o *McpHTTPOptions) enrichDescs() bool {
	if o == nil || o.EnrichDescriptions == nil {
		return true
	}
	return *o.EnrichDescriptions
}

// ResolveAuth resolves auth from a bearer token string for HTTP MCP transport.
// JWT-first, API-key fallback. Same pattern as restapi/auth.go.
//
//  1. Try svc.ResolveBearerToken(bearer) — JWT mode, preserves delegation chain
//  2. If ANIPError → try svc.AuthenticateBearer(bearer) — API key mode
//  3. If API key works → issue synthetic token scoped to the capability
//  4. If neither works → re-throw the original JWT error
//  5. Only catch ANIPError from JWT resolution, rethrow anything else
func ResolveAuth(bearer string, svc *service.Service, capabilityName string) (*core.DelegationToken, error) {
	// Try as JWT first — preserves original delegation chain
	var jwtError *core.ANIPError
	token, err := svc.ResolveBearerToken(bearer)
	if err == nil {
		return token, nil
	}

	// Only catch ANIPError from JWT resolution
	anipErr, isANIP := err.(*core.ANIPError)
	if !isANIP {
		return nil, err
	}
	jwtError = anipErr

	// Try as API key — only if JWT failed with ANIPError
	principal, ok := svc.AuthenticateBearer(bearer)
	if ok && principal != "" {
		// This is a real API key — issue synthetic token
		capDecl := svc.GetCapabilityDeclaration(capabilityName)
		var minScope []string
		if capDecl != nil {
			minScope = capDecl.MinimumScope
		}
		if len(minScope) == 0 {
			minScope = []string{"*"}
		}

		tokenResult, issueErr := svc.IssueToken(principal, core.TokenRequest{
			Subject:           "adapter:anip-mcp",
			Scope:             minScope,
			Capability:        capabilityName,
			PurposeParameters: map[string]any{"source": "mcp-http"},
		})
		if issueErr != nil {
			// API key authenticated but token issuance failed — surface the real error
			return nil, issueErr
		}

		return svc.ResolveBearerToken(tokenResult.Token)
	}

	// Neither JWT nor API key — surface the original JWT error
	return nil, jwtError
}

// buildHTTPTools builds MCP tools with per-request auth handlers for HTTP transport.
func buildHTTPTools(svc *service.Service, enrichDescs bool) []mcpserver.ServerTool {
	manifest := svc.GetManifest()
	var tools []mcpserver.ServerTool

	for name := range manifest.Capabilities {
		capName := name // capture for closure
		fullDecl := svc.GetCapabilityDeclaration(capName)
		if fullDecl == nil {
			continue
		}

		// Build description
		description := fullDecl.Description
		if enrichDescs {
			description = EnrichDescription(fullDecl)
		}

		// Build input schema as raw JSON
		inputSchema := CapabilityToInputSchema(fullDecl)
		schemaBytes, err := json.Marshal(inputSchema)
		if err != nil {
			continue
		}

		// Build tool with raw schema (avoids InputSchema/RawInputSchema conflict)
		readOnly := fullDecl.SideEffect.Type == "read"
		destructive := fullDecl.SideEffect.Type == "irreversible"

		tool := mcp.NewToolWithRawSchema(capName, description, json.RawMessage(schemaBytes))
		tool.Annotations = mcp.ToolAnnotation{
			ReadOnlyHint:    mcp.ToBoolPtr(readOnly),
			DestructiveHint: mcp.ToBoolPtr(destructive),
		}

		handler := func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			args := request.GetArguments()
			if args == nil {
				args = make(map[string]any)
			}

			// Extract bearer from context (set by WithHTTPContextFunc)
			bearer := bearerFromContext(ctx)
			if bearer == "" {
				return mcp.NewToolResultError(
					"FAILED: authentication_required\nDetail: No Authorization header provided\nRetryable: no",
				), nil
			}

			// Resolve auth: JWT-first, API-key fallback
			token, err := ResolveAuth(bearer, svc, capName)
			if err != nil {
				if anipErr, ok := err.(*core.ANIPError); ok {
					return mcp.NewToolResultError(
						fmt.Sprintf("FAILED: %s\nDetail: %s\nRetryable: no", anipErr.ErrorType, anipErr.Detail),
					), nil
				}
				return mcp.NewToolResultError(
					fmt.Sprintf("FAILED: authentication_failed\nDetail: %s\nRetryable: no", err.Error()),
				), nil
			}

			result := InvokeWithToken(svc, capName, args, token)
			if result.IsError {
				return mcp.NewToolResultError(result.Text), nil
			}
			return mcp.NewToolResultText(result.Text), nil
		}

		tools = append(tools, mcpserver.ServerTool{
			Tool:    tool,
			Handler: handler,
		})
	}

	return tools
}

// newStreamableHTTPServer creates a StreamableHTTPServer with ANIP tools and per-request auth.
func newStreamableHTTPServer(svc *service.Service, enrichDescs bool) *mcpserver.StreamableHTTPServer {
	mcpSrv := NewMCPServer()

	// Build and register tools with HTTP auth handlers
	tools := buildHTTPTools(svc, enrichDescs)
	mcpSrv.AddTools(tools...)

	// Extract bearer from Authorization header and inject into context
	ctxFunc := func(ctx context.Context, r *http.Request) context.Context {
		auth := r.Header.Get("Authorization")
		if strings.HasPrefix(auth, "Bearer ") {
			bearer := strings.TrimPrefix(auth, "Bearer ")
			ctx = contextWithBearer(ctx, bearer)
		}
		return ctx
	}

	return mcpserver.NewStreamableHTTPServer(mcpSrv,
		mcpserver.WithStateLess(true),
		mcpserver.WithHTTPContextFunc(ctxFunc),
	)
}

// MountAnipMcpHTTP mounts MCP Streamable HTTP on a net/http ServeMux.
// Per-request auth is resolved from the Authorization: Bearer header.
// JWT-first, API-key fallback.
func MountAnipMcpHTTP(mux *http.ServeMux, svc *service.Service, opts *McpHTTPOptions) {
	if err := svc.Start(); err != nil {
		panic(fmt.Sprintf("mcpapi: start service: %v", err))
	}

	enrichDescs := opts.enrichDescs()
	path := opts.path()

	httpServer := newStreamableHTTPServer(svc, enrichDescs)

	// The StreamableHTTPServer implements http.Handler.
	// Mount it at the configured path.
	mux.Handle(path, httpServer)
}

// MountAnipMcpHTTPGin mounts MCP Streamable HTTP on a Gin router.
// Per-request auth is resolved from the Authorization: Bearer header.
// JWT-first, API-key fallback.
func MountAnipMcpHTTPGin(router *gin.Engine, svc *service.Service, opts *McpHTTPOptions) {
	if err := svc.Start(); err != nil {
		panic(fmt.Sprintf("mcpapi: start service: %v", err))
	}

	enrichDescs := opts.enrichDescs()
	path := opts.path()

	httpServer := newStreamableHTTPServer(svc, enrichDescs)

	// Gin requires explicit method registration; use Any to handle POST/GET/DELETE.
	router.Any(path, gin.WrapH(httpServer))
}
