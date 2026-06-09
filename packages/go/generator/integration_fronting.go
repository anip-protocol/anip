package generator

import (
	"fmt"
	"sort"
	"strings"
)

func buildIntegrationFrontingArtifacts(model *GenerationModel) []GeneratedFile {
	if model == nil || model.Definition == nil || model.Definition.IntegrationFronting == nil {
		return nil
	}
	mappings := model.Definition.IntegrationFronting.CapabilityMappings
	if len(mappings) == 0 {
		return nil
	}

	bindings := buildIntegrationFrontingBindingPack(model)
	bindingsJSON, _ := marshalIndented(bindings)
	selectionJSON, _ := marshalIndented(buildIntegrationFrontingSelectionTemplate(model))
	conformanceJSON, _ := marshalIndented(buildIntegrationFrontingConformance(model))
	profileJSON, _ := marshalIndented(buildIntegrationFrontingBackendProfile(model))

	files := []GeneratedFile{
		{
			Path:    "integration-fronting/adapter-bindings.json",
			Content: string(bindingsJSON),
		},
		{
			Path:    "integration-fronting/backend-profile.example.json",
			Content: string(profileJSON),
		},
		{
			Path:    "integration-fronting/backend-selection.example.json",
			Content: string(selectionJSON),
		},
		{
			Path:    "integration-fronting/conformance.json",
			Content: string(conformanceJSON),
		},
		{
			Path:    "integration-fronting/README.md",
			Content: buildIntegrationFrontingReadme(model),
		},
	}
	for _, family := range integrationBackendTemplateFamilies(model) {
		files = append(files, GeneratedFile{
			Path:    "integration-fronting/backend-templates/" + family + ".md",
			Content: buildIntegrationBackendTemplate(family),
		})
	}
	return files
}

func buildIntegrationFrontingBindingPack(model *GenerationModel) map[string]any {
	capabilityByID := map[string]GeneratedCapabilityRuntimeMetadata{}
	for _, capability := range model.Capabilities {
		capabilityByID[capability.CapabilityID] = capability
	}
	items := []map[string]any{}
	for _, mapping := range model.Definition.IntegrationFronting.CapabilityMappings {
		capability := capabilityByID[mapping.CapabilityID]
		items = append(items, map[string]any{
			"mapping_id":        mapping.ID,
			"capability_id":     mapping.CapabilityID,
			"title":             firstNonEmpty(mapping.Title, capability.Title),
			"intent":            mapping.Intent,
			"service_id":        mapping.ServiceID,
			"service_name":      firstNonEmpty(mapping.ServiceName, capability.ServiceName),
			"execution_posture": firstNonEmpty(mapping.ExecutionPosture, capability.ExecutionPosture),
			"side_effect_level": firstNonEmpty(mapping.SideEffectLevel, capability.SideEffectLevel),
			"semantic_inputs": map[string]any{
				"required": mapping.RequiredInputs,
				"optional": mapping.OptionalInputs,
			},
			"backend_input_contract": map[string]any{
				"mode":              firstNonEmpty(mapping.BackendInputMode, capability.BackendInputMode, "implicit"),
				"derived_required":  mapping.DerivedRequiredBackendInputs,
				"derived_optional":  mapping.DerivedOptionalBackendInputs,
				"explicit_required": mapping.ExplicitRequiredBackendInputs,
				"explicit_optional": mapping.ExplicitOptionalBackendInputs,
			},
			"backend_bindings": effectiveIntegrationBackendBindings(mapping),
			"governance": map[string]any{
				"approval_rule_refs":      mapping.ApprovalRuleRefs,
				"denial_rule_refs":        mapping.DenialRuleRefs,
				"clarification_rule_refs": mapping.ClarificationRuleRefs,
				"audit_required":          mapping.AuditRequired,
			},
			"outbound_controls": mapping.OutboundControls,
		})
	}
	return map[string]any{
		"schema_version": "anip-integration-fronting/v0",
		"system_name":    model.SystemName,
		"project_type":   model.Definition.IntegrationFronting.ProjectType,
		"mappings":       items,
	}
}

