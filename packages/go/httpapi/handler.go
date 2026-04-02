// Package httpapi provides net/http handlers for all 9 ANIP protocol endpoints.
package httpapi

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/internal/httputil"
	"github.com/anip-protocol/anip/packages/go/server"
	"github.com/anip-protocol/anip/packages/go/service"
)

// MountANIPOpts holds optional configuration for MountANIP.
type MountANIPOpts struct {
	// HealthEndpoint enables GET /-/health when true.
	HealthEndpoint bool
}

// MountANIP registers all 9 ANIP protocol routes on the given ServeMux.
// Requires Go 1.22+ ServeMux for path parameter support.
func MountANIP(mux *http.ServeMux, svc *service.Service, opts ...MountANIPOpts) {
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

	// Optional health endpoint.
	if len(opts) > 0 && opts[0].HealthEndpoint {
		mux.HandleFunc("GET /-/health", handleHealth(svc))
	}
}

func handleHealth(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		report := svc.GetHealth()
		writeJSON(w, http.StatusOK, report)
	}
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
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Failed to list checkpoints", nil)
			writeJSON(w, status, body)
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

		consistencyFrom := r.URL.Query().Get("consistency_from")

		resp, err := svc.GetCheckpoint(id, includeProof, leafIndex, consistencyFrom)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				status, body := httputil.FailureResponse(anipErr)
				writeJSON(w, status, body)
				return
			}
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Failed to get checkpoint", nil)
			writeJSON(w, status, body)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

// --- Token Issuance (Bootstrap Auth) ---

func handleTokens(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bearer := httputil.ExtractBearer(r.Header.Get("Authorization"))
		if bearer == "" {
			status, body := httputil.AuthFailureTokenEndpoint()
			writeJSON(w, status, body)
			return
		}

		principal, ok := svc.AuthenticateBearer(bearer)
		if !ok {
			status, body := httputil.AuthFailureTokenEndpoint()
			writeJSON(w, status, body)
			return
		}

		var req core.TokenRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Invalid request body", nil)
			writeJSON(w, status, body)
			return
		}

		resp, err := svc.IssueToken(principal, req)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				status, body := httputil.FailureResponse(anipErr)
				writeJSON(w, status, body)
				return
			}
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Token issuance failed", nil)
			writeJSON(w, status, body)
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
			status, respBody := httputil.SimpleFailureResponse(core.FailureInternalError, "Invalid request body", nil)
			writeJSON(w, status, respBody)
			return
		}

		params, _ := body["parameters"].(map[string]any)
		if params == nil {
			// Fall back to body itself if no "parameters" key.
			params = body
		}
		clientRefID, _ := body["client_reference_id"].(string)
		taskID, _ := body["task_id"].(string)
		parentInvID, _ := body["parent_invocation_id"].(string)
		upstreamSvc, _ := body["upstream_service"].(string)
		stream, _ := body["stream"].(bool)

		// Extract budget from request body.
		var budget *core.Budget
		if budgetRaw, ok := body["budget"].(map[string]any); ok {
			currency, _ := budgetRaw["currency"].(string)
			maxAmount, _ := budgetRaw["max_amount"].(float64)
			if currency != "" && maxAmount > 0 {
				budget = &core.Budget{Currency: currency, MaxAmount: maxAmount}
			}
		}

		if stream {
			handleStreamInvoke(w, svc, capName, token, params, clientRefID, taskID, parentInvID, upstreamSvc, budget)
			return
		}

		result, err := svc.Invoke(capName, token, params, service.InvokeOpts{
			ClientReferenceID:  clientRefID,
			TaskID:             taskID,
			ParentInvocationID: parentInvID,
			UpstreamService:    upstreamSvc,
			Stream:             false,
			Budget:             budget,
		})
		if err != nil {
			status, respBody := httputil.SimpleFailureResponse(core.FailureInternalError, "Invocation failed", nil)
			writeJSON(w, status, respBody)
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

func handleStreamInvoke(w http.ResponseWriter, svc *service.Service, capName string, token *core.DelegationToken, params map[string]any, clientRefID, taskID, parentInvID, upstreamSvc string, budget *core.Budget) {
	sr, err := svc.InvokeStream(capName, token, params, service.InvokeOpts{
		ClientReferenceID:  clientRefID,
		TaskID:             taskID,
		ParentInvocationID: parentInvID,
		UpstreamService:    upstreamSvc,
		Stream:             true,
		Budget:             budget,
	})
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			status, body := httputil.FailureResponse(anipErr)
			writeJSON(w, status, body)
			return
		}
		status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Invocation failed", nil)
		writeJSON(w, status, body)
		return
	}

	// Set SSE headers.
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)

	flusher, hasFlusher := w.(http.Flusher)

	for event := range sr.Events {
		data, _ := json.Marshal(event.Payload)
		_, writeErr := fmt.Fprintf(w, "event: %s\ndata: %s\n\n", event.Type, data)
		if writeErr != nil {
			// Client disconnected — signal handler to stop
			sr.Cancel()
			return
		}
		if hasFlusher {
			flusher.Flush()
		}
	}
}

func handleAudit(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, ok := resolveToken(w, r, svc)
		if !ok {
			return
		}

		filters := server.AuditFilters{
			Capability:         r.URL.Query().Get("capability"),
			Since:              r.URL.Query().Get("since"),
			InvocationID:       r.URL.Query().Get("invocation_id"),
			ClientReferenceID:  r.URL.Query().Get("client_reference_id"),
			TaskID:             r.URL.Query().Get("task_id"),
			ParentInvocationID: r.URL.Query().Get("parent_invocation_id"),
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
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Audit query failed", nil)
			writeJSON(w, status, body)
			return
		}
		writeJSON(w, http.StatusOK, resp)
	}
}

// --- Auth Helpers ---

// resolveToken extracts and resolves the JWT from the Authorization header.
// On failure, it writes the appropriate error response and returns (nil, false).
func resolveToken(w http.ResponseWriter, r *http.Request, svc *service.Service) (*core.DelegationToken, bool) {
	bearer := httputil.ExtractBearer(r.Header.Get("Authorization"))
	if bearer == "" {
		status, body := httputil.AuthFailureJWTEndpoint()
		writeJSON(w, status, body)
		return nil, false
	}

	token, err := svc.ResolveBearerToken(bearer)
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			status, body := httputil.FailureResponse(anipErr)
			writeJSON(w, status, body)
			return nil, false
		}
		anipErr := core.NewANIPError(core.FailureInvalidToken, "Invalid or expired delegation token").
			WithResolution("request_new_delegation")
		status, body := httputil.FailureResponse(anipErr)
		writeJSON(w, status, body)
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
