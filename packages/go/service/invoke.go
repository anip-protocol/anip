package service

import (
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

// Invoke routes a capability invocation through validation, handler execution, and audit.
func (s *Service) Invoke(
	capName string,
	token *core.DelegationToken,
	params map[string]any,
	opts InvokeOpts,
) (map[string]any, error) {
	invocationID := core.GenerateInvocationID()

	// 1. Look up capability.
	capDef, ok := s.capabilities[capName]
	if !ok {
		resp := map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureUnknownCapability,
				"detail": "Capability '" + capName + "' not found",
			},
			"invocation_id":      invocationID,
			"client_reference_id": opts.ClientReferenceID,
		}
		return resp, nil
	}

	// 2. Check streaming support (Phase 1: always reject).
	if opts.Stream {
		resp := map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureStreamingNotSupported,
				"detail": "Capability '" + capName + "' does not support streaming",
			},
			"invocation_id":      invocationID,
			"client_reference_id": opts.ClientReferenceID,
		}
		return resp, nil
	}

	// 3. Validate token scope covers capability's minimum_scope.
	if err := server.ValidateScope(token, capDef.Declaration.MinimumScope); err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			failure := map[string]any{
				"type":   anipErr.ErrorType,
				"detail": anipErr.Detail,
			}
			if anipErr.Resolution != nil {
				failure["resolution"] = map[string]any{
					"action": anipErr.Resolution.Action,
				}
			}

			// Log audit for scope failure.
			s.appendAuditEntry(capName, token, false, anipErr.ErrorType, nil, nil, invocationID, opts.ClientReferenceID)

			resp := map[string]any{
				"success":             false,
				"failure":             failure,
				"invocation_id":       invocationID,
				"client_reference_id": opts.ClientReferenceID,
			}
			return resp, nil
		}
		return nil, err
	}

	// 4. Build invocation context.
	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}

	ctx := InvocationContext{
		Token:             token,
		RootPrincipal:     rootPrincipal,
		Subject:           token.Subject,
		Scopes:            token.Scope,
		DelegationChain:   []string{token.TokenID},
		InvocationID:      invocationID,
		ClientReferenceID: opts.ClientReferenceID,
	}

	// 5. Call handler.
	result, err := capDef.Handler(ctx, params)
	if err != nil {
		// Handler returned an error.
		if anipErr, ok := err.(*core.ANIPError); ok {
			s.appendAuditEntry(capName, token, false, anipErr.ErrorType, map[string]any{"detail": anipErr.Detail}, nil, invocationID, opts.ClientReferenceID)

			resp := map[string]any{
				"success": false,
				"failure": map[string]any{
					"type":   anipErr.ErrorType,
					"detail": anipErr.Detail,
				},
				"invocation_id":       invocationID,
				"client_reference_id": opts.ClientReferenceID,
			}
			return resp, nil
		}

		// Generic error -> internal_error.
		s.appendAuditEntry(capName, token, false, core.FailureInternalError, nil, nil, invocationID, opts.ClientReferenceID)

		resp := map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureInternalError,
				"detail": "Internal error",
			},
			"invocation_id":       invocationID,
			"client_reference_id": opts.ClientReferenceID,
		}
		return resp, nil
	}

	// 6. Extract cost actual from context.
	costActual := ctx.costActual

	// 7. Log audit (success).
	s.appendAuditEntry(capName, token, true, "", result, costActual, invocationID, opts.ClientReferenceID)

	// 8. Build response.
	resp := map[string]any{
		"success":              true,
		"result":               result,
		"invocation_id":        invocationID,
		"client_reference_id":  opts.ClientReferenceID,
	}
	if costActual != nil {
		resp["cost_actual"] = costActual
	}

	return resp, nil
}

// appendAuditEntry logs an audit entry for an invocation.
func (s *Service) appendAuditEntry(
	capability string,
	token *core.DelegationToken,
	success bool,
	failureType string,
	resultSummary map[string]any,
	costActual *core.CostActual,
	invocationID string,
	clientReferenceID string,
) {
	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}

	entry := &core.AuditEntry{
		Capability:        capability,
		TokenID:           token.TokenID,
		Issuer:            token.Issuer,
		Subject:           token.Subject,
		RootPrincipal:     rootPrincipal,
		Success:           success,
		FailureType:       failureType,
		ResultSummary:     resultSummary,
		CostActual:        costActual,
		DelegationChain:   []string{token.TokenID},
		InvocationID:      invocationID,
		ClientReferenceID: clientReferenceID,
	}

	// Best effort - don't fail the invocation if audit logging fails.
	_ = server.AppendAudit(s.keys, s.storage, entry)
}
