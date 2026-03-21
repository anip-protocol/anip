package mcpapi

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// McpCredentials holds mount-time authentication credentials for stdio transport.
// Since stdio has no per-request auth (no HTTP headers), credentials are provided
// once at mount time and used for all tool invocations.
type McpCredentials struct {
	APIKey  string
	Scope   []string
	Subject string
}

// InvokeResult is the outcome of an MCP tool invocation.
type InvokeResult struct {
	Text    string
	IsError bool
}

// InvokeWithMountCredentials authenticates using mount-time credentials,
// narrows scope to the capability's minimum_scope, issues a synthetic
// delegation token, and invokes the capability.
func InvokeWithMountCredentials(svc *service.Service, capName string, args map[string]any, creds *McpCredentials) InvokeResult {
	// 1. Authenticate the bootstrap credential
	principal, ok := svc.AuthenticateBearer(creds.APIKey)
	if !ok || principal == "" {
		return InvokeResult{
			Text:    "FAILED: authentication_required\nDetail: Invalid bootstrap credential\nRetryable: no",
			IsError: true,
		}
	}

	// 2. Narrow scope to what the capability needs
	capDecl := svc.GetCapabilityDeclaration(capName)
	capScope := creds.Scope
	if capDecl != nil && len(capDecl.MinimumScope) > 0 {
		needed := make(map[string]bool)
		for _, s := range capDecl.MinimumScope {
			needed[s] = true
		}
		var narrowed []string
		for _, s := range creds.Scope {
			base := strings.SplitN(s, ":", 2)[0]
			if needed[base] || needed[s] {
				narrowed = append(narrowed, s)
			}
		}
		if len(narrowed) > 0 {
			capScope = narrowed
		}
	}

	// 3. Issue a synthetic token
	tokenResult, err := svc.IssueToken(principal, core.TokenRequest{
		Subject:           creds.Subject,
		Scope:             capScope,
		Capability:        capName,
		PurposeParameters: map[string]any{"source": "mcp"},
	})
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			return InvokeResult{
				Text:    fmt.Sprintf("FAILED: %s\nDetail: %s\nRetryable: no", anipErr.ErrorType, anipErr.Detail),
				IsError: true,
			}
		}
		return InvokeResult{
			Text:    fmt.Sprintf("FAILED: internal_error\nDetail: %s\nRetryable: no", err.Error()),
			IsError: true,
		}
	}

	// 4. Resolve the JWT into a DelegationToken
	token, err := svc.ResolveBearerToken(tokenResult.Token)
	if err != nil {
		return InvokeResult{
			Text:    fmt.Sprintf("FAILED: invalid_token\nDetail: %s\nRetryable: no", err.Error()),
			IsError: true,
		}
	}

	// 5. Invoke with the resolved token
	return InvokeWithToken(svc, capName, args, token)
}

// InvokeWithToken invokes a capability with an already-resolved delegation token.
func InvokeWithToken(svc *service.Service, capName string, args map[string]any, token *core.DelegationToken) InvokeResult {
	result, err := svc.Invoke(capName, token, args, service.InvokeOpts{})
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			return InvokeResult{
				Text:    fmt.Sprintf("FAILED: %s\nDetail: %s\nRetryable: no", anipErr.ErrorType, anipErr.Detail),
				IsError: true,
			}
		}
		return InvokeResult{
			Text:    fmt.Sprintf("FAILED: internal_error\nDetail: %s\nRetryable: no", err.Error()),
			IsError: true,
		}
	}

	return TranslateResponse(result)
}

// TranslateResponse converts an ANIP invoke response map into an MCP InvokeResult.
//
// Success: JSON pretty-print of result + optional cost annotation.
// Failure: structured error text with type, detail, resolution, and retryable flag.
func TranslateResponse(response map[string]any) InvokeResult {
	success, _ := response["success"].(bool)

	if success {
		result := response["result"]
		pretty, err := json.MarshalIndent(result, "", "  ")
		if err != nil {
			pretty = []byte(fmt.Sprintf("%v", result))
		}

		text := string(pretty)

		// Append cost annotation if present
		if costActual, ok := response["cost_actual"]; ok && costActual != nil {
			if costMap, ok := costActual.(*core.CostActual); ok && costMap != nil {
				if costMap.Financial != nil {
					amount := costMap.Financial["amount"]
					currency, _ := costMap.Financial["currency"].(string)
					if currency == "" {
						currency = "USD"
					}
					if amount != nil {
						text += fmt.Sprintf("\n[Cost: %s %v]", currency, amount)
					}
				}
			} else if costMap, ok := costActual.(map[string]any); ok {
				financial, _ := costMap["financial"].(map[string]any)
				if financial != nil {
					amount := financial["amount"]
					currency, _ := financial["currency"].(string)
					if currency == "" {
						currency = "USD"
					}
					if amount != nil {
						text += fmt.Sprintf("\n[Cost: %s %v]", currency, amount)
					}
				}
			}
		}

		return InvokeResult{Text: text, IsError: false}
	}

	// Failure path
	failure, _ := response["failure"].(map[string]any)
	if failure == nil {
		return InvokeResult{
			Text:    "FAILED: unknown\nDetail: no detail\nRetryable: no",
			IsError: true,
		}
	}

	failType, _ := failure["type"].(string)
	if failType == "" {
		failType = "unknown"
	}
	detail, _ := failure["detail"].(string)
	if detail == "" {
		detail = "no detail"
	}

	var parts []string
	parts = append(parts, fmt.Sprintf("FAILED: %s", failType))
	parts = append(parts, fmt.Sprintf("Detail: %s", detail))

	if resolution, ok := failure["resolution"].(map[string]any); ok && resolution != nil {
		if action, ok := resolution["action"].(string); ok && action != "" {
			parts = append(parts, fmt.Sprintf("Resolution: %s", action))
		}
		if requires, ok := resolution["requires"].(string); ok && requires != "" {
			parts = append(parts, fmt.Sprintf("Requires: %s", requires))
		}
	}

	retry, _ := failure["retry"].(bool)
	if retry {
		parts = append(parts, "Retryable: yes")
	} else {
		parts = append(parts, "Retryable: no")
	}

	return InvokeResult{
		Text:    strings.Join(parts, "\n"),
		IsError: true,
	}
}
