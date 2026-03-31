package server

import (
	"crypto/rand"
	"fmt"
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
	constraints := core.DelegationConstraints{
		MaxDelegationDepth: 3,
		ConcurrentBranches: "allowed",
		Budget:             req.Budget,
	}

	// Determine issuer and root_principal.
	issuer := serviceID
	rootPrincipal := principal
	parent := ""

	// If there's a parent token, look it up by ID for sub-delegation.
	// parent_token is a stored token ID (e.g., "tok_root_001"), not a JWT.
	if req.ParentToken != "" {
		parentToken, err := storage.LoadToken(req.ParentToken)
		if err != nil || parentToken == nil {
			return core.TokenResponse{}, core.NewANIPError(core.FailureInvalidToken,
				fmt.Sprintf("parent token not found: %s", req.ParentToken))
		}

		issuer = parentToken.Subject
		rootPrincipal = parentToken.RootPrincipal
		parent = parentToken.TokenID
		constraints = parentToken.Constraints

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

	jwt, err := crypto.SignDelegationJWT(km, claims)
	if err != nil {
		return core.TokenResponse{}, fmt.Errorf("sign JWT: %w", err)
	}

	return core.TokenResponse{
		Issued:  true,
		TokenID: tokenID,
		Token:   jwt,
		Expires: expires.Format(time.RFC3339),
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
		).WithResolution("request_scope_grant")
	}

	return nil
}

// generateTokenID creates a random token ID.
func generateTokenID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return fmt.Sprintf("anip-%x", b)
}
