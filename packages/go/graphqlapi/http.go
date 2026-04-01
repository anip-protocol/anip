package graphqlapi

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/graphql-go/graphql"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/internal/httputil"
	"github.com/anip-protocol/anip/packages/go/service"
)

// GraphQLOptions configures the GraphQL mount.
type GraphQLOptions struct {
	Path   string // default "/graphql"
	Prefix string // default ""
}

// contextKey is a private key type for context values.
type contextKey string

const authHeaderKey contextKey = "authHeader"

// graphQLRequest is the JSON body for a GraphQL POST request.
type graphQLRequest struct {
	Query         string         `json:"query"`
	Variables     map[string]any `json:"variables"`
	OperationName string         `json:"operationName"`
}

// MountANIPGraphQL registers GraphQL endpoints on a net/http ServeMux.
func MountANIPGraphQL(mux *http.ServeMux, svc *service.Service, opts *GraphQLOptions) {
	if opts == nil {
		opts = &GraphQLOptions{}
	}
	path := opts.Path
	if path == "" {
		path = "/graphql"
	}
	prefix := opts.Prefix
	fullPath := prefix + path

	// Build schema with resolver factory.
	schema, sdlText, err := BuildSchema(svc, func(capName string) graphql.FieldResolveFn {
		return makeResolver(svc, capName)
	})
	if err != nil {
		panic(fmt.Sprintf("graphqlapi: build schema: %v", err))
	}

	// POST {prefix}{path} -- execute GraphQL query/mutation
	mux.HandleFunc("POST "+fullPath, func(w http.ResponseWriter, r *http.Request) {
		var req graphQLRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONResponse(w, http.StatusOK, map[string]any{
				"errors": []map[string]any{
					{"message": "Invalid JSON body"},
				},
			})
			return
		}

		// Inject auth header into context for the resolver.
		authHeader := r.Header.Get("Authorization")
		ctx := context.WithValue(r.Context(), authHeaderKey, authHeader)

		result := graphql.Do(graphql.Params{
			Schema:         *schema,
			RequestString:  req.Query,
			VariableValues: req.Variables,
			OperationName:  req.OperationName,
			Context:        ctx,
		})

		writeJSONResponse(w, http.StatusOK, result)
	})

	// GET {prefix}{path} -- simple HTML playground
	mux.HandleFunc("GET "+fullPath, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(playgroundHTML(fullPath)))
	})

	// GET {prefix}/schema.graphql -- raw SDL text
	mux.HandleFunc("GET "+prefix+"/schema.graphql", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(sdlText))
	})
}

// makeResolver creates a resolver function for a given capability.
// It extracts the auth header from context, resolves auth, converts args,
// invokes the capability, and maps the result to GraphQL camelCase shape.
func makeResolver(svc *service.Service, capName string) graphql.FieldResolveFn {
	return func(p graphql.ResolveParams) (any, error) {
		// Extract auth header from context.
		authHeader, _ := p.Context.Value(authHeaderKey).(string)
		bearer := httputil.ExtractBearer(authHeader)

		if bearer == "" {
			return BuildGraphQLResponse(map[string]any{
				"success": false,
				"failure": map[string]any{
					"type":       core.FailureAuthRequired,
					"detail":     "Authorization header required",
					"resolution": map[string]any{"action": "provide_credentials", "recovery_class": core.RecoveryClassForAction("provide_credentials")},
					"retry":      true,
				},
			}), nil
		}

		token, err := resolveGraphQLAuth(bearer, svc, capName)
		if err != nil {
			if anipErr, ok := err.(*core.ANIPError); ok {
				failure := map[string]any{
					"type":   anipErr.ErrorType,
					"detail": anipErr.Detail,
					"retry":  anipErr.Retry,
				}
				if anipErr.Resolution != nil {
					failure["resolution"] = resolutionToMap(anipErr.Resolution)
				}
				return BuildGraphQLResponse(map[string]any{
					"success": false,
					"failure": failure,
				}), nil
			}
			return nil, err
		}

		// Convert camelCase args to snake_case for ANIP.
		snakeArgs := make(map[string]any)
		for k, v := range p.Args {
			snakeArgs[ToSnakeCase(k)] = v
		}

		result, err := svc.Invoke(capName, token, snakeArgs, service.InvokeOpts{})
		if err != nil {
			failure := map[string]any{
				"type":   core.FailureInternalError,
				"detail": "Invocation failed",
				"retry":  false,
			}
			if anipErr, ok := err.(*core.ANIPError); ok {
				failure["type"] = anipErr.ErrorType
				failure["detail"] = anipErr.Detail
				failure["retry"] = anipErr.Retry
				if anipErr.Resolution != nil {
					failure["resolution"] = resolutionToMap(anipErr.Resolution)
				}
			}
			return BuildGraphQLResponse(map[string]any{
				"success": false,
				"failure": failure,
			}), nil
		}

		return BuildGraphQLResponse(result), nil
	}
}

// playgroundHTML returns a simple HTML playground for GraphQL.
func playgroundHTML(endpoint string) string {
	return `<!DOCTYPE html>
<html><head><title>ANIP GraphQL</title></head><body>
<h2>ANIP GraphQL Playground</h2>
<textarea id="q" rows="10" cols="60">{ }</textarea><br>
<button onclick="run()">Run</button><pre id="r"></pre>
<script>
async function run() {
  const r = await fetch("` + endpoint + `", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query: document.getElementById("q").value})
  });
  document.getElementById("r").textContent = JSON.stringify(await r.json(), null, 2);
}
</script></body></html>`
}

// resolutionToMap converts a *core.Resolution struct to a map[string]any with snake_case keys
// suitable for passing through BuildGraphQLResponse.
func resolutionToMap(r *core.Resolution) map[string]any {
	m := map[string]any{
		"action":         r.Action,
		"recovery_class": r.RecoveryClass,
		"requires":       r.Requires,
		"grantable_by":   r.GrantableBy,
	}
	return m
}

// writeJSONResponse writes a JSON response.
func writeJSONResponse(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
