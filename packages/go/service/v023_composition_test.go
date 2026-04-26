// Composition validation + execution tests (v0.23 §4.6).
//
// Mirrors anip-service/tests/test_v023_composition.py and the TS equivalent
// in packages/typescript/service/tests/v023-composition.test.ts.

package service

import (
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
)

// --- Builders -------------------------------------------------------------

func atomicDecl(name string, fields []string) *core.CapabilityDeclaration {
	if fields == nil {
		fields = []string{"x"}
	}
	return &core.CapabilityDeclaration{
		Name:         name,
		Description:  "atomic " + name,
		Inputs:       []core.CapabilityInput{{Name: "x", Type: "string"}},
		Output:       core.CapabilityOutput{Type: "x", Fields: fields},
		SideEffect:   core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope: []string{"s"},
		Kind:         core.CapabilityKindAtomic,
	}
}

func composedDecl(name string, comp *core.Composition) *core.CapabilityDeclaration {
	if name == "" {
		name = "summary"
	}
	return &core.CapabilityDeclaration{
		Name:         name,
		Description:  "composed",
		Output:       core.CapabilityOutput{Type: "x", Fields: []string{"count", "items"}},
		SideEffect:   core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope: []string{"s"},
		Kind:         core.CapabilityKindComposed,
		Composition:  comp,
	}
}

func basicComposition() *core.Composition {
	return &core.Composition{
		AuthorityBoundary: core.AuthorityBoundarySameService,
		Steps: []core.CompositionStep{
			{ID: "select", Capability: "select_cap", EmptyResultSource: true},
			{ID: "enrich", Capability: "enrich_cap"},
		},
		InputMapping: map[string]map[string]string{
			"select": {"q": "$.input.q"},
			"enrich": {"items": "$.steps.select.output.items"},
		},
		OutputMapping: map[string]string{
			"count": "$.steps.enrich.output.count",
			"items": "$.steps.enrich.output.items",
		},
		EmptyResultPolicy: core.EmptyResultPolicyReturnSuccessNoResults,
		EmptyResultOutput: map[string]any{"count": 0, "items": []any{}},
		FailurePolicy: core.FailurePolicy{
			ChildClarification:    core.FailurePolicyOutcomePropagate,
			ChildDenial:           core.FailurePolicyOutcomePropagate,
			ChildApprovalRequired: core.FailurePolicyOutcomePropagate,
			ChildError:            core.FailurePolicyOutcomeFailParent,
		},
		AuditPolicy: core.AuditPolicy{
			RecordChildInvocations: true,
			ParentTaskLineage:      true,
		},
	}
}

func registry() map[string]*core.CapabilityDeclaration {
	return map[string]*core.CapabilityDeclaration{
		"select_cap": atomicDecl("select_cap", []string{"items"}),
		"enrich_cap": atomicDecl("enrich_cap", []string{"count", "items"}),
	}
}

// --- ValidateComposition -------------------------------------------------

func TestValidateCompositionAtomicPasses(t *testing.T) {
	if err := ValidateComposition("a", atomicDecl("a", nil), map[string]*core.CapabilityDeclaration{}); err != nil {
		t.Fatalf("ValidateComposition on atomic must succeed, got %v", err)
	}
}

func TestValidateCompositionHappyPath(t *testing.T) {
	decl := composedDecl("summary", basicComposition())
	if err := ValidateComposition("summary", decl, registry()); err != nil {
		t.Fatalf("happy-path validate: %v", err)
	}
}

func TestValidateCompositionMissingComposition(t *testing.T) {
	decl := composedDecl("summary", nil)
	err := ValidateComposition("summary", decl, registry())
	if err == nil {
		t.Fatal("expected error when composition is nil")
	}
	if !strings.Contains(err.Error(), "composition is missing") {
		t.Errorf("error = %q, want substring 'composition is missing'", err.Error())
	}
}

func TestValidateCompositionUnsupportedAuthorityBoundary(t *testing.T) {
	comp := basicComposition()
	comp.AuthorityBoundary = "same_package"
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "composition_unsupported_authority_boundary") {
		t.Fatalf("expected composition_unsupported_authority_boundary, got %v", err)
	}
}

