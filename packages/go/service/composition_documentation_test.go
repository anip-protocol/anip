// Documentation contract tests: the composition example under
// "Capability composition (v0.23)" in website/docs/protocol/capabilities.md
// must decode strictly and execute as documented. The fence is read from the
// joined repository document at test time; nothing here repairs or copies it.

package service

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
)

// Frozen contract for the documented composition (v0.23).
const (
	docHeading          = "Capability composition (v0.23)"
	docParentCapability = "gtm.at_risk_account_enrichment_summary"
	docRiskCapability   = "gtm.account_risk_summary"
	docEnrichCapability = "gtm.account_enrichment_summary"
)

// docCapabilitiesFile locates the joined repository document relative to the
// test working directory (packages/go/service).
func docCapabilitiesFile(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("could not determine working directory: %v", err)
	}
	rel := filepath.Join("website", "docs", "protocol", "capabilities.md")
	for i := 0; i < 8; i++ {
		candidate := filepath.Join(dir, rel)
		if st, err := os.Stat(candidate); err == nil && !st.IsDir() {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatalf("capabilities documentation not found above the test package (looking for %s)", rel)
	return ""
}

// docComposition reads the unique matching example in the exact composition
// section. Only its composition member is strictly decoded, not a full manifest.
func docComposition(t *testing.T) (string, core.Composition) {
	t.Helper()
	raw, err := os.ReadFile(docCapabilitiesFile(t))
	if err != nil {
		t.Fatalf("reading capabilities documentation: %v", err)
	}
	compRaw, err := extractDocComposition(string(raw))
	if err != nil {
		t.Fatalf("extracting documented composition: %v", err)
	}
	name := docParentCapability

	// Exercise the same strict single-value decoder for the documented value
	// and both negative controls. A streaming decoder alone permits two values.
	comp, err := decodeDocComposition(compRaw)
	if err != nil {
		t.Fatalf("strict decode of documented composition failed: %v\ncomposition: %s", err, compRaw)
	}
	withUnknown := strings.Replace(string(compRaw), "{", "{\"undocumented_field\":true,", 1)
	if _, err := decodeDocComposition([]byte(withUnknown)); err == nil {
		t.Fatal("strict decode unexpectedly accepted an unknown field")
	}
	if _, err := decodeDocComposition([]byte(string(compRaw) + " 42")); err == nil {
		t.Fatal("strict decode unexpectedly accepted trailing JSON")
	}
	return name, comp
}

func decodeDocComposition(raw []byte) (core.Composition, error) {
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.DisallowUnknownFields()
	var comp core.Composition
	if err := dec.Decode(&comp); err != nil {
		return comp, err
	}
	var extra json.RawMessage
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return comp, fmt.Errorf("composition contains a trailing JSON value")
		}
		return comp, fmt.Errorf("composition contains trailing data: %w", err)
	}
	return comp, nil
}

// extractDocComposition deliberately supports this page's ATX headings and
// triple-backtick fences, not general Markdown. Headings inside fences are data.
func extractDocComposition(doc string) (json.RawMessage, error) {
	var selected json.RawMessage
	headings, matches := 0, 0
	inSection, inFence, jsonFence := false, false, false
	var body []string
	for _, line := range strings.Split(strings.ReplaceAll(doc, "\r\n", "\n"), "\n") {
		text := strings.TrimSpace(line)
		if inFence {
			if text != "```" {
				if inSection && jsonFence {
					body = append(body, line)
				}
				continue
			}
			inFence = false
			if !inSection || !jsonFence {
				continue
			}
			var fragment map[string]json.RawMessage
			if err := json.Unmarshal([]byte(strings.Join(body, "\n")), &fragment); err != nil || fragment == nil {
				return nil, fmt.Errorf("malformed JSON object in composition section")
			}
			var name string
			if raw, ok := fragment["name"]; ok {
				if err := json.Unmarshal(raw, &name); err != nil {
					return nil, fmt.Errorf("example name is not a JSON string")
				}
			}
			if name != docParentCapability {
				continue
			}
			var kind string
			if err := json.Unmarshal(fragment["kind"], &kind); err != nil || kind != core.CapabilityKindComposed {
				return nil, fmt.Errorf("matching example must have kind composed")
			}
			raw, ok := fragment["composition"]
			if !ok || !strings.HasPrefix(strings.TrimSpace(string(raw)), "{") {
				return nil, fmt.Errorf("matching example requires a composition object")
			}
			matches++
			selected = raw
			continue
		}
		if strings.HasPrefix(text, "```") {
			inFence, jsonFence = true, text == "```json"
			body = nil
			continue
		}
		if text == "## "+docHeading {
			headings++
			inSection = true
		} else if strings.HasPrefix(text, "# ") || strings.HasPrefix(text, "## ") {
			inSection = false
		}
	}
	if inFence && inSection {
		return nil, fmt.Errorf("unterminated fence in composition section")
	}
	if headings != 1 {
		return nil, fmt.Errorf("expected exactly one composition heading, found %d", headings)
	}
	if matches != 1 {
		return nil, fmt.Errorf("expected exactly one matching JSON example, found %d", matches)
	}
	return selected, nil
}

