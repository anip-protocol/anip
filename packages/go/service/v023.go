// v0.23 — Capability composition and approval grants runtime.
//
// This file is the canonical Go translation of `anip_service.v023` (Python)
// and `@anip-dev/service` v023.ts. The wire-format primitives — canonical
// JSON, SHA-256 digests, detached JWS over canonical payload — match the
// other runtimes byte-for-byte so that a grant signed by Python verifies
// here and vice versa.
//
// See SPEC.md §4.6, §4.7, §4.8, §4.9.

package service

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/crypto"
	"github.com/anip-protocol/anip/packages/go/server"
)

// --- v0.23 failure types ---

// Canonical v0.23 failure types. Mirrors `FAILURE_*` constants in
// anip_service.v023 (Python) and v023.ts (TypeScript).
const (
	FailureGrantNotFound              = "grant_not_found"
	FailureGrantExpired               = "grant_expired"
	FailureGrantConsumed              = "grant_consumed"
	FailureGrantCapabilityMismatch    = "grant_capability_mismatch"
	FailureGrantScopeMismatch         = "grant_scope_mismatch"
	FailureGrantParamDrift            = "grant_param_drift"
	FailureGrantSessionInvalid        = "grant_session_invalid"
	FailureApprovalRequestNotFound    = "approval_request_not_found"
	FailureApprovalRequestAlreadyDone = "approval_request_already_decided"
	FailureApprovalRequestExpired     = "approval_request_expired"
	FailureApproverNotAuthorized      = "approver_not_authorized"
	FailureGrantTypeNotAllowed        = "grant_type_not_allowed_by_policy"
	FailureCompositionChildFailed     = "composition_child_failed"
	FailureCompositionInvalidStep     = "composition_invalid_step"
	FailureCompositionUnknownCap      = "composition_unknown_capability"
	FailureCompositionUnsupported     = "composition_unsupported_authority_boundary"
	FailureCompositionEmptyClarify    = "composition_empty_result_clarification_required"
	FailureCompositionEmptyDeny       = "composition_empty_result_denied"
	FailureApprovalRequired           = "approval_required"
)

// --- ID + time helpers ---

// NewApprovalRequestID returns "apr_<12 hex chars>".
func NewApprovalRequestID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return "apr_" + hex.EncodeToString(b)
}

// NewGrantID returns "grant_<12 hex chars>".
func NewGrantID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return "grant_" + hex.EncodeToString(b)
}

// utcNowISO returns now() in RFC 3339 nano UTC. Match other runtimes'
// canonical "isoformat" that supports lexicographic comparison.
func utcNowISO() string {
	return time.Now().UTC().Format(time.RFC3339Nano)
}

// utcInISO returns "now + n seconds" in the same ISO format.
func utcInISO(seconds int) string {
	return time.Now().UTC().Add(time.Duration(seconds) * time.Second).Format(time.RFC3339Nano)
}

// --- Canonical JSON + digest ---

// CanonicalJSON serializes value with recursively sorted keys, no whitespace,
// no trailing whitespace. Matches Python's
// `json.dumps(value, sort_keys=True, separators=(",", ":"))` byte-for-byte
// and the TypeScript canonicalJson implementation.
//
// IMPORTANT: byte-compatibility across runtimes is load-bearing — grants
// signed in Python or TS must verify here and vice versa.
func CanonicalJSON(value any) ([]byte, error) {
	// Round-trip through encoding/json to normalize types (e.g. struct → map).
	raw, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		return nil, err
	}
	var buf strings.Builder
	if err := canonicalEncode(&buf, v); err != nil {
		return nil, err
	}
	return []byte(buf.String()), nil
}

