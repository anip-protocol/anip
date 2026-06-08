package generator

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

func BuildAgentConsumptionKit(resolved *ResolvedServiceDefinition) ([]GeneratedFile, error) {
	if resolved == nil {
		return nil, fmt.Errorf("resolved service definition is required")
	}
	files := []GeneratedFile{}
	if len(resolved.AgentConsumability) > 0 {
		content, err := prettyJSON(resolved.AgentConsumability)
		if err != nil {
			return nil, fmt.Errorf("encode agent consumability metadata: %w", err)
		}
		files = append(files, GeneratedFile{Path: "agent-consumption/agent-consumability.json", Content: content})
	}
	if len(resolved.AgentReadiness) > 0 {
		content, err := prettyJSON(resolved.AgentReadiness)
		if err != nil {
			return nil, fmt.Errorf("encode agent readiness metadata: %w", err)
		}
		files = append(files, GeneratedFile{Path: "agent-consumption/agent-readiness.json", Content: content})
	}
	appProfile := buildAgentAppProfile(resolved.Definition, resolved.AgentConsumability)
	if len(appProfile) > 0 {
		content, err := prettyJSON(appProfile)
		if err != nil {
			return nil, fmt.Errorf("encode agent app profile metadata: %w", err)
		}
		files = append(files, GeneratedFile{Path: "agent-consumption/agent-app-profile.json", Content: content})
	}
	capabilityIndex := buildCapabilityIndex(resolved.Definition, resolved.AgentConsumability)
	if len(capabilityIndex) > 0 {
		content, err := prettyJSON(map[string]any{
			"artifact_type":  "agent_capability_index",
			"schema_version": "anip-agent-consumption-kit/v0",
			"capabilities":   capabilityIndex,
		})
		if err != nil {
			return nil, fmt.Errorf("encode agent capability index: %w", err)
		}
		files = append(files, GeneratedFile{Path: "agent-consumption/capability-index.json", Content: content})
	}
	appGlue := buildAppGlueRequired(resolved.AgentConsumability)
	if len(appGlue) > 0 {
		content, err := prettyJSON(map[string]any{
			"artifact_type":  "agent_app_glue_required",
			"schema_version": "anip-agent-consumption-kit/v0",
			"items":          appGlue,
		})
		if err != nil {
			return nil, fmt.Errorf("encode required app glue metadata: %w", err)
		}
		files = append(files, GeneratedFile{Path: "agent-consumption/app-glue-required.json", Content: content})
	}
	runtimeCustomization, err := prettyJSON(buildRuntimeCustomization(resolved.AgentConsumability))
	if err != nil {
		return nil, fmt.Errorf("encode agent runtime customization metadata: %w", err)
	}
	files = append(files, GeneratedFile{Path: "agent-consumption/runtime-customization.json", Content: runtimeCustomization})
	runtimeOverrides, err := prettyJSON(buildRuntimeCustomizationOverrides(resolved.AgentConsumability))
	if err != nil {
		return nil, fmt.Errorf("encode agent runtime customization overrides: %w", err)
	}
	files = append(files, GeneratedFile{Path: "agent-consumption/custom/runtime-overrides.json", Content: runtimeOverrides})
	files = append(files, GeneratedFile{Path: "agent-consumption/custom/README.md", Content: buildRuntimeCustomizationReadme()})
	files = append(files, GeneratedFile{Path: "agent-consumption/prompt-brief.md", Content: buildPromptBrief(resolved, capabilityIndex, appGlue)})
	return files, nil
}

func prettyJSON(value any) (string, error) {
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return "", err
	}
	return string(append(bytes, '\n')), nil
}