func TestValidateCompositionDuplicateStepIDs(t *testing.T) {
	comp := basicComposition()
	comp.Steps = []core.CompositionStep{
		{ID: "a", Capability: "select_cap"},
		{ID: "a", Capability: "enrich_cap"},
	}
	comp.InputMapping = map[string]map[string]string{"a": {}}
	comp.OutputMapping = map[string]string{}
	comp.EmptyResultPolicy = ""
	comp.EmptyResultOutput = nil
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "duplicate step ids") {
		t.Fatalf("expected duplicate step ids, got %v", err)
	}
}

func TestValidateCompositionSelfReferenceRejected(t *testing.T) {
	comp := basicComposition()
	comp.Steps[0].Capability = "summary"
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "self-references") {
		t.Fatalf("expected self-reference rejection, got %v", err)
	}
}

func TestValidateCompositionUnknownStepCapability(t *testing.T) {
	comp := basicComposition()
	comp.Steps[0].Capability = "does_not_exist"
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "composition_unknown_capability") {
		t.Fatalf("expected composition_unknown_capability, got %v", err)
	}
}

func TestValidateCompositionComposedReferencingComposedRejected(t *testing.T) {
	// A composed step capability is rejected: composed→composed is not
	// allowed in v0.23.
	reg := map[string]*core.CapabilityDeclaration{
		"select_cap": composedDecl("select_cap", basicComposition()),
		"enrich_cap": atomicDecl("enrich_cap", nil),
	}
	err := ValidateComposition("summary", composedDecl("summary", basicComposition()), reg)
	if err == nil || !strings.Contains(err.Error(), `kind="composed"`) && !strings.Contains(err.Error(), "kind='composed'") {
		t.Fatalf("expected composed-calling-composed rejection, got %v", err)
	}
}

func TestValidateCompositionAtMostOneEmptyResultSource(t *testing.T) {
	comp := basicComposition()
	comp.Steps[1].EmptyResultSource = true
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "at most one") {
		t.Fatalf("expected 'at most one' rejection, got %v", err)
	}
}

func TestValidateCompositionInputMappingUnknownStepKey(t *testing.T) {
	comp := basicComposition()
	comp.InputMapping = map[string]map[string]string{"nope": {"q": "$.input.q"}}
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "not a declared step id") {
		t.Fatalf("expected unknown step key rejection, got %v", err)
	}
}

func TestValidateCompositionInputMappingForwardReferenceRejected(t *testing.T) {
	comp := basicComposition()
	comp.InputMapping["select"] = map[string]string{"items": "$.steps.enrich.output.items"}
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "forward-references") {
		t.Fatalf("expected forward-reference rejection, got %v", err)
	}
}

func TestValidateCompositionOutputMappingUnknownStep(t *testing.T) {
	comp := basicComposition()
	comp.OutputMapping = map[string]string{"count": "$.steps.bogus.output.count"}
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "references unknown step") {
		t.Fatalf("expected unknown step in output_mapping, got %v", err)
	}
}

func TestValidateCompositionEmptyResultPolicyClarifyWithOutputRejected(t *testing.T) {
	comp := basicComposition()
	comp.EmptyResultPolicy = core.EmptyResultPolicyClarify
	// empty_result_output is still set from basicComposition.
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "forbidden") {
		t.Fatalf("expected 'forbidden' for clarify with output, got %v", err)
	}
}

func TestValidateCompositionReturnSuccessWithoutOutputRejected(t *testing.T) {
	comp := basicComposition()
	comp.EmptyResultOutput = nil
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "requires empty_result_output") {
		t.Fatalf("expected 'requires empty_result_output', got %v", err)
	}
}

func TestValidateCompositionEmptyResultOutputReferencingSkippedStepRejected(t *testing.T) {
	comp := basicComposition()
	// source is "select", so referencing "enrich" is forbidden.
	comp.EmptyResultOutput = map[string]any{"items": "$.steps.enrich.output.items"}
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "only the empty_result_source") {
		t.Fatalf("expected 'only the empty_result_source' rejection, got %v", err)
	}
}