func canonicalEncode(buf *strings.Builder, v any) error {
	switch x := v.(type) {
	case nil:
		buf.WriteString("null")
		return nil
	case bool:
		if x {
			buf.WriteString("true")
		} else {
			buf.WriteString("false")
		}
		return nil
	case string:
		b, err := json.Marshal(x)
		if err != nil {
			return err
		}
		buf.Write(b)
		return nil
	case float64:
		// json.Number-style: encoder emits "1" for integer floats.
		b, err := json.Marshal(x)
		if err != nil {
			return err
		}
		buf.Write(b)
		return nil
	case json.Number:
		buf.WriteString(string(x))
		return nil
	case []any:
		buf.WriteByte('[')
		for i, item := range x {
			if i > 0 {
				buf.WriteByte(',')
			}
			if err := canonicalEncode(buf, item); err != nil {
				return err
			}
		}
		buf.WriteByte(']')
		return nil
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		buf.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				buf.WriteByte(',')
			}
			kb, _ := json.Marshal(k)
			buf.Write(kb)
			buf.WriteByte(':')
			if err := canonicalEncode(buf, x[k]); err != nil {
				return err
			}
		}
		buf.WriteByte('}')
		return nil
	default:
		// Fallback: rely on encoding/json. Should not occur after the
		// Marshal/Unmarshal normalization above.
		b, err := json.Marshal(x)
		if err != nil {
			return err
		}
		buf.Write(b)
		return nil
	}
}

