package service

import (
	"fmt"
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
)

// DiscoverPermissions checks the token's scope against all registered capabilities
// and returns what the token can and cannot do.
func (s *Service) DiscoverPermissions(token *core.DelegationToken) core.PermissionResponse {
	var available []core.AvailableCapability
	var restricted []core.RestrictedCapability
	var denied []core.DeniedCapability

	// Build token scope bases: (base, full_scope)
	type scopeEntry struct {
		base string
		full string
	}
	tokenScopeEntries := make([]scopeEntry, len(token.Scope))
	for i, s := range token.Scope {
		tokenScopeEntries[i] = scopeEntry{
			base: strings.SplitN(s, ":", 2)[0],
			full: s,
		}
	}

	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}

	for name, cap := range s.capabilities {
		requiredScopes := cap.Declaration.MinimumScope
		var matchedScopeStrs []string
		var missing []string

		for _, required := range requiredScopes {
			var matchedFull string
			for _, entry := range tokenScopeEntries {
				if entry.base == required || strings.HasPrefix(required, entry.base+".") {
					matchedFull = entry.full
					break
				}
			}
			if matchedFull != "" {
				matchedScopeStrs = append(matchedScopeStrs, matchedFull)
			} else {
				missing = append(missing, required)
			}
		}

		if len(missing) == 0 {
			// Scope matched — check token-evaluable control requirements.
			var unmet []string
			for _, req := range cap.Declaration.ControlRequirements {
				switch req.Type {
				case "cost_ceiling":
					if token.Constraints.Budget == nil {
						unmet = append(unmet, "cost_ceiling")
					}
				case "stronger_delegation_required":
					tokenHasExplicitBinding := token.Purpose.Capability == name
					if !tokenHasExplicitBinding {
						unmet = append(unmet, "stronger_delegation_required")
					}
				}
			}

			if len(unmet) > 0 {
				hasRejectEnforcement := false
				for _, req := range cap.Declaration.ControlRequirements {
					if req.Enforcement == "reject" {
						for _, u := range unmet {
							if req.Type == u {
								hasRejectEnforcement = true
								break
							}
						}
					}
					if hasRejectEnforcement {
						break
					}
				}
				if hasRejectEnforcement {
					ctrlResolutionHint := "request_capability_binding"
					for _, u := range unmet {
						if u == "cost_ceiling" {
							ctrlResolutionHint = "request_budget_bound_delegation"
							break
						}
					}
					restricted = append(restricted, core.RestrictedCapability{
						Capability:             name,
						Reason:                 fmt.Sprintf("missing control requirements: %s", strings.Join(unmet, ", ")),
						ReasonType:             "unmet_control_requirement",
						GrantableBy:            rootPrincipal,
						UnmetTokenRequirements: unmet,
						ResolutionHint:         ctrlResolutionHint,
					})
					continue
				}
			}

			// Available.
			constraints := map[string]any{}
			for _, scopeStr := range matchedScopeStrs {
				if strings.Contains(scopeStr, ":max_$") {
					parts := strings.SplitN(scopeStr, ":max_$", 2)
					if len(parts) == 2 {
						var maxBudget float64
						fmt.Sscanf(parts[1], "%f", &maxBudget)
						constraints["budget_remaining"] = maxBudget
						constraints["currency"] = "USD"
					}
				}
			}
			// Include constraints-level budget info if present.
			if token.Constraints.Budget != nil {
				constraints["budget_remaining"] = token.Constraints.Budget.MaxAmount
				constraints["currency"] = token.Constraints.Budget.Currency
			}
			available = append(available, core.AvailableCapability{
				Capability:  name,
				ScopeMatch:  strings.Join(matchedScopeStrs, ", "),
				Constraints: constraints,
			})
		} else {
			// Check if any missing scopes require admin.
			hasAdmin := false
			for _, s := range missing {
				if strings.HasPrefix(s, "admin.") {
					hasAdmin = true
					break
				}
			}

			if hasAdmin {
				denied = append(denied, core.DeniedCapability{
					Capability: name,
					Reason:     "requires admin principal",
					ReasonType: "non_delegable",
				})
			} else {
				restricted = append(restricted, core.RestrictedCapability{
					Capability:     name,
					Reason:         fmt.Sprintf("delegation chain lacks scope(s): %s", strings.Join(missing, ", ")),
					ReasonType:     "insufficient_scope",
					GrantableBy:    rootPrincipal,
					ResolutionHint: "request_broader_scope",
				})
			}
		}
	}

	// Ensure non-nil slices for JSON serialization.
	if available == nil {
		available = []core.AvailableCapability{}
	}
	if restricted == nil {
		restricted = []core.RestrictedCapability{}
	}
	if denied == nil {
		denied = []core.DeniedCapability{}
	}

	return core.PermissionResponse{
		Available:  available,
		Restricted: restricted,
		Denied:     denied,
	}
}