func TestValidateCompositionEmptyResultOutputInputReferenceAllowed(t *testing.T) {
	comp := basicComposition()
	comp.EmptyResultOutput = map[string]any{"q": "$.input.q", "items": []any{}}
	if err := ValidateComposition("summary", composedDecl("summary", comp), registry()); err != nil {
		t.Fatalf("expected $.input.* reference to be allowed, got %v", err)
	}
}

func TestValidateCompositionStepWithEmptyResultSourceRequiresPolicy(t *testing.T) {
	comp := basicComposition()
	comp.EmptyResultPolicy = ""
	comp.EmptyResultOutput = nil
	err := ValidateComposition("summary", composedDecl("summary", comp), registry())
	if err == nil || !strings.Contains(err.Error(), "empty_result_source") {
		t.Fatalf("expected empty_result_source policy requirement, got %v", err)
	}
}

// --- ExecuteComposition --------------------------------------------------

// makeStepRunner returns an InvokeStepFunc that returns scripted results,
// records calls, and lets tests assert on the call sequence. Each scripted
// entry mirrors the wire shape Service.Invoke produces.
func makeStepRunner(scripted map[string]map[string]any) (InvokeStepFunc, *[][2]any) {
	calls := &[][2]any{}
	runner := func(capability string, params map[string]any) (map[string]any, error) {
		*calls = append(*calls, [2]any{capability, params})
		return scripted[capability], nil
	}
	return runner, calls
}

func TestExecuteCompositionHappyPath(t *testing.T) {
	decl := composedDecl("summary", basicComposition())
	runner, calls := makeStepRunner(map[string]map[string]any{
		"select_cap": {"success": true, "result": map[string]any{"items": []any{
			map[string]any{"id": 1}, map[string]any{"id": 2},
		}}},
		"enrich_cap": {"success": true, "result": map[string]any{
			"count": 2, "items": []any{"a", "b"},
		}},
	})
	out, err := ExecuteComposition("summary", decl, map[string]any{"q": "test"}, runner)
	if err != nil {
		t.Fatalf("ExecuteComposition: %v", err)
	}
	count, _ := out["count"].(int)
	if count != 2 {
		t.Errorf("count = %v, want 2", out["count"])
	}
	items, _ := out["items"].([]any)
	if len(items) != 2 || items[0] != "a" || items[1] != "b" {
		t.Errorf("items = %v", items)
	}
	// Verify input flow: select got q from parent, enrich got items.
	if len(*calls) != 2 {
		t.Fatalf("expected 2 calls, got %d", len(*calls))
	}
	if (*calls)[0][0] != "select_cap" {
		t.Errorf("call[0] capability = %v", (*calls)[0][0])
	}
	if (*calls)[1][0] != "enrich_cap" {
		t.Errorf("call[1] capability = %v", (*calls)[1][0])
	}
}

func TestExecuteCompositionEmptyResultReturnSuccessNoResults(t *testing.T) {
	decl := composedDecl("summary", basicComposition())
	runner, calls := makeStepRunner(map[string]map[string]any{
		"select_cap": {"success": true, "result": map[string]any{"items": []any{}}},
	})
	out, err := ExecuteComposition("summary", decl, map[string]any{"q": "test"}, runner)
	if err != nil {
		t.Fatalf("ExecuteComposition: %v", err)
	}
	count, _ := out["count"].(int)
	if count != 0 {
		t.Errorf("count = %v, want 0", out["count"])
	}
	// enrich_cap is NEVER called because select's output was empty.
	if len(*calls) != 1 {
		t.Errorf("expected 1 call (only select), got %d", len(*calls))
	}
}

func TestExecuteCompositionEmptyResultClarifyRaises(t *testing.T) {
	comp := basicComposition()
	comp.EmptyResultPolicy = core.EmptyResultPolicyClarify
	comp.EmptyResultOutput = nil
	decl := composedDecl("summary", comp)
	runner, _ := makeStepRunner(map[string]map[string]any{
		"select_cap": {"success": true, "result": map[string]any{"items": []any{}}},
	})
	_, err := ExecuteComposition("summary", decl, map[string]any{"q": "x"}, runner)
	if err == nil {
		t.Fatal("expected error")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected *core.ANIPError, got %T: %v", err, err)
	}
	if anipErr.ErrorType != "composition_empty_result_clarification_required" {
		t.Errorf("ErrorType = %q", anipErr.ErrorType)
	}
}

