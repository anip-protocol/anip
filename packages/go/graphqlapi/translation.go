// Package graphqlapi auto-generates a GraphQL schema from ANIP capabilities
// and mounts it on net/http and Gin.
package graphqlapi

import (
	"fmt"
	"sort"
	"strings"
	"unicode"

	"github.com/graphql-go/graphql"
	"github.com/graphql-go/graphql/language/ast"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// ToCamelCase converts snake_case to camelCase.
// e.g. "search_flights" -> "searchFlights"
func ToCamelCase(snake string) string {
	parts := strings.Split(snake, "_")
	if len(parts) == 0 {
		return snake
	}
	result := parts[0]
	for _, p := range parts[1:] {
		if len(p) == 0 {
			continue
		}
		result += string(unicode.ToUpper(rune(p[0]))) + p[1:]
	}
	return result
}

// ToSnakeCase converts camelCase to snake_case.
// e.g. "searchFlights" -> "search_flights"
func ToSnakeCase(camel string) string {
	var result []rune
	for i, r := range camel {
		if unicode.IsUpper(r) {
			if i > 0 {
				result = append(result, '_')
			}
			result = append(result, unicode.ToLower(r))
		} else {
			result = append(result, r)
		}
	}
	return string(result)
}

// toPascalCase converts snake_case to PascalCase.
// e.g. "search_flights" -> "SearchFlights"
func toPascalCase(snake string) string {
	parts := strings.Split(snake, "_")
	var result string
	for _, p := range parts {
		if len(p) == 0 {
			continue
		}
		result += string(unicode.ToUpper(rune(p[0]))) + p[1:]
	}
	return result
}

// anipTypeToGraphQL maps ANIP types to GraphQL type names.
func anipTypeToGraphQL(anipType string) string {
	switch anipType {
	case "string":
		return "String"
	case "integer":
		return "Int"
	case "number":
		return "Float"
	case "boolean":
		return "Boolean"
	default:
		return "JSON"
	}
}

// graphqlScalarType returns the graphql-go scalar type for a GraphQL type name.
func graphqlScalarType(typeName string) graphql.Output {
	switch typeName {
	case "String":
		return graphql.String
	case "Int":
		return graphql.Int
	case "Float":
		return graphql.Float
	case "Boolean":
		return graphql.Boolean
	default:
		return jsonScalar
	}
}

// jsonScalar is a custom scalar for arbitrary JSON values.
var jsonScalar = graphql.NewScalar(graphql.ScalarConfig{
	Name:        "JSON",
	Description: "Arbitrary JSON value",
	Serialize: func(value any) any {
		return value
	},
	ParseValue: func(value any) any {
		return value
	},
	ParseLiteral: func(valueAST ast.Value) any {
		return nil
	},
})

// BuildSchema builds both an executable graphql.Schema and an SDL text string
// from the service's registered capabilities.
// The resolverFactory is called once per capability name and should return
// a resolver function that handles auth and invocation.
func BuildSchema(svc *service.Service, resolverFactory func(capName string) graphql.FieldResolveFn) (*graphql.Schema, string, error) {
	manifest := svc.GetManifest()

	// Collect capability names in sorted order for deterministic output.
	capNames := make([]string, 0, len(manifest.Capabilities))
	for name := range manifest.Capabilities {
		capNames = append(capNames, name)
	}
	sort.Strings(capNames)

	// Build shared GraphQL types.
	financialCostType := graphql.NewObject(graphql.ObjectConfig{
		Name: "FinancialCost",
		Fields: graphql.Fields{
			"amount":   &graphql.Field{Type: graphql.Float},
			"currency": &graphql.Field{Type: graphql.String},
		},
	})

	costActualType := graphql.NewObject(graphql.ObjectConfig{
		Name: "CostActual",
		Fields: graphql.Fields{
			"financial":            &graphql.Field{Type: financialCostType},
			"varianceFromEstimate": &graphql.Field{Type: graphql.String},
		},
	})

	resolutionType := graphql.NewObject(graphql.ObjectConfig{
		Name: "Resolution",
		Fields: graphql.Fields{
			"action":        &graphql.Field{Type: graphql.NewNonNull(graphql.String)},
			"recoveryClass": &graphql.Field{Type: graphql.NewNonNull(graphql.String)},
			"requires":      &graphql.Field{Type: graphql.String},
			"grantableBy":   &graphql.Field{Type: graphql.String},
		},
	})

	anipFailureType := graphql.NewObject(graphql.ObjectConfig{
		Name: "ANIPFailure",
		Fields: graphql.Fields{
			"type":       &graphql.Field{Type: graphql.NewNonNull(graphql.String)},
			"detail":     &graphql.Field{Type: graphql.NewNonNull(graphql.String)},
			"resolution": &graphql.Field{Type: resolutionType},
			"retry":      &graphql.Field{Type: graphql.NewNonNull(graphql.Boolean)},
		},
	})

	// Build per-capability result types and fields.
	queryFields := graphql.Fields{}
	mutationFields := graphql.Fields{}

	for _, name := range capNames {
		decl := manifest.Capabilities[name]
		pascal := toPascalCase(name)
		camel := ToCamelCase(name)

		resultType := graphql.NewObject(graphql.ObjectConfig{
			Name: pascal + "Result",
			Fields: graphql.Fields{
				"success":    &graphql.Field{Type: graphql.NewNonNull(graphql.Boolean)},
				"result":     &graphql.Field{Type: jsonScalar},
				"costActual": &graphql.Field{Type: costActualType},
				"failure":    &graphql.Field{Type: anipFailureType},
			},
		})

		// Build args from capability inputs.
		args := graphql.FieldConfigArgument{}
		for _, inp := range decl.Inputs {
			argName := ToCamelCase(inp.Name)
			gqlTypeName := anipTypeToGraphQL(inp.Type)
			gqlType := graphqlScalarType(gqlTypeName)
			var argType graphql.Input
			if inp.Required {
				argType = graphql.NewNonNull(gqlType)
			} else {
				argType = gqlType
			}
			args[argName] = &graphql.ArgumentConfig{
				Type: argType,
			}
		}

		field := &graphql.Field{
			Type:    graphql.NewNonNull(resultType),
			Args:    args,
			Resolve: resolverFactory(name),
		}

		if decl.SideEffect.Type == "" || decl.SideEffect.Type == "read" {
			queryFields[camel] = field
		} else {
			mutationFields[camel] = field
		}
	}

	// Build schema config.
	schemaConfig := graphql.SchemaConfig{}

	if len(queryFields) > 0 {
		schemaConfig.Query = graphql.NewObject(graphql.ObjectConfig{
			Name:   "Query",
			Fields: queryFields,
		})
	}
	if len(mutationFields) > 0 {
		schemaConfig.Mutation = graphql.NewObject(graphql.ObjectConfig{
			Name:   "Mutation",
			Fields: mutationFields,
		})
	}

	// graphql-go requires a Query type; add a dummy if we only have mutations.
	if schemaConfig.Query == nil {
		schemaConfig.Query = graphql.NewObject(graphql.ObjectConfig{
			Name: "Query",
			Fields: graphql.Fields{
				"_empty": &graphql.Field{
					Type: graphql.String,
					Resolve: func(p graphql.ResolveParams) (any, error) {
						return nil, nil
					},
				},
			},
		})
	}

	schema, err := graphql.NewSchema(schemaConfig)
	if err != nil {
		return nil, "", fmt.Errorf("build graphql schema: %w", err)
	}

	// Build SDL text.
	sdl := generateSDL(svc, capNames)

	return &schema, sdl, nil
}

// generateSDL produces the SDL text for the GraphQL schema including
// custom @anip* directives.
func generateSDL(svc *service.Service, capNames []string) string {
	var lines []string

	// Directives
	lines = append(lines,
		"directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION",
		"directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION",
		"directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION",
		"directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION",
		"",
		"scalar JSON",
		"",
	)

	// Shared types
	lines = append(lines,
		"type CostActual { financial: FinancialCost, varianceFromEstimate: String }",
		"type FinancialCost { amount: Float, currency: String }",
		"type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }",
		"type Resolution { action: String!, recoveryClass: String!, requires: String, grantableBy: String }",
		"type RestrictedCapability { capability: String!, reason: String!, reasonType: String!, grantableBy: String!, unmetTokenRequirements: [String!]!, resolutionHint: String }",
		"type DeniedCapability { capability: String!, reason: String!, reasonType: String! }",
		"",
	)

	var queries []string
	var mutations []string

	for _, name := range capNames {
		decl := svc.GetCapabilityDeclaration(name)
		if decl == nil {
			continue
		}
		pascal := toPascalCase(name)
		camel := ToCamelCase(name)

		// Result type
		lines = append(lines,
			fmt.Sprintf("type %sResult { success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }", pascal),
		)

		// Build args string
		argsStr := buildSDLArgs(decl)

		// Build directives string
		dirStr := buildSDLDirectives(decl)

		fieldLine := fmt.Sprintf("  %s%s: %sResult! %s", camel, argsStr, pascal, dirStr)

		seType := decl.SideEffect.Type
		if seType == "" || seType == "read" {
			queries = append(queries, fieldLine)
		} else {
			mutations = append(mutations, fieldLine)
		}
	}

	lines = append(lines, "")
	if len(queries) > 0 {
		lines = append(lines, "type Query {")
		lines = append(lines, queries...)
		lines = append(lines, "}")
	}
	if len(mutations) > 0 {
		lines = append(lines, "type Mutation {")
		lines = append(lines, mutations...)
		lines = append(lines, "}")
	}

	return strings.Join(lines, "\n")
}

// buildSDLArgs generates the GraphQL argument list for a capability.
func buildSDLArgs(decl *core.CapabilityDeclaration) string {
	if len(decl.Inputs) == 0 {
		return ""
	}
	var args []string
	for _, inp := range decl.Inputs {
		argName := ToCamelCase(inp.Name)
		gqlType := anipTypeToGraphQL(inp.Type)
		if inp.Required {
			gqlType += "!"
		}
		args = append(args, fmt.Sprintf("%s: %s", argName, gqlType))
	}
	return "(" + strings.Join(args, ", ") + ")"
}

// buildSDLDirectives generates the directive annotations for a capability.
func buildSDLDirectives(decl *core.CapabilityDeclaration) string {
	var parts []string

	// @anipSideEffect
	seType := decl.SideEffect.Type
	if seType == "" {
		seType = "read"
	}
	seDir := fmt.Sprintf(`@anipSideEffect(type: "%s"`, seType)
	if decl.SideEffect.RollbackWindow != "" {
		seDir += fmt.Sprintf(`, rollbackWindow: "%s"`, decl.SideEffect.RollbackWindow)
	}
	seDir += ")"
	parts = append(parts, seDir)

	// @anipCost
	if decl.Cost != nil {
		certainty := decl.Cost.Certainty
		if certainty == "" {
			certainty = "estimate"
		}
		costDir := fmt.Sprintf(`@anipCost(certainty: "%s"`, certainty)
		if decl.Cost.Financial != nil {
			costDir += fmt.Sprintf(`, currency: "%s"`, decl.Cost.Financial.Currency)
			if decl.Cost.Financial.RangeMin != nil {
				costDir += fmt.Sprintf(`, rangeMin: %v`, *decl.Cost.Financial.RangeMin)
			}
			if decl.Cost.Financial.RangeMax != nil {
				costDir += fmt.Sprintf(`, rangeMax: %v`, *decl.Cost.Financial.RangeMax)
			}
		}
		costDir += ")"
		parts = append(parts, costDir)
	}

	// @anipRequires
	if len(decl.Requires) > 0 {
		var capNames []string
		for _, r := range decl.Requires {
			capNames = append(capNames, fmt.Sprintf(`"%s"`, r.Capability))
		}
		parts = append(parts, fmt.Sprintf("@anipRequires(capabilities: [%s])", strings.Join(capNames, ", ")))
	}

	// @anipScope
	if len(decl.MinimumScope) > 0 {
		var scopeVals []string
		for _, s := range decl.MinimumScope {
			scopeVals = append(scopeVals, fmt.Sprintf(`"%s"`, s))
		}
		parts = append(parts, fmt.Sprintf("@anipScope(scopes: [%s])", strings.Join(scopeVals, ", ")))
	}

	return strings.Join(parts, " ")
}

// BuildGraphQLResponse maps an ANIP invoke result (map[string]any with snake_case keys)
// to the GraphQL result shape with camelCase keys.
func BuildGraphQLResponse(result map[string]any) map[string]any {
	response := map[string]any{
		"success":    result["success"],
		"result":     result["result"],
		"costActual": nil,
		"failure":    nil,
	}
	if response["success"] == nil {
		response["success"] = false
	}

	if costActual, ok := result["cost_actual"].(map[string]any); ok {
		response["costActual"] = map[string]any{
			"financial":            costActual["financial"],
			"varianceFromEstimate": costActual["variance_from_estimate"],
		}
	}

	if failure, ok := result["failure"].(map[string]any); ok {
		f := map[string]any{
			"type":       failure["type"],
			"detail":     failure["detail"],
			"resolution": nil,
			"retry":      failure["retry"],
		}
		if f["type"] == nil {
			f["type"] = "unknown"
		}
		if f["detail"] == nil {
			f["detail"] = ""
		}
		if f["retry"] == nil {
			f["retry"] = false
		}

		if resolution, ok := failure["resolution"].(map[string]any); ok {
			f["resolution"] = map[string]any{
				"action":        resolution["action"],
				"recoveryClass": resolution["recovery_class"],
				"requires":      resolution["requires"],
				"grantableBy":   resolution["grantable_by"],
			}
		}

		response["failure"] = f
	}

	return response
}
