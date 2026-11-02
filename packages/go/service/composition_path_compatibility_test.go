// Composition path compatibility characterization (v0.23, Go runtime).
//
// COMPATIBILITY NOTE — unresolved decision; characterization only.
//
// SPEC.md §4.6 "Input and Output Mapping" (base revision
// 8263c68a2977d4a4e1a428d1d1e26a92a5f61659) says v0.23 JSONPath is
// restricted to SINGLE-SEGMENT property access, with no filters, no
// wildcards, and no recursion; anything more complex is rejected at
// registration with composition_invalid_step.
//
// Observed Go behavior differs from that wording on segment count, not on
// the exclusions. In packages/go/service/v023.go the path regexes
//
//	jsonpathInputRE  ^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$
//	jsonpathStepRE   ^\$\.steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$
//
// accept repeated property segments after `$.input` and after
// `$.steps.<id>.output`, and resolveJsonPath walks the nested maps
// map-by-map. Multi-segment nested paths therefore validate and resolve
// successfully in the Go runtime. Brackets, wildcards, filters and
// recursive descent match neither regex and are rejected by parseStepRef
// with composition_invalid_step "malformed JSONPath"; forward references
// are rejected by ValidateComposition with "forward-references", matching
// the earlier-steps-only requirement.
//
// Evidence:
//   - source:    packages/go/service/v023.go (jsonpathInputRE, jsonpathStepRE,
//                parseStepRef, ValidateComposition, resolveJsonPath,
//                ExecuteComposition)
//   - baseline: packages/go/service/v023_composition_test.go (existing
//                composition validation/execution tests)
//   - this file: independent characterization of nested-path Go behavior
//                plus regression coverage for the rejected forms.
//
// These tests characterize the existing Go runtime only. Passing them is
// NOT proof of SPEC conformance and NOT proof of five-SDK parity. They do
// not amend the SPEC, tighten declaration membership, or change any null,
// failure, or empty-result behavior. The SPEC remains normative. Whether
// to revise its single-segment restriction or narrow the Go runtime's
// multi-segment behavior remains an UNRESOLVED compatibility decision.

package service

import (
	"reflect"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
)

// pathCompatFailurePolicy mirrors the propagate/fail_parent defaults used
// by basicComposition in v023_composition_test.go.
func pathCompatFailurePolicy() core.FailurePolicy {
	return core.FailurePolicy{
		ChildClarification:    core.FailurePolicyOutcomePropagate,
		ChildDenial:           core.FailurePolicyOutcomePropagate,
		ChildApprovalRequired: core.FailurePolicyOutcomePropagate,
		ChildError:            core.FailurePolicyOutcomeFailParent,
	}
}

// pathCompatComposition builds a two-step composition whose "select" step
// maps parameter "q" from jp, exercising whatever path form is under test.
// "enrich" is declared after "select" and is never forward-referenced by the
// base mappings, so only jp determines rejection.
func pathCompatComposition(jp string) *core.Composition {
	return &core.Composition{
		AuthorityBoundary: core.AuthorityBoundarySameService,
		Steps: []core.CompositionStep{
			{ID: "select", Capability: "select_cap"},
			{ID: "enrich", Capability: "enrich_cap"},
		},
		InputMapping: map[string]map[string]string{
			"select": {"q": jp},
		},
		OutputMapping: map[string]string{
			"items": "$.steps.enrich.output.items",
		},
		FailurePolicy: pathCompatFailurePolicy(),
	}
}

// --- Validation: rejected forms ------------------------------------------

