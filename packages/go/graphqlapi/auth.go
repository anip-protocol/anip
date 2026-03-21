package graphqlapi

import (
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// resolveGraphQLAuth resolves auth from a bearer token string.
// JWT-first, API-key fallback. Only catches *core.ANIPError from JWT resolution;
// any other error is rethrown.
//
// 1. Try svc.ResolveBearerToken(bearer) -- JWT mode, preserves delegation chain
// 2. If ANIPError -> try svc.AuthenticateBearer(bearer) -- API key mode
// 3. If API key works -> issue synthetic token scoped to the capability
// 4. If neither works -> re-throw the original JWT error
// 5. Only catch ANIPError from JWT resolution, rethrow anything else
func resolveGraphQLAuth(bearer string, svc *service.Service, capabilityName string) (*core.DelegationToken, error) {
	// Try as JWT first -- preserves original delegation chain
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

	// Try as API key -- only if JWT failed with ANIPError
	principal, ok := svc.AuthenticateBearer(bearer)
	if ok && principal != "" {
		// This is a real API key -- issue synthetic token
		capDecl := svc.GetCapabilityDeclaration(capabilityName)
		var minScope []string
		if capDecl != nil {
			minScope = capDecl.MinimumScope
		}
		if len(minScope) == 0 {
			minScope = []string{"*"}
		}

		tokenResult, issueErr := svc.IssueToken(principal, core.TokenRequest{
			Subject:           "adapter:anip-graphql",
			Scope:             minScope,
			Capability:        capabilityName,
			PurposeParameters: map[string]any{"source": "graphql"},
		})
		if issueErr != nil {
			// API key authenticated but token issuance failed -- surface the real error
			return nil, issueErr
		}

		return svc.ResolveBearerToken(tokenResult.Token)
	}

	// Neither JWT nor API key -- surface the original JWT error
	return nil, jwtError
}
