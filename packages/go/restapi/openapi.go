package restapi

import (
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
)

// typeMap converts ANIP input types to OpenAPI types.
var typeMap = map[string]string{
	"string":       "string",
	"integer":      "integer",
	"number":       "number",
	"boolean":      "boolean",
	"date":         "string",
	"airport_code": "string",
}

// mapType returns the OpenAPI type for a given ANIP input type.
func mapType(t string) string {
	if mapped, ok := typeMap[t]; ok {
		return mapped
	}
	return "string"
}

// GenerateOpenAPISpec generates an OpenAPI 3.1 spec from routes.
func GenerateOpenAPISpec(serviceID string, routes []RESTRoute) map[string]any {
	paths := make(map[string]any)

	for _, route := range routes {
		method := strings.ToLower(route.Method)
		decl := route.Declaration

		seType := decl.SideEffect.Type
		if seType == "" {
			seType = "read"
		}

		minScope := decl.MinimumScope
		if minScope == nil {
			minScope = []string{}
		}

		financial := false
		if decl.Cost != nil && decl.Cost.Financial != nil {
			financial = true
		}

		operation := map[string]any{
			"summary":              decl.Description,
			"operationId":         route.CapabilityName,
			"responses": map[string]any{
				"200": map[string]any{
					"description": "Success",
					"content": map[string]any{
						"application/json": map[string]any{
							"schema": map[string]any{"$ref": "#/components/schemas/ANIPResponse"},
						},
					},
				},
				"401": map[string]any{"description": "Authentication required"},
				"403": map[string]any{"description": "Authorization failed"},
				"404": map[string]any{"description": "Unknown capability"},
			},
			"x-anip-side-effect":    seType,
			"x-anip-minimum-scope": minScope,
			"x-anip-financial":     financial,
		}

		if method == "get" {
			operation["parameters"] = buildQueryParameters(decl)
		} else {
			operation["requestBody"] = buildRequestBody(decl)
		}

		paths[route.Path] = map[string]any{method: operation}
	}

	return map[string]any{
		"openapi": "3.1.0",
		"info":    map[string]any{"title": "ANIP REST \u2014 " + serviceID, "version": "1.0"},
		"paths":   paths,
		"components": map[string]any{
			"schemas": map[string]any{
				"ANIPResponse": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"success":       map[string]any{"type": "boolean"},
						"result":        map[string]any{"type": "object"},
						"invocation_id": map[string]any{"type": "string"},
						"failure":       map[string]any{"$ref": "#/components/schemas/ANIPFailure"},
					},
				},
				"ANIPFailure": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"type":       map[string]any{"type": "string"},
						"detail":     map[string]any{"type": "string"},
						"resolution": map[string]any{"type": "object"},
						"retry":      map[string]any{"type": "boolean"},
					},
				},
			},
			"securitySchemes": map[string]any{
				"bearer": map[string]any{"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
			},
		},
		"security": []map[string]any{{"bearer": []string{}}},
	}
}

// buildQueryParameters builds OpenAPI 3.1 query parameters from capability inputs (for GET routes).
func buildQueryParameters(decl core.CapabilityDeclaration) []map[string]any {
	var params []map[string]any
	for _, inp := range decl.Inputs {
		schema := map[string]any{
			"type": mapType(inp.Type),
		}
		if inp.Type == "date" {
			schema["format"] = "date"
		}
		if inp.Default != nil {
			schema["default"] = inp.Default
		}

		desc := inp.Description

		params = append(params, map[string]any{
			"name":        inp.Name,
			"in":          "query",
			"required":    inp.Required,
			"schema":      schema,
			"description": desc,
		})
	}
	if params == nil {
		params = []map[string]any{}
	}
	return params
}

// buildRequestBody builds OpenAPI 3.1 request body from capability inputs (for POST routes).
func buildRequestBody(decl core.CapabilityDeclaration) map[string]any {
	properties := make(map[string]any)
	var required []string

	for _, inp := range decl.Inputs {
		prop := map[string]any{
			"type":        mapType(inp.Type),
			"description": inp.Description,
		}
		if inp.Type == "date" {
			prop["format"] = "date"
		}
		properties[inp.Name] = prop
		if inp.Required {
			required = append(required, inp.Name)
		}
	}

	schema := map[string]any{
		"type":       "object",
		"properties": properties,
	}
	if len(required) > 0 {
		schema["required"] = required
	}

	return map[string]any{
		"required": true,
		"content": map[string]any{
			"application/json": map[string]any{
				"schema": schema,
			},
		},
	}
}
