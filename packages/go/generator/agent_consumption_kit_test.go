package generator

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestBuildAgentConsumptionKit(t *testing.T) {
	resolved := &ResolvedServiceDefinition{
		PackageID:         "work-item-fronting",
		PackageVersion:    "0.2.0",
		ContractSignature: "sha256:test-contract",
		Definition: map[string]any{
			"capability_formalizations": []any{
				map[string]any{
					"capability_id": "work_item.search",
					"service_id":    "work-item",
					"title":         "Search Work Items",
					"summary":       "Search work items.",
					"kind":          "atomic",
					"minimum_scope": []any{"work.read"},
					"business_effects": map[string]any{
						"produces": []any{"data.read"},
					},
					"inputs": []any{
						map[string]any{"input_name": "query", "required": true},
					},
				},
			},
		},
		AgentReadiness: map[string]any{
			"artifact_type": "agent_consumption_readiness",
			"status":        "ready",
		},
		AgentConsumability: map[string]any{
			"artifact_type":  "agent_consumability_metadata",
			"schema_version": "anip-agent-consumability/v0",
			"capabilities": map[string]any{
				"work_item.search": map[string]any{
					"intent": map[string]any{"category": "work.item.search", "summary": "Search work items."},
					"business_effects": map[string]any{
						"produces": []any{"data.read"},
					},
					"input_meanings": map[string]any{
						"status": map[string]any{"open": "Open work items."},
					},
					"app_boundaries": map[string]any{
						"conditional_approval_boundary": map[string]any{
							"when_missing": []any{"assignee"},
							"produces":     []any{"approval.request", "system.preview_mutation"},
						},
					},
					"app_glue": map[string]any{
						"required": true,
						"reason":   "The app supplies the search query.",
					},
					"business_language_rules": []any{
						map[string]any{
							"id":      "reviewed-search-language",
							"meaning": "Reviewed search wording maps to bounded search.",
							"applies_when": map[string]any{
								"all_terms": []any{"find"},
								"any_terms": []any{"work item", "ticket"},
							},
							"interpretation": "Treat as supported bounded search intent.",
							"agent_action":   "treat_as_supported",
						},
					},
				},
			},
			"selection_hints": []any{
				map[string]any{
					"capability": "work_item.search",
					"all_terms":  []any{"work"},
					"any_terms":  []any{"ticket"},
				},
			},
		},
	}

	files, err := BuildAgentConsumptionKit(resolved)
	if err != nil {
		t.Fatalf("BuildAgentConsumptionKit: %v", err)
	}
	paths := map[string]string{}
	for _, file := range files {
		paths[file.Path] = file.Content
	}
	for _, expected := range []string{
		"agent-consumption/agent-consumability.json",
		"agent-consumption/agent-readiness.json",
		"agent-consumption/agent-app-profile.json",
		"agent-consumption/capability-index.json",
		"agent-consumption/app-glue-required.json",
		"agent-consumption/runtime-customization.json",
		"agent-consumption/custom/runtime-overrides.json",
		"agent-consumption/custom/README.md",
		"agent-consumption/prompt-brief.md",
	} {
		if paths[expected] == "" {
			t.Fatalf("expected generated agent kit file %s", expected)
		}
	}
	var appGlue struct {
		Items []map[string]any `json:"items"`
	}
	if err := json.Unmarshal([]byte(paths["agent-consumption/app-glue-required.json"]), &appGlue); err != nil {
		t.Fatalf("decode app glue file: %v", err)
	}
	if len(appGlue.Items) != 1 || appGlue.Items[0]["capability_id"] != "work_item.search" {
		t.Fatalf("unexpected app glue metadata: %+v", appGlue.Items)
	}
	var appProfile struct {
		ArtifactType       string                    `json:"artifact_type"`
		CapabilityMetadata map[string]map[string]any `json:"capability_metadata"`
	}
	if err := json.Unmarshal([]byte(paths["agent-consumption/agent-app-profile.json"]), &appProfile); err != nil {
		t.Fatalf("decode app profile file: %v", err)
	}
	if appProfile.ArtifactType != "agent_app_profile" {
		t.Fatalf("unexpected app profile artifact type: %s", appProfile.ArtifactType)
	}
	searchProfile := appProfile.CapabilityMetadata["work_item.search"]
	if searchProfile["capability_framing"] != "Search work items." {
		t.Fatalf("expected capability framing in app profile, got %+v", searchProfile)
	}
	if _, ok := searchProfile["app_boundaries"].(map[string]any); !ok {
		t.Fatalf("expected app boundaries in app profile, got %+v", searchProfile)
	}
	if rules, ok := searchProfile["business_language_rules"].([]any); !ok || len(rules) != 1 {
		t.Fatalf("expected business language rules in app profile, got %+v", searchProfile)
	}
	var runtimeCustomization struct {
		ArtifactType        string         `json:"artifact_type"`
		Normalization       map[string]any `json:"normalization"`
		CapabilitySelection map[string]any `json:"capability_selection"`
	}
	if err := json.Unmarshal([]byte(paths["agent-consumption/runtime-customization.json"]), &runtimeCustomization); err != nil {
		t.Fatalf("decode runtime customization file: %v", err)
	}
	if runtimeCustomization.ArtifactType != "agent_runtime_customization" || len(runtimeCustomization.Normalization) == 0 {
		t.Fatalf("unexpected runtime customization metadata: %+v", runtimeCustomization)
	}
	if rules, ok := runtimeCustomization.CapabilitySelection["business_language_rules"].([]any); !ok || len(rules) != 1 {
		t.Fatalf("expected reviewed business language rules in runtime customization, got %+v", runtimeCustomization.CapabilitySelection)
	}
	if hints, ok := runtimeCustomization.CapabilitySelection["selection_hints"].([]any); !ok || len(hints) != 1 {
		t.Fatalf("expected selection hints in runtime customization, got %+v", runtimeCustomization.CapabilitySelection)
	}
	var runtimeOverrides struct {
		CapabilitySelection map[string]any `json:"capability_selection"`
	}
	if err := json.Unmarshal([]byte(paths["agent-consumption/custom/runtime-overrides.json"]), &runtimeOverrides); err != nil {
		t.Fatalf("decode runtime overrides file: %v", err)
	}
	if rules, ok := runtimeOverrides.CapabilitySelection["business_language_rules"].([]any); !ok || len(rules) != 1 {
		t.Fatalf("expected reviewed business language rules in runtime overrides, got %+v", runtimeOverrides.CapabilitySelection)
	}
	if !strings.Contains(paths["agent-consumption/custom/README.md"], "package-specific agent glue") {
		t.Fatalf("expected custom runtime README to explain app-owned customization")
	}
	if paths["agent-consumption/prompt-brief.md"] == "" || !strings.Contains(paths["agent-consumption/prompt-brief.md"], "framework-agnostic") {
		t.Fatalf("expected framework-agnostic prompt brief, got %q", paths["agent-consumption/prompt-brief.md"])
	}
	if !strings.Contains(paths["agent-consumption/prompt-brief.md"], "runtime-customization.json") {
		t.Fatalf("expected prompt brief to mention runtime customization")
	}
}

