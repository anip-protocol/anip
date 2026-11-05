package generator

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

func TestCompositionEmptyResultOutputJSONPresence(t *testing.T) {
	for _, tc := range []struct {
		name    string
		input   string
		present bool
	}{
		{name: "absent", input: `{}`},
		{name: "explicit_empty", input: `{"empty_result_output":{}}`, present: true},
		{
			name:    "populated",
			input:   `{"empty_result_output":{"query":"$.input.query","flag":false,"count":0,"items":[],"nested":{"status":"no_results"}}}`,
			present: true,
		},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var original Composition
			if err := json.Unmarshal([]byte(tc.input), &original); err != nil {
				t.Fatal(err)
			}
			if got := original.EmptyResultOutput != nil; got != tc.present {
				t.Fatalf("decoded output presence = %v, want %v", got, tc.present)
			}
			encoded, err := json.Marshal(original)
			if err != nil {
				t.Fatal(err)
			}
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(encoded, &fields); err != nil {
				t.Fatal(err)
			}
			if _, present := fields["empty_result_output"]; present != tc.present {
				t.Errorf("encoded output presence = %v, want %v: %s", present, tc.present, encoded)
			}
			var roundTrip Composition
			if err := json.Unmarshal(encoded, &roundTrip); err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(roundTrip.EmptyResultOutput, original.EmptyResultOutput) {
				t.Errorf("output changed after JSON round trip: got %#v, want %#v", roundTrip.EmptyResultOutput, original.EmptyResultOutput)
			}
		})
	}
}

func TestGeneratedCompositionEmptyResultOutputPresence(t *testing.T) {
	definition := mustReadGeneratorConformanceDefinition(t, "generator-conformance-definition.json")
	found := false
	for i := range definition.CapabilityFormalizations {
		capability := &definition.CapabilityFormalizations[i]
		if capability.CapabilityID == "conformance.lookup_and_prepare" {
			if capability.Composition == nil {
				t.Fatal("fixture must declare the lookup composition")
			}
			capability.Composition.EmptyResultOutput = map[string]any{}
			found = true
		}
	}
	if !found {
		t.Fatal("missing conformance composition")
	}
	// Inspect generated artifacts only; no target toolchains or providers execute.
	markers := map[string]string{
		"python":     "GENERATED_CAPABILITY_METADATA = json.loads(r'''",
		"typescript": "export const generatedCapabilityMetadata: GeneratedCapabilityRuntimeMetadata[] = ",
		"go":         "const generatedCapabilityMetadataJSON = `",
		"java":       "private static final String CAPABILITY_METADATA_JSON = ",
		"csharp":     "private const string CapabilityMetadataJson = \"\"\"",
	}
	for _, target := range buildGeneratorConformanceProjects(t, definition) {
		t.Run(target.Name, func(t *testing.T) {
			marker, ok := markers[target.Name]
			if !ok {
				t.Fatalf("missing metadata start marker for %s", target.Name)
			}
			_, content, ok := strings.Cut(fileContent(target.Project.Files, target.RuntimePath), marker)
			if !ok {
				t.Fatalf("missing capability metadata in %s", target.RuntimePath)
			}
			if target.Name == "java" {
				// Java embeds JSON as quoted chunks, optionally joined with an empty separator.
				content = strings.TrimPrefix(content, "String.join(")
				var decoded strings.Builder
				for {
					decoder := json.NewDecoder(strings.NewReader(content))
					var chunk string
					if err := decoder.Decode(&chunk); err != nil {
						t.Fatalf("decode Java metadata string: %v", err)
					}
					decoded.WriteString(chunk)
					content = strings.TrimSpace(content[decoder.InputOffset():])
					if !strings.HasPrefix(content, ",") {
						break
					}
					content = strings.TrimPrefix(content, ",")
				}
				content = decoded.String()
			}
			var capabilities []struct {
				CapabilityID string         `json:"capability_id"`
				Composition  map[string]any `json:"composition"`
			}
			// Decode only the first JSON value, leaving target-language suffixes unread.
			if err := json.NewDecoder(strings.NewReader(content)).Decode(&capabilities); err != nil {
				t.Fatalf("decode metadata in %s: %v", target.RuntimePath, err)
			}
			for _, capability := range capabilities {
				if capability.CapabilityID != "conformance.lookup_and_prepare" {
					continue
				}
				output, ok := capability.Composition["empty_result_output"].(map[string]any)
				if !ok || output == nil || len(output) != 0 {
					t.Fatalf("empty_result_output must be an explicit empty object: %#v", capability.Composition)
				}
				return
			}
			t.Fatal("missing conformance composition in generated metadata")
		})
	}
}
