package server

import (
	"crypto/rand"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/crypto"
)

// IssueDelegationToken creates a delegation token, signs it as a JWT, and stores it.
func IssueDelegationToken(
	km *crypto.KeyManager,
	storage Storage,
	serviceID string,
	principal string,
	req core.TokenRequest,
) (core.TokenResponse, error) {
	tokenID := generateTokenID()
	now := time.Now().UTC()

	ttlHours := req.TTLHours
	if ttlHours <= 0 {
		ttlHours = 2
	}
	expires := now.Add(time.Duration(ttlHours) * time.Hour)

	// Build purpose — use caller-supplied task_id if present
	pp := req.PurposeParameters
	if pp == nil {
		pp = map[string]any{}
	}
	var resolvedTaskID string
	if callerTaskID, ok := pp["task_id"]; ok && callerTaskID != nil {
		resolvedTaskID = fmt.Sprintf("%v", callerTaskID)
		delete(pp, "task_id")
	} else if req.PurposeParameters == nil {
		resolvedTaskID = fmt.Sprintf("task-%s", tokenID)
	}
	purpose := core.Purpose{
		Capability: req.Capability,
		Parameters: pp,
		TaskID:     resolvedTaskID,
	}

	// Build constraints.
	concurrent := req.ConcurrentBranches
	if concurrent == "" {
		concurrent = "allowed"
	}
	constraints := core.DelegationConstraints{
		MaxDelegationDepth: 3,
		ConcurrentBranches: concurrent,
		Budget:             req.Budget,
	}

	// Determine issuer and root_principal.
	issuer := serviceID
	rootPrincipal := principal
	parent := ""

	// v0.23: child tokens inherit parent.SessionID verbatim. Roots may set
	// SessionID via the request. SPEC.md §4.8: session identity is bound
	// at issuance and never widened.
	sessionID := req.SessionID

	// If there's a parent token, look it up by ID for sub-delegation.
	// parent_token is a stored token ID (e.g., "tok_root_001"), not a JWT.
	if req.ParentToken != "" {
		parentToken, err := storage.LoadToken(req.ParentToken)
		if err != nil || parentToken == nil {
			return core.TokenResponse{}, core.NewANIPError(core.FailureInvalidToken,
				fmt.Sprintf("parent token not found: %s", req.ParentToken))
		}

		// Trust boundary: only the holder of a token (its subject) may
		// delegate from it. A token ID is not a credential.
		if principal != parentToken.Subject {
			return core.TokenResponse{}, core.NewANIPError(core.FailureInsufficientAuthority,
				fmt.Sprintf("Caller '%s' is not the parent token's subject ('%s') — only the delegatee can sub-delegate",
					principal, parentToken.Subject))
		}
		// A child token can never carry more scope than its parent.
		if err := validateScopeNarrowing(parentToken, req.Scope); err != nil {
			return core.TokenResponse{}, err
		}

		issuer = parentToken.Subject
		rootPrincipal = parentToken.RootPrincipal
		parent = parentToken.TokenID
		constraints = parentToken.Constraints
		// v0.23: child inherits parent's session identity verbatim.
		sessionID = parentToken.SessionID

		// Budget narrowing: child budget must not exceed parent budget.
		if parentToken.Constraints.Budget != nil {
			if req.Budget == nil {
				// Child inherits parent budget.
				constraints.Budget = parentToken.Constraints.Budget
			} else if req.Budget.Currency != parentToken.Constraints.Budget.Currency {
				return core.TokenResponse{}, core.NewANIPError(core.FailureBudgetCurrencyMismatch,
					fmt.Sprintf("Child budget currency %s does not match parent %s",
						req.Budget.Currency, parentToken.Constraints.Budget.Currency))
			} else if req.Budget.MaxAmount > parentToken.Constraints.Budget.MaxAmount {
				return core.TokenResponse{}, core.NewANIPError(core.FailureBudgetExceeded,
					fmt.Sprintf("Child budget $%v exceeds parent budget $%v",
						req.Budget.MaxAmount, parentToken.Constraints.Budget.MaxAmount))
			} else {
				constraints.Budget = req.Budget
			}
		} else if req.Budget != nil {
			constraints.Budget = req.Budget
		}
	}

	// Default subject to the authenticated principal if not provided.
	subject := req.Subject
	if subject == "" {
		subject = principal
	}

	// Build the token record.
	token := &core.DelegationToken{
		TokenID:       tokenID,
		Issuer:        issuer,
		Subject:       subject,
		Scope:         req.Scope,
		Purpose:       purpose,
		Parent:        parent,
		Expires:       expires.Format(time.RFC3339),
		Constraints:   constraints,
		RootPrincipal: rootPrincipal,
		CallerClass:   req.CallerClass,
		SessionID:     sessionID,
	}

	// Store the token.
	if err := storage.StoreToken(token); err != nil {
		return core.TokenResponse{}, fmt.Errorf("store token: %w", err)
	}

	// Sign as JWT.
	claims := map[string]any{
		"jti":            tokenID,
		"iss":            serviceID,
		"sub":            subject,
		"aud":            serviceID,
		"iat":            now.Unix(),
		"exp":            expires.Unix(),
		"scope":          req.Scope,
		"root_principal": rootPrincipal,
		"capability":     req.Capability,
		"purpose":        purpose,
		"constraints":    constraints,
	}
	if parent != "" {
		claims["parent_token_id"] = parent
	}
	if sessionID != "" {
		// v0.23: bind session identity into the signed JWT so session_bound
		// grant validation can trust it. SPEC.md §4.8 line 1035.
		claims["anip:session_id"] = sessionID
	}

	jwt, err := crypto.SignDelegationJWT(km, claims)
	if err != nil {
		return core.TokenResponse{}, fmt.Errorf("sign JWT: %w", err)
	}

	return core.TokenResponse{
		Issued:  true,
		TokenID: tokenID,
		Token:   jwt,
		Expires: expires.Format(time.RFC3339),
		TaskID:  purpose.TaskID,
		Budget:  constraints.Budget,
	}, nil
}