func buildCapabilityIndex(definition map[string]any, consumability map[string]any) []map[string]any {
	formalizations, _ := definition["capability_formalizations"].([]any)
	consumabilityCaps := mapValue(consumability, "capabilities")
	index := make([]map[string]any, 0, len(formalizations))
	for _, item := range formalizations {
		capability, ok := item.(map[string]any)
		if !ok {
			continue
		}
		capabilityID := strings.TrimSpace(stringValue(capability["capability_id"]))
		if capabilityID == "" {
			continue
		}
		entry := map[string]any{
			"capability_id":    capabilityID,
			"service_id":       stringValue(capability["service_id"]),
			"title":            stringValue(capability["title"]),
			"summary":          stringValue(capability["summary"]),
			"kind":             stringValue(capability["kind"]),
			"minimum_scope":    capability["minimum_scope"],
			"inputs":           capability["inputs"],
			"business_effects": capability["business_effects"],
			"grant_policy":     capability["grant_policy"],
		}
		if hint := mapValue(consumabilityCaps, capabilityID); len(hint) > 0 {
			entry["agent_consumability"] = hint
		}
		index = append(index, compactMap(entry))
	}
	sort.Slice(index, func(i, j int) bool {
		return stringValue(index[i]["capability_id"]) < stringValue(index[j]["capability_id"])
	})
	return index
}

func buildAgentAppProfile(definition map[string]any, consumability map[string]any) map[string]any {
	capabilities := mapValue(consumability, "capabilities")
	formalizations := capabilityFormalizationsByID(definition)
	if len(capabilities) == 0 && len(formalizations) == 0 {
		return nil
	}
	profileCapabilities := map[string]any{}
	capabilityIDs := map[string]struct{}{}
	for capabilityID := range capabilities {
		capabilityIDs[capabilityID] = struct{}{}
	}
	for capabilityID := range formalizations {
		capabilityIDs[capabilityID] = struct{}{}
	}
	for capabilityID := range capabilityIDs {
		hint, _ := capabilities[capabilityID].(map[string]any)
		if hint == nil {
			hint = map[string]any{}
		}
		formalization := formalizations[capabilityID]
		businessEffects := effectiveAgentBusinessEffects(hint["business_effects"], formalization)
		appBoundaries := effectiveAgentAppBoundaries(hint["app_boundaries"], businessEffects, formalization)
		profile := compactMap(map[string]any{
			"capability_framing":      stringValue(mapValue(hint, "intent")["summary"]),
			"business_effects":        businessEffects,
			"input_meanings":          hint["input_meanings"],
			"reference_catalogs":      hint["reference_catalogs"],
			"result_display":          hint["result_display"],
			"app_boundaries":          appBoundaries,
			"approval":                effectiveAgentApproval(hint["approval"], formalization),
			"required_context":        effectiveAgentRequiredContext(hint["required_context"], formalization),
			"app_glue":                hint["app_glue"],
			"derived_target_owner":    hint["derived_target_owner"],
			"intent_rules":            hint["intent_rules"],
			"business_language_rules": hint["business_language_rules"],
		})
		if len(profile) > 0 {
			profileCapabilities[capabilityID] = profile
		}
	}
	result := compactMap(map[string]any{
		"artifact_type":       "agent_app_profile",
		"schema_version":      "anip-agent-app-profile/v0",
		"capability_metadata": profileCapabilities,
		"selection_hints":     consumability["selection_hints"],
	})
	if len(profileCapabilities) == 0 && result["selection_hints"] == nil {
		return nil
	}
	return result
}

func effectiveAgentRequiredContext(raw any, formalization map[string]any) []any {
	contexts := listValue(raw)
	if len(contexts) == 0 {
		return nil
	}
	inputs := capabilityInputsByName(formalization)
	result := make([]any, 0, len(contexts))
	seen := map[string]struct{}{}
	for _, item := range contexts {
		context, ok := item.(map[string]any)
		if !ok {
			continue
		}
		inputName := strings.TrimSpace(stringValue(context["input"]))
		if inputName == "" {
			continue
		}
		missingBehavior := strings.TrimSpace(stringValue(context["missing_behavior"]))
		if input := inputs[inputName]; len(input) > 0 {
			if strings.TrimSpace(stringValue(input["default_value"])) != "" {
				missingBehavior = "use_default"
			} else if input["required"] != true && missingBehavior != "clarify" {
				missingBehavior = "optional"
			}
		}
		if missingBehavior == "" {
			missingBehavior = "clarify"
		}
		key := inputName + ":" + missingBehavior
		if _, exists := seen[key]; exists {
			continue
		}
		seen[key] = struct{}{}
		result = append(result, compactMap(map[string]any{
			"input":            inputName,
			"missing_behavior": missingBehavior,
		}))
	}
	if len(result) == 0 {
		return nil
	}
	return result
}

