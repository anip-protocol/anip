package restapi

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/internal/httputil"
	"github.com/anip-protocol/anip/packages/go/service"
)

// MountANIPRest registers REST API endpoints on a net/http ServeMux.
// Routes are auto-generated from service capabilities.
func MountANIPRest(mux *http.ServeMux, svc *service.Service, opts *RestOptions) {
	if opts == nil {
		opts = &RestOptions{}
	}
	prefix := opts.Prefix

	// Generate routes from service capabilities.
	routes := GenerateRoutes(svc, opts.Routes)
	serviceID := svc.ServiceID()
	openAPISpec := GenerateOpenAPISpec(serviceID, routes)

	// Register OpenAPI endpoints under /rest/ to avoid framework collisions.
	mux.HandleFunc("GET "+prefix+"/rest/openapi.json", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, openAPISpec)
	})
	mux.HandleFunc("GET "+prefix+"/rest/docs", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(swaggerHTML(prefix)))
	})

	// Register capability routes.
	for _, route := range routes {
		route := route // capture loop variable
		handler := func(w http.ResponseWriter, r *http.Request) {
			handleRESTRoute(w, r, svc, route)
		}
		if route.Method == "GET" {
			mux.HandleFunc("GET "+prefix+route.Path, handler)
		} else {
			mux.HandleFunc("POST "+prefix+route.Path, handler)
		}
	}
}

// handleRESTRoute processes a single REST capability route.
func handleRESTRoute(w http.ResponseWriter, r *http.Request, svc *service.Service, route RESTRoute) {
	// Extract auth
	authHeader := r.Header.Get("Authorization")
	bearer := httputil.ExtractBearer(authHeader)
	if bearer == "" {
		writeJSON(w, 401, map[string]any{
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureAuthRequired,
				"detail": "Authorization header with Bearer token or API key required",
				"resolution": map[string]any{
					"action":   "provide_credentials",
					"requires": "Bearer token or API key",
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
			writeJSON(w, status, body)
			return
		}
		writeJSON(w, 500, map[string]any{
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
		params = convertQueryParams(r.URL.Query(), route.Declaration)
	} else {
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeJSON(w, 400, map[string]any{
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

	clientReferenceID := r.Header.Get("X-Client-Reference-Id")

	result, err := svc.Invoke(route.CapabilityName, token, params, service.InvokeOpts{
		ClientReferenceID: clientReferenceID,
	})
	if err != nil {
		writeJSON(w, 500, map[string]any{
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
		writeJSON(w, status, result)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

// convertQueryParams converts URL query parameters to typed values based on capability inputs.
func convertQueryParams(query map[string][]string, decl core.CapabilityDeclaration) map[string]any {
	// Build type map from inputs
	typeMap := make(map[string]string)
	for _, inp := range decl.Inputs {
		typeMap[inp.Name] = inp.Type
	}

	result := make(map[string]any)
	for key, values := range query {
		if len(values) == 0 {
			continue
		}
		value := values[0]
		inputType := typeMap[key]
		switch inputType {
		case "integer":
			if v, err := strconv.Atoi(value); err == nil {
				result[key] = v
			} else {
				result[key] = value
			}
		case "number":
			if v, err := strconv.ParseFloat(value, 64); err == nil {
				result[key] = v
			} else {
				result[key] = value
			}
		case "boolean":
			result[key] = value == "true"
		default:
			result[key] = value
		}
	}
	return result
}

// swaggerHTML returns a simple Swagger UI HTML page.
func swaggerHTML(prefix string) string {
	return `<!DOCTYPE html>
<html><head><title>ANIP REST API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({ url: "` + prefix + `/rest/openapi.json", dom_id: "#swagger-ui" });</script>
</body></html>`
}

// writeJSON writes a JSON response.
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
