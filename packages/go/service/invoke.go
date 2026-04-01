package service

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"sync"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
)

// parseISO8601Duration parses a simple ISO 8601 duration string like PT15M, PT1H30M, PT30S.
func parseISO8601Duration(d string) time.Duration {
	re := regexp.MustCompile(`PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?`)
	m := re.FindStringSubmatch(d)
	if m == nil {
		return 0
	}
	var total time.Duration
	if m[1] != "" {
		h, _ := strconv.Atoi(m[1])
		total += time.Duration(h) * time.Hour
	}
	if m[2] != "" {
		mins, _ := strconv.Atoi(m[2])
		total += time.Duration(mins) * time.Minute
	}
	if m[3] != "" {
		s, _ := strconv.Atoi(m[3])
		total += time.Duration(s) * time.Second
	}
	return total
}

// resolveBoundPrice extracts a bound price from params using capability's binding declarations.
func resolveBoundPrice(bindings []core.BindingRequirement, params map[string]any) *float64 {
	for _, binding := range bindings {
		if v, ok := params[binding.Field]; ok && v != nil {
			if m, ok := v.(map[string]any); ok {
				if price, ok := m["price"]; ok {
					switch p := price.(type) {
					case float64:
						return &p
					case int:
						f := float64(p)
						return &f
					}
				}
			}
		}
	}
	return nil
}

// resolveBindingAge determines the age of a binding value.
// Returns -1 if age cannot be determined.
func resolveBindingAge(bindingValue any) time.Duration {
	now := time.Now().Unix()
	if m, ok := bindingValue.(map[string]any); ok {
		if issuedAt, ok := m["issued_at"]; ok {
			switch v := issuedAt.(type) {
			case float64:
				return time.Duration(now-int64(v)) * time.Second
			case int64:
				return time.Duration(now-v) * time.Second
			}
		}
	}
	if s, ok := bindingValue.(string); ok {
		// Try to extract unix timestamp from format like "qt-hexhex-1234567890"
		re := regexp.MustCompile(`-(\d{10,})$`)
		m := re.FindStringSubmatch(s)
		if m != nil {
			ts, err := strconv.ParseInt(m[1], 10, 64)
			if err == nil && ts > 1000000000 {
				return time.Duration(now-ts) * time.Second
			}
		}
	}
	return -1
}

// validateInputs checks that required inputs are present and basic types match.
func validateInputs(decl *core.CapabilityDeclaration, params map[string]any) error {
	// Check required inputs are present.
	for _, inp := range decl.Inputs {
		if inp.Required {
			if _, ok := params[inp.Name]; !ok {
				return core.NewANIPError(core.FailureInvalidParameters,
					fmt.Sprintf("missing required parameter: %s", inp.Name))
			}
		}
	}
	// Type checking for basic types.
	for _, inp := range decl.Inputs {
		val, ok := params[inp.Name]
		if !ok {
			continue
		}
		if err := validateType(val, inp.Type); err != nil {
			return core.NewANIPError(core.FailureInvalidParameters,
				fmt.Sprintf("parameter '%s': %s", inp.Name, err))
		}
	}
	return nil
}

// validateType checks that a value matches the expected type string.
func validateType(val any, typeName string) error {
	switch typeName {
	case "string", "airport_code", "date":
		if _, ok := val.(string); !ok {
			return fmt.Errorf("expected string, got %T", val)
		}
	case "integer":
		switch val.(type) {
		case int, int32, int64, float64:
			// float64 is the default JSON number type; accept it
		default:
			return fmt.Errorf("expected integer, got %T", val)
		}
	case "number", "float":
		switch val.(type) {
		case float64, float32, int, int32, int64:
		default:
			return fmt.Errorf("expected number, got %T", val)
		}
	case "boolean":
		if _, ok := val.(bool); !ok {
			return fmt.Errorf("expected boolean, got %T", val)
		}
	case "object":
		if _, ok := val.(map[string]any); !ok {
			return fmt.Errorf("expected object, got %T", val)
		}
	case "array":
		if _, ok := val.([]any); !ok {
			return fmt.Errorf("expected array, got %T", val)
		}
	}
	// Unknown types pass through (extensible).
	return nil
}

// StreamEvent represents a single SSE event in a streaming invocation.
type StreamEvent struct {
	Type    string         // "progress", "completed", "failed"
	Payload map[string]any // full SSE data payload
}

