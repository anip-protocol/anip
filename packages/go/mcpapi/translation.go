// Package mcpapi exposes ANIP capabilities as MCP tools for stdio transport.
package mcpapi

import (
	"fmt"
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
)

// typeMap maps ANIP types to JSON Schema types.
var typeMap = map[string]string{
	"string":       "string",
	"integer":      "integer",
	"number":       "number",
	"boolean":      "boolean",
	"date":         "string",
	"airport_code": "string",
}

// CapabilityToInputSchema converts an ANIP CapabilityDeclaration into a
// JSON Schema object suitable for MCP tool inputSchema.
func CapabilityToInputSchema(decl *core.CapabilityDeclaration) map[string]any {
	properties := make(map[string]any)
	var required []string

	for _, input := range decl.Inputs {
		jsonType, ok := typeMap[input.Type]
		if !ok {
			jsonType = "string"
		}

		prop := map[string]any{
			"type":        jsonType,
			"description": input.Description,
		}

		if input.Type == "date" {
			prop["format"] = "date"
		}

		if input.Default != nil {
			prop["default"] = input.Default
		}

		properties[input.Name] = prop

		if input.Required {
			required = append(required, input.Name)
		}
	}

	schema := map[string]any{
		"type":       "object",
		"properties": properties,
	}
	if len(required) > 0 {
		schema["required"] = required
	}

	return schema
}

// EnrichDescription builds an MCP-friendly description that includes ANIP
// metadata not representable in MCP's native schema: side-effect warnings,
// cost information, prerequisites, and scope requirements.
func EnrichDescription(decl *core.CapabilityDeclaration) string {
	parts := []string{decl.Description}

	se := decl.SideEffect
	switch se.Type {
	case "irreversible":
		parts = append(parts, "WARNING: IRREVERSIBLE action — cannot be undone.")
		if se.RollbackWindow == "none" {
			parts = append(parts, "No rollback window.")
		}
	case "write":
		if se.RollbackWindow != "" && se.RollbackWindow != "none" && se.RollbackWindow != "not_applicable" {
			parts = append(parts, fmt.Sprintf("Reversible within %s.", se.RollbackWindow))
		}
	case "read":
		parts = append(parts, "Read-only, no side effects.")
	}

	if decl.Cost != nil {
		financial := decl.Cost.Financial
		switch decl.Cost.Certainty {
		case "fixed":
			if financial != nil {
				amount, _ := financial["amount"]
				currency, _ := financial["currency"].(string)
				if currency == "" {
					currency = "USD"
				}
				if amount != nil {
					parts = append(parts, fmt.Sprintf("Cost: %s %v (fixed).", currency, amount))
				}
			}
		case "estimated":
			if financial != nil {
				currency, _ := financial["currency"].(string)
				if currency == "" {
					currency = "USD"
				}
				// Handle both flat range fields and nested estimated_range
				rangeMin, hasMin := financial["range_min"]
				rangeMax, hasMax := financial["range_max"]
				if !hasMin || !hasMax {
					if estRange, ok := financial["estimated_range"].(map[string]any); ok {
						rangeMin, hasMin = estRange["min"]
						rangeMax, hasMax = estRange["max"]
					}
				}
				if hasMin && hasMax {
					parts = append(parts, fmt.Sprintf("Estimated cost: %s %v-%v.", currency, rangeMin, rangeMax))
				}
			}
		}
	}

	if len(decl.Requires) > 0 {
		var prereqs []string
		for _, r := range decl.Requires {
			prereqs = append(prereqs, r.Capability)
		}
		parts = append(parts, fmt.Sprintf("Requires calling first: %s.", strings.Join(prereqs, ", ")))
	}

	if len(decl.MinimumScope) > 0 {
		parts = append(parts, fmt.Sprintf("Delegation scope: %s.", strings.Join(decl.MinimumScope, ", ")))
	}

	return strings.Join(parts, " ")
}