func buildIntegrationFrontingSelectionTemplate(model *GenerationModel) map[string]any {
	selection := map[string]any{}
	for _, mapping := range model.Definition.IntegrationFronting.CapabilityMappings {
		bindings := effectiveIntegrationBackendBindings(mapping)
		if len(bindings) == 0 {
			continue
		}
		selected := bindings[0]
		selection[mapping.CapabilityID] = map[string]any{
			"active_backend_kind":   selected.BackendKind,
			"active_connection_ref": selected.ConnectionRef,
			"available":             backendSelectionLabels(bindings),
		}
	}
	return map[string]any{
		"schema_version": "anip-integration-fronting-selection/v0",
		"description":    "Deployment-time backend selection template. Edit only when a governed capability has multiple backend realizations.",
		"selection":      selection,
	}
}

func buildIntegrationFrontingConformance(model *GenerationModel) map[string]any {
	capabilityIDs := map[string]bool{}
	for _, capability := range model.Capabilities {
		capabilityIDs[capability.CapabilityID] = true
	}
	checks := []map[string]any{}
	for _, mapping := range model.Definition.IntegrationFronting.CapabilityMappings {
		bindings := effectiveIntegrationBackendBindings(mapping)
		hasRawOps := true
		for _, binding := range bindings {
			if strings.TrimSpace(binding.ConnectionRef) == "" || len(binding.RawOperationRefs) == 0 {
				hasRawOps = false
				break
			}
		}
		checks = append(checks,
			map[string]any{
				"id":            fmt.Sprintf("%s.capability_formalized", mapping.CapabilityID),
				"status":        passFail(capabilityIDs[mapping.CapabilityID]),
				"detail":        "Governed fronting mapping points at a formalized ANIP capability.",
				"capability_id": mapping.CapabilityID,
			},
			map[string]any{
				"id":            fmt.Sprintf("%s.raw_backend_bound", mapping.CapabilityID),
				"status":        passFail(hasRawOps),
				"detail":        "Raw backend operations are reachable only through the mapped governed capability binding metadata.",
				"capability_id": mapping.CapabilityID,
			},
		)
	}
	return map[string]any{
		"schema_version": "anip-integration-fronting-conformance/v0",
		"status":         aggregateCheckStatus(checks),
		"checks":         checks,
	}
}

func buildIntegrationFrontingBackendProfile(model *GenerationModel) map[string]any {
	families := integrationBackendTemplateFamilies(model)
	profilesByFamily := map[string]map[string]any{}
	for _, family := range families {
		profilesByFamily[family] = map[string]any{
			"profile_id":     family + "-default",
			"backend_family": family,
			"template":       "backend-templates/" + family + ".md",
			"capabilities":   []map[string]any{},
		}
	}

	for _, mapping := range model.Definition.IntegrationFronting.CapabilityMappings {
		for _, binding := range effectiveIntegrationBackendBindings(mapping) {
			family := integrationBackendTemplateFamily(binding.BackendKind)
			if family == "" {
				continue
			}
			profile, ok := profilesByFamily[family]
			if !ok {
				continue
			}
			capabilities := profile["capabilities"].([]map[string]any)
			capabilities = append(capabilities, map[string]any{
				"capability_id":      mapping.CapabilityID,
				"connection_ref":     binding.ConnectionRef,
				"backend_kind":       binding.BackendKind,
				"raw_operation_refs": binding.RawOperationRefs,
				"input_mode":         firstNonEmpty(binding.BackendInputMode, mapping.BackendInputMode, "implicit"),
			})
			profile["capabilities"] = capabilities
		}
	}

	profiles := make([]map[string]any, 0, len(families))
	for _, family := range families {
		profiles = append(profiles, profilesByFamily[family])
	}
	return map[string]any{
		"schema_version": "anip-backend-implementation-profile/v0",
		"description":    "Implementation profile for local backend code. This is replaceable deployment material, not the governed ANIP behavior contract.",
		"contract_boundary": strings.Join([]string{
			"Agents invoke ANIP capabilities.",
			"Generated policy, approval, clarification, and audit logic runs before backend execution.",
			"Backend profiles may change when the implementation moves from REST to MCP, SQL, dbt, Cube, or another provider, as long as governed capability behavior is unchanged.",
		}, " "),
		"backend_families": families,
		"profiles":         profiles,
	}
}