func TestCompositionDocumentationDiscovery(t *testing.T) {
	heading := "## " + docHeading + "\n"
	example := `{"name":"gtm.at_risk_account_enrichment_summary","kind":"composed","composition":{}}`
	fence := func(value string) string { return "```json\n" + value + "\n```\n" }
	valid := heading + fence(example)
	cases := []struct {
		name, document, wantError string
	}{
		{name: "exact section", document: valid},
		{name: "CRLF", document: strings.ReplaceAll(valid, "\n", "\r\n")},
		{name: "unrelated example", document: heading + fence(`{"name":"other"}`) + fence(example)},
		{name: "nested heading", document: heading + "### Example\n" + fence(example)},
		{name: "next section excluded", document: valid + "## Next\n" + fence(example)},
		{name: "fenced heading ignored", document: "```text\n" + heading + "```\n" + valid},
		{name: "missing heading", document: fence(example), wantError: "exactly one composition heading"},
		{name: "heading mentioned in prose", document: "See " + docHeading + "\n" + fence(example), wantError: "exactly one composition heading"},
		{name: "duplicate heading", document: valid + valid, wantError: "exactly one composition heading"},
		{name: "missing fence", document: heading + example, wantError: "exactly one matching JSON example"},
		{name: "wrong fence language", document: heading + "```text\n" + example + "\n```\n", wantError: "exactly one matching JSON example"},
		{name: "duplicate matching examples", document: valid + fence(example), wantError: "exactly one matching JSON example"},
		{name: "missing matching example", document: heading + fence(`{"name":"other"}`), wantError: "exactly one matching JSON example"},
		{name: "malformed JSON", document: heading + fence("{"), wantError: "malformed JSON object"},
		{name: "empty JSON", document: heading + fence(""), wantError: "malformed JSON object"},
		{name: "nonobject JSON", document: heading + fence("null"), wantError: "malformed JSON object"},
		{name: "unterminated fence", document: heading + "```json\n" + example, wantError: "unterminated fence"},
		{name: "example only in next section", document: heading + "No example.\n## Next\n" + fence(example), wantError: "exactly one matching JSON example"},
		{name: "example only after level one heading", document: heading + "# Next\n" + fence(example), wantError: "exactly one matching JSON example"},
		{name: "malformed name", document: heading + fence(`{"name":42}`), wantError: "not a JSON string"},
		{name: "wrong kind", document: heading + fence(strings.Replace(example, "composed", "atomic", 1)), wantError: "kind composed"},
		{name: "missing composition", document: heading + fence(`{"name":"gtm.at_risk_account_enrichment_summary","kind":"composed"}`), wantError: "requires a composition object"},
		{name: "null composition", document: heading + fence(strings.Replace(example, `"composition":{}`, `"composition":null`, 1)), wantError: "requires a composition object"},
		{name: "trailing JSON", document: heading + fence(example+" 42"), wantError: "malformed JSON object"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := extractDocComposition(tc.document)
			if tc.wantError != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantError) {
					t.Fatalf("error = %v, want %q", err, tc.wantError)
				}
				return
			}
			if err != nil || string(got) != "{}" {
				t.Fatalf("composition = %s, error = %v; want unchanged {}", got, err)
			}
		})
	}
}

// docAtomicDecl builds an atomic fixture for a documented child capability.
func docAtomicDecl(name, input string, fields []string) *core.CapabilityDeclaration {
	return &core.CapabilityDeclaration{
		Name:         name,
		Description:  "fixture for " + name,
		Inputs:       []core.CapabilityInput{{Name: input, Type: "string"}},
		Output:       core.CapabilityOutput{Type: "x", Fields: fields},
		SideEffect:   core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope: []string{"gtm"},
		Kind:         core.CapabilityKindAtomic,
	}
}