// StreamResult holds a channel of streaming events.
// The channel is closed after exactly one terminal event (completed or failed).
// Call Cancel() to signal the handler that the client has disconnected.
type StreamResult struct {
	Events <-chan StreamEvent
	Cancel func() // signals handler that client disconnected
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
	invokeStart := time.Now()
	invokeSuccess := false

	// Fire completion hooks on all exit paths (success and failure).
	defer func() {
		if s.hooks != nil {
			durationMs := time.Since(invokeStart).Milliseconds()
			if s.hooks.OnInvokeComplete != nil {
				callHook(func() { s.hooks.OnInvokeComplete(invocationID, capName, invokeSuccess, durationMs) })
			}
			if s.hooks.OnInvokeDuration != nil {
				callHook(func() { s.hooks.OnInvokeDuration(capName, durationMs, invokeSuccess) })
			}
		}
	}()

	// task_id precedence: token purpose.task_id is authoritative
	tokenTaskID := ""
	if token.Purpose.TaskID != "" {
		tokenTaskID = token.Purpose.TaskID
	}
	if tokenTaskID != "" && opts.TaskID != "" && opts.TaskID != tokenTaskID {
		failure := map[string]any{
			"type":       core.FailurePurposeMismatch,
			"detail":     "Request task_id '" + opts.TaskID + "' does not match token purpose task_id '" + tokenTaskID + "'",
			"resolution": map[string]any{"action": "use_token_task_id", "recovery_class": core.RecoveryClassForAction("use_token_task_id"), "requires": "matching task_id or omit from request"},
			"retry":      false,
		}
		resp := map[string]any{
			"success":               false,
			"failure":               failure,
			"invocation_id":         invocationID,
			"client_reference_id":   opts.ClientReferenceID,
			"task_id":               opts.TaskID,
			"parent_invocation_id":  opts.ParentInvocationID,
		}
		return resp, nil
	}
	effectiveTaskID := opts.TaskID
	if effectiveTaskID == "" {
		effectiveTaskID = tokenTaskID
	}

	// 1. Look up capability.
	capDef, ok := s.capabilities[capName]
	if !ok {
		failure := map[string]any{
			"type":   core.FailureUnknownCapability,
			"detail": "Capability '" + capName + "' not found",
		}

		// Apply failure redaction (no token available).
		effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, nil, s.disclosurePolicy)
		failure = RedactFailure(failure, effectiveLevel)

		resp := map[string]any{
			"success":               false,
			"failure":               failure,
			"invocation_id":         invocationID,
			"client_reference_id":   opts.ClientReferenceID,
			"task_id":               effectiveTaskID,
			"parent_invocation_id":  opts.ParentInvocationID,
		}
		return resp, nil
	}

	// Fire OnInvokeStart hook.
	if s.hooks != nil && s.hooks.OnInvokeStart != nil {
		callHook(func() { s.hooks.OnInvokeStart(invocationID, capName, token.Subject) })
	}

	// 2. Check streaming support.
	if opts.Stream {
		if !capabilitySupportsStreaming(capDef.Declaration) {
			failure := map[string]any{
				"type":   core.FailureStreamingNotSupported,
				"detail": "Capability '" + capName + "' does not support streaming",
			}

			// Apply failure redaction (no token claims needed for streaming check).
			effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, nil, s.disclosurePolicy)
			failure = RedactFailure(failure, effectiveLevel)

			resp := map[string]any{
				"success":               false,
				"failure":               failure,
				"invocation_id":         invocationID,
				"client_reference_id":   opts.ClientReferenceID,
				"task_id":               effectiveTaskID,
				"parent_invocation_id":  opts.ParentInvocationID,
			}
			return resp, nil
		}
		// Streaming is supported but Invoke is for unary only;
		// callers wanting streaming must use InvokeStream.
		failure := map[string]any{
			"type":   core.FailureStreamingNotSupported,
			"detail": "Use InvokeStream for streaming invocations",
		}

		// Apply failure redaction (no token claims needed for streaming check).
		effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, nil, s.disclosurePolicy)
		failure = RedactFailure(failure, effectiveLevel)

		resp := map[string]any{
			"success":               false,
			"failure":               failure,
			"invocation_id":         invocationID,
			"client_reference_id":   opts.ClientReferenceID,
			"task_id":               effectiveTaskID,
			"parent_invocation_id":  opts.ParentInvocationID,
		}
		return resp, nil
	}

	// Note: Input validation is intentionally NOT done at the protocol layer.
	// The Python and TypeScript runtimes pass params directly to the handler,
	// which decides how to handle missing/invalid inputs. The conformance suite
	// invokes with empty params and expects the handler to produce a result.

	// 3. Validate token scope covers capability's minimum_scope.
	if err := server.ValidateScope(token, capDef.Declaration.MinimumScope); err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			// Fire scope validation hook (denied).
			if s.hooks != nil && s.hooks.OnScopeValidation != nil {
				callHook(func() { s.hooks.OnScopeValidation(capName, false) })
			}

			failure := map[string]any{
				"type":   anipErr.ErrorType,
				"detail": anipErr.Detail,
			}
			if anipErr.Resolution != nil {
				failure["resolution"] = map[string]any{
					"action":         anipErr.Resolution.Action,
					"recovery_class": anipErr.Resolution.RecoveryClass,
				}
			}

			// Log audit for scope failure.
			s.appendAuditEntry(capName, token, false, anipErr.ErrorType, nil, nil, invocationID, opts.ClientReferenceID, effectiveTaskID, opts.ParentInvocationID, capDef.Declaration.SideEffect.Type)

			// Apply failure redaction.
			effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
			failure = RedactFailure(failure, effectiveLevel)

			resp := map[string]any{
				"success":               false,
				"failure":               failure,
				"invocation_id":         invocationID,
				"client_reference_id":   opts.ClientReferenceID,
				"task_id":               effectiveTaskID,
				"parent_invocation_id":  opts.ParentInvocationID,
			}
			return resp, nil
		}
		return nil, err
	}

	// Fire scope validation hook (granted).
	if s.hooks != nil && s.hooks.OnScopeValidation != nil {
		callHook(func() { s.hooks.OnScopeValidation(capName, true) })
	}

	// --- Budget, binding, and control requirement enforcement (v0.14) ---

	// Parse invocation-level budget hint.
	var requestBudget *core.Budget
	if opts.Budget != nil {
		requestBudget = opts.Budget
	}

	// Determine effective budget (token is ceiling, invocation hint can only narrow).
	var effectiveBudget *core.Budget
	if token.Constraints.Budget != nil {
		effectiveBudget = token.Constraints.Budget
		if requestBudget != nil {
			if requestBudget.Currency != effectiveBudget.Currency {
				failure := map[string]any{
					"type":   core.FailureBudgetCurrencyMismatch,
					"detail": fmt.Sprintf("Invocation budget is in %s but token budget is in %s", requestBudget.Currency, effectiveBudget.Currency),
				}
				effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
				failure = RedactFailure(failure, effectiveLevel)
				return map[string]any{
					"success":              false,
					"failure":              failure,
					"invocation_id":        invocationID,
					"client_reference_id":  opts.ClientReferenceID,
					"task_id":              effectiveTaskID,
					"parent_invocation_id": opts.ParentInvocationID,
				}, nil
			}
			narrowedAmount := effectiveBudget.MaxAmount
			if requestBudget.MaxAmount < narrowedAmount {
				narrowedAmount = requestBudget.MaxAmount
			}
			effectiveBudget = &core.Budget{
				Currency:  effectiveBudget.Currency,
				MaxAmount: narrowedAmount,
			}
		}
	} else if requestBudget != nil {
		effectiveBudget = requestBudget
	}

	// Budget enforcement against declared cost.
	var checkAmount *float64
	if effectiveBudget != nil {
		decl := capDef.Declaration
		if decl.Cost != nil && decl.Cost.Financial != nil {
			if decl.Cost.Financial.Currency != effectiveBudget.Currency {
				failure := map[string]any{
					"type":   core.FailureBudgetCurrencyMismatch,
					"detail": fmt.Sprintf("Token budget is in %s but capability cost is in %s", effectiveBudget.Currency, decl.Cost.Financial.Currency),
				}
				effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
				failure = RedactFailure(failure, effectiveLevel)
				return map[string]any{
					"success":              false,
					"failure":              failure,
					"invocation_id":        invocationID,
					"client_reference_id":  opts.ClientReferenceID,
					"task_id":              effectiveTaskID,
					"parent_invocation_id": opts.ParentInvocationID,
				}, nil
			}

			switch decl.Cost.Certainty {
			case "fixed":
				checkAmount = decl.Cost.Financial.Amount
			case "estimated":
				if len(decl.RequiresBinding) > 0 {
					checkAmount = resolveBoundPrice(decl.RequiresBinding, params)
					if checkAmount == nil {
						// Binding exists but no resolvable price — budget cannot be enforced.
						failure := map[string]any{
							"type":   core.FailureBudgetNotEnforceable,
							"detail": fmt.Sprintf("Capability %s has estimated cost with requires_binding but the provided binding does not carry a resolvable price", capName),
							"resolution": map[string]any{
								"action":         "provide_priced_binding",
								"recovery_class": core.RecoveryClassForAction("provide_priced_binding"),
								"requires":       "binding value must include a 'price' field or the service must resolve binding to a concrete price",
							},
							"retry": false,
						}
						effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
						failure = RedactFailure(failure, effectiveLevel)
						return map[string]any{
							"success":              false,
							"failure":              failure,
							"invocation_id":        invocationID,
							"client_reference_id":  opts.ClientReferenceID,
							"task_id":              effectiveTaskID,
							"parent_invocation_id": opts.ParentInvocationID,
						}, nil
					}
				} else {
					failure := map[string]any{
						"type":   core.FailureBudgetNotEnforceable,
						"detail": fmt.Sprintf("Capability %s has estimated cost but no requires_binding — budget cannot be enforced", capName),
					}
					effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
					failure = RedactFailure(failure, effectiveLevel)
					return map[string]any{
						"success":              false,
						"failure":              failure,
						"invocation_id":        invocationID,
						"client_reference_id":  opts.ClientReferenceID,
						"task_id":              effectiveTaskID,
						"parent_invocation_id": opts.ParentInvocationID,
					}, nil
				}
			case "dynamic":
				checkAmount = decl.Cost.Financial.UpperBound
			}

			if checkAmount != nil && *checkAmount > effectiveBudget.MaxAmount {
				failure := map[string]any{
					"type":   core.FailureBudgetExceeded,
					"detail": fmt.Sprintf("Cost $%v exceeds budget $%v", *checkAmount, effectiveBudget.MaxAmount),
				}
				effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
				failure = RedactFailure(failure, effectiveLevel)
				resp := map[string]any{
					"success":              false,
					"failure":              failure,
					"invocation_id":        invocationID,
					"client_reference_id":  opts.ClientReferenceID,
					"task_id":              effectiveTaskID,
					"parent_invocation_id": opts.ParentInvocationID,
					"budget_context": map[string]any{
						"budget_max":        effectiveBudget.MaxAmount,
						"budget_currency":   effectiveBudget.Currency,
						"cost_check_amount": *checkAmount,
						"cost_certainty":    decl.Cost.Certainty,
					},
				}
				return resp, nil
			}
		}
	}

	// Binding enforcement.
	for _, binding := range capDef.Declaration.RequiresBinding {
		val, exists := params[binding.Field]
		if !exists || val == nil {
			sourceDesc := binding.SourceCapability
			if sourceDesc == "" {
				sourceDesc = "source capability"
			}
			failure := map[string]any{
				"type":   core.FailureBindingMissing,
				"detail": fmt.Sprintf("Capability %s requires '%s' (type: %s)", capName, binding.Field, binding.Type),
				"resolution": map[string]any{
					"action":         "obtain_binding",
					"recovery_class": core.RecoveryClassForAction("obtain_binding"),
					"requires":       fmt.Sprintf("invoke %s to obtain a %s", sourceDesc, binding.Field),
				},
			}
			effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
			failure = RedactFailure(failure, effectiveLevel)
			return map[string]any{
				"success":              false,
				"failure":              failure,
				"invocation_id":        invocationID,
				"client_reference_id":  opts.ClientReferenceID,
				"task_id":              effectiveTaskID,
				"parent_invocation_id": opts.ParentInvocationID,
			}, nil
		}
		if binding.MaxAge != "" {
			age := resolveBindingAge(val)
			if age >= 0 {
				maxAge := parseISO8601Duration(binding.MaxAge)
				if maxAge > 0 && age > maxAge {
					sourceDesc := binding.SourceCapability
					if sourceDesc == "" {
						sourceDesc = "source capability"
					}
					failure := map[string]any{
						"type":   core.FailureBindingStale,
						"detail": fmt.Sprintf("Binding '%s' has exceeded max_age of %s", binding.Field, binding.MaxAge),
						"resolution": map[string]any{
							"action":         "refresh_binding",
							"recovery_class": core.RecoveryClassForAction("refresh_binding"),
							"requires":       fmt.Sprintf("invoke %s again for a fresh %s", sourceDesc, binding.Field),
						},
					}
					effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
					failure = RedactFailure(failure, effectiveLevel)
					return map[string]any{
						"success":              false,
						"failure":              failure,
						"invocation_id":        invocationID,
						"client_reference_id":  opts.ClientReferenceID,
						"task_id":              effectiveTaskID,
						"parent_invocation_id": opts.ParentInvocationID,
					}, nil
				}
			}
		}
	}

	// Control requirement enforcement (reject only — no warn in v0.14).
	// NOTE: The stronger_delegation_required check is defence-in-depth.
	// Purpose validation in the delegation engine fires before this loop,
	// making the stronger_delegation_required branch unreachable through
	// normal invoke.
	for _, req := range capDef.Declaration.ControlRequirements {
		satisfied := true
		switch req.Type {
		case "cost_ceiling":
			satisfied = effectiveBudget != nil
		case "stronger_delegation_required":
			satisfied = token.Purpose.Capability == capName
		}

		if !satisfied {
			failure := map[string]any{
				"type":                      core.FailureControlRequirementUnsatisfied,
				"detail":                    fmt.Sprintf("Capability %s requires %s", capName, req.Type),
				"unsatisfied_requirements":  []string{req.Type},
			}
			effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
			failure = RedactFailure(failure, effectiveLevel)
			return map[string]any{
				"success":              false,
				"failure":              failure,
				"invocation_id":        invocationID,
				"client_reference_id":  opts.ClientReferenceID,
				"task_id":              effectiveTaskID,
				"parent_invocation_id": opts.ParentInvocationID,
			}, nil
		}
	}

	// 4. Build invocation context.
	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}

	ctx := InvocationContext{
		Token:              token,
		RootPrincipal:      rootPrincipal,
		Subject:            token.Subject,
		Scopes:             token.Scope,
		DelegationChain:    []string{token.TokenID},
		InvocationID:       invocationID,
		ClientReferenceID:  opts.ClientReferenceID,
		TaskID:             effectiveTaskID,
		ParentInvocationID: opts.ParentInvocationID,
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
			s.appendAuditEntry(capName, token, false, anipErr.ErrorType, map[string]any{"detail": anipErr.Detail}, nil, invocationID, opts.ClientReferenceID, effectiveTaskID, opts.ParentInvocationID, capDef.Declaration.SideEffect.Type)

			failure := map[string]any{
				"type":   anipErr.ErrorType,
				"detail": anipErr.Detail,
			}

			// Apply failure redaction.
			effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
			failure = RedactFailure(failure, effectiveLevel)

			resp := map[string]any{
				"success":               false,
				"failure":               failure,
				"invocation_id":         invocationID,
				"client_reference_id":   opts.ClientReferenceID,
				"task_id":               effectiveTaskID,
				"parent_invocation_id":  opts.ParentInvocationID,
			}
			return resp, nil
		}

		// Generic error -> internal_error.
		s.appendAuditEntry(capName, token, false, core.FailureInternalError, nil, nil, invocationID, opts.ClientReferenceID, effectiveTaskID, opts.ParentInvocationID, capDef.Declaration.SideEffect.Type)

		failure := map[string]any{
			"type":   core.FailureInternalError,
			"detail": "Internal error",
		}

		// Apply failure redaction.
		effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
		failure = RedactFailure(failure, effectiveLevel)

		resp := map[string]any{
			"success":               false,
			"failure":               failure,
			"invocation_id":         invocationID,
			"client_reference_id":   opts.ClientReferenceID,
			"task_id":               effectiveTaskID,
			"parent_invocation_id":  opts.ParentInvocationID,
		}
		return resp, nil
	}

	// 6. Extract cost actual from context.
	costActual := ctx.costActual

	// 7. Log audit (success).
	s.appendAuditEntry(capName, token, true, "", result, costActual, invocationID, opts.ClientReferenceID, effectiveTaskID, opts.ParentInvocationID, capDef.Declaration.SideEffect.Type)

	// 8. Build response.
	resp := map[string]any{
		"success":               true,
		"result":                result,
		"invocation_id":         invocationID,
		"client_reference_id":   opts.ClientReferenceID,
		"task_id":               effectiveTaskID,
		"parent_invocation_id":  opts.ParentInvocationID,
	}
	if costActual != nil {
		resp["cost_actual"] = costActual
	}

	// Budget context in response (v0.14).
	if effectiveBudget != nil {
		var costActualAmount *float64
		if costActual != nil && costActual.Financial != nil && costActual.Financial.Amount != nil {
			costActualAmount = costActual.Financial.Amount
		}
		var costCertainty string
		if capDef.Declaration.Cost != nil {
			costCertainty = capDef.Declaration.Cost.Certainty
		}
		budgetCtx := map[string]any{
			"budget_max":      effectiveBudget.MaxAmount,
			"budget_currency": effectiveBudget.Currency,
			"cost_certainty":  costCertainty,
			"within_budget":   true,
		}
		if checkAmount != nil {
			budgetCtx["cost_check_amount"] = *checkAmount
		}
		if costActualAmount != nil {
			budgetCtx["cost_actual"] = *costActualAmount
		}
		resp["budget_context"] = budgetCtx
	}

	invokeSuccess = true
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

	// task_id precedence: token purpose.task_id is authoritative
	tokenTaskID := ""
	if token.Purpose.TaskID != "" {
		tokenTaskID = token.Purpose.TaskID
	}
	if tokenTaskID != "" && opts.TaskID != "" && opts.TaskID != tokenTaskID {
		return nil, core.NewANIPError(core.FailurePurposeMismatch,
			"Request task_id '"+opts.TaskID+"' does not match token purpose task_id '"+tokenTaskID+"'")
	}
	effectiveTaskID := opts.TaskID
	if effectiveTaskID == "" {
		effectiveTaskID = tokenTaskID
	}

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
	parentInvID := opts.ParentInvocationID

	emitProgress := func(payload map[string]any) error {
		mu.Lock()
		defer mu.Unlock()
		if closed {
			return errors.New("stream closed")
		}
		event := StreamEvent{
			Type: "progress",
			Payload: map[string]any{
				"invocation_id":        invocationID,
				"client_reference_id":  nilIfEmpty(clientRefID),
				"task_id":              nilIfEmpty(effectiveTaskID),
				"parent_invocation_id": nilIfEmpty(parentInvID),
				"timestamp":            time.Now().UTC().Format(time.RFC3339),
				"payload":              payload,
			},
		}
		ch <- event
		return nil
	}

	ctx := InvocationContext{
		Token:              token,
		RootPrincipal:      rootPrincipal,
		Subject:            token.Subject,
		Scopes:             token.Scope,
		DelegationChain:    []string{token.TokenID},
		InvocationID:       invocationID,
		ClientReferenceID:  clientRefID,
		TaskID:             effectiveTaskID,
		ParentInvocationID: parentInvID,
		EmitProgress:       emitProgress,
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
			var failureObj map[string]any
			if anipErr, ok := err.(*core.ANIPError); ok {
				failType = anipErr.ErrorType
				detail = anipErr.Detail
				failureObj = map[string]any{
					"type":   anipErr.ErrorType,
					"detail": anipErr.Detail,
					"retry":  anipErr.Retry,
				}
				if anipErr.Resolution != nil {
					failureObj["resolution"] = anipErr.Resolution
				} else {
					failureObj["resolution"] = nil
				}
			} else {
				failureObj = map[string]any{
					"type":       failType,
					"detail":     detail,
					"resolution": nil,
					"retry":      false,
				}
			}

			s.appendAuditEntry(capName, token, false, failType, map[string]any{"detail": detail}, nil, invocationID, clientRefID, effectiveTaskID, parentInvID, capDef.Declaration.SideEffect.Type)

			// Apply failure redaction to streaming failure.
			effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaimsMap(token), s.disclosurePolicy)
			failureObj = RedactFailure(failureObj, effectiveLevel)

			ch <- StreamEvent{
				Type: "failed",
				Payload: map[string]any{
					"invocation_id":        invocationID,
					"client_reference_id":  nilIfEmpty(clientRefID),
					"task_id":              nilIfEmpty(effectiveTaskID),
					"parent_invocation_id": nilIfEmpty(parentInvID),
					"timestamp":            time.Now().UTC().Format(time.RFC3339),
					"success":              false,
					"failure":              failureObj,
				},
			}
			return
		}

		// Success — send completed event.
		costActual := ctx.costActual
		s.appendAuditEntry(capName, token, true, "", result, costActual, invocationID, clientRefID, effectiveTaskID, parentInvID, capDef.Declaration.SideEffect.Type)

		payload := map[string]any{
			"invocation_id":        invocationID,
			"client_reference_id":  nilIfEmpty(clientRefID),
			"task_id":              nilIfEmpty(effectiveTaskID),
			"parent_invocation_id": nilIfEmpty(parentInvID),
			"timestamp":            time.Now().UTC().Format(time.RFC3339),
			"success":              true,
			"result":               result,
			"cost_actual":          nil,
		}
		if costActual != nil {
			payload["cost_actual"] = costActual
		}

		ch <- StreamEvent{
			Type:    "completed",
			Payload: payload,
		}
	}()

	return &StreamResult{
		Events: ch,
		Cancel: func() {
			mu.Lock()
			closed = true
			mu.Unlock()
		},
	}, nil
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
	taskID string,
	parentInvocationID string,
	sideEffectType string,
) {
	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}

	eventClass := ClassifyEvent(sideEffectType, success, failureType)
	tier := s.retentionPolicy.ResolveTier(eventClass)
	expiresAt := s.retentionPolicy.ComputeExpiresAt(tier, time.Now().UTC())

	entry := &core.AuditEntry{
		Capability:         capability,
		TokenID:            token.TokenID,
		Issuer:             token.Issuer,
		Subject:            token.Subject,
		RootPrincipal:      rootPrincipal,
		Success:            success,
		FailureType:        failureType,
		ResultSummary:      resultSummary,
		CostActual:         costActual,
		DelegationChain:    []string{token.TokenID},
		InvocationID:       invocationID,
		ClientReferenceID:  clientReferenceID,
		TaskID:             taskID,
		ParentInvocationID: parentInvocationID,
		EventClass:         eventClass,
		RetentionTier:      tier,
		ExpiresAt:          expiresAt,
	}

	// Apply storage-side redaction.
	entryMap := map[string]any{
		"event_class": entry.EventClass,
		"parameters":  entry.Parameters,
	}
	redacted := StorageRedactEntry(entryMap)
	if redacted["storage_redacted"] == true {
		entry.Parameters = nil
		entry.StorageRedacted = true
	}

	// Route low-value events through aggregator if enabled.
	if s.aggregator != nil && eventClass == "malformed_or_spam" {
		s.aggregator.Submit(s.entryToMap(entry))
		return
	}

	// Best effort - don't fail the invocation if audit logging fails.
	err := server.AppendAudit(s.keys, s.storage, entry)
	if err == nil && s.hooks != nil && s.hooks.OnAuditAppend != nil {
		callHook(func() { s.hooks.OnAuditAppend(entry.SequenceNumber, capability, invocationID) })
	}
}

func (s *Service) entryToMap(entry *core.AuditEntry) map[string]any {
	m := map[string]any{
		"timestamp":              entry.Timestamp,
		"capability":             entry.Capability,
		"actor_key":              entry.RootPrincipal,
		"failure_type":           entry.FailureType,
		"event_class":            entry.EventClass,
		"retention_tier":         entry.RetentionTier,
		"expires_at":             entry.ExpiresAt,
		"invocation_id":          entry.InvocationID,
		"client_reference_id":    entry.ClientReferenceID,
		"task_id":                entry.TaskID,
		"parent_invocation_id":   entry.ParentInvocationID,
		"token_id":               entry.TokenID,
		"issuer":                 entry.Issuer,
		"subject":                entry.Subject,
	}
	if entry.ResultSummary != nil {
		if detail, ok := entry.ResultSummary["detail"]; ok {
			m["detail"] = detail
		}
	}
	return m
}

// tokenClaimsMap builds the claims map used for disclosure level resolution.
func tokenClaimsMap(token *core.DelegationToken) map[string]any {
	claims := map[string]any{
		"scope": token.Scope,
	}
	if token.CallerClass != "" {
		claims["anip:caller_class"] = token.CallerClass
	}
	return claims
}