func buildIntegrationFrontingReadme(model *GenerationModel) string {
	return strings.Join([]string{
		"# Governed API / MCP Fronting",
		"",
		"This directory is generated from reviewed fronting mappings. Treat it as implementation profile material plus conformance evidence, not as the agent-facing behavior surface.",
		"",
		"Raw MCP tools, API endpoints, database operations, and hybrid backend calls are not the agent-facing surface.",
		"Agents invoke governed ANIP capabilities; generated runtime code builds a backend invocation plan only after semantic inputs, policy, approval posture, and clarification rules are evaluated.",
		"",
		"## Files",
		"",
		"- `adapter-bindings.json`: reviewed capability-to-backend bindings for implementation work.",
		"- `backend-profile.example.json`: replaceable implementation profile showing which local backend template family can realize each binding.",
		"- `backend-selection.example.json`: deployment-time selection template when a capability has multiple backend realizations.",
		"- `backend-templates/`: generated local backend implementation guidance. Copy or replace these templates inside the generated backend adapter seam; do not depend on shared outbound adapter packages for governed behavior.",
		"- `conformance.json`: static checks proving saved mappings are represented by generated capability metadata.",
		"",
		"## Implementation rule",
		"",
		"Provider-specific code belongs in the generated backend adapter seam, generated backend template files, or a reviewed custom code bundle. Do not expose raw backend operations directly to agents.",
		"Generated runtimes pass only declared semantic inputs and declared backend input-contract fields into the adapter. If callers need extensibility, model it as an explicit governed input such as `filters`, `fields`, or `adapter_options` with documented bounds and audit handling.",
		"",
		"Changing from REST to MCP, dbt to Cube, or Snowflake to Databricks should normally be a backend profile/code change, not a contract change, unless the governed capability behavior, inputs, approval posture, denial rules, clarification rules, or audit semantics change.",
		"",
	}, "\n")
}

func integrationBackendTemplateFamilies(model *GenerationModel) []string {
	if model == nil || model.Definition == nil || model.Definition.IntegrationFronting == nil {
		return nil
	}
	seen := map[string]bool{}
	for _, mapping := range model.Definition.IntegrationFronting.CapabilityMappings {
		for _, binding := range effectiveIntegrationBackendBindings(mapping) {
			family := integrationBackendTemplateFamily(binding.BackendKind)
			if family != "" {
				seen[family] = true
			}
		}
	}
	families := make([]string, 0, len(seen))
	for family := range seen {
		families = append(families, family)
	}
	sort.Strings(families)
	return families
}

func integrationBackendTemplateFamily(kind string) string {
	normalized := strings.ToLower(strings.TrimSpace(strings.ReplaceAll(kind, "_", "-")))
	switch normalized {
	case "", "none":
		return ""
	case "native", "native-api", "openapi", "rest", "http", "jira-rest", "slack-web-api", "notion-api":
		return "native-api"
	case "graphql", "github-graphql", "linear-graphql":
		return "graphql"
	case "mcp", "mcp-server", "remote-mcp", "local-mcp":
		return "mcp"
	case "sql", "database", "warehouse", "snowflake", "databricks", "databricks-sql":
		return "sql"
	case "dbt", "dbt-semantic", "cube", "semantic-query":
		return "semantic-query"
	default:
		return sanitizeTemplateFamily(normalized)
	}
}

func sanitizeTemplateFamily(value string) string {
	if value == "" {
		return ""
	}
	var builder strings.Builder
	lastDash := false
	for _, r := range value {
		switch {
		case r >= 'a' && r <= 'z':
			builder.WriteRune(r)
			lastDash = false
		case r >= '0' && r <= '9':
			builder.WriteRune(r)
			lastDash = false
		case r == '-' || r == '.':
			if !lastDash {
				builder.WriteByte('-')
				lastDash = true
			}
		default:
			if !lastDash {
				builder.WriteByte('-')
				lastDash = true
			}
		}
	}
	return strings.Trim(builder.String(), "-")
}