func capabilityInputsByName(formalization map[string]any) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range listValue(formalization["inputs"]) {
		input, ok := item.(map[string]any)
		if !ok {
			continue
		}
		name := strings.TrimSpace(stringValue(input["input_name"]))
		if name == "" {
			name = strings.TrimSpace(stringValue(input["name"]))
		}
		if name != "" {
			result[name] = input
		}
	}
	return result
}

func capabilityFormalizationsByID(definition map[string]any) map[string]map[string]any {
	formalizations, _ := definition["capability_formalizations"].([]any)
	result := map[string]map[string]any{}
	for _, item := range formalizations {
		capability, ok := item.(map[string]any)
		if !ok {
			continue
		}
		capabilityID := strings.TrimSpace(stringValue(capability["capability_id"]))
		if capabilityID == "" {
			continue
		}
		result[capabilityID] = capability
	}
	return result
}

func effectiveAgentBusinessEffects(raw any, formalization map[string]any) map[string]any {
	effects, _ := raw.(map[string]any)
	if len(effects) == 0 {
		effects = mapValue(formalization, "business_effects")
	}
	if len(effects) == 0 && len(mapValue(formalization, "grant_policy")) == 0 {
		return nil
	}
	produces := stringSetFromAny(effects["produces"])
	doesNotProduce := stringSetFromAny(effects["does_not_produce"])
	if len(mapValue(formalization, "grant_policy")) > 0 {
		delete(produces, "data.read")
		produces["approval.request"] = struct{}{}
		produces["system.preview_mutation"] = struct{}{}
		doesNotProduce["approval.execute"] = struct{}{}
	}
	return compactMap(map[string]any{
		"produces":         sortedStringSet(produces),
		"does_not_produce": sortedStringSet(doesNotProduce),
	})
}

func effectiveAgentAppBoundaries(raw any, businessEffects map[string]any, formalization map[string]any) map[string]any {
	boundaries, _ := raw.(map[string]any)
	result := map[string]any{}
	for key, value := range boundaries {
		result[key] = value
	}
	blocked := stringSetFromAny(result["unsupported_effects"])
	for value := range stringSetFromAny(businessEffects["does_not_produce"]) {
		blocked[value] = struct{}{}
	}
	if len(blocked) > 0 {
		result["unsupported_effects"] = sortedStringSet(blocked)
	}
	if len(mapValue(formalization, "grant_policy")) > 0 {
		if strings.TrimSpace(stringValue(result["guidance"])) == "" {
			result["guidance"] = "This capability is approval-governed. Invoke it to produce the service-owned preview/request; do not execute the governed action in app code."
		}
	}
	return compactMap(result)
}

func effectiveAgentApproval(raw any, formalization map[string]any) map[string]any {
	approval, _ := raw.(map[string]any)
	if len(mapValue(formalization, "grant_policy")) == 0 {
		return approval
	}
	result := map[string]any{}
	for key, value := range approval {
		result[key] = value
	}
	result["required"] = true
	if result["grant_types"] == nil {
		result["grant_types"] = mapValue(formalization, "grant_policy")["allowed_grant_types"]
	}
	if result["approval_effect"] == nil {
		result["approval_effect"] = "approval.request"
	}
	return compactMap(result)
}

func stringSetFromAny(value any) map[string]struct{} {
	result := map[string]struct{}{}
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			text := strings.TrimSpace(stringValue(item))
			if text != "" {
				result[text] = struct{}{}
			}
		}
	case []string:
		for _, item := range typed {
			text := strings.TrimSpace(item)
			if text != "" {
				result[text] = struct{}{}
			}
		}
	}
	return result
}

func sortedStringSet(values map[string]struct{}) []any {
	if len(values) == 0 {
		return nil
	}
	items := make([]string, 0, len(values))
	for value := range values {
		items = append(items, value)
	}
	sort.Strings(items)
	result := make([]any, 0, len(items))
	for _, item := range items {
		result = append(result, item)
	}
	return result
}

func buildAppGlueRequired(consumability map[string]any) []map[string]any {
	capabilities := mapValue(consumability, "capabilities")
	items := make([]map[string]any, 0)
	for capabilityID, raw := range capabilities {
		hint, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		appGlue := mapValue(hint, "app_glue")
		if appGlue["required"] != true {
			continue
		}
		items = append(items, compactMap(map[string]any{
			"capability_id":        capabilityID,
			"reason":               stringValue(appGlue["reason"]),
			"required_context":     hint["required_context"],
			"derived_target_owner": hint["derived_target_owner"],
		}))
	}
	sort.Slice(items, func(i, j int) bool {
		return stringValue(items[i]["capability_id"]) < stringValue(items[j]["capability_id"])
	})
	return items
}