// ResolveBearerToken verifies a JWT, loads the stored token, and compares signed claims
// against stored state to prevent forged inline fields.
func ResolveBearerToken(
	km *crypto.KeyManager,
	storage Storage,
	serviceID string,
	jwtStr string,
) (*core.DelegationToken, error) {
	// 1. Verify JWT signature + expiry + issuer/audience.
	claims, err := crypto.VerifyDelegationJWT(km, jwtStr, serviceID, serviceID)
	if err != nil {
		if strings.Contains(err.Error(), "expired") {
			return nil, core.NewANIPError(core.FailureTokenExpired, "delegation token has expired")
		}
		return nil, core.NewANIPError(core.FailureInvalidToken, "JWT verification failed: "+err.Error())
	}

	// 2. Extract jti -> token_id.
	tokenID, ok := claims["jti"].(string)
	if !ok || tokenID == "" {
		return nil, core.NewANIPError(core.FailureInvalidToken, "JWT missing jti claim")
	}

	// 3. Load stored token.
	stored, err := storage.LoadToken(tokenID)
	if err != nil {
		return nil, core.NewANIPError(core.FailureInternalError, "error loading token: "+err.Error())
	}
	if stored == nil {
		return nil, core.NewANIPError(core.FailureInvalidToken, "token not found in storage")
	}

	// 4. Compare signed claims against stored state.
	if sub, ok := claims["sub"].(string); ok && sub != stored.Subject {
		return nil, core.NewANIPError(core.FailureInvalidToken, "subject mismatch between JWT and stored token")
	}

	if rp, ok := claims["root_principal"].(string); ok && rp != stored.RootPrincipal {
		return nil, core.NewANIPError(core.FailureInvalidToken, "root_principal mismatch between JWT and stored token")
	}

	// v0.23 trust boundary: if either side carries a session_id, both must
	// agree. SPEC.md §4.8 line 1035: session identity for session_bound
	// grant validation MUST come from the signed token.
	jwtSessionID, _ := claims["anip:session_id"].(string)
	if jwtSessionID != stored.SessionID {
		return nil, core.NewANIPError(core.FailureInvalidToken,
			fmt.Sprintf("session_id mismatch: jwt=%q store=%q", jwtSessionID, stored.SessionID))
	}

	// 5. Return stored token.
	return stored, nil
}

// ValidateScope checks if the token's scope covers the capability's minimum_scope.
// Returns nil if valid, or an ANIPError if insufficient.
func ValidateScope(token *core.DelegationToken, minimumScope []string) error {
	tokenScopeBases := make([]string, len(token.Scope))
	for i, s := range token.Scope {
		tokenScopeBases[i] = strings.Split(s, ":")[0]
	}

	var missing []string
	for _, required := range minimumScope {
		matched := false
		for _, base := range tokenScopeBases {
			if base == required || strings.HasPrefix(required, base+".") {
				matched = true
				break
			}
		}
		if !matched {
			missing = append(missing, required)
		}
	}

	if len(missing) > 0 {
		return core.NewANIPError(
			core.FailureScopeInsufficient,
			fmt.Sprintf("delegation chain lacks scope(s): %s", strings.Join(missing, ", ")),
		).WithResolution("request_broader_scope")
	}

	return nil
}

// scopeBase strips a scope's constraint suffix: "travel.book:max_$500" -> "travel.book".
func scopeBase(scope string) string {
	return strings.Split(scope, ":")[0]
}

