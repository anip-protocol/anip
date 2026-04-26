// Package httpapi provides net/http handlers for all 9 ANIP protocol endpoints.
package httpapi

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

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
	mux.HandleFunc("GET /anip/graph/{capability}", handleGraph(svc))

	// Bootstrap auth route (API key).
	mux.HandleFunc("POST /anip/tokens", handleTokens(svc))

	// JWT-authenticated routes.
	mux.HandleFunc("POST /anip/permissions", handlePermissions(svc))
	mux.HandleFunc("POST /anip/invoke/{capability}", handleInvoke(svc))
	mux.HandleFunc("POST /anip/approval_grants", handleApprovalGrants(svc)) // v0.23
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

func handleGraph(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		capability := r.PathValue("capability")
		graph := svc.GetCapabilityGraph(capability)
		if graph == nil {
			status, body := httputil.SimpleFailureResponse(
				"not_found",
				fmt.Sprintf("Capability '%s' not found", capability),
				nil,
			)
			writeJSON(w, status, body)
			return
		}
		writeJSON(w, http.StatusOK, graph)
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
		approvalGrant, _ := body["approval_grant"].(string) // v0.23

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
			handleStreamInvoke(w, svc, capName, token, params, clientRefID, taskID, parentInvID, upstreamSvc, budget, approvalGrant)
			return
		}

		result, err := svc.Invoke(capName, token, params, service.InvokeOpts{
			ClientReferenceID:  clientRefID,
			TaskID:             taskID,
			ParentInvocationID: parentInvID,
			UpstreamService:    upstreamSvc,
			Stream:             false,
			Budget:             budget,
			ApprovalGrant:      approvalGrant,
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

// handleApprovalGrants implements POST /anip/approval_grants. v0.23 §4.9.
//
// Validation order is security-relevant per SPEC.md §4.9 line 1090:
//  1. authn (already handled by resolveToken)
//  2. parse body + schema-validate
//  3. load ApprovalRequest
//  4. state check (decided / expired) — BEFORE approver auth
//  5. approver authority check
//  6. issueApprovalGrant (steps 6–11 of the spec)
func handleApprovalGrants(svc *service.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, ok := resolveToken(w, r, svc)
		if !ok {
			return
		}

		var body core.IssueApprovalGrantRequest
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			status, resp := httputil.SimpleFailureResponse(core.FailureInvalidParameters, "request body must be JSON", nil)
			writeJSON(w, status, resp)
			return
		}
		if err := validateIssueGrantBody(&body); err != nil {
			status, resp := httputil.SimpleFailureResponse(core.FailureInvalidParameters, err.Error(), nil)
			writeJSON(w, status, resp)
			return
		}

		req, err := svc.GetApprovalRequest(body.ApprovalRequestID)
		if err != nil {
			status, resp := httputil.SimpleFailureResponse(core.FailureInternalError, "lookup failed", nil)
			writeJSON(w, status, resp)
			return
		}
		if req == nil {
			status, resp := httputil.SimpleFailureResponse(service.FailureApprovalRequestNotFound,
				fmt.Sprintf("approval_request_id %q not found", body.ApprovalRequestID), nil)
			writeJSON(w, status, resp)
			return
		}

		// SPEC.md §4.9 step 4: state check BEFORE approver authority.
		now := time.Now().UTC().Format(time.RFC3339Nano)
		if req.Status != core.ApprovalRequestStatusPending {
			status, resp := httputil.SimpleFailureResponse(service.FailureApprovalRequestAlreadyDone,
				fmt.Sprintf("approval_request %q status=%s", body.ApprovalRequestID, req.Status), nil)
			writeJSON(w, 409, resp)
			_ = status
			return
		}
		if req.ExpiresAt <= now {
			_, resp := httputil.SimpleFailureResponse(service.FailureApprovalRequestExpired,
				fmt.Sprintf("approval_request %q expired", body.ApprovalRequestID), nil)
			writeJSON(w, 409, resp)
			return
		}

		// Approver authority: token scope contains approver:* OR approver:<capability>.
		accepted := map[string]struct{}{
			"approver:*":                {},
			"approver:" + req.Capability: {},
		}
		authorized := false
		for _, sc := range token.Scope {
			if _, ok := accepted[sc]; ok {
				authorized = true
				break
			}
		}
		if !authorized {
			_, resp := httputil.SimpleFailureResponse(service.FailureApproverNotAuthorized,
				fmt.Sprintf("token lacks approver:%s scope", req.Capability), nil)
			writeJSON(w, 403, resp)
			return
		}

		approver := map[string]any{
			"subject":        token.Subject,
			"root_principal": token.RootPrincipal,
		}
		opts := service.IssueApprovalGrantOpts{
			SessionID:        body.SessionID,
			ExpiresInSeconds: body.ExpiresInSeconds,
			MaxUses:          body.MaxUses,
		}
		grant, err := svc.IssueApprovalGrant(body.ApprovalRequestID, body.GrantType, approver, opts)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				status, resp := httputil.FailureResponse(anipErr)
				writeJSON(w, status, resp)
				return
			}
			status, resp := httputil.SimpleFailureResponse(core.FailureInternalError, "issuance failed", nil)
			writeJSON(w, status, resp)
			return
		}
		// SPEC.md §4.9: 200 IS the signed ApprovalGrant — no wrapper.
		writeJSON(w, http.StatusOK, grant)
	}
}

// validateIssueGrantBody enforces the schema invariants on the issuance
// request. The HTTP layer surfaces these as invalid_parameters; the service
// layer additionally clamps against grant_policy.
func validateIssueGrantBody(b *core.IssueApprovalGrantRequest) error {
	if b.ApprovalRequestID == "" {
		return fmt.Errorf("approval_request_id: required")
	}
	switch b.GrantType {
	case core.GrantTypeOneTime, core.GrantTypeSessionBound:
	default:
		return fmt.Errorf("grant_type: must be one_time or session_bound")
	}
	if b.GrantType == core.GrantTypeSessionBound && b.SessionID == "" {
		return fmt.Errorf("session_id: required when grant_type=session_bound")
	}
	if b.GrantType == core.GrantTypeOneTime && b.SessionID != "" {
		return fmt.Errorf("session_id: must not be set when grant_type=one_time")
	}
	// SPEC.md §4.9: when present, expires_in_seconds and max_uses must be
	// positive integers. Pointers distinguish absence from explicit 0.
	if b.ExpiresInSeconds != nil && *b.ExpiresInSeconds < 1 {
		return fmt.Errorf("expires_in_seconds: must be a positive integer")
	}
	if b.MaxUses != nil && *b.MaxUses < 1 {
		return fmt.Errorf("max_uses: must be a positive integer")
	}
	return nil
}

func handleStreamInvoke(w http.ResponseWriter, svc *service.Service, capName string, token *core.DelegationToken, params map[string]any, clientRefID, taskID, parentInvID, upstreamSvc string, budget *core.Budget, approvalGrant string) {
	sr, err := svc.InvokeStream(capName, token, params, service.InvokeOpts{
		ClientReferenceID:  clientRefID,
		TaskID:             taskID,
		ParentInvocationID: parentInvID,
		UpstreamService:    upstreamSvc,
		Stream:             true,
		Budget:             budget,
		ApprovalGrant:      approvalGrant,
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
