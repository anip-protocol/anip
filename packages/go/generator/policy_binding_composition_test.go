package generator

import "testing"

// The runtime runs a composition's steps itself and never evaluates a policy
// binding on the composed capability, so the generator refuses a definition
// whose bindings name one instead of emitting a rule that would be ignored.
func TestGenerationRefusesPolicyBindingOnComposedCapability(t *testing.T) {
	const suffix = `; the runtime runs a composition's steps itself and never evaluates a binding on the composed capability, so put the rule on its child capabilities`
	cases := []struct {
		name   string
		mutate func(definition *AnipServiceDefinition)
		want   string
	}{
		{
			name: "runtime policy binding",
			mutate: func(definition *AnipServiceDefinition) {
				definition.RuntimePolicyBindings = append(definition.RuntimePolicyBindings, RuntimePolicyBinding{
					ID:                "manager-runs-flow",
					ActorID:           "manager",
					PrincipalSelector: PrincipalSelector{Claim: "actor_id", Equals: "manager"},
					CapabilityIDs:     []string{"conformance.lookup", "conformance.lookup_and_prepare"},
					Decision:          "allow",
				})
			},
			want: `runtime_policy_bindings[9] "manager-runs-flow" names composed capability "conformance.lookup_and_prepare"` + suffix,
		},
		{
			name: "permission intent binding",
			mutate: func(definition *AnipServiceDefinition) {
				definition.RuntimePolicyBindings = nil
				definition.PermissionIntentBindings = []PermissionIntentBinding{
					{ID: "manager-reads", ActorID: "manager", TargetCapabilityIDs: []string{"conformance.lookup"}},
					{ID: "manager-runs-flow", ActorID: "manager", TargetCapabilityIDs: []string{"conformance.lookup_and_prepare"}},
				}
			},
			want: `permission_intent_bindings[1] "manager-runs-flow" names composed capability "conformance.lookup_and_prepare"` + suffix,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			definition := mustReadGeneratorConformanceDefinition(t, "generator-conformance-definition.json")
			if got := len(definition.RuntimePolicyBindings); got != 9 && tc.name == "runtime policy binding" {
				t.Fatalf("fixture has %d runtime policy bindings; update the expected index", got)
			}
			tc.mutate(definition)
			model, err := BuildGenerationModel(definition)
			if err == nil {
				t.Fatalf("expected generation to be refused, got a model with %d bindings", len(model.RuntimeTarget.PolicyBindings))
			}
			if err.Error() != tc.want {
				t.Fatalf("unexpected diagnostic:\n got: %v\nwant: %s", err, tc.want)
			}
		})
	}
}

func TestGenerationAcceptsPolicyBindingsOnChildCapabilities(t *testing.T) {
	definition := mustReadGeneratorConformanceDefinition(t, "generator-conformance-definition.json")
	model, err := BuildGenerationModel(definition)
	if err != nil {
		t.Fatalf("conformance fixture should generate: %v", err)
	}
	for _, binding := range model.RuntimeTarget.PolicyBindings {
		for _, capabilityID := range binding.CapabilityIDs {
			if capabilityID == "conformance.lookup_and_prepare" {
				t.Fatalf("binding %q names the composed capability", binding.ID)
			}
		}
	}

	// A permission intent that targets a whole service reaches the composed
	// capability only through its children, so it is not refused.
	definition.RuntimePolicyBindings = nil
	definition.PermissionIntentBindings = []PermissionIntentBinding{
		{ID: "service-wide", ActorID: "manager", TargetServiceIDs: []string{"generator-conformance-service"}},
	}
	if _, err := BuildGenerationModel(definition); err != nil {
		t.Fatalf("service-wide permission intent should generate: %v", err)
	}
}
