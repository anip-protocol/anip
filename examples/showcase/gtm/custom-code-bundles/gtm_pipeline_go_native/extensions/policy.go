package extensions

import "{{ANIP_GO_MODULE_PATH}}/generated"

type PolicyDecision struct {
	Decision   string
	Detail     string
	Resolution map[string]any
}

type PolicyContext struct {
	Capability    generated.GeneratedCapabilityRuntimeMetadata
	Params        map[string]any
	RootPrincipal string
}

func EvaluatePolicy(_ PolicyContext) PolicyDecision {
	return PolicyDecision{
		Decision: "allow",
		Detail:   "GTM Go native bundle evaluates actor and approval behavior in its backend adapter.",
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}
