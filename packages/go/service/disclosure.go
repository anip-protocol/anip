package service

// ResolveDisclosureLevel resolves the effective disclosure level.
// Fixed modes ("full", "reduced", "redacted") pass through.
// "policy" mode resolves caller class from token claims and applies the policy map.
// Implements SPEC §6.9 caller-class-aware disclosure.
func ResolveDisclosureLevel(level string, tokenClaims map[string]any, policy map[string]string) string {
	if level != "policy" {
		return level
	}

	callerClass := resolveCallerClass(tokenClaims)

	if policy == nil {
		return "redacted"
	}

	if mapped, ok := policy[callerClass]; ok {
		return mapped
	}
	if def, ok := policy["default"]; ok {
		return def
	}
	return "redacted"
}

// resolveCallerClass determines the caller class from token claims.
// Priority: 1) explicit anip:caller_class claim, 2) scope-derived, 3) "default".
func resolveCallerClass(claims map[string]any) string {
	if claims == nil {
		return "default"
	}

	if cc, ok := claims["anip:caller_class"].(string); ok && cc != "" {
		return cc
	}

	if scopes, ok := claims["scope"].([]any); ok {
		for _, s := range scopes {
			if str, ok := s.(string); ok && str == "audit:full" {
				return "audit_full"
			}
		}
	}

	return "default"
}