// scopeBudget reads the "max_$" amount carried by a scope string.
// present reports whether the scope carries a budget at all; valid reports
// whether that budget is a finite, non-negative number. NaN in particular
// must never be accepted: it compares false against everything.
func scopeBudget(scope string) (amount float64, present, valid bool) {
	_, raw, found := strings.Cut(scope, ":max_$")
	if !found {
		return 0, false, false
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil || math.IsNaN(value) || math.IsInf(value, 0) || value < 0 {
		return 0, true, false
	}
	return value, true, true
}

// validateScopeNarrowing rejects a delegated token whose scope is not within
// its parent's: every child scope must equal a parent scope or sit below it
// ("travel" covers "travel.search"), and a budget carried by the parent scope
// may be lowered but not dropped or raised.
func validateScopeNarrowing(parent *core.DelegationToken, childScope []string) error {
	parentBases := make([]string, len(parent.Scope))
	for i, s := range parent.Scope {
		parentBases[i] = scopeBase(s)
	}
	escalation := func(detail string) error {
		return core.NewANIPError(core.FailureScopeEscalation, detail).WithResolution("request_new_delegation")
	}

	for _, child := range childScope {
		childBase := scopeBase(child)
		covered := false
		for _, parentBase := range parentBases {
			if childBase == parentBase || strings.HasPrefix(childBase, parentBase+".") {
				covered = true
				break
			}
		}
		if !covered {
			sorted := append([]string(nil), parentBases...)
			sort.Strings(sorted)
			return escalation(fmt.Sprintf("child token scope '%s' is not a subset of parent token scopes: %s",
				childBase, strings.Join(sorted, ", ")))
		}

		for _, parentScope := range parent.Scope {
			parentBudget, parentHasBudget, parentValid := scopeBudget(parentScope)
			if !parentHasBudget || scopeBase(parentScope) != childBase {
				continue
			}
			if !parentValid {
				return escalation(fmt.Sprintf("parent scope '%s' carries a malformed budget; it cannot be delegated", childBase))
			}
			childBudget, childHasBudget, childValid := scopeBudget(child)
			if !childHasBudget {
				return escalation(fmt.Sprintf("child dropped budget constraint from scope '%s' (parent has max $%v)",
					childBase, parentBudget))
			}
			if !childValid {
				return escalation(fmt.Sprintf("child budget for scope '%s' is not a finite, non-negative amount", childBase))
			}
			// Written as "not within" so that any unexpected value fails closed.
			if !(childBudget <= parentBudget) {
				return escalation(fmt.Sprintf("child budget $%v exceeds parent budget $%v for scope '%s'",
					childBudget, parentBudget, childBase))
			}
		}
	}
	return nil
}

// ValidatePurpose enforces purpose binding: a token can only invoke the
// capability it was issued for, even when its scope would cover another.
func ValidatePurpose(token *core.DelegationToken, capabilityName string) error {
	if token.Purpose.Capability == capabilityName {
		return nil
	}
	return core.NewANIPError(core.FailurePurposeMismatch,
		fmt.Sprintf("delegation token purpose is %s but request is for %s", token.Purpose.Capability, capabilityName),
	).WithResolution("request_new_delegation").WithRetry()
}

// ValidateChain walks the token's delegation chain up to its root and
// rejects chains that are incomplete, deeper than the token's
// max_delegation_depth, or that pass through an expired ancestor.
func ValidateChain(storage Storage, token *core.DelegationToken) error {
	depth := 0
	seen := map[string]bool{token.TokenID: true}
	now := time.Now().UTC()

	for current := token; current.Parent != ""; depth++ {
		ancestor, err := storage.LoadToken(current.Parent)
		if err != nil {
			return core.NewANIPError(core.FailureInternalError, "error loading token: "+err.Error())
		}
		if ancestor == nil || seen[ancestor.TokenID] {
			return core.NewANIPError(core.FailureBrokenDelegationChain,
				fmt.Sprintf("delegation chain is incomplete — ancestor token '%s' is not registered", current.Parent),
			).WithResolution("request_deeper_delegation").WithRetry()
		}
		seen[ancestor.TokenID] = true
		if expires, err := time.Parse(time.RFC3339, ancestor.Expires); err == nil && expires.Before(now) {
			return core.NewANIPError(core.FailureParentTokenExpired,
				fmt.Sprintf("ancestor token %s in delegation chain has expired", ancestor.TokenID),
			).WithResolution("refresh_binding").WithRetry()
		}
		current = ancestor
	}

	if maxDepth := token.Constraints.MaxDelegationDepth; depth > maxDepth {
		return core.NewANIPError(core.FailureDelegationDepthExceeded,
			fmt.Sprintf("delegation chain depth is %d, max allowed is %d", depth, maxDepth),
		).WithResolution("request_deeper_delegation").WithRetry()
	}
	return nil
}

// ValidateDelegation runs every check a token must pass before it may invoke
// a capability: scope, purpose binding, and the delegation chain. Token
// signature and expiry are verified earlier, by ResolveBearerToken.
func ValidateDelegation(storage Storage, token *core.DelegationToken, minimumScope []string, capabilityName string) error {
	if err := ValidateScope(token, minimumScope); err != nil {
		return err
	}
	if err := ValidatePurpose(token, capabilityName); err != nil {
		return err
	}
	return ValidateChain(storage, token)
}

// generateTokenID creates a random token ID.
func generateTokenID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return fmt.Sprintf("anip-%x", b)
}
