package packagecmd

import "testing"

// SPEC.md §4.1: an input that does not state required is required.
func TestLocalAgentMetadataTreatsUnstatedRequiredAsRequired(t *testing.T) {
	definition := map[string]any{
		"capability_formalizations": []any{
			map[string]any{
				"capability_id": "jira.story.prepare",
				"inputs": []any{
					map[string]any{"input_name": "summary"},
					map[string]any{"input_name": "labels", "required": false},
					map[string]any{"input_name": "project_key", "required": true, "semantic_type": "project_scope"},
				},
			},
		},
	}

	findings := buildLocalAgentReadinessFindings(definition)
	if len(findings) != 1 {
		t.Fatalf("expected one finding (the unclassified required input), got %+v", findings)
	}
	if id := findings[0].(map[string]any)["id"]; id != "jira.story.prepare:summary:classification" {
		t.Fatalf("unexpected finding: %+v", findings[0])
	}

	consumability := buildLocalAgentConsumability(definition)
	capability := consumability["capabilities"].(map[string]any)["jira.story.prepare"].(map[string]any)
	postures := map[string]string{}
	for _, item := range capability["required_context"].([]any) {
		context := item.(map[string]any)
		postures[context["input"].(string)] = context["posture"].(string)
	}
	want := map[string]string{"summary": "required", "labels": "optional", "project_key": "required"}
	for name, posture := range want {
		if postures[name] != posture {
			t.Fatalf("posture of %s = %q, want %q (all: %+v)", name, postures[name], posture, postures)
		}
	}
}
