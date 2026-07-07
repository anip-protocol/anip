package runtimeutils

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"testing"
)

type fixtureDocument struct {
	Cases []fixtureCase `json:"cases"`
}

type fallbackFixtureDocument struct {
	Cases []fallbackFixtureCase `json:"cases"`
}

type fixtureCase struct {
	ID                         string                        `json:"id"`
	Conversation               string                        `json:"conversation"`
	SelectedCapability         string                        `json:"selected_capability"`
	ExpectedCapability         string                        `json:"expected_capability"`
	ExpectedMissingInputs      []string                      `json:"expected_missing_inputs"`
	ExpectedUnsupportedEffects []string                      `json:"expected_unsupported_effects"`
	Metadata                   map[string]CapabilityMetadata `json:"metadata"`
}

type fallbackFixtureCase struct {
	ID                  string                        `json:"id"`
	Conversation        string                        `json:"conversation"`
	Plan                CapabilityMetadata            `json:"plan"`
	CompactCandidateIDs []string                      `json:"compact_candidate_ids"`
	ExpectedReasons     []string                      `json:"expected_reasons"`
	Metadata            map[string]CapabilityMetadata `json:"metadata"`
}

func TestSharedAgentConsumptionFixtures(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "agent-consumption-fixtures", "capability-selection.json"))
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}

	var fixture fixtureDocument
	if err := json.Unmarshal(data, &fixture); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}

	for _, item := range fixture.Cases {
		t.Run(item.ID, func(t *testing.T) {
			chosen := SelectConsumableCapability(item.Conversation, item.SelectedCapability, item.Metadata)
			if chosen != item.ExpectedCapability {
				t.Fatalf("selected capability = %q, want %q", chosen, item.ExpectedCapability)
			}

			if got := sortedStrings(MissingRequiredInputNames(item.Conversation, item.Metadata[chosen])); !reflect.DeepEqual(got, sortedStrings(item.ExpectedMissingInputs)) {
				t.Fatalf("missing required inputs = %v, want %v", got, sortedStrings(item.ExpectedMissingInputs))
			}

			if got := sortedStrings(RequestedUnsupportedEffects(item.Conversation, item.Metadata[item.SelectedCapability])); !reflect.DeepEqual(got, sortedStrings(item.ExpectedUnsupportedEffects)) {
				t.Fatalf("requested unsupported effects = %v, want %v", got, sortedStrings(item.ExpectedUnsupportedEffects))
			}
		})
	}
}

func TestSharedPlannerFallbackValidationFixtures(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "agent-consumption-fixtures", "planner-fallback-validation.json"))
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}

	var fixture fallbackFixtureDocument
	if err := json.Unmarshal(data, &fixture); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}

	for _, item := range fixture.Cases {
		t.Run(item.ID, func(t *testing.T) {
			got := ValidateInvocationPlanForFallback(item.Plan, item.Conversation, item.Metadata, FallbackValidationOptions{
				CompactCandidateIDs: item.CompactCandidateIDs,
			})
			if !reflect.DeepEqual(got, item.ExpectedReasons) {
				t.Fatalf("fallback reasons = %v, want %v", got, item.ExpectedReasons)
			}
		})
	}
}

func sortedStrings(values []string) []string {
	out := append([]string(nil), values...)
	sort.Strings(out)
	return out
}
