package definitionvalidation

import "testing"

// The runtime executes a composed capability itself and never calls its
// generated handler, so a policy binding on the composed capability would
// never be evaluated. Each child step is checked with the caller's root
// principal; a parent-level rule belongs on the children.
func TestPolicyBindingNamingComposedCapabilityIsRefused(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(definition map[string]any)
		want   string
	}{
		{
			name: "runtime policy binding",
			mutate: func(definition map[string]any) {
				definition["runtime_policy_bindings"] = []any{
					map[string]any{"id": "children-only", "capability_ids": []any{"compat.lookup"}, "decision": "allow"},
					map[string]any{"id": "managers-run-flow", "capability_ids": []any{"compat.lookup", "compat.lookup_and_prepare"}, "decision": "allow"},
				}
			},
			want: `runtime_policy_bindings[1] "managers-run-flow" names composed capability "compat.lookup_and_prepare"; the runtime runs a composition's steps itself and never evaluates a binding on the composed capability, so put the rule on its child capabilities`,
		},
		{
			name: "permission intent binding",
			mutate: func(definition map[string]any) {
				definition["permission_intent_bindings"] = []any{
					map[string]any{"id": "managers-run-flow", "target_capability_ids": []any{"compat.lookup_and_prepare"}},
				}
			},
			want: `permission_intent_bindings[0] "managers-run-flow" names composed capability "compat.lookup_and_prepare"; the runtime runs a composition's steps itself and never evaluates a binding on the composed capability, so put the rule on its child capabilities`,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			definition := loadCompatDefinition(t)
			tc.mutate(definition)
			err := ValidateServiceDefinition(definition)
			if err == nil {
				t.Fatalf("expected a validation error, got none")
			}
			if err.Error() != tc.want {
				t.Fatalf("unexpected diagnostic:\n got: %v\nwant: %s", err, tc.want)
			}
		})
	}
}

func TestPolicyBindingOnChildCapabilitiesIsAccepted(t *testing.T) {
	definition := loadCompatDefinition(t)
	definition["runtime_policy_bindings"] = []any{
		map[string]any{"id": "managers-prepare", "capability_ids": []any{"compat.lookup", "compat.prepare_change"}, "decision": "allow"},
	}
	definition["permission_intent_bindings"] = []any{
		// A binding that targets a whole service reaches its composed
		// capabilities only through their children; it is not refused.
		map[string]any{"id": "service-wide", "target_service_ids": []any{"compat-primary-service"}},
	}
	if err := ValidateServiceDefinition(definition); err != nil {
		t.Fatalf("expected bindings on child capabilities to validate, got: %v", err)
	}
}