func docRegistry() map[string]*core.CapabilityDeclaration {
	return map[string]*core.CapabilityDeclaration{
		docRiskCapability:   docAtomicDecl(docRiskCapability, "quarter", []string{"accounts", "generated_at"}),
		docEnrichCapability: docAtomicDecl(docEnrichCapability, "account_set", []string{"accounts"}),
	}
}

func docParentDecl(name string, comp *core.Composition) *core.CapabilityDeclaration {
	return &core.CapabilityDeclaration{
		Name:         name,
		Description:  "documented composed capability",
		Inputs:       []core.CapabilityInput{{Name: "quarter", Type: "string"}},
		Output:       core.CapabilityOutput{Type: "accounts", Fields: []string{"accounts"}},
		SideEffect:   core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope: []string{"gtm"},
		Kind:         core.CapabilityKindComposed,
		Composition:  comp,
	}
}

type docCall struct {
	capability string
	params     map[string]any
}

func docRunner(scripted map[string]map[string]any) (InvokeStepFunc, *[]docCall) {
	calls := &[]docCall{}
	runner := func(capability string, params map[string]any) (map[string]any, error) {
		*calls = append(*calls, docCall{capability: capability, params: params})
		return scripted[capability], nil
	}
	return runner, calls
}

func TestCompositionDocumentationContract(t *testing.T) {
	name, comp := docComposition(t)

	// Structural policy assertions: each documented field is asserted
	// directly so an unknown-field or zero-value decode cannot pass.
	if comp.AuthorityBoundary != core.AuthorityBoundarySameService {
		t.Errorf("authority_boundary = %q, want %q", comp.AuthorityBoundary, core.AuthorityBoundarySameService)
	}
	if len(comp.Steps) != 2 {
		t.Fatalf("steps = %+v, want exactly risk then enrichment", comp.Steps)
	}
	if comp.Steps[0].ID != "risk" || comp.Steps[0].Capability != docRiskCapability {
		t.Errorf("step[0] = %+v, want id risk -> %s", comp.Steps[0], docRiskCapability)
	}
	if !comp.Steps[0].EmptyResultSource || comp.Steps[0].EmptyResultPath != "$.accounts" {
		t.Errorf("risk step empty_result flags = %+v, want source=true path=$.accounts", comp.Steps[0])
	}
	if comp.Steps[1].ID != "enrichment" || comp.Steps[1].Capability != docEnrichCapability {
		t.Errorf("step[1] = %+v, want id enrichment -> %s", comp.Steps[1], docEnrichCapability)
	}
	if comp.Steps[1].EmptyResultSource || comp.Steps[1].EmptyResultPath != "" {
		t.Errorf("enrichment step empty_result flags = %+v, want unset", comp.Steps[1])
	}
	wantInput := map[string]map[string]string{
		"risk":       {"quarter": "$.input.quarter"},
		"enrichment": {"account_set": "$.steps.risk.output.accounts"},
	}
	if !reflect.DeepEqual(comp.InputMapping, wantInput) {
		t.Errorf("input_mapping = %+v, want %+v", comp.InputMapping, wantInput)
	}
	wantOutput := map[string]string{"accounts": "$.steps.enrichment.output.accounts"}
	if !reflect.DeepEqual(comp.OutputMapping, wantOutput) {
		t.Errorf("output_mapping = %+v, want %+v", comp.OutputMapping, wantOutput)
	}
	if comp.EmptyResultPolicy != core.EmptyResultPolicyReturnSuccessNoResults {
		t.Errorf("empty_result_policy = %q, want %q", comp.EmptyResultPolicy, core.EmptyResultPolicyReturnSuccessNoResults)
	}
	if len(comp.EmptyResultOutput) != 1 {
		t.Fatalf("empty_result_output = %+v, want exactly one key: accounts", comp.EmptyResultOutput)
	}
	if accts, ok := comp.EmptyResultOutput["accounts"].([]any); !ok || len(accts) != 0 {
		t.Errorf("empty_result_output[accounts] = %#v, want an empty array", comp.EmptyResultOutput["accounts"])
	}
	if comp.FailurePolicy != (core.FailurePolicy{
		ChildClarification:    core.FailurePolicyOutcomePropagate,
		ChildDenial:           core.FailurePolicyOutcomePropagate,
		ChildApprovalRequired: core.FailurePolicyOutcomePropagate,
		ChildError:            core.FailurePolicyOutcomeFailParent,
	}) {
		t.Errorf("failure_policy = %+v, want SPEC defaults (propagate x3, child_error fail_parent)", comp.FailurePolicy)
	}
	if !comp.AuditPolicy.RecordChildInvocations || !comp.AuditPolicy.ParentTaskLineage {
		t.Errorf("audit_policy = %+v, want record_child_invocations=true parent_task_lineage=true", comp.AuditPolicy)
	}

	// Validate against the declared atomic fixtures.
	decl := docParentDecl(name, &comp)
	if err := ValidateComposition(name, decl, docRegistry()); err != nil {
		t.Fatalf("documented composition failed validation against declared atomic fixtures: %v", err)
	}
}

