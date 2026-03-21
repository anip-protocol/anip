// Package httpapi provides net/http handlers for all 9 ANIP protocol endpoints.
package httpapi

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
	"github.com/anip-protocol/anip/packages/go/service"
)

// MountANIP registers all 9 ANIP protocol routes on the given ServeMux.
// Requires Go 1.22+ ServeMux for path parameter support.
func MountANIP(mux *http.ServeMux, svc *service.Service) {
	// Public routes (no auth).
	mux.HandleFunc("GET /.well-known/anip", handleDiscovery(svc))
	mux.HandleFunc("GET /.well-known/jwks.json", handleJWKS(svc))
	mux.HandleFunc("GET /anip/manifest", handleManifest(svc))
	mux.HandleFunc("GET /anip/checkpoints", handleListCheckpoints(svc))
	mux.HandleFunc("GET /anip/checkpoints/{id}", handleGetCheckpoint(svc))

	// Bootstrap auth route (API key).
	mux.HandleFunc("POST /anip/tokens", handleTokens(svc))

	// JWT-authenticated routes.
	mux.HandleFunc("POST /anip/permissions", handlePermissions(svc))
	mux.HandleFunc("POST /anip/invoke/{capability}", handleInvoke(svc))
	mux.HandleFunc("POST /anip/audit", handleAudit(svc))
}

// --- Public Routes ---

func handleDiscovery(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		baseURL := deriveBaseURL(r)
		doc := svc.GetDiscovery(baseURL)
		writeJSON(w, http.StatusOK, doc)
	}
}

func handleJWKS(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		jwks := svc.GetJWKS()
		writeJSON(w, http.StatusOK, jwks)
	}
}

func handleManifest(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bodyBytes, signature := svc.GetSignedManifest()
		w.Header().Set("Content-Type", "application/json")
		if signature != "" {
			w.Header().Set("X-ANIP-Signature", signature)
		}
		w.WriteHeader(http.StatusOK)
		w.Write(bodyBytes)
	}
}

func handleListCheckpoints(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit := 10
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
				limit = parsed
			}
		}
		resp, err := svc.ListCheckpoints(limit)
		if err != nil {
			writeFailure(w, core.FailureInternalError, "Failed to list checkpoints", nil)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

func handleGetCheckpoint(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		includeProof := r.URL.Query().Get("include_proof") == "true"
		leafIndex := 0
		if li := r.URL.Query().Get("leaf_index"); li != "" {
			if parsed, err := strconv.Atoi(li); err == nil {
				leafIndex = parsed
			}
		}

		resp, err := svc.GetCheckpoint(id, includeProof, leafIndex)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				writeANIPError(w, anipErr)
				return
			}
			writeFailure(w, core.FailureInternalError, "Failed to get checkpoint", nil)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

// --- Token Issuance (Bootstrap Auth) ---

func handleTokens(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bearer := extractBearer(r)
		if bearer == "" {
			writeAuthFailureTokenEndpoint(w)
			return
		}

		principal, ok := svc.AuthenticateBearer(bearer)
		if !ok {
			writeAuthFailureTokenEndpoint(w)
			return
		}

		var req core.TokenRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeFailure(w, core.FailureInternalError, "Invalid request body", nil)
			return
		}

		resp, err := svc.IssueToken(principal, req)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				writeANIPError(w, anipErr)
				return
			}
			writeFailure(w, core.FailureInternalError, "Token issuance failed", nil)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

// --- JWT-Authenticated Routes ---

func handlePermissions(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, ok := resolveToken(w, r, svc)
		if !ok {
			return
		}
		perms := svc.DiscoverPermissions(token)
		writeJSON(w, http.StatusOK, perms)
	}
}

func handleInvoke(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		capName := r.PathValue("capability")

		token, ok := resolveToken(w, r, svc)
		if !ok {
			return
		}

		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeFailure(w, core.FailureInternalError, "Invalid request body", nil)
			return
		}

		params, _ := body["parameters"].(map[string]any)
		if params == nil {
			// Fall back to body itself if no "parameters" key.
			params = body
		}
		clientRefID, _ := body["client_reference_id"].(string)
		stream, _ := body["stream"].(bool)

		result, err := svc.Invoke(capName, token, params, service.InvokeOpts{
			ClientReferenceID: clientRefID,
			Stream:            stream,
		})
		if err != nil {
			writeFailure(w, core.FailureInternalError, "Invocation failed", nil)
			return
		}

		// Determine HTTP status from the result.
		success, _ := result["success"].(bool)
		if !success {
			failure, _ := result["failure"].(map[string]any)
			failType, _ := failure["type"].(string)
			status := core.FailureStatusCode(failType)
			writeJSON(w, status, result)
			return
		}
		writeJSON(w, http.StatusOK, result)
	}
}

