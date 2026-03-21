package service

import (
	"errors"
	"sync"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

// StreamEvent represents a single SSE event in a streaming invocation.
type StreamEvent struct {
	Type    string         // "progress", "completed", "failed"
	Payload map[string]any // full SSE data payload
}

// StreamResult holds a channel of streaming events.
// The channel is closed after exactly one terminal event (completed or failed).
type StreamResult struct {
	Events <-chan StreamEvent
}

// capabilitySupportsStreaming checks if a capability declares "streaming" in its response_modes.
func capabilitySupportsStreaming(decl core.CapabilityDeclaration) bool {
	for _, mode := range decl.ResponseModes {
		if mode == "streaming" {
			return true
		}
	}
	return false
}

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

	// 2. Check streaming support.
	if opts.Stream {
		if !capabilitySupportsStreaming(capDef.Declaration) {
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
		// Streaming is supported but Invoke is for unary only;
		// callers wanting streaming must use InvokeStream.
		resp := map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureStreamingNotSupported,
				"detail": "Use InvokeStream for streaming invocations",
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
		EmitProgress: func(payload map[string]any) error {
			// No-op for unary invocations.
			return nil
		},
	}

	// 5. Call handler.
	result, err := capDef.Handler(&ctx, params)
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

// InvokeStream routes a streaming capability invocation.
// It returns a StreamResult whose Events channel emits progress events
// followed by exactly one terminal event (completed or failed), then closes.
func (s *Service) InvokeStream(
	capName string,
	token *core.DelegationToken,
	params map[string]any,
	opts InvokeOpts,
) (*StreamResult, error) {
	invocationID := core.GenerateInvocationID()

	// 1. Look up capability.
	capDef, ok := s.capabilities[capName]
	if !ok {
		return nil, core.NewANIPError(core.FailureUnknownCapability, "Capability '"+capName+"' not found")
	}

	// 2. Check streaming support.
	if !capabilitySupportsStreaming(capDef.Declaration) {
		return nil, core.NewANIPError(core.FailureStreamingNotSupported, "Capability '"+capName+"' does not support streaming")
	}

	// 3. Validate token scope.
	if err := server.ValidateScope(token, capDef.Declaration.MinimumScope); err != nil {
		return nil, err
	}

	// 4. Build invocation context with streaming EmitProgress.
	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}

	ch := make(chan StreamEvent, 16)

	var mu sync.Mutex
	closed := false

	clientRefID := opts.ClientReferenceID

	emitProgress := func(payload map[string]any) error {
		mu.Lock()
		defer mu.Unlock()
		if closed {
			return errors.New("stream closed")
		}
		event := StreamEvent{
			Type: "progress",
			Payload: map[string]any{
				"invocation_id":       invocationID,
				"client_reference_id": nilIfEmpty(clientRefID),
				"timestamp":           time.Now().UTC().Format(time.RFC3339),
				"payload":             payload,
			},
		}
		ch <- event
		return nil
	}

	ctx := InvocationContext{
		Token:             token,
		RootPrincipal:     rootPrincipal,
		Subject:           token.Subject,
		Scopes:            token.Scope,
		DelegationChain:   []string{token.TokenID},
		InvocationID:      invocationID,
		ClientReferenceID: clientRefID,
		EmitProgress:      emitProgress,
	}

	// 5. Run handler in goroutine.
	go func() {
		defer func() {
			mu.Lock()
			closed = true
			mu.Unlock()
			close(ch)
		}()

		result, err := capDef.Handler(&ctx, params)
		if err != nil {
			// Handler returned an error — send failed event.
			failType := core.FailureInternalError
			detail := "Internal error"
			if anipErr, ok := err.(*core.ANIPError); ok {
				failType = anipErr.ErrorType
				detail = anipErr.Detail
			}

			s.appendAuditEntry(capName, token, false, failType, map[string]any{"detail": detail}, nil, invocationID, clientRefID)

			ch <- StreamEvent{
				Type: "failed",
				Payload: map[string]any{
					"invocation_id":       invocationID,
					"client_reference_id": nilIfEmpty(clientRefID),
					"timestamp":           time.Now().UTC().Format(time.RFC3339),
					"success":             false,
					"failure": map[string]any{
						"type":       failType,
						"detail":     detail,
						"resolution": nil,
						"retry":      false,
					},
				},
			}
			return
		}

		// Success — send completed event.
		costActual := ctx.costActual
		s.appendAuditEntry(capName, token, true, "", result, costActual, invocationID, clientRefID)

		payload := map[string]any{
			"invocation_id":       invocationID,
			"client_reference_id": nilIfEmpty(clientRefID),
			"timestamp":           time.Now().UTC().Format(time.RFC3339),
			"success":             true,
			"result":              result,
			"cost_actual":         nil,
		}
		if costActual != nil {
			payload["cost_actual"] = costActual
		}

		ch <- StreamEvent{
			Type:    "completed",
			Payload: payload,
		}
	}()

	return &StreamResult{Events: ch}, nil
}

// nilIfEmpty returns nil if s is empty, otherwise returns s.
// Used to match the SSE format where client_reference_id is null when not set.
func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
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