func TestCompositionDocumentationNonEmpty(t *testing.T) {
	name, comp := docComposition(t)
	riskAccounts := []any{
		map[string]any{"account_id": "a1"},
		map[string]any{"account_id": "a2"},
	}
	// Distinct enrichment accounts: enriched shapes differ from risk output.
	enrichAccounts := []any{
		map[string]any{"account_id": "a1", "risk": "high"},
		map[string]any{"account_id": "a2", "risk": "low"},
	}
	runner, calls := docRunner(map[string]map[string]any{
		docRiskCapability: {
			"success": true,
			"result": map[string]any{
				"accounts":     riskAccounts,
				"generated_at": "2026-01-01T00:00:00Z",
			},
		},
		docEnrichCapability: {
			"success": true,
			"result":  map[string]any{"accounts": enrichAccounts},
		},
	})
	// The unrelated parent input field must not be forwarded to any child.
	input := map[string]any{"quarter": "2026-Q1", "tenant": "unrelated-value"}
	out, err := ExecuteComposition(name, docParentDecl(name, &comp), input, runner)
	if err != nil {
		t.Fatalf("ExecuteComposition: %v", err)
	}
	if len(*calls) != 2 {
		t.Fatalf("expected ordered calls risk then enrichment, got %d: %+v", len(*calls), *calls)
	}
	if (*calls)[0].capability != docRiskCapability || (*calls)[1].capability != docEnrichCapability {
		t.Fatalf("ordered calls = %+v, want risk then enrichment", *calls)
	}
	if want := map[string]any{"quarter": "2026-Q1"}; !reflect.DeepEqual((*calls)[0].params, want) {
		t.Errorf("risk child arguments = %#v, want exactly %#v", (*calls)[0].params, want)
	}
	if want := map[string]any{"account_set": riskAccounts}; !reflect.DeepEqual((*calls)[1].params, want) {
		t.Errorf("enrichment child arguments = %#v, want exactly %#v", (*calls)[1].params, want)
	}
	if want := map[string]any{"accounts": enrichAccounts}; !reflect.DeepEqual(out, want) {
		t.Errorf("output = %#v, want exactly %#v", out, want)
	}
}

func docEmptyOutputCheck(t *testing.T, out map[string]any) {
	t.Helper()
	if len(out) != 1 {
		t.Fatalf("output = %#v, want exactly one key: accounts", out)
	}
	accts, ok := out["accounts"].([]any)
	if !ok || len(accts) != 0 {
		t.Errorf("output accounts = %#v, want the declared empty array", out["accounts"])
	}
}

// docEmptyOnlyRisk runs an empty-account scenario and asserts the risk-only
// short-circuit: one risk call, zero enrichment calls, declared empty output.
func docEmptyOnlyRisk(t *testing.T, accounts any) {
	name, comp := docComposition(t)
	runner, calls := docRunner(map[string]map[string]any{
		docRiskCapability: {
			"success": true,
			"result": map[string]any{
				// Nonempty unrelated field proves only the empty accounts
				// path triggers the short-circuit.
				"accounts":     accounts,
				"generated_at": "2026-01-01T00:00:00Z",
			},
		},
	})
	out, err := ExecuteComposition(name, docParentDecl(name, &comp), map[string]any{"quarter": "2026-Q1"}, runner)
	if err != nil {
		t.Fatalf("ExecuteComposition: %v", err)
	}
	if len(*calls) != 1 || (*calls)[0].capability != docRiskCapability {
		t.Fatalf("expected exactly one risk call, got %+v", *calls)
	}
	if want := map[string]any{"quarter": "2026-Q1"}; !reflect.DeepEqual((*calls)[0].params, want) {
		t.Errorf("risk child arguments = %#v, want exactly %#v", (*calls)[0].params, want)
	}
	docEmptyOutputCheck(t, out)
}

func TestCompositionDocumentationEmpty(t *testing.T) {
	docEmptyOnlyRisk(t, []any{})
}

func TestCompositionDocumentationNull(t *testing.T) {
	docEmptyOnlyRisk(t, nil)
}