func handleAudit(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, ok := resolveToken(w, r, svc)
		if !ok {
			return
		}

		filters := server.AuditFilters{
			Capability:        r.URL.Query().Get("capability"),
			Since:             r.URL.Query().Get("since"),
			InvocationID:      r.URL.Query().Get("invocation_id"),
			ClientReferenceID: r.URL.Query().Get("client_reference_id"),
		}
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
				filters.Limit = parsed
			}
		} else {
			filters.Limit = 50
		}

		resp, err := svc.QueryAudit(token, filters)
		if err != nil {
			writeFailure(w, core.FailureInternalError, "Audit query failed", nil)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

// --- Auth Helpers ---

// extractBearer extracts the bearer token from the Authorization header.
func extractBearer(r *http.Request) string {
	auth := r.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return ""
	}
	return strings.TrimSpace(auth[7:])
}

// resolveToken extracts and resolves the JWT from the Authorization header.
// On failure, it writes the appropriate error response and returns (nil, false).
func resolveToken(w http.ResponseWriter, r *http.Request, svc *service.Service) (*core.DelegationToken, bool) {
	bearer := extractBearer(r)
	if bearer == "" {
		writeAuthFailureJWTEndpoint(w)
		return nil, false
	}

	token, err := svc.ResolveBearerToken(bearer)
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			writeANIPError(w, anipErr)
			return nil, false
		}
		writeANIPError(w, core.NewANIPError(core.FailureInvalidToken, "Invalid or expired delegation token").
			WithResolution("obtain_delegation_token"))
		return nil, false
	}
	return token, true
}

// --- Response Writers ---

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeFailure(w http.ResponseWriter, failureType, detail string, resolution *core.Resolution) {
	status := core.FailureStatusCode(failureType)
	resp := map[string]any{
		"success": false,
		"failure": buildFailureBody(failureType, detail, resolution, false),
	}
	writeJSON(w, status, resp)
}

func writeANIPError(w http.ResponseWriter, anipErr *core.ANIPError) {
	status := core.FailureStatusCode(anipErr.ErrorType)
	resolution := anipErr.Resolution
	if resolution == nil {
		resolution = defaultResolution(anipErr.ErrorType)
	}
	resp := map[string]any{
		"success": false,
		"failure": buildFailureBody(anipErr.ErrorType, anipErr.Detail, resolution, anipErr.Retry),
	}
	writeJSON(w, status, resp)
}

func buildFailureBody(failureType, detail string, resolution *core.Resolution, retry bool) map[string]any {
	body := map[string]any{
		"type":   failureType,
		"detail": detail,
		"retry":  retry,
	}
	if resolution != nil {
		body["resolution"] = map[string]any{
			"action":                 resolution.Action,
			"requires":              nilIfEmpty(resolution.Requires),
			"grantable_by":          nilIfEmpty(resolution.GrantableBy),
			"estimated_availability": nilIfEmpty(resolution.EstimatedAvailability),
		}
	} else {
		body["resolution"] = map[string]any{
			"action":                 "contact_service_owner",
			"requires":              nil,
			"grantable_by":          nil,
			"estimated_availability": nil,
		}
	}
	return body
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func writeAuthFailureTokenEndpoint(w http.ResponseWriter) {
	resp := map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   core.FailureAuthRequired,
			"detail": "A valid API key is required to issue delegation tokens",
			"resolution": map[string]any{
				"action":                 "provide_api_key",
				"requires":              "API key in Authorization header",
				"grantable_by":          nil,
				"estimated_availability": nil,
			},
			"retry": true,
		},
	}
	writeJSON(w, http.StatusUnauthorized, resp)
}

func writeAuthFailureJWTEndpoint(w http.ResponseWriter) {
	resp := map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   core.FailureAuthRequired,
			"detail": "A valid delegation token (JWT) is required in the Authorization header",
			"resolution": map[string]any{
				"action":                 "obtain_delegation_token",
				"requires":              "Bearer token from POST /anip/tokens",
				"grantable_by":          nil,
				"estimated_availability": nil,
			},
			"retry": true,
		},
	}
	writeJSON(w, http.StatusUnauthorized, resp)
}

// defaultResolution returns a default resolution for known failure types.
func defaultResolution(failureType string) *core.Resolution {
	switch failureType {
	case core.FailureInvalidToken, core.FailureTokenExpired:
		return &core.Resolution{
			Action:   "obtain_delegation_token",
			Requires: "Valid JWT from POST /anip/tokens",
		}
	case core.FailureScopeInsufficient:
		return &core.Resolution{
			Action:   "request_broader_scope",
			Requires: "Token with required scope",
		}
	case core.FailureUnknownCapability:
		return &core.Resolution{
			Action:   "check_manifest",
			Requires: "Valid capability name from GET /anip/manifest",
		}
	default:
		return &core.Resolution{
			Action: "contact_service_owner",
		}
	}
}

// deriveBaseURL extracts the base URL from the request.
func deriveBaseURL(r *http.Request) string {
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	// Check X-Forwarded-Proto header.
	if proto := r.Header.Get("X-Forwarded-Proto"); proto != "" {
		scheme = proto
	}
	return scheme + "://" + r.Host
}
