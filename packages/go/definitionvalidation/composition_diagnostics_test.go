package definitionvalidation

import (
	"strings"
	"testing"
)

// Validation stops at the first problem it finds. When a composition contains
// several problems, the one reported must not depend on Go's randomized map
// iteration order: the same definition must always produce the same diagnostic.
func TestCompositionDiagnosticsAreDeterministic(t *testing.T) {
	cases := []struct {
		name   string
		mutate func(composition map[string]any)
		want   string
	}{
		{
			name: "input mapping steps are checked in lexical order",
			mutate: func(composition map[string]any) {
				mapping := composition["input_mapping"].(map[string]any)
				mapping["prepare_change"].(map[string]any)["extra"] = 5
				mapping["lookup"].(map[string]any)["extra"] = 5
			},
			want: `input_mapping["lookup"].extra`,
		},
		{
			name: "inputs within a step are checked in lexical order",
			mutate: func(composition map[string]any) {
				mapping := composition["input_mapping"].(map[string]any)
				lookup := mapping["lookup"].(map[string]any)
				lookup["zz_extra"] = 5
				lookup["aa_extra"] = 5
			},
			want: `input_mapping["lookup"].aa_extra`,
		},
		{
			name: "output mapping fields are checked in lexical order",
			mutate: func(composition map[string]any) {
				mapping := composition["output_mapping"].(map[string]any)
				mapping["zz_field"] = 5
				mapping["aa_field"] = 5
			},
			want: `output_mapping.aa_field`,
		},
	}

	const runs = 100
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			definition := loadCompatDefinition(t)
			tc.mutate(composedCompatCapability(definition)["composition"].(map[string]any))
			for run := 0; run < runs; run++ {
				err := ValidateServiceDefinition(definition)
				if err == nil {
					t.Fatalf("run %d: expected a validation error, got none", run)
				}
				if !strings.Contains(err.Error(), tc.want) {
					t.Fatalf("run %d: expected the diagnostic to name %s, got: %v", run, tc.want, err)
				}
			}
		})
	}
}
