package generator

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// Uses the same opt-in and installed Python toolchain as executable conformance.
// The generated host and local SDK execute normally, with test authentication
// lookup and a backend spy; this is not production-authentication coverage.
func TestGeneratedPythonCompositionEmptyResultPolicies(t *testing.T) {
	if os.Getenv("ANIP_GENERATOR_EXECUTABLE_CONFORMANCE") != "1" {
		t.Skip("set ANIP_GENERATOR_EXECUTABLE_CONFORMANCE=1 to execute the generated Python composition")
	}
	runGeneratedPythonCompositionEmptyResultPolicies(t, mustRepoRoot(t))
}

func runGeneratedPythonCompositionEmptyResultPolicies(t *testing.T, repoRoot string) {
	t.Helper()
	for _, policy := range []string{"clarify", "deny", "return_success_no_results"} {
		for _, empty := range []bool{true, false} {
			t.Run(policy+"/empty="+strconv.FormatBool(empty), func(t *testing.T) {
				definition := mustReadGeneratorConformanceDefinition(t, "generator-conformance-definition.json")
				found := false
				for i := range definition.CapabilityFormalizations {
					capability := &definition.CapabilityFormalizations[i]
					if capability.CapabilityID != "conformance.lookup_and_prepare" {
						continue
					}
					found = true
					if capability.Composition == nil || !capability.Composition.Steps[0].EmptyResultSource {
						t.Fatal("fixture must designate its first step as the empty source")
					}
					capability.Composition.EmptyResultPolicy = policy
					capability.Composition.EmptyResultOutput = nil
					if policy == "return_success_no_results" {
						capability.Composition.EmptyResultOutput = map[string]any{"prepared_status": "no_results"}
					}
				}
				if !found {
					t.Fatal("missing conformance composition")
				}
				runGeneratedPythonCompositionScript(t, repoRoot, definition,
					pythonCompositionEmptyResultRegression, policy, strconv.FormatBool(empty))
			})
		}
	}
}

func TestGeneratedPythonCompositionEmptyResultOutput(t *testing.T) {
	if os.Getenv("ANIP_GENERATOR_EXECUTABLE_CONFORMANCE") != "1" {
		t.Skip("set ANIP_GENERATOR_EXECUTABLE_CONFORMANCE=1 to execute the generated Python composition")
	}
	runGeneratedPythonCompositionEmptyResultOutput(t, mustRepoRoot(t))
}

func runGeneratedPythonCompositionEmptyResultOutput(t *testing.T, repoRoot string) {
	t.Helper()
	for _, tc := range []struct {
		name     string
		output   map[string]any
		expected map[string]any
	}{
		{
			name:     "empty_mapping",
			output:   map[string]any{},
			expected: map[string]any{},
		},
		{
			name:     "parent_input_reference",
			output:   map[string]any{"query": "$.input.query"},
			expected: map[string]any{"query": "CON-1"},
		},
		{
			name:     "source_output_reference",
			output:   map[string]any{"matches": "$.steps.lookup.output.result"},
			expected: map[string]any{"matches": []any{}},
		},
		{
			name: "source_output_falsy_references",
			output: map[string]any{
				"flag": "$.steps.lookup.output.flag", "count": "$.steps.lookup.output.count",
			},
			expected: map[string]any{"flag": false, "count": 0},
		},
		{
			name: "literal_values",
			output: map[string]any{
				"status": "no_results", "flag": false, "count": 0, "items": []any{},
				"paths":  []any{"$.input.query", "$.steps.lookup.output.result"},
				"nested": map[string]any{"query": "$.input.query", "flag": false},
			},
			expected: map[string]any{
				"status": "no_results", "flag": false, "count": 0, "items": []any{},
				"paths":  []any{"$.input.query", "$.steps.lookup.output.result"},
				"nested": map[string]any{"query": "$.input.query", "flag": false},
			},
		},
		{
			name: "missing_references",
			output: map[string]any{
				"missing_input": "$.input.missing", "missing_source": "$.steps.lookup.output.missing",
			},
			expected: map[string]any{"missing_input": nil, "missing_source": nil},
		},
	} {
		t.Run(tc.name, func(t *testing.T) {
			definition := mustReadGeneratorConformanceDefinition(t, "generator-conformance-definition.json")
			found := false
			for i := range definition.CapabilityFormalizations {
				capability := &definition.CapabilityFormalizations[i]
				if capability.CapabilityID != "conformance.lookup_and_prepare" {
					continue
				}
				found = true
				composition := capability.Composition
				if composition == nil || len(composition.Steps) != 2 ||
					composition.Steps[0].ID != "lookup" || !composition.Steps[0].EmptyResultSource ||
					composition.Steps[0].Capability != "conformance.lookup" ||
					composition.Steps[1].Capability != "conformance.prepare_change" {
					t.Fatal("fixture must designate lookup as the empty source before prepare_change")
				}
				composition.EmptyResultPolicy = "return_success_no_results"
				composition.EmptyResultOutput = tc.output
			}
			if !found {
				t.Fatal("missing conformance composition")
			}
			expected, err := json.Marshal(tc.expected)
			if err != nil {
				t.Fatal(err)
			}
			runGeneratedPythonCompositionScript(t, repoRoot, definition,
				pythonCompositionEmptyResultOutputRegression, string(expected))
		})
	}
}