// Sha256Digest returns sha256:<hex> over the canonical JSON of value.
// Used for ApprovalRequest preview_digest, requested_parameters_digest,
// and the grant payload during signing.
func Sha256Digest(value any) (string, error) {
	canon, err := CanonicalJSON(value)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(canon)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

// --- Composition validation ---

// CompositionValidationError is raised when a composed capability
// declaration violates a v0.23 invariant.
type CompositionValidationError struct {
	Message string
}

func (e *CompositionValidationError) Error() string { return e.Message }

func newCompErr(format string, args ...any) error {
	return &CompositionValidationError{Message: fmt.Sprintf(format, args...)}
}

var (
	jsonpathInputRE = regexp.MustCompile(`^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$`)
	jsonpathStepRE  = regexp.MustCompile(`^\$\.steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$`)
)

// parseStepRef returns the step id referenced by a JSONPath, or "" if it
// matches the $.input.* form. A malformed path returns an error.
func parseStepRef(path string) (string, error) {
	if jsonpathInputRE.MatchString(path) {
		return "", nil
	}
	m := jsonpathStepRE.FindStringSubmatch(path)
	if m == nil {
		return "", newCompErr("composition_invalid_step: malformed JSONPath %q (must be $.input.* or $.steps.<id>.output.*)", path)
	}
	return m[1], nil
}

// ValidateComposition enforces the SPEC.md §4.6 invariants on a composed
// capability declaration. No-op for kind != "composed".
func ValidateComposition(parentName string, decl *core.CapabilityDeclaration, registry map[string]*core.CapabilityDeclaration) error {
	if decl.Kind != core.CapabilityKindComposed {
		return nil
	}
	comp := decl.Composition
	if comp == nil {
		return newCompErr("composition_invalid_step: capability %q declares kind='composed' but composition is missing", parentName)
	}
	if comp.AuthorityBoundary != core.AuthorityBoundarySameService {
		return newCompErr("composition_unsupported_authority_boundary: %q is reserved in v0.23", comp.AuthorityBoundary)
	}
	if len(comp.Steps) == 0 {
		return newCompErr("composition_invalid_step: composition has no steps")
	}

	// Step IDs must be unique.
	stepIndex := make(map[string]int, len(comp.Steps))
	for i, st := range comp.Steps {
		if _, dup := stepIndex[st.ID]; dup {
			return newCompErr("composition_invalid_step: duplicate step ids in composition")
		}
		stepIndex[st.ID] = i
	}

	// At most one empty_result_source.
	var sourceStep *core.CompositionStep
	for i := range comp.Steps {
		if comp.Steps[i].EmptyResultSource {
			if sourceStep != nil {
				return newCompErr("composition_invalid_step: at most one step may have empty_result_source=true")
			}
			sourceStep = &comp.Steps[i]
		}
	}

	// Step capabilities resolve and are kind=atomic.
	for _, step := range comp.Steps {
		if step.Capability == parentName {
			return newCompErr("composition_invalid_step: step %q self-references parent capability", step.ID)
		}
		target, ok := registry[step.Capability]
		if !ok {
			return newCompErr("composition_unknown_capability: step %q references unknown capability %q", step.ID, step.Capability)
		}
		// kind defaults to "atomic" when empty.
		kind := target.Kind
		if kind == "" {
			kind = core.CapabilityKindAtomic
		}
		if kind != core.CapabilityKindAtomic {
			return newCompErr("composition_invalid_step: step %q references %q which is kind=%q; composed capabilities may only call kind='atomic' steps in v0.23", step.ID, step.Capability, kind)
		}
	}

	// input_mapping references must resolve and be forward-only.
	for stepKey, mapping := range comp.InputMapping {
		stepPos, ok := stepIndex[stepKey]
		if !ok {
			return newCompErr("composition_invalid_step: input_mapping key %q is not a declared step id", stepKey)
		}
		for param, jp := range mapping {
			ref, err := parseStepRef(jp)
			if err != nil {
				return err
			}
			if ref == "" {
				continue
			}
			refPos, ok := stepIndex[ref]
			if !ok {
				return newCompErr("composition_invalid_step: input_mapping[%q].%s references unknown step %q", stepKey, param, ref)
			}
			if refPos >= stepPos {
				return newCompErr("composition_invalid_step: input_mapping[%q].%s forward-references %q (forward-only references required)", stepKey, param, ref)
			}
		}
	}

	// output_mapping references must resolve.
	for field, jp := range comp.OutputMapping {
		ref, err := parseStepRef(jp)
		if err != nil {
			return err
		}
		if ref == "" {
			continue
		}
		if _, ok := stepIndex[ref]; !ok {
			return newCompErr("composition_invalid_step: output_mapping[%q] references unknown step %q", field, ref)
		}
	}

	// empty_result_source step requires composition-level empty_result_policy.
	if sourceStep != nil && comp.EmptyResultPolicy == "" {
		return newCompErr("composition_invalid_step: step has empty_result_source=true but composition has no empty_result_policy")
	}

	switch comp.EmptyResultPolicy {
	case core.EmptyResultPolicyReturnSuccessNoResults:
		if comp.EmptyResultOutput == nil {
			return newCompErr("composition_invalid_step: empty_result_policy='return_success_no_results' requires empty_result_output")
		}
		if sourceStep == nil {
			return newCompErr("composition_invalid_step: empty_result_output requires a step with empty_result_source=true")
		}
		for field, value := range comp.EmptyResultOutput {
			if str, ok := value.(string); ok && strings.HasPrefix(str, "$") {
				ref, err := parseStepRef(str)
				if err != nil {
					return err
				}
				if ref != "" && ref != sourceStep.ID {
					return newCompErr("composition_invalid_step: empty_result_output[%q] references step %q but only the empty_result_source step %q (or $.input.*) is allowed", field, ref, sourceStep.ID)
				}
			}
		}
	case core.EmptyResultPolicyClarify, core.EmptyResultPolicyDeny:
		if comp.EmptyResultOutput != nil {
			return newCompErr("composition_invalid_step: empty_result_output is forbidden when empty_result_policy=%q", comp.EmptyResultPolicy)
		}
	}

	return nil
}

// --- Composition execution ---

// InvokeStepFunc is supplied by the runtime: invokes a child capability with
// the parent's authority/audit lineage and returns the child's full
// invocation response (the same map shape Service.Invoke returns).
type InvokeStepFunc func(capability string, params map[string]any) (map[string]any, error)

// ExecuteComposition runs a composed capability's steps and returns the
// parent response body. v0.23 §4.6.
func ExecuteComposition(
	parentName string,
	decl *core.CapabilityDeclaration,
	parentInput map[string]any,
	invokeStep InvokeStepFunc,
) (map[string]any, error) {
	comp := decl.Composition
	if comp == nil {
		return nil, fmt.Errorf("capability %q has no composition", parentName)
	}
	var sourceStep *core.CompositionStep
	for i := range comp.Steps {
		if comp.Steps[i].EmptyResultSource {
			sourceStep = &comp.Steps[i]
			break
		}
	}

	stepOutputs := make(map[string]map[string]any, len(comp.Steps))
	for _, step := range comp.Steps {
		mapping := comp.InputMapping[step.ID]
		stepInput := make(map[string]any, len(mapping))
		for param, jp := range mapping {
			val, err := resolveJsonPath(jp, parentInput, stepOutputs)
			if err != nil {
				stepInput[param] = nil
			} else {
				stepInput[param] = val
			}
		}

		result, err := invokeStep(step.Capability, stepInput)
		if err != nil {
			return nil, err
		}
		success, _ := result["success"].(bool)
		if !success {
			failure, _ := result["failure"].(map[string]any)
			failureType, _ := failure["type"].(string)
			outcome := failureOutcomeFor(failureType, comp.FailurePolicy)
			detail, _ := failure["detail"].(string)
			if outcome == core.FailurePolicyOutcomeFailParent {
				// Collapse to composition_child_failed; capture the child
				// failure in detail for diagnostics.
				return nil, core.NewANIPError(
					FailureCompositionChildFailed,
					fmt.Sprintf("child step %q (%s) failed with %s: %s", step.ID, step.Capability, failureType, detail),
				).WithResolution("contact_service_owner")
			}
			// Propagate (default): forward the child's failure type.
			cerr := core.NewANIPError(failureType, detail)
			if approval, ok := failure["approval_required"].(map[string]any); ok && approval != nil {
				// Re-attach approval_required metadata into the propagated error.
				meta, ok := approvalMetadataFromMap(approval)
				if ok {
					cerr.ApprovalRequired = meta
				}
			}
			return nil, cerr
		}

		out, _ := result["result"].(map[string]any)
		if out == nil {
			out = map[string]any{}
		}
		stepOutputs[step.ID] = out

		if sourceStep != nil && step.ID == sourceStep.ID && isEmptyForStep(&step, out) {
			return buildEmptyResultResponse(comp, parentInput, out)
		}
	}

	return buildOutput(comp.OutputMapping, parentInput, stepOutputs), nil
}

func failureOutcomeFor(failureType string, policy core.FailurePolicy) string {
	switch failureType {
	case FailureApprovalRequired:
		return policy.ChildApprovalRequired
	case core.FailureScopeInsufficient, "denied", core.FailureNonDelegableAction:
		return policy.ChildDenial
	case core.FailureBindingMissing, core.FailureBindingStale,
		core.FailureControlRequirementUnsatisfied,
		core.FailurePurposeMismatch, core.FailureInvalidParameters:
		return policy.ChildClarification
	default:
		return policy.ChildError
	}
}

func resolveJsonPath(path string, parentInput map[string]any, stepOutputs map[string]map[string]any) (any, error) {
	if jsonpathInputRE.MatchString(path) {
		keys := strings.Split(path, ".")[2:]
		var cur any = parentInput
		for _, k := range keys {
			m, ok := cur.(map[string]any)
			if !ok {
				return nil, fmt.Errorf("not an object at %q", path)
			}
			v, exists := m[k]
			if !exists {
				return nil, fmt.Errorf("missing key %q at %q", k, path)
			}
			cur = v
		}
		return cur, nil
	}
	m := jsonpathStepRE.FindStringSubmatch(path)
	if m == nil {
		return nil, fmt.Errorf("malformed JSONPath %q", path)
	}
	step := m[1]
	out, ok := stepOutputs[step]
	if !ok {
		return nil, fmt.Errorf("step %q has no output", step)
	}
	keys := strings.Split(path, ".")[4:]
	var cur any = out
	for _, k := range keys {
		mm, ok := cur.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("not an object at %q", path)
		}
		v, exists := mm[k]
		if !exists {
			return nil, fmt.Errorf("missing key %q at %q", k, path)
		}
		cur = v
	}
	return cur, nil
}

