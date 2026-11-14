package generator

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type generatorConformanceSuite struct {
	SchemaVersion     string                     `json:"schema_version"`
	DefinitionFixture string                     `json:"definition_fixture"`
	Cases             []generatorConformanceCase `json:"cases"`
}

type generatorConformanceCase struct {
	ID             string                              `json:"id"`
	Description    string                              `json:"description"`
	RuntimeMarkers []string                            `json:"runtime_markers"`
	ProjectMarkers []string                            `json:"project_markers"`
	TargetMarkers  map[string][]generatorTargetMarkers `json:"target_markers"`
}

type generatorTargetMarkers struct {
	Path     string   `json:"path"`
	Contains []string `json:"contains"`
}

type generatedTargetProject struct {
	Name        string
	Project     *GeneratedProject
	RuntimePath string
}

func TestGeneratorConformanceSuite(t *testing.T) {
	suite := mustReadGeneratorConformanceSuite(t)
	definition := mustReadGeneratorConformanceDefinition(t, suite.DefinitionFixture)
	projects := buildGeneratorConformanceProjects(t, definition)

	for _, testCase := range suite.Cases {
		t.Run(testCase.ID, func(t *testing.T) {
			if testCase.Description == "" {
				t.Fatalf("conformance case must include a description")
			}
			for _, target := range projects {
				t.Run(target.Name, func(t *testing.T) {
					if len(testCase.RuntimeMarkers) > 0 {
						content := fileContent(target.Project.Files, target.RuntimePath)
						if content == "" {
							t.Fatalf("target %s missing runtime metadata file %s", target.Name, target.RuntimePath)
						}
						assertContainsAll(t, content, testCase.RuntimeMarkers)
					}
					if len(testCase.ProjectMarkers) > 0 {
						assertContainsAll(t, generatedProjectContent(target.Project), testCase.ProjectMarkers)
					}
					for _, marker := range testCase.TargetMarkers[target.Name] {
						content := fileContent(target.Project.Files, marker.Path)
						if content == "" {
							t.Fatalf("target %s missing conformance file %s", target.Name, marker.Path)
						}
						assertContainsAll(t, content, marker.Contains)
					}
				})
			}
		})
	}
}

func TestGeneratorConformanceDeclaresExplicitBackendInput(t *testing.T) {
	definition := backendOnlyConformanceDefinition(t)
	marker := "Required by the backend adapter (explicit backend input)."
	for _, target := range buildGeneratorConformanceProjects(t, definition) {
		// The emitted service definition and the runtime metadata the
		// manifest is built from both declare change_reason.
		for _, path := range []string{"anip-service-definition.json", target.RuntimePath} {
			if !containsGeneratedMarker(fileContent(target.Project.Files, path), marker) {
				t.Fatalf("%s: %s does not declare the explicit backend input", target.Name, path)
			}
		}
	}
}

// withoutPolicyOrApprovalGate removes the fixture's policy bindings and the
// approval gate on conformance.prepare_change, for suites that exercise backend
// inputs and compositions rather than policy. Without bindings every actor is
// allowed (a capability without bindings is allowed), and without the gate the
// child reaches its backend adapter without an approval grant.
func withoutPolicyOrApprovalGate(definition *AnipServiceDefinition) {
	definition.RuntimePolicyBindings = nil
	definition.PermissionIntentBindings = nil
	for i := range definition.CapabilityFormalizations {
		capability := &definition.CapabilityFormalizations[i]
		if capability.CapabilityID == "conformance.prepare_change" {
			capability.OperationType = "write"
			capability.SideEffectLevel = "write"
		}
	}
	if definition.IntegrationFronting == nil {
		return
	}
	for i := range definition.IntegrationFronting.CapabilityMappings {
		mapping := &definition.IntegrationFronting.CapabilityMappings[i]
		if mapping.CapabilityID == "conformance.prepare_change" {
			mapping.ExecutionPosture = "write"
			mapping.SideEffectLevel = "write"
		}
	}
}

