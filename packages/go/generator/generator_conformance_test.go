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