func TestValidateCompositionRejectsUnsupportedPathForms(t *testing.T) {
	cases := []struct {
		name    string
		jp      string
		wantSub string
	}{
		// Forward references are rejected regardless of path shape.
		{"forward reference to later step", "$.steps.enrich.output.count", "forward-references"},
		{"bracket subscript on input", "$.input.items[0]", "malformed JSONPath"},
		{"bracket subscript on step output", "$.steps.enrich.output.items[0]", "malformed JSONPath"},
		{"wildcard", "$.input.*", "malformed JSONPath"},
		{"recursive descent", "$.input..nested", "malformed JSONPath"},
		{"filter expression", "$.input.items[?(@.id)]", "malformed JSONPath"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			comp := pathCompatComposition(tc.jp)
			err := ValidateComposition("path_compat", composedDecl("path_compat", comp), registry())
			if err == nil {
				t.Fatalf("expected path %q to be rejected, got nil error", tc.jp)
			}
			if !strings.Contains(err.Error(), tc.wantSub) {
				t.Fatalf("ValidateComposition(%q) error = %q, want substring %q", tc.jp, err.Error(), tc.wantSub)
			}
		})
	}
}

func TestValidateCompositionOutputMappingRejectsUnsupportedForms(t *testing.T) {
	cases := []struct {
		name string
		jp   string
	}{
		{"wildcard on step output", "$.steps.enrich.output.items[*]"},
		{"bracket on input", "$.input.items[?]"},
		{"recursive descent on step output", "$.steps.enrich.output..items"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			comp := pathCompatComposition("$.input.q")
			comp.OutputMapping["items"] = tc.jp
			err := ValidateComposition("path_compat", composedDecl("path_compat", comp), registry())
			if err == nil || !strings.Contains(err.Error(), "malformed JSONPath") {
				t.Fatalf("expected malformed JSONPath rejection for %q, got %v", tc.jp, err)
			}
		})
	}
}

// --- Validation: observed nested-path acceptance --------------------------

// Observed Go behavior: multi-segment nested property paths are accepted at
// registration, although SPEC.md §4.6 restricts JSONPath to single-segment
// property access. This test records the observation only; see the
// compatibility note above for the unresolved decision.
func TestValidateCompositionAcceptsNestedMultiSegmentPathsGoBehavior(t *testing.T) {
	comp := pathCompatComposition("$.input.filters.user.contact.email")
	comp.OutputMapping["owner"] = "$.steps.enrich.output.report.digest"
	if err := ValidateComposition("path_compat", composedDecl("path_compat", comp), registry()); err != nil {
		t.Fatalf("Go runtime accepts nested multi-segment paths; unexpected error: %v", err)
	}
}

// --- Execution: nested parent input, prior-step nested output, nested
// output mapping, and preserved flat paths -------------------------------

