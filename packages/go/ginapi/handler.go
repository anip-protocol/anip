// Package ginapi provides Gin framework handlers for all 9 ANIP protocol endpoints.
package ginapi

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/internal/httputil"
	"github.com/anip-protocol/anip/packages/go/server"
	"github.com/anip-protocol/anip/packages/go/service"
)

// MountANIPGin registers all 9 ANIP protocol routes on a Gin router.
func MountANIPGin(router *gin.Engine, svc *service.Service) {
	// Public routes (no auth).
	router.GET("/.well-known/anip", handleDiscovery(svc))
	router.GET("/.well-known/jwks.json", handleJWKS(svc))
	router.GET("/anip/manifest", handleManifest(svc))
	router.GET("/anip/checkpoints", handleListCheckpoints(svc))
	router.GET("/anip/checkpoints/:id", handleGetCheckpoint(svc))

	// Bootstrap auth route (API key).
	router.POST("/anip/tokens", handleTokens(svc))

	// JWT-authenticated routes.
	router.POST("/anip/permissions", handlePermissions(svc))
	router.POST("/anip/invoke/:capability", handleInvoke(svc))
	router.POST("/anip/audit", handleAudit(svc))
}

// --- Public Routes ---

func handleDiscovery(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		baseURL := deriveBaseURL(c)
		doc := svc.GetDiscovery(baseURL)
		c.JSON(http.StatusOK, doc)
	}
}

func handleJWKS(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		jwks := svc.GetJWKS()
		c.JSON(http.StatusOK, jwks)
	}
}

func handleManifest(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		bodyBytes, signature := svc.GetSignedManifest()
		if signature != "" {
			c.Header("X-ANIP-Signature", signature)
		}
		c.Data(http.StatusOK, "application/json", bodyBytes)
	}
}

func handleListCheckpoints(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		limit := 10
		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
				limit = parsed
			}
		}
		resp, err := svc.ListCheckpoints(limit)
		if err != nil {
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Failed to list checkpoints", nil)
			c.JSON(status, body)
			return
		}
		c.JSON(http.StatusOK, resp)
	}
}

func handleGetCheckpoint(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		includeProof := c.Query("include_proof") == "true"
		leafIndex := 0
		if li := c.Query("leaf_index"); li != "" {
			if parsed, err := strconv.Atoi(li); err == nil {
				leafIndex = parsed
			}
		}

		resp, err := svc.GetCheckpoint(id, includeProof, leafIndex)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				status, body := httputil.FailureResponse(anipErr)
				c.JSON(status, body)
				return
			}
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Failed to get checkpoint", nil)
			c.JSON(status, body)
			return
		}
		c.JSON(http.StatusOK, resp)
	}
}

// --- Token Issuance (Bootstrap Auth) ---

func handleTokens(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		bearer := httputil.ExtractBearer(c.GetHeader("Authorization"))
		if bearer == "" {
			status, body := httputil.AuthFailureTokenEndpoint()
			c.JSON(status, body)
			return
		}

		principal, ok := svc.AuthenticateBearer(bearer)
		if !ok {
			status, body := httputil.AuthFailureTokenEndpoint()
			c.JSON(status, body)
			return
		}

		var req core.TokenRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Invalid request body", nil)
			c.JSON(status, body)
			return
		}

		resp, err := svc.IssueToken(principal, req)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				status, body := httputil.FailureResponse(anipErr)
				c.JSON(status, body)
				return
			}
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Token issuance failed", nil)
			c.JSON(status, body)
			return
		}
		c.JSON(http.StatusOK, resp)
	}
}

// --- JWT-Authenticated Routes ---

func handlePermissions(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		token, ok := resolveToken(c, svc)
		if !ok {
			return
		}
		perms := svc.DiscoverPermissions(token)
		c.JSON(http.StatusOK, perms)
	}
}