func buildRuntimeCustomization(consumability map[string]any) map[string]any {
	runtimeRules := buildRuntimeCapabilitySelectionRules(consumability)
	return map[string]any{
		"artifact_type":  "agent_runtime_customization",
		"schema_version": "anip-agent-consumption-kit/v0",
		"description":    "Generated starter rules for package-specific agent consumption. Review and edit custom/runtime-overrides.json instead of changing generic runtime libraries.",
		"normalization": map[string]any{
			"deictic_terms": []any{"one", "ones"},
			"token_variant_rules": []any{
				map[string]any{
					"id":          "adjective-al",
					"suffix":      "al",
					"replacement": "",
					"min_length":  float64(6),
					"example":     "regional -> region",
				},
				map[string]any{
					"id":          "adjective-ial",
					"suffix":      "ial",
					"replacement": "",
					"min_length":  float64(7),
					"example":     "territorial -> territor",
				},
				map[string]any{
					"id":          "adjective-y",
					"suffix":      "y",
					"replacement": "",
					"min_length":  float64(5),
					"example":     "risky -> risk",
				},
			},
		},
		"capability_selection": map[string]any{
			"approval_boundary_min_score": float64(0.12),
			"effect_rewrite_min_score":    float64(0.12),
			"effect_rewrite_margin":       float64(0.1),
			"effect_floor_min_score":       float64(0.12),
			"effect_floor_margin":          float64(0.02),
			"business_language_rules":      runtimeRules["business_language_rules"],
			"selection_hints":              runtimeRules["selection_hints"],
		},
	}
}

func buildRuntimeCustomizationOverrides(consumability map[string]any) map[string]any {
	runtimeRules := buildRuntimeCapabilitySelectionRules(consumability)
	return map[string]any{
		"artifact_type":        "agent_runtime_customization_overrides",
		"schema_version":       "anip-agent-consumption-kit/v0",
		"description":          "Editable app-owned overrides. Keep package or domain-specific language interpretation here, not in shared ANIP runtime utilities.",
		"normalization":        map[string]any{},
		"capability_selection": runtimeRules,
	}
}

func buildRuntimeCapabilitySelectionRules(consumability map[string]any) map[string]any {
	capabilities := mapValue(consumability, "capabilities")
	capabilityIDs := make([]string, 0, len(capabilities))
	for capabilityID := range capabilities {
		capabilityIDs = append(capabilityIDs, capabilityID)
	}
	sort.Strings(capabilityIDs)

	businessRules := make([]any, 0)
	for _, capabilityID := range capabilityIDs {
		hint, ok := capabilities[capabilityID].(map[string]any)
		if !ok {
			continue
		}
		for _, rawRule := range listValue(hint["business_language_rules"]) {
			rule, ok := rawRule.(map[string]any)
			if !ok {
				continue
			}
			withCapability := map[string]any{"capability": capabilityID}
			for key, value := range rule {
				withCapability[key] = value
			}
			businessRules = append(businessRules, compactMap(withCapability))
		}
	}

	selectionHints := listValue(consumability["selection_hints"])
	return compactMap(map[string]any{
		"business_language_rules": businessRules,
		"selection_hints":         selectionHints,
	})
}