func isEmptyValue(v any) bool {
	if v == nil {
		return true
	}
	switch x := v.(type) {
	case []any:
		return len(x) == 0
	case map[string]any:
		return len(x) == 0
	case string:
		return len(x) == 0
	}
	return false
}

func isEmptyForStep(step *core.CompositionStep, output map[string]any) bool {
	if len(output) == 0 {
		return true
	}
	if step.EmptyResultPath != "" {
		keys := strings.Split(step.EmptyResultPath, ".")
		// Drop $ and empty fragments — empty_result_path is scoped to the
		// step's output, so the leading $ is optional.
		filtered := keys[:0]
		for _, k := range keys {
			if k != "" && k != "$" {
				filtered = append(filtered, k)
			}
		}
		var cur any = output
		for _, k := range filtered {
			m, ok := cur.(map[string]any)
			if !ok {
				return true
			}
			v, exists := m[k]
			if !exists {
				return true
			}
			cur = v
		}
		return isEmptyValue(cur)
	}
	for _, v := range output {
		if arr, ok := v.([]any); ok {
			return len(arr) == 0
		}
	}
	for _, v := range output {
		if !isEmptyValue(v) {
			return false
		}
	}
	return true
}

func buildOutput(mapping map[string]string, parentInput map[string]any, stepOutputs map[string]map[string]any) map[string]any {
	out := make(map[string]any, len(mapping))
	for field, jp := range mapping {
		v, err := resolveJsonPath(jp, parentInput, stepOutputs)
		if err != nil {
			out[field] = nil
		} else {
			out[field] = v
		}
	}
	return out
}

