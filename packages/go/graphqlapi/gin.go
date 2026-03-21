package graphqlapi

import (
	"context"
	"fmt"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/graphql-go/graphql"

	"github.com/anip-protocol/anip/packages/go/service"
)

// MountANIPGraphQLGin registers GraphQL endpoints on a Gin router.
func MountANIPGraphQLGin(router *gin.Engine, svc *service.Service, opts *GraphQLOptions) {
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
	router.POST(fullPath, func(c *gin.Context) {
		var req graphQLRequest
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusOK, map[string]any{
				"errors": []map[string]any{
					{"message": "Invalid JSON body"},
				},
			})
			return
		}

		// Inject auth header into context for the resolver.
		authHeader := c.GetHeader("Authorization")
		ctx := context.WithValue(c.Request.Context(), authHeaderKey, authHeader)

		result := graphql.Do(graphql.Params{
			Schema:         *schema,
			RequestString:  req.Query,
			VariableValues: req.Variables,
			OperationName:  req.OperationName,
			Context:        ctx,
		})

		c.JSON(http.StatusOK, result)
	})

	// GET {prefix}{path} -- simple HTML playground
	router.GET(fullPath, func(c *gin.Context) {
		c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(playgroundHTML(fullPath)))
	})

	// GET {prefix}/schema.graphql -- raw SDL text
	router.GET(prefix+"/schema.graphql", func(c *gin.Context) {
		c.Data(http.StatusOK, "text/plain; charset=utf-8", []byte(sdlText))
	})
}
