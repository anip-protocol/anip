package generator

import (
	"encoding/json"
	"strings"
)

// The generated policy seam (policy.py, policy.ts, policy.go, Policy.java,
// Policy.cs) fails closed:
//
//  1. A matching deny binding refuses, whatever the capability posture. A
//     binding whose decision the host does not recognise refuses too.
//  2. When a capability has bindings and none matches the actor, the request
//     is refused. A principal without actor claims matches none.
//  3. A capability without bindings is allowed: bindings are sparse
//     capability-level overrides.
//  4. An approval-gated capability stops before the backend adapter runs,
//     unless the runtime validated an approval grant for this invocation.
//
// Among matching bindings, deny wins over approval_required, which wins over
// clarify, which wins over allow and allow_with_limits.
//
// The functions below mirror those templates so the generator can choose the
// principal a generated smoke test invokes as, and the outcome to expect.

var generatedPolicyKnownDecisions = map[string]bool{
	"allow": true, "allow_with_limits": true, "deny": true, "clarify": true, "approval_required": true,
}

func generatedPolicyEffectiveDecision(binding RuntimePolicyBinding) string {
	decision := strings.TrimSpace(binding.Decision)
	if generatedPolicyKnownDecisions[decision] {
		return decision
	}
	return "deny"
}

func generatedPolicyMatches(binding RuntimePolicyBinding, claims map[string]string) bool {
	claim := firstNonEmpty(binding.PrincipalSelector.Claim, "actor_id")
	expected := firstNonEmpty(binding.PrincipalSelector.Equals, binding.ActorID)
	if expected == "" {
		return true
	}
	actual, ok := claims[claim]
	return ok && actual == expected
}

func generatedPrincipalClaims(principal string) map[string]string {
	principal = strings.TrimSpace(principal)
	if principal == "" {
		return map[string]string{}
	}
	pieces := strings.Split(principal, "|")
	claims := map[string]string{"principal": pieces[0]}
	for _, piece := range pieces[1:] {
		key, value, ok := strings.Cut(piece, "=")
		if !ok {
			continue
		}
		claims[strings.TrimSpace(key)] = strings.TrimSpace(value)
	}
	return claims
}

// generatedPolicyDecision returns the decision the generated policy seam makes:
// allow, deny, clarify or approval_required.
func generatedPolicyDecision(bindings []RuntimePolicyBinding, capabilityID string, principal string) string {
	relevant := []RuntimePolicyBinding{}
	for _, binding := range bindings {
		for _, id := range binding.CapabilityIDs {
			if id == capabilityID {
				relevant = append(relevant, binding)
				break
			}
		}
	}
	if len(relevant) == 0 {
		return "allow"
	}
	claims := generatedPrincipalClaims(principal)
	matching := []RuntimePolicyBinding{}
	for _, binding := range relevant {
		if len(claims) > 0 && generatedPolicyMatches(binding, claims) {
			matching = append(matching, binding)
		}
	}
	if len(matching) == 0 {
		return "deny"
	}
	for _, decision := range []string{"deny", "approval_required", "clarify"} {
		for _, binding := range matching {
			if generatedPolicyEffectiveDecision(binding) == decision {
				return decision
			}
		}
	}
	return "allow"
}

func generatedCapabilityRequiresApproval(capability GeneratedCapabilityRuntimeMetadata) bool {
	return capability.SideEffectLevel == "approval_required" ||
		capability.ExecutionPosture == "approval_required" ||
		capability.ExecutionPosture == "approval_gated" ||
		capability.OperationType == "approval_gated"
}

// generatedSmokeInvocation is the principal a generated smoke test invokes a
// capability as, and the outcome the generated host gives it: success,
// approval_required, clarification_required or denied.
type generatedSmokeInvocation struct {
	Principal string
	Expect    string
}

const generatedSmokeDefaultPrincipal = "human:local-developer"

// smokeInvocationFor prefers a principal one of the capability's allow
// bindings selects, so the smoke test reaches the backend where policy lets
// any actor do so.
func smokeInvocationFor(bindings []RuntimePolicyBinding, capability GeneratedCapabilityRuntimeMetadata) generatedSmokeInvocation {
	candidates := []string{generatedSmokeDefaultPrincipal}
	for _, binding := range bindings {
		decision := generatedPolicyEffectiveDecision(binding)
		if decision != "allow" && decision != "allow_with_limits" {
			continue
		}
		claim := firstNonEmpty(binding.PrincipalSelector.Claim, "actor_id")
		expected := firstNonEmpty(binding.PrincipalSelector.Equals, binding.ActorID)
		if expected == "" || strings.ContainsAny(claim+expected, "|=") {
			continue
		}
		for _, id := range binding.CapabilityIDs {
			if id == capability.CapabilityID {
				candidates = append(candidates, "human:smoke-test|"+claim+"="+expected)
				break
			}
		}
	}
	rank := map[string]int{"success": 0, "approval_required": 1, "clarification_required": 2, "denied": 3}
	var best generatedSmokeInvocation
	for index, principal := range candidates {
		outcome := "success"
		switch generatedPolicyDecision(bindings, capability.CapabilityID, principal) {
		case "deny":
			outcome = "denied"
		case "clarify":
			outcome = "clarification_required"
		case "approval_required":
			outcome = "approval_required"
		default:
			if generatedCapabilityRequiresApproval(capability) {
				outcome = "approval_required"
			}
		}
		if index == 0 || rank[outcome] < rank[best.Expect] {
			best = generatedSmokeInvocation{Principal: principal, Expect: outcome}
		}
	}
	return best
}

// smokeAPIKeysJSON is the ANIP_API_KEYS_JSON value a generated smoke test sets
// so its bearer key authenticates as the chosen principal.
func smokeAPIKeysJSON(principal string) string {
	encoded, _ := json.Marshal(map[string]string{"smoke-test-key": principal})
	return string(encoded)
}

// firstCapabilitySmoke is the smoke invocation for the first generated
// capability, the one the TypeScript and Go smoke tests invoke.
func firstCapabilitySmoke(model *GenerationModel) generatedSmokeInvocation {
	if model == nil || len(model.Capabilities) == 0 {
		return generatedSmokeInvocation{Principal: generatedSmokeDefaultPrincipal, Expect: "success"}
	}
	return smokeInvocationFor(model.RuntimeTarget.PolicyBindings, model.Capabilities[0])
}
