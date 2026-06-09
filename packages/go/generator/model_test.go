package generator

import "testing"

func TestEffectiveMinimumScopeIncludesComposedChildScopes(t *testing.T) {
	child := CapabilityFormalization{
		CapabilityID: "example.child",
		MinimumScope: []string{"example.child.read"},
	}
	parent := CapabilityFormalization{
		CapabilityID: "example.parent",
		MinimumScope: []string{"example.parent.run"},
		Composition: &Composition{
			Steps: []CompositionStep{{ID: "lookup", Capability: "example.child"}},
		},
	}

	got := effectiveMinimumScope(parent, map[string]CapabilityFormalization{
		child.CapabilityID:  child,
		parent.CapabilityID: parent,
	})
	want := []string{"example.parent.run", "example.child.read"}
	if len(got) != len(want) {
		t.Fatalf("effectiveMinimumScope() = %#v, want %#v", got, want)
	}
	for index, value := range want {
		if got[index] != value {
			t.Fatalf("effectiveMinimumScope()[%d] = %q, want %q; full=%#v", index, got[index], value, got)
		}
	}
}

func TestSampleValueForInputHonorsDeclaredValidationPattern(t *testing.T) {
	cases := []struct {
		name  string
		input CapabilityInputFormalization
		want  any
	}{
		{
			name: "issue key pattern",
			input: CapabilityInputFormalization{
				InputName:         "issue_key",
				InputType:         "string",
				ValidationPattern: `^[A-Za-z][A-Za-z0-9_.-]*-[0-9]+$`,
			},
			want: "PROJECT-123",
		},
		{
			name: "project key pattern",
			input: CapabilityInputFormalization{
				InputName:         "project_key",
				InputType:         "string",
				ValidationPattern: `^[A-Za-z][A-Za-z0-9_.-]*$`,
			},
			want: "PROJECT",
		},
		{
			name: "positive integer pattern",
			input: CapabilityInputFormalization{
				InputName:         "limit",
				InputType:         "integer",
				ValidationPattern: `^[1-9][0-9]*$`,
			},
			want: 25,
		},
		{
			name: "business quarter format",
			input: CapabilityInputFormalization{
				InputName:   "quarter",
				InputType:   "string",
				InputFormat: "business_quarter",
			},
			want: "2026-Q2",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := sampleValueForInput(tc.input); got != tc.want {
				t.Fatalf("sampleValueForInput() = %#v, want %#v", got, tc.want)
			}
		})
	}
}