func buildIntegrationBackendTemplate(family string) string {
	title := strings.ReplaceAll(family, "-", " ")
	switch family {
	case "native-api":
		return strings.Join([]string{
			"# Native API Backend Template",
			"",
			"This template is local implementation material. Use it to call REST/OpenAPI-style or SDK-backed APIs after ANIP policy and approval checks have passed.",
			"",
			"Implementation checklist:",
			"",
			"- Resolve `connection_ref` to deploy-time configuration and secret refs.",
			"- Build downstream requests only from `adapter_input` and reviewed backend input-contract fields.",
			"- Reject unexpected backend options unless they are modeled as governed inputs such as `filters`, `fields`, or `adapter_options`.",
			"- Normalize downstream errors into ANIP errors or preview results without leaking secrets.",
			"- Record audit evidence for selected backend operation, outbound payload category, redaction, approval id, and downstream result id.",
			"",
		}, "\n")
	case "graphql":
		return strings.Join([]string{
			"# GraphQL Backend Template",
			"",
			"This template is local implementation material. Use it to execute reviewed GraphQL operations after ANIP policy and approval checks have passed.",
			"",
			"Implementation checklist:",
			"",
			"- Pin operation names or persisted query ids instead of accepting caller-supplied query text.",
			"- Map semantic inputs into typed variables from `adapter_input`.",
			"- Bound selection sets through reviewed `fields` inputs or service-owned defaults.",
			"- Normalize GraphQL errors and partial data into explicit ANIP results.",
			"- Audit operation name, variable categories, redaction, approval id, and downstream response id.",
			"",
		}, "\n")
	case "mcp":
		return strings.Join([]string{
			"# MCP Backend Template",
			"",
			"This template is local implementation material. Use it to invoke selected MCP tools/resources behind governed ANIP capabilities.",
			"",
			"Implementation checklist:",
			"",
			"- Treat MCP tool names as backend supply, not as agent-facing capability names.",
			"- Call only reviewed `raw_operation_refs` selected in the backend profile.",
			"- Validate and redact outbound payloads before they cross the MCP boundary.",
			"- Fail closed when the required MCP connection, identity context, or secret refs are missing.",
			"- Audit selected tool/resource, payload category, redaction, approval id, and downstream result id.",
			"",
		}, "\n")
	case "sql":
		return strings.Join([]string{
			"# SQL / Warehouse Backend Template",
			"",
			"This template is local implementation material. Use it for bounded SQL, Snowflake, Databricks, or warehouse-backed execution after ANIP policy has passed.",
			"",
			"Implementation checklist:",
			"",
			"- Use reviewed query templates, stored procedures, or semantic views rather than caller-supplied SQL.",
			"- Bind parameters from `adapter_input`; do not concatenate user text into queries.",
			"- Apply row, column, tenant, and actor visibility restrictions before returning data.",
			"- Bound result size and redact sensitive values before response construction.",
			"- Audit query template id, parameter categories, scope, row count, and redaction decisions.",
			"",
		}, "\n")
	case "semantic-query":
		return strings.Join([]string{
			"# Semantic Query Backend Template",
			"",
			"This template is local implementation material. Use it for dbt Semantic Layer, Cube, metrics APIs, or other semantic query engines.",
			"",
			"Implementation checklist:",
			"",
			"- Map capabilities to reviewed metrics, dimensions, filters, and time windows.",
			"- Keep engine-specific names out of the governed capability contract unless they are user-visible semantics.",
			"- Bound optional filters and field lists through governed inputs.",
			"- Normalize engine errors into clarification, denial, or bounded result responses.",
			"- Audit metric ids, dimension ids, filters, time windows, and redaction decisions.",
			"",
		}, "\n")
	default:
		return strings.Join([]string{
			"# " + titleCase(title) + " Backend Template",
			"",
			"This template is local implementation material for backend family `" + family + "`.",
			"",
			"Implementation checklist:",
			"",
			"- Resolve `connection_ref` through deploy-time configuration and secret refs.",
			"- Execute only reviewed raw operations listed in the backend profile.",
			"- Build downstream calls from declared semantic inputs and backend input-contract fields.",
			"- Fail closed for unexpected inputs, missing identity context, or missing connection material.",
			"- Audit selected backend operation, outbound payload category, approval id, and downstream result id.",
			"",
		}, "\n")
	}
}

func effectiveIntegrationBackendBindings(mapping IntegrationCapabilityMapping) []IntegrationBackendBinding {
	return normalizeBackendBindings(true, mapping)
}

func backendSelectionLabels(bindings []IntegrationBackendBinding) []string {
	labels := make([]string, 0, len(bindings))
	for _, binding := range bindings {
		ops := strings.Join(binding.RawOperationRefs, ",")
		labels = append(labels, binding.BackendKind+":"+binding.ConnectionRef+":"+ops)
	}
	return labels
}

func aggregateCheckStatus(checks []map[string]any) string {
	for _, check := range checks {
		if check["status"] != "pass" {
			return "failed"
		}
	}
	return "passed"
}

func passFail(ok bool) string {
	if ok {
		return "pass"
	}
	return "fail"
}