func buildEmptyResultResponse(comp *core.Composition, parentInput map[string]any, sourceOutput map[string]any) (map[string]any, error) {
	switch comp.EmptyResultPolicy {
	case core.EmptyResultPolicyClarify:
		return nil, core.NewANIPError(FailureCompositionEmptyClarify,
			"selection step returned no results; clarification required")
	case core.EmptyResultPolicyDeny:
		return nil, core.NewANIPError(FailureCompositionEmptyDeny,
			"selection step returned no results; policy denies an empty answer")
	}
	out := make(map[string]any, len(comp.EmptyResultOutput))
	for field, value := range comp.EmptyResultOutput {
		if str, ok := value.(string); ok && strings.HasPrefix(str, "$") {
			v, err := resolveEmptyRef(str, parentInput, sourceOutput)
			if err != nil {
				out[field] = nil
			} else {
				out[field] = v
			}
		} else {
			out[field] = value
		}
	}
	return out, nil
}

func resolveEmptyRef(path string, parentInput map[string]any, sourceOutput map[string]any) (any, error) {
	if jsonpathInputRE.MatchString(path) {
		keys := strings.Split(path, ".")[2:]
		var cur any = parentInput
		for _, k := range keys {
			m, ok := cur.(map[string]any)
			if !ok {
				return nil, fmt.Errorf("not an object at %q", path)
			}
			cur = m[k]
		}
		return cur, nil
	}
	m := jsonpathStepRE.FindStringSubmatch(path)
	if m == nil {
		return nil, fmt.Errorf("malformed JSONPath %q", path)
	}
	keys := strings.Split(path, ".")[4:]
	var cur any = sourceOutput
	for _, k := range keys {
		mm, ok := cur.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("not an object at %q", path)
		}
		cur = mm[k]
	}
	return cur, nil
}

// --- Approval grant signing/verification ---

// SignGrant produces the detached JWS signature over the canonical JSON of
// the grant excluding `signature` and `use_count`. v0.23 §4.8.
func SignGrant(km *crypto.KeyManager, grant *core.ApprovalGrant) (string, error) {
	payload, err := grantSigningPayload(grant)
	if err != nil {
		return "", err
	}
	return crypto.SignDetachedJWS(km, payload)
}

// VerifyGrantSignature verifies the grant's detached JWS over the same
// canonical payload SignGrant produces. Returns nil if valid.
func VerifyGrantSignature(km *crypto.KeyManager, grant *core.ApprovalGrant) error {
	payload, err := grantSigningPayload(grant)
	if err != nil {
		return err
	}
	return crypto.VerifyDetachedJWS(km, payload, grant.Signature)
}

// grantSigningPayload builds the canonical JSON byte slice the signature
// covers: every grant field except "signature" and "use_count".
func grantSigningPayload(grant *core.ApprovalGrant) ([]byte, error) {
	raw, err := json.Marshal(grant)
	if err != nil {
		return nil, err
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil, err
	}
	delete(m, "signature")
	delete(m, "use_count")
	return CanonicalJSON(m)
}

// GrantScopeSubsetOfToken enforces SPEC.md §4.8 'Scope Subset Rule':
// every grant scope element must appear in the token's scope.
func GrantScopeSubsetOfToken(grantScope, tokenScope []string) bool {
	tokenSet := make(map[string]struct{}, len(tokenScope))
	for _, s := range tokenScope {
		tokenSet[s] = struct{}{}
	}
	for _, s := range grantScope {
		if _, ok := tokenSet[s]; !ok {
			return false
		}
	}
	return true
}

// --- ApprovalRequest materialization ---