func buildRuntimeCustomizationReadme() string {
	var builder strings.Builder
	builder.WriteString("# Runtime Customization\n\n")
	builder.WriteString("This folder is the intended place for package-specific agent glue that cannot honestly be solved by generic ANIP runtime code.\n\n")
	builder.WriteString("- Keep shared runtime libraries generic: parsing, validation, token issuance, invocation, and ANIP outcome handling.\n")
	builder.WriteString("- Put business-language interpretation, package-specific normalization, and routing thresholds in `runtime-overrides.json`.\n")
	builder.WriteString("- Treat `../runtime-customization.json` as generated starter behavior. It can be regenerated; this custom folder is the reviewed app-owned layer.\n")
	builder.WriteString("- Prefer small reviewed rules with examples over endless phrase lists.\n\n")
	builder.WriteString("Supported sections:\n\n")
	builder.WriteString("- `normalization.deictic_terms`: words such as `one` or `ones` that should not ground a required entity by themselves.\n")
	builder.WriteString("- `normalization.token_variant_rules`: simple suffix rules used to match business adjectives to reviewed enum/reference values.\n")
	builder.WriteString("- `capability_selection.*`: score thresholds used when the runtime chooses a more precise declared capability after the model's first choice.\n\n")
	builder.WriteString("- `capability_selection.business_language_rules`: reviewed app-owned wording rules exported from Studio app customization review.\n")
	builder.WriteString("- `capability_selection.selection_hints`: compact reviewed routing hints for package-specific capability selection.\n\n")
	builder.WriteString("If a behavior is specific to this package, keep it here or in reviewed app-profile metadata. Do not hide it in `anip-runtime-utils`.\n")
	return builder.String()
}

func buildPromptBrief(resolved *ResolvedServiceDefinition, capabilityIndex []map[string]any, appGlue []map[string]any) string {
	var builder strings.Builder
	builder.WriteString("# ANIP Agent Consumption Brief\n\n")
	builder.WriteString("This directory is generated from signed ANIP package metadata. It is framework-agnostic and can be loaded by LangGraph, Mastra, CrewAI, or custom agents.\n\n")
	if resolved.PackageID != "" {
		builder.WriteString(fmt.Sprintf("- Package: `%s@%s`\n", resolved.PackageID, resolved.PackageVersion))
	}
	if resolved.ContractSignature != "" {
		builder.WriteString(fmt.Sprintf("- Contract signature: `%s`\n", resolved.ContractSignature))
	}
	if schema := stringValue(resolved.AgentConsumability["schema_version"]); schema != "" {
		builder.WriteString(fmt.Sprintf("- Consumability schema: `%s`\n", schema))
	}
	builder.WriteString(fmt.Sprintf("- Capability hints: `%d`\n", len(capabilityIndex)))
	builder.WriteString(fmt.Sprintf("- Required app glue items: `%d`\n\n", len(appGlue)))
	builder.WriteString("## How To Use\n\n")
	builder.WriteString("- Load `agent-consumability.json` as the semantic hint source.\n")
	builder.WriteString("- Load `agent-app-profile.json` when an agent runtime supports structured app-layer guidance.\n")
	builder.WriteString("- Load `capability-index.json` to map capability IDs to services, scopes, inputs, and hints.\n")
	builder.WriteString("- Use `app-glue-required.json` to keep app-specific behavior explicit instead of hiding it in generic runtime code.\n")
	builder.WriteString("- Load `runtime-customization.json` plus `custom/runtime-overrides.json` for reviewed app-specific normalization and capability-selection behavior.\n")
	builder.WriteString("- Use reviewed `intent_rules` as app-consumption guidance; do not treat unreviewed AI drafts as authority.\n")
	builder.WriteString("- Treat this brief as convenience text; JSON files are the authoritative artifacts.\n\n")
	if len(appGlue) > 0 {
		builder.WriteString("## Required App Glue\n\n")
		for _, item := range appGlue {
			builder.WriteString(fmt.Sprintf("- `%s`: %s\n", stringValue(item["capability_id"]), stringValue(item["reason"])))
		}
		builder.WriteString("\n")
	}
	return builder.String()
}

func mapValue(source map[string]any, key string) map[string]any {
	if source == nil {
		return nil
	}
	value, _ := source[key].(map[string]any)
	return value
}

func listValue(value any) []any {
	switch typed := value.(type) {
	case []any:
		return typed
	case []string:
		result := make([]any, 0, len(typed))
		for _, item := range typed {
			result = append(result, item)
		}
		return result
	default:
		return nil
	}
}

func compactMap(source map[string]any) map[string]any {
	result := map[string]any{}
	for key, value := range source {
		if value == nil {
			continue
		}
		if text, ok := value.(string); ok && strings.TrimSpace(text) == "" {
			continue
		}
		if list, ok := value.([]any); ok && len(list) == 0 {
			continue
		}
		if object, ok := value.(map[string]any); ok && len(object) == 0 {
			continue
		}
		result[key] = value
	}
	return result
}
