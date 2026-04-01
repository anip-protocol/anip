package restapi

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/internal/httputil"
	"github.com/anip-protocol/anip/packages/go/service"
)

// MountANIPRestGin registers REST API endpoints on a Gin router.
// Routes are auto-generated from service capabilities.
func MountANIPRestGin(router *gin.Engine, svc *service.Service, opts *RestOptions) {
	if opts == nil {
		opts = &RestOptions{}
	}
	prefix := opts.Prefix

	// Generate routes from service capabilities.
	routes := GenerateRoutes(svc, opts.Routes)
	serviceID := svc.ServiceID()
	openAPISpec := GenerateOpenAPISpec(serviceID, routes)

	// Register OpenAPI endpoints under /rest/ to avoid framework collisions.
	router.GET(prefix+"/rest/openapi.json", func(c *gin.Context) {
		c.JSON(http.StatusOK, openAPISpec)
	})
	router.GET(prefix+"/rest/docs", func(c *gin.Context) {
		c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(swaggerHTML(prefix)))
	})

	// Register capability routes.
	for _, route := range routes {
		route := route // capture loop variable
		handler := func(c *gin.Context) {
			handleGinRESTRoute(c, svc, route)
		}
		if route.Method == "GET" {
			router.GET(prefix+route.Path, handler)
		} else {
			router.POST(prefix+route.Path, handler)
		}
	}
}

// handleGinRESTRoute processes a single REST capability route using Gin.
func handleGinRESTRoute(c *gin.Context, svc *service.Service, route RESTRoute) {
	// Extract auth
	authHeader := c.GetHeader("Authorization")
	bearer := httputil.ExtractBearer(authHeader)
	if bearer == "" {
		c.JSON(401, map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureAuthRequired,
				"detail": "Authorization header with Bearer token or API key required",
				"resolution": map[string]any{
					"action":         "provide_credentials",
					"recovery_class": core.RecoveryClassForAction("provide_credentials"),
					"requires":       "Bearer token or API key",
				},
				"retry": true,
			},
		})
		return
	}

	token, err := resolveRestAuth(bearer, svc, route.CapabilityName)
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok {
			status, body := httputil.FailureResponse(anipErr)
			c.JSON(status, body)
			return
		}
		c.JSON(500, map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureInternalError,
				"detail": "Authentication failed",
				"retry":  false,
			},
		})
		return
	}

	// Extract parameters
	var params map[string]any
	if route.Method == "GET" {
		// Convert Gin query params to map[string][]string for convertQueryParams
		queryMap := make(map[string][]string)
		for key, values := range c.Request.URL.Query() {
			queryMap[key] = values
		}
		params = convertQueryParams(queryMap, route.Declaration)
	} else {
		var body map[string]any
		if err := c.ShouldBindJSON(&body); err != nil {
			c.JSON(400, map[string]any{
				"success": false,
				"failure": map[string]any{
					"type":   "invalid_parameters",
					"detail": "Invalid JSON body",
					"retry":  false,
				},
			})
			return
		}
		// Accept both {parameters: {...}} and flat body
		if p, ok := body["parameters"].(map[string]any); ok {
			params = p
		} else {
			params = body
		}
	}

	clientReferenceID := c.GetHeader("X-Client-Reference-Id")

	result, err := svc.Invoke(route.CapabilityName, token, params, service.InvokeOpts{
		ClientReferenceID: clientReferenceID,
	})
	if err != nil {
		c.JSON(500, map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureInternalError,
				"detail": "Invocation failed",
				"retry":  false,
			},
		})
		return
	}

	// Determine HTTP status from result
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

// convertGinQueryParams converts Gin query params to typed values based on capability inputs.
// This is a convenience for Gin routes that want individual query param access.
func convertGinQueryParams(c *gin.Context, decl core.CapabilityDeclaration) map[string]any {
	result := make(map[string]any)
	for _, inp := range decl.Inputs {
		value := c.Query(inp.Name)
		if value == "" {
			continue
		}
		switch inp.Type {
		case "integer":
			if v, err := strconv.Atoi(value); err == nil {
				result[inp.Name] = v
			} else {
				result[inp.Name] = value
			}
		case "number":
			if v, err := strconv.ParseFloat(value, 64); err == nil {
				result[inp.Name] = v
			} else {
				result[inp.Name] = value
			}
		case "boolean":
			result[inp.Name] = value == "true"
		default:
			result[inp.Name] = value
		}
	}
	return result
}