func TestExecuteCompositionEmptyResultDenyRaises(t *testing.T) {
	comp := basicComposition()
	comp.EmptyResultPolicy = core.EmptyResultPolicyDeny
	comp.EmptyResultOutput = nil
	decl := composedDecl("summary", comp)
	runner, _ := makeStepRunner(map[string]map[string]any{
		"select_cap": {"success": true, "result": map[string]any{"items": []any{}}},
	})
	_, err := ExecuteComposition("summary", decl, map[string]any{"q": "x"}, runner)
	if err == nil {
		t.Fatal("expected error")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	if anipErr.ErrorType != "composition_empty_result_denied" {
		t.Errorf("ErrorType = %q", anipErr.ErrorType)
	}
}

func TestExecuteCompositionChildFailurePropagatesByDefault(t *testing.T) {
	decl := composedDecl("summary", basicComposition())
	runner, _ := makeStepRunner(map[string]map[string]any{
		"select_cap": {
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureScopeInsufficient,
				"detail": "select_cap requires more scope",
			},
		},
	})
	_, err := ExecuteComposition("summary", decl, map[string]any{"q": "x"}, runner)
	if err == nil {
		t.Fatal("expected error")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	// Default failure_policy.child_denial = "propagate".
	if anipErr.ErrorType != core.FailureScopeInsufficient {
		t.Errorf("ErrorType = %q, want %q", anipErr.ErrorType, core.FailureScopeInsufficient)
	}
}

func TestExecuteCompositionChildErrorFailsParent(t *testing.T) {
	// child_error policy is fail_parent — collapse to composition_child_failed
	// per SPEC.md §4.6, with original child error type captured in detail.
	decl := composedDecl("summary", basicComposition())
	runner, _ := makeStepRunner(map[string]map[string]any{
		"select_cap": {
			"success": false,
			"failure": map[string]any{
				"type":   core.FailureInternalError,
				"detail": "boom",
			},
		},
	})
	_, err := ExecuteComposition("summary", decl, map[string]any{"q": "x"}, runner)
	if err == nil {
		t.Fatal("expected error")
	}
	anipErr, ok := err.(*core.ANIPError)
	if !ok {
		t.Fatalf("expected *core.ANIPError, got %T", err)
	}
	if anipErr.ErrorType != FailureCompositionChildFailed {
		t.Errorf("ErrorType = %q, want %q", anipErr.ErrorType, FailureCompositionChildFailed)
	}
	if !strings.Contains(anipErr.Detail, core.FailureInternalError) {
		t.Errorf("detail %q should contain original child error type %q", anipErr.Detail, core.FailureInternalError)
	}
	if !strings.Contains(anipErr.Detail, "child step") {
		t.Errorf("detail %q should mention 'child step'", anipErr.Detail)
	}
}

// --- Digests --------------------------------------------------------------

func TestSha256DigestSortsKeys(t *testing.T) {
	d1, err := Sha256Digest(map[string]any{"a": 1, "b": 2})
	if err != nil {
		t.Fatalf("Sha256Digest: %v", err)
	}
	d2, err := Sha256Digest(map[string]any{"b": 2, "a": 1})
	if err != nil {
		t.Fatalf("Sha256Digest: %v", err)
	}
	if d1 != d2 {
		t.Errorf("digests differ when only key order differs: %q vs %q", d1, d2)
	}
}

func TestSha256DigestDistinctInputs(t *testing.T) {
	d1, _ := Sha256Digest(map[string]any{"a": 1})
	d2, _ := Sha256Digest(map[string]any{"a": 2})
	if d1 == d2 {
		t.Error("distinct inputs produced identical digests")
	}
}

func TestSha256DigestPrefix(t *testing.T) {
	d, err := Sha256Digest(map[string]any{"x": 1})
	if err != nil {
		t.Fatalf("Sha256Digest: %v", err)
	}
	if !strings.HasPrefix(d, "sha256:") {
		t.Errorf("digest must start with sha256:, got %q", d)
	}
}