func runGeneratedPythonCompositionScript(t *testing.T, repoRoot string, definition *AnipServiceDefinition, script string, args ...string) {
	t.Helper()
	helpers, _, ok := strings.Cut(pythonExecutableBehaviorMatrixTest(), "def test_behavior_matrix_lookup_success")
	if !ok {
		t.Fatal("missing Python conformance invocation helper boundary")
	}
	project, err := BuildPythonProject(definition, BuildPythonProjectOptions{DependencySource: DependencySourceLocal, Port: 4100})
	if err != nil {
		t.Fatal(err)
	}
	outputDir := t.TempDir()
	if err := WriteGeneratedProject(project, outputDir, true); err != nil {
		t.Fatal(err)
	}
	paths := []string{filepath.Join(outputDir, "src")}
	for _, pkg := range []string{"anip-core", "anip-crypto", "anip-server", "anip-service", "anip-fastapi", "anip-stdio"} {
		paths = append(paths, filepath.Join(repoRoot, "packages", "python", pkg, "src"))
	}
	env := append(os.Environ(), "PYTHONPATH="+strings.Join(paths, string(os.PathListSeparator)), "PYTHONDONTWRITEBYTECODE=1")
	runConformanceCommand(t, outputDir, env, pythonExecutable(repoRoot),
		append([]string{"-B", "-c", helpers + script}, args...)...)
}

const pythonCompositionEmptyResultOutputRegression = `
import json
import sys

expected = json.loads(sys.argv[1])
module = importlib.import_module("generator_conformance_service.capabilities")
calls = []


class RecordingAdapter:
    async def execute(self, capability, plan, adapter_input, context):
        name = capability["capability_id"]
        calls.append(name)
        assert name == "conformance.lookup", f"downstream backend called: {name}"
        assert adapter_input["query"] == "CON-1", adapter_input
        return {"result": [], "flag": False, "count": 0}


module.backend_adapter = RecordingAdapter()
payload = _invoke(_client(), "dev-admin-key", "conformance.lookup_and_prepare",
                  ["conformance.read", "conformance.prepare"],
                  {"query": "CON-1", "requested_status": "done", "change_reason": "regression"})
assert calls == ["conformance.lookup"], (calls, payload)
assert payload["success"] is True, payload
# Compare serialized values too: Python equality otherwise treats False and 0 as equal.
assert payload["result"] == expected, (expected, payload)
assert json.dumps(payload["result"], sort_keys=True) == json.dumps(expected, sort_keys=True), payload
`

const pythonCompositionEmptyResultRegression = `
import sys

policy, empty_arg = sys.argv[1:]
empty = empty_arg == "true"
module = importlib.import_module("generator_conformance_service.capabilities")
calls = []


class RecordingAdapter:
    async def execute(self, capability, plan, adapter_input, context):
        name = capability["capability_id"]
        calls.append(name)
        if name == "conformance.lookup":
            return {"result": [] if empty else [{"record_ref": "CON-1"}]}
        assert name == "conformance.prepare_change", name
        assert adapter_input == {"record_ref": "CON-1", "new_status": "done", "change_reason": "regression"}
        return {"execution_status": "prepared_by_test"}


module.backend_adapter = RecordingAdapter()
payload = _invoke(_client(), "dev-admin-key", "conformance.lookup_and_prepare",
                  ["conformance.read", "conformance.prepare"],
                  {"query": "CON-1", "requested_status": "done", "change_reason": "regression"})
expected_calls = ["conformance.lookup"]
if not empty:
    expected_calls.append("conformance.prepare_change")
assert calls == expected_calls, f"policy={policy} empty={empty}: calls={calls}, response={payload}"

if empty and policy in ("clarify", "deny"):
    expected_failure = {
        "clarify": "composition_empty_result_clarification_required",
        "deny": "composition_empty_result_denied",
    }[policy]
    _assert_failure_type(payload, expected_failure)
    assert "result" not in payload or payload["result"] is None, payload
else:
    assert payload["success"] is True, payload
    expected = {"prepared_status": "no_results"} if empty else {"prepared_status": "prepared_by_test"}
    assert payload["result"] == expected, payload
`