func TestBuildAgentConsumptionKitAugmentsGrantGovernedCapabilities(t *testing.T) {
	resolved := &ResolvedServiceDefinition{
		Definition: map[string]any{
			"capability_formalizations": []any{
				map[string]any{
					"capability_id": "gtm.prepare_followup_tasks",
					"service_id":    "pipeline",
					"title":         "Prepare Follow-up Tasks",
					"summary":       "Prepare follow-up tasks for high-risk accounts without executing downstream mutations.",
					"kind":          "atomic",
					"minimum_scope": []any{"gtm.pipeline.followup"},
					"business_effects": map[string]any{
						"produces":         []any{"data.read"},
						"does_not_produce": []any{"raw_data_export"},
					},
					"grant_policy": map[string]any{
						"allowed_grant_types": []any{"one_time", "session_bound"},
						"default_grant_type":  "one_time",
						"expires_in_seconds":  float64(900),
						"max_uses":            float64(1),
					},
				},
			},
		},
		AgentConsumability: map[string]any{
			"artifact_type":  "agent_consumability_metadata",
			"schema_version": "anip-agent-consumability/v0",
			"capabilities": map[string]any{
				"gtm.prepare_followup_tasks": map[string]any{
					"intent": map[string]any{"summary": "Prepare follow-up tasks."},
					"business_effects": map[string]any{
						"produces":         []any{"data.read"},
						"does_not_produce": []any{"raw_data_export"},
					},
				},
			},
		},
	}

	files, err := BuildAgentConsumptionKit(resolved)
	if err != nil {
		t.Fatalf("BuildAgentConsumptionKit: %v", err)
	}
	paths := map[string]string{}
	for _, file := range files {
		paths[file.Path] = file.Content
	}
	var appProfile struct {
		CapabilityMetadata map[string]map[string]any `json:"capability_metadata"`
	}
	if err := json.Unmarshal([]byte(paths["agent-consumption/agent-app-profile.json"]), &appProfile); err != nil {
		t.Fatalf("decode app profile file: %v", err)
	}
	profile := appProfile.CapabilityMetadata["gtm.prepare_followup_tasks"]
	effects, _ := profile["business_effects"].(map[string]any)
	produces := effects["produces"].([]any)
	if containsAny(produces, "data.read") || !containsAny(produces, "approval.request") || !containsAny(produces, "system.preview_mutation") {
		t.Fatalf("expected approval-preview effects without data.read, got %+v", produces)
	}
	approval, _ := profile["approval"].(map[string]any)
	if approval["required"] != true {
		t.Fatalf("expected approval required profile, got %+v", approval)
	}
	boundaries, _ := profile["app_boundaries"].(map[string]any)
	if !strings.Contains(stringValue(boundaries["guidance"]), "approval-governed") {
		t.Fatalf("expected approval guidance, got %+v", boundaries)
	}
}