func handleInvoke(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		capName := c.Param("capability")

		token, ok := resolveToken(c, svc)
		if !ok {
			return
		}

		var body map[string]any
		if err := c.ShouldBindJSON(&body); err != nil {
			status, respBody := httputil.SimpleFailureResponse(core.FailureInternalError, "Invalid request body", nil)
			c.JSON(status, respBody)
			return
		}

		params, _ := body["parameters"].(map[string]any)
		if params == nil {
			// Fall back to body itself if no "parameters" key.
			params = body
		}
		clientRefID, _ := body["client_reference_id"].(string)
		stream, _ := body["stream"].(bool)

		if stream {
			handleStreamInvoke(c, svc, capName, token, params, clientRefID)
			return
		}

		result, err := svc.Invoke(capName, token, params, service.InvokeOpts{
			ClientReferenceID: clientRefID,
			Stream:            false,
		})
		if err != nil {
			status, respBody := httputil.SimpleFailureResponse(core.FailureInternalError, "Invocation failed", nil)
			c.JSON(status, respBody)
			return
		}

		// Determine HTTP status from the result.
		success, _ := result["success"].(bool)
		if !success {
			failure, _ := result["failure"].(map[string]any)
			failType, _ := failure["type"].(string)
			status := core.FailureStatusCode(failType)
			c.JSON(status, result)
			return
		}
		c.JSON(http.StatusOK, result)
	}
}

func handleStreamInvoke(c *gin.Context, svc *service.Service, capName string, token *core.DelegationToken, params map[string]any, clientRefID string) {
	sr, err := svc.InvokeStream(capName, token, params, service.InvokeOpts{
		ClientReferenceID: clientRefID,
		Stream:            true,
	})
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			status, body := httputil.FailureResponse(anipErr)
			c.JSON(status, body)
			return
		}
		status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Invocation failed", nil)
		c.JSON(status, body)
		return
	}

	// Set SSE headers.
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.WriteHeader(http.StatusOK)

	for event := range sr.Events {
		data, _ := json.Marshal(event.Payload)
		_, writeErr := fmt.Fprintf(c.Writer, "event: %s\ndata: %s\n\n", event.Type, data)
		if writeErr != nil {
			// Client disconnected — signal handler to stop
			sr.Cancel()
			return
		}
		c.Writer.Flush()
	}
}

func handleAudit(svc *service.Service) gin.HandlerFunc {
	return func(c *gin.Context) {
		token, ok := resolveToken(c, svc)
		if !ok {
			return
		}

		filters := server.AuditFilters{
			Capability:        c.Query("capability"),
			Since:             c.Query("since"),
			InvocationID:      c.Query("invocation_id"),
			ClientReferenceID: c.Query("client_reference_id"),
		}
		if l := c.Query("limit"); l != "" {
			if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
				filters.Limit = parsed
			}
		} else {
			filters.Limit = 50
		}

		resp, err := svc.QueryAudit(token, filters)
		if err != nil {
			status, body := httputil.SimpleFailureResponse(core.FailureInternalError, "Audit query failed", nil)
			c.JSON(status, body)
			return
		}
		c.JSON(http.StatusOK, resp)
	}
}

// --- Auth Helpers ---

// resolveToken extracts and resolves the JWT from the Authorization header.
// On failure, it writes the appropriate error response and returns (nil, false).
func resolveToken(c *gin.Context, svc *service.Service) (*core.DelegationToken, bool) {
	bearer := httputil.ExtractBearer(c.GetHeader("Authorization"))
	if bearer == "" {
		status, body := httputil.AuthFailureJWTEndpoint()
		c.JSON(status, body)
		return nil, false
	}

	token, err := svc.ResolveBearerToken(bearer)
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			status, body := httputil.FailureResponse(anipErr)
			c.JSON(status, body)
			return nil, false
		}
		anipErr := core.NewANIPError(core.FailureInvalidToken, "Invalid or expired delegation token").
			WithResolution("obtain_delegation_token")
		status, body := httputil.FailureResponse(anipErr)
		c.JSON(status, body)
		return nil, false
	}
	return token, true
}

// deriveBaseURL extracts the base URL from the Gin context request.
func deriveBaseURL(c *gin.Context) string {
	scheme := "http"
	if c.Request.TLS != nil {
		scheme = "https"
	}
	// Check X-Forwarded-Proto header.
	if proto := c.GetHeader("X-Forwarded-Proto"); proto != "" {
		scheme = proto
	}
	return scheme + "://" + c.Request.Host
}