// MaterializeApprovalRequest persists a fresh ApprovalRequest and returns
// the metadata to attach to the approval_required failure response.
//
// Per SPEC.md §4.7: storage failures must propagate; the caller is
// responsible for downgrading to service_unavailable.
func MaterializeApprovalRequest(
	storage server.Storage,
	decl *core.CapabilityDeclaration,
	parentInvocationID string,
	requester map[string]any,
	parameters map[string]any,
	preview map[string]any,
	serviceDefaultGrantPolicy *core.GrantPolicy,
) (*core.ApprovalRequiredMetadata, *core.ApprovalRequest, error) {
	var gp core.GrantPolicy
	switch {
	case decl.GrantPolicy != nil:
		gp = *decl.GrantPolicy
	case serviceDefaultGrantPolicy != nil:
		gp = *serviceDefaultGrantPolicy
	default:
		return nil, nil, fmt.Errorf(
			"capability %q raised approval_required but has no grant_policy declared and no service-level default exists",
			decl.Name,
		)
	}

	previewDigest, err := Sha256Digest(preview)
	if err != nil {
		return nil, nil, err
	}
	paramsDigest, err := Sha256Digest(parameters)
	if err != nil {
		return nil, nil, err
	}

	req := &core.ApprovalRequest{
		ApprovalRequestID:         NewApprovalRequestID(),
		Capability:                decl.Name,
		Scope:                     append([]string(nil), decl.MinimumScope...),
		Requester:                 requester,
		ParentInvocationID:        parentInvocationID,
		Preview:                   preview,
		PreviewDigest:             previewDigest,
		RequestedParameters:       parameters,
		RequestedParametersDigest: paramsDigest,
		GrantPolicy:               gp,
		Status:                    core.ApprovalRequestStatusPending,
		CreatedAt:                 utcNowISO(),
		ExpiresAt:                 utcInISO(gp.ExpiresInSeconds),
	}
	if err := storage.StoreApprovalRequest(req); err != nil {
		return nil, nil, err
	}
	return &core.ApprovalRequiredMetadata{
		ApprovalRequestID:         req.ApprovalRequestID,
		PreviewDigest:             req.PreviewDigest,
		RequestedParametersDigest: req.RequestedParametersDigest,
		GrantPolicy:               gp,
	}, req, nil
}

// approvalMetadataFromMap rebuilds an ApprovalRequiredMetadata from a
// JSON-shaped map (used when propagating a child failure that already
// carries an approval_required block).
func approvalMetadataFromMap(m map[string]any) (*core.ApprovalRequiredMetadata, bool) {
	raw, err := json.Marshal(m)
	if err != nil {
		return nil, false
	}
	var meta core.ApprovalRequiredMetadata
	if err := json.Unmarshal(raw, &meta); err != nil {
		return nil, false
	}
	if meta.ApprovalRequestID == "" {
		return nil, false
	}
	return &meta, true
}

// --- Continuation grant validation (Phase A) ---

// ValidateContinuationGrant performs the read-side validation of an
// ApprovalGrant submitted with an invoke. Returns ("", true) on success or
// (failureType, false) on rejection. The atomic reservation is the
// caller's responsibility (see Storage.TryReserveGrant — Phase B).
//
// SPEC.md §4.8: tokenSessionID for session_bound grants MUST come from the
// signed delegation token, never from caller-supplied input.
func ValidateContinuationGrant(
	storage server.Storage,
	km *crypto.KeyManager,
	grantID string,
	capability string,
	parameters map[string]any,
	tokenScope []string,
	tokenSessionID string,
	nowISO string,
) (*core.ApprovalGrant, string) {
	grant, err := storage.GetGrant(grantID)
	if err != nil || grant == nil {
		return nil, FailureGrantNotFound
	}
	if err := VerifyGrantSignature(km, grant); err != nil {
		// Don't leak existence — surface as not_found.
		return nil, FailureGrantNotFound
	}
	if grant.ExpiresAt <= nowISO {
		return nil, FailureGrantExpired
	}
	if grant.Capability != capability {
		return nil, FailureGrantCapabilityMismatch
	}
	if !GrantScopeSubsetOfToken(grant.Scope, tokenScope) {
		return nil, FailureGrantScopeMismatch
	}
	submittedDigest, err := Sha256Digest(parameters)
	if err != nil {
		return nil, FailureGrantParamDrift
	}
	if submittedDigest != grant.ApprovedParametersDigest {
		return nil, FailureGrantParamDrift
	}
	if grant.GrantType == core.GrantTypeSessionBound {
		if tokenSessionID == "" || tokenSessionID != grant.SessionID {
			return nil, FailureGrantSessionInvalid
		}
	}
	return grant, ""
}
