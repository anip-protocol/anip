package extensions

import (
	"strings"

	"github.com/anip-protocol/anip/examples/showcase/notion_fronting/generated/language-parity/go/generated"
)

type PolicyDecision struct {
	Decision string
	Detail string
	Resolution map[string]any
}

type PolicyContext struct {
	Capability generated.GeneratedCapabilityRuntimeMetadata
	Params map[string]any
	RootPrincipal string
}

func principalClaims(rootPrincipal string) map[string]string {
	rootPrincipal = strings.TrimSpace(rootPrincipal)
	if rootPrincipal == "" {
		return map[string]string{}
	}
	pieces := strings.Split(rootPrincipal, "|")
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

func containsCapability(binding generated.RuntimePolicyBinding, capabilityID string) bool {
	for _, value := range binding.CapabilityIDs {
		if value == capabilityID {
			return true
		}
	}
	return false
}

func matchesPrincipal(binding generated.RuntimePolicyBinding, claims map[string]string) bool {
	claim := firstNonEmpty(binding.PrincipalSelector.Claim, "actor_id")
	expected := firstNonEmpty(binding.PrincipalSelector.Equals, binding.ActorID)
	if expected == "" {
		return true
	}
	if _, ok := claims[claim]; !ok {
		return false
	}
	return claims[claim] == expected
}

func requiresGovernedStop(capability generated.GeneratedCapabilityRuntimeMetadata) bool {
	return len(capability.GrantPolicy) > 0 || capability.SideEffectLevel == "approval_required" || capability.ExecutionPosture == "approval_required" || capability.OperationType == "approval_gated"
}

func decisionFor(binding generated.RuntimePolicyBinding) PolicyDecision {
	detail := firstNonEmpty(binding.BusinessRule, binding.EnforcementNotes)
	if binding.Decision == "deny" || binding.Decision == "clarify" || binding.Decision == "approval_required" {
		return PolicyDecision{Decision: binding.Decision, Detail: detail}
	}
	return PolicyDecision{Decision: "allow", Detail: detail}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func EvaluatePolicy(context PolicyContext) PolicyDecision {
	bindings := make([]generated.RuntimePolicyBinding, 0)
	for _, binding := range generated.RuntimeTarget.PolicyBindings {
		if containsCapability(binding, context.Capability.CapabilityID) {
			bindings = append(bindings, binding)
		}
	}
	if len(bindings) == 0 {
		return PolicyDecision{Decision: "allow"}
	}
	claims := principalClaims(context.RootPrincipal)
	if len(claims) == 0 {
		return PolicyDecision{Decision: "allow"}
	}
	matching := make([]generated.RuntimePolicyBinding, 0)
	for _, binding := range bindings {
		if !matchesPrincipal(binding, claims) {
			continue
		}
		matching = append(matching, binding)
	}
	if requiresGovernedStop(context.Capability) {
		for _, binding := range matching {
			if binding.Decision == "deny" {
				return decisionFor(binding)
			}
		}
		for _, binding := range matching {
			if binding.Decision == "approval_required" {
				return decisionFor(binding)
			}
		}
		for _, binding := range matching {
			if binding.Decision == "clarify" {
				return decisionFor(binding)
			}
		}
	}
	for _, binding := range matching {
		if binding.Decision != "deny" && binding.Decision != "clarify" && binding.Decision != "approval_required" {
			return decisionFor(binding)
		}
	}
	return PolicyDecision{Decision: "allow", Detail: "No matching runtime policy binding; continuing."}
}