func TestExecuteCompositionNestedPathsFlowInputStepOutputAndOutputMapping(t *testing.T) {
	comp := &core.Composition{
		AuthorityBoundary: core.AuthorityBoundarySameService,
		Steps: []core.CompositionStep{
			{ID: "select", Capability: "select_cap"},
			{ID: "enrich", Capability: "enrich_cap"},
		},
		InputMapping: map[string]map[string]string{
			// Nested parent input path.
			"select": {"q": "$.input.filters.user.contact.email"},
			// Nested prior-step output paths.
			"enrich": {
				"items": "$.steps.select.output.selection.items",
				"owner": "$.steps.select.output.selection.owner",
			},
		},
		OutputMapping: map[string]string{
			// Nested output-mapping targets, spanning a prior-step output
			// and a nested parent input path.
			"owner":  "$.steps.select.output.selection.owner",
			"digest": "$.steps.enrich.output.report.digest",
			"source": "$.input.filters.tenant",
		},
		FailurePolicy: pathCompatFailurePolicy(),
	}
	decl := composedDecl("path_compat", comp)
	if err := ValidateComposition("path_compat", decl, registry()); err != nil {
		t.Fatalf("ValidateComposition: %v", err)
	}

	selectUser := map[string]any{
		"name":    "ada",
		"contact": map[string]any{"email": "ada@example.org"},
	}
	runner, calls := makeStepRunner(map[string]map[string]any{
		"select_cap": {"success": true, "result": map[string]any{
			"selection": map[string]any{"owner": "ada", "items": []any{"i1", "i2"}},
		}},
		"enrich_cap": {"success": true, "result": map[string]any{
			"report": map[string]any{"digest": "d1"},
		}},
	})
	parentInput := map[string]any{
		"filters": map[string]any{"tenant": "t1", "user": selectUser},
	}

	out, err := ExecuteComposition("path_compat", decl, parentInput, runner)
	if err != nil {
		t.Fatalf("ExecuteComposition: %v", err)
	}

	// Capture the exact child arguments produced by nested resolution.
	if len(*calls) != 2 {
		t.Fatalf("expected 2 child invocations, got %d", len(*calls))
	}
	if (*calls)[0][0] != "select_cap" {
		t.Errorf("call[0] capability = %v, want select_cap", (*calls)[0][0])
	}
	wantSelect := map[string]any{"q": "ada@example.org"}
	if !reflect.DeepEqual((*calls)[0][1], wantSelect) {
		t.Errorf("select params = %#v, want exactly %#v", (*calls)[0][1], wantSelect)
	}
	if (*calls)[1][0] != "enrich_cap" {
		t.Errorf("call[1] capability = %v, want enrich_cap", (*calls)[1][0])
	}
	wantEnrich := map[string]any{"items": []any{"i1", "i2"}, "owner": "ada"}
	if !reflect.DeepEqual((*calls)[1][1], wantEnrich) {
		t.Errorf("enrich params = %#v, want exactly %#v", (*calls)[1][1], wantEnrich)
	}

	// Assert the final parent output built from nested output mappings.
	if out["owner"] != "ada" {
		t.Errorf("out[owner] = %v, want ada", out["owner"])
	}
	if out["digest"] != "d1" {
		t.Errorf("out[digest] = %v, want d1", out["digest"])
	}
	if out["source"] != "t1" {
		t.Errorf("out[source] = %v, want t1", out["source"])
	}
}

func TestExecuteCompositionFlatSingleSegmentPathsPreserved(t *testing.T) {
	comp := &core.Composition{
		AuthorityBoundary: core.AuthorityBoundarySameService,
		Steps: []core.CompositionStep{
			{ID: "select", Capability: "select_cap"},
			{ID: "enrich", Capability: "enrich_cap"},
		},
		InputMapping: map[string]map[string]string{
			"select": {"q": "$.input.q"},
			"enrich": {"items": "$.steps.select.output.items"},
		},
		OutputMapping: map[string]string{
			"count": "$.steps.enrich.output.count",
			"q":     "$.input.q",
		},
		FailurePolicy: pathCompatFailurePolicy(),
	}
	decl := composedDecl("path_compat_flat", comp)
	if err := ValidateComposition("path_compat_flat", decl, registry()); err != nil {
		t.Fatalf("ValidateComposition: %v", err)
	}

	runner, calls := makeStepRunner(map[string]map[string]any{
		"select_cap": {"success": true, "result": map[string]any{"items": []any{"x"}}},
		"enrich_cap": {"success": true, "result": map[string]any{"count": 1}},
	})

	out, err := ExecuteComposition("path_compat_flat", decl, map[string]any{"q": "hello"}, runner)
	if err != nil {
		t.Fatalf("ExecuteComposition: %v", err)
	}

	if len(*calls) != 2 {
		t.Fatalf("expected 2 child invocations, got %d", len(*calls))
	}
	wantSelect := map[string]any{"q": "hello"}
	if !reflect.DeepEqual((*calls)[0][1], wantSelect) {
		t.Errorf("select params = %#v, want exactly %#v", (*calls)[0][1], wantSelect)
	}
	wantEnrich := map[string]any{"items": []any{"x"}}
	if !reflect.DeepEqual((*calls)[1][1], wantEnrich) {
		t.Errorf("enrich params = %#v, want exactly %#v", (*calls)[1][1], wantEnrich)
	}

	if out["count"] != 1 {
		t.Errorf("out[count] = %v, want 1", out["count"])
	}
	if out["q"] != "hello" {
		t.Errorf("out[q] = %v, want hello", out["q"])
	}
}
