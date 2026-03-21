package mcpapi

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	mcpserver "github.com/mark3labs/mcp-go/server"

	"github.com/anip-protocol/anip/packages/go/service"
)

// McpServer is the interface required from the MCP server implementation.
// It is satisfied by *mcpserver.MCPServer from mcp-go.
type McpServer interface {
	AddTools(tools ...mcpserver.ServerTool)
}

// MountOptions configures the ANIP MCP mount.
type MountOptions struct {
	// Credentials for stdio transport (no per-request auth).
	Credentials *McpCredentials
	// EnrichDescriptions appends ANIP metadata to MCP tool descriptions.
	// Default: true.
	EnrichDescriptions *bool
}

func (o *MountOptions) enrichDescs() bool {
	if o == nil || o.EnrichDescriptions == nil {
		return true
	}
	return *o.EnrichDescriptions
}

// McpLifecycle provides lifecycle control over the mounted ANIP MCP service.
type McpLifecycle struct {
	svc *service.Service
}

// Stop halts the service (currently a no-op; kept for symmetry with TypeScript).
func (l *McpLifecycle) Stop() {
	// Service does not have a Stop; Shutdown releases resources.
}

// Shutdown releases all service resources (storage, keys).
func (l *McpLifecycle) Shutdown() error {
	return l.svc.Shutdown()
}

// MountAnipMCP registers ANIP capabilities as MCP tools on the given MCP server.
//
// This function:
//  1. Validates that credentials are provided (required for stdio transport).
//  2. Starts the ANIP service lifecycle.
//  3. Builds MCP tools from the service manifest.
//  4. Registers tool handlers that authenticate via mount-time credentials.
//  5. Returns a lifecycle handle for shutdown.
func MountAnipMCP(target McpServer, svc *service.Service, opts *MountOptions) (*McpLifecycle, error) {
	if opts == nil || opts.Credentials == nil {
		return nil, fmt.Errorf(
			"MountAnipMCP requires credentials for stdio transport. " +
				"Provide MountOptions with Credentials set.",
		)
	}

	creds := opts.Credentials
	enrichDescs := opts.enrichDescs()

	// Start the ANIP service
	if err := svc.Start(); err != nil {
		return nil, fmt.Errorf("start service: %w", err)
	}

	// Build tool list from manifest
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

		// Set MCP annotations based on side-effect type
		readOnly := fullDecl.SideEffect.Type == "read"
		destructive := fullDecl.SideEffect.Type == "irreversible"

		tool := mcp.NewTool(capName,
			mcp.WithDescription(description),
			mcp.WithRawInputSchema(json.RawMessage(schemaBytes)),
			mcp.WithReadOnlyHintAnnotation(readOnly),
			mcp.WithDestructiveHintAnnotation(destructive),
		)

		handler := func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			args := request.GetArguments()
			if args == nil {
				args = make(map[string]any)
			}

			result := InvokeWithMountCredentials(svc, capName, args, creds)

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

	// Register all tools
	target.AddTools(tools...)

	return &McpLifecycle{svc: svc}, nil
}

// NewMCPServer creates a new mcp-go MCPServer pre-configured for ANIP.
func NewMCPServer() *mcpserver.MCPServer {
	return mcpserver.NewMCPServer("anip-mcp", "0.11.0")
}

// ServeStdio is a convenience function that creates an MCP server with ANIP
// capabilities and serves it over stdio. This blocks until the process
// receives SIGTERM/SIGINT or stdin closes.
func ServeStdio(svc *service.Service, opts *MountOptions) error {
	mcpSrv := NewMCPServer()

	lifecycle, err := MountAnipMCP(mcpSrv, svc, opts)
	if err != nil {
		return err
	}
	defer lifecycle.Shutdown()

	return mcpserver.ServeStdio(mcpSrv)
}

// ToolNames returns the names of all capabilities that would be registered as
// MCP tools. Useful for testing and introspection.
func ToolNames(svc *service.Service) []string {
	manifest := svc.GetManifest()
	var names []string
	for name := range manifest.Capabilities {
		names = append(names, name)
	}
	return names
}

// NarrowScope filters the given scope entries to only include those matching
// the capability's minimum_scope. Exported for testing.
func NarrowScope(mountScope []string, minScope []string) []string {
	if len(minScope) == 0 {
		return mountScope
	}

	needed := make(map[string]bool)
	for _, s := range minScope {
		needed[s] = true
	}

	var narrowed []string
	for _, s := range mountScope {
		base := strings.SplitN(s, ":", 2)[0]
		if needed[base] || needed[s] {
			narrowed = append(narrowed, s)
		}
	}

	if len(narrowed) > 0 {
		return narrowed
	}
	return mountScope
}