// backendOnlyConformanceDefinition leaves change_reason out of the child's
// public inputs while its backend still requires it explicitly. The generator
// declares it, so the generated child accepts it from the caller. The parent
// takes no change_reason: it maps the child's change_reason from the lookup
// step's output, a value the service derives, and parent parameters reach the
// child only through input_mapping.
func backendOnlyConformanceDefinition(t *testing.T) *AnipServiceDefinition {
	t.Helper()
	suite := mustReadGeneratorConformanceSuite(t)
	definition := mustReadGeneratorConformanceDefinition(t, suite.DefinitionFixture)
	withoutChangeReason := func(inputs []CapabilityInputFormalization) []CapabilityInputFormalization {
		var kept []CapabilityInputFormalization
		for _, input := range inputs {
			if input.InputName != "change_reason" {
				kept = append(kept, input)
			}
		}
		return kept
	}
	for i := range definition.CapabilityFormalizations {
		capability := &definition.CapabilityFormalizations[i]
		switch capability.CapabilityID {
		case "conformance.prepare_change":
			capability.Inputs = withoutChangeReason(capability.Inputs)
		case "conformance.lookup_and_prepare":
			capability.Inputs = withoutChangeReason(capability.Inputs)
			capability.Composition.InputMapping["prepare_change"]["change_reason"] = "$.steps.lookup.output.capability_id"
		}
	}
	for i := range definition.IntegrationFronting.CapabilityMappings {
		mapping := &definition.IntegrationFronting.CapabilityMappings[i]
		if mapping.CapabilityID == "conformance.lookup_and_prepare" {
			mapping.ExplicitRequiredBackendInputs = nil
		}
	}
	withoutPolicyOrApprovalGate(definition)
	model, err := BuildGenerationModel(definition)
	if err != nil {
		t.Fatal(err)
	}
	for _, capability := range definition.CapabilityFormalizations {
		for _, input := range capability.Inputs {
			if input.InputName == "change_reason" {
				t.Fatalf("BuildGenerationModel modified the definition it was given: %s", capability.CapabilityID)
			}
		}
	}
	declared := map[string][]string{}
	for _, capability := range model.Capabilities {
		if capability.CapabilityID == "conformance.prepare_change" && (capability.BackendInputMode != "hybrid" || len(capability.ExplicitRequiredBackendInputs) != 1 || capability.ExplicitRequiredBackendInputs[0] != "change_reason") {
			t.Fatalf("child backend requirement was lost: %#v", capability)
		}
		for _, input := range capability.RequiredInputs {
			declared[capability.CapabilityID] = append(declared[capability.CapabilityID], input.InputName)
		}
		for _, input := range capability.OptionalInputs {
			declared[capability.CapabilityID] = append(declared[capability.CapabilityID], input.InputName+"?")
		}
	}
	if got := strings.Join(declared["conformance.prepare_change"], ","); got != "record_ref,new_status,change_reason" {
		t.Fatalf("child must declare its explicit backend input as required: %s", got)
	}
	if got := strings.Join(declared["conformance.lookup_and_prepare"], ","); got != "query,requested_status" {
		t.Fatalf("parent must not declare change_reason: %s", got)
	}
	return definition
}

func mustReadGeneratorConformanceSuite(t *testing.T) generatorConformanceSuite {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", "generator-conformance-cases.json"))
	if err != nil {
		t.Fatalf("read generator conformance cases: %v", err)
	}
	var suite generatorConformanceSuite
	if err := json.Unmarshal(data, &suite); err != nil {
		t.Fatalf("parse generator conformance cases: %v", err)
	}
	if suite.SchemaVersion != "anip-generator-conformance/v0" {
		t.Fatalf("unexpected generator conformance schema %q", suite.SchemaVersion)
	}
	if suite.DefinitionFixture == "" {
		t.Fatalf("generator conformance suite missing definition fixture")
	}
	if len(suite.Cases) == 0 {
		t.Fatalf("generator conformance suite must include at least one case")
	}
	return suite
}

func mustReadGeneratorConformanceDefinition(t *testing.T, fixtureName string) *AnipServiceDefinition {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", fixtureName))
	if err != nil {
		t.Fatalf("read generator conformance definition: %v", err)
	}
	definition, err := ParseServiceDefinition(data)
	if err != nil {
		t.Fatalf("parse generator conformance definition: %v", err)
	}
	return definition
}

func buildGeneratorConformanceProjects(t *testing.T, definition *AnipServiceDefinition) []generatedTargetProject {
	t.Helper()
	targets := []struct {
		name        string
		runtimePath string
		build       func() (*GeneratedProject, error)
	}{
		{
			name:        "python",
			runtimePath: "src/generator_conformance_service/runtime_target.py",
			build: func() (*GeneratedProject, error) {
				return BuildPythonProject(definition, BuildPythonProjectOptions{DependencySource: DependencySourceLocal, Port: 4100})
			},
		},
		{
			name:        "typescript",
			runtimePath: "src/generated/runtime-target.ts",
			build: func() (*GeneratedProject, error) {
				return BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{DependencySource: DependencySourceLocal, HttpRuntime: HttpRuntimeHono, Port: 4100})
			},
		},
		{
			name:        "go",
			runtimePath: "generated/runtime_target.go",
			build: func() (*GeneratedProject, error) {
				return BuildGoProject(definition, BuildGoProjectOptions{DependencySource: DependencySourceLocal, Port: 4100})
			},
		},
		{
			name:        "java",
			runtimePath: "src/main/java/dev/anip/generated/generator_conformance_service/GeneratedRuntimeTarget.java",
			build: func() (*GeneratedProject, error) {
				return BuildJavaProject(definition, BuildJavaProjectOptions{DependencySource: DependencySourceLocal, Port: 4100})
			},
		},
		{
			name:        "csharp",
			runtimePath: "GeneratedRuntimeTarget.cs",
			build: func() (*GeneratedProject, error) {
				return BuildCSharpProject(definition, BuildCSharpProjectOptions{DependencySource: DependencySourceLocal, Port: 4100})
			},
		},
	}

	projects := make([]generatedTargetProject, 0, len(targets))
	for _, target := range targets {
		project, err := target.build()
		if err != nil {
			t.Fatalf("build %s conformance project: %v", target.name, err)
		}
		projects = append(projects, generatedTargetProject{Name: target.name, Project: project, RuntimePath: target.runtimePath})
	}
	return projects
}

func assertContainsAll(t *testing.T, content string, markers []string) {
	t.Helper()
	for _, marker := range markers {
		if !containsGeneratedMarker(content, marker) {
			t.Fatalf("content missing conformance marker %q", marker)
		}
	}
}

func containsGeneratedMarker(content, marker string) bool {
	if strings.Contains(content, marker) {
		return true
	}
	quoted := javaQuoted(marker)
	if len(quoted) >= 2 {
		escapedJavaStringContent := quoted[1 : len(quoted)-1]
		return strings.Contains(content, escapedJavaStringContent)
	}
	return false
}