func TestBuildAgentConsumptionKitSanitizesRequiredContextFromContractInputs(t *testing.T) {
	resolved := &ResolvedServiceDefinition{
		Definition: map[string]any{
			"capability_formalizations": []any{
				map[string]any{
					"capability_id": "gtm.draft_outreach_message",
					"service_id":    "outreach",
					"title":         "Draft Outreach Message",
					"summary":       "Draft outreach content.",
					"inputs": []any{
						map[string]any{"input_name": "target", "required": true},
						map[string]any{"input_name": "channel", "required": false, "default_value": "email"},
						map[string]any{"input_name": "persona", "required": false},
					},
				},
			},
		},
		AgentConsumability: map[string]any{
			"artifact_type":  "agent_consumability_metadata",
			"schema_version": "anip-agent-consumability/v0",
			"capabilities": map[string]any{
				"gtm.draft_outreach_message": map[string]any{
					"intent": map[string]any{"summary": "Draft outreach content."},
					"required_context": []any{
						map[string]any{"input": "target", "missing_behavior": "clarify"},
						map[string]any{"input": "channel", "missing_behavior": "clarify"},
						map[string]any{"input": "persona", "missing_behavior": "clarify_or_app_select"},
					},
				},
			},
		},
	}

	files, err := BuildAgentConsumptionKit(resolved)
	if err != nil {
		t.Fatalf("BuildAgentConsumptionKit: %v", err)
	}
	paths := map[string]string{}
	for _, file := range files {
		paths[file.Path] = file.Content
	}
	var appProfile struct {
		CapabilityMetadata map[string]map[string]any `json:"capability_metadata"`
	}
	if err := json.Unmarshal([]byte(paths["agent-consumption/agent-app-profile.json"]), &appProfile); err != nil {
		t.Fatalf("decode app profile file: %v", err)
	}
	contexts, _ := appProfile.CapabilityMetadata["gtm.draft_outreach_message"]["required_context"].([]any)
	behaviors := map[string]string{}
	for _, item := range contexts {
		context, _ := item.(map[string]any)
		behaviors[stringValue(context["input"])] = stringValue(context["missing_behavior"])
	}
	if behaviors["target"] != "clarify" || behaviors["channel"] != "use_default" || behaviors["persona"] != "optional" {
		t.Fatalf("expected contract input semantics to win over stale profile required context, got %+v", behaviors)
	}
}

func containsAny(values []any, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}
