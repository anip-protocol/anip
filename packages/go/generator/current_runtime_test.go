package generator

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func mustReadCurrentRuntimeDefinition(t *testing.T) *AnipServiceDefinition {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "testdata", "current-runtime-service-definition.json"))
	if err != nil {
		t.Fatalf("read current runtime fixture: %v", err)
	}
	definition, err := ParseServiceDefinition(data)
	if err != nil {
		t.Fatalf("parse current runtime fixture: %v", err)
	}
	return definition
}

func TestCurrentRuntimeFixturePreservedAcrossAllTargets(t *testing.T) {
	definition := mustReadCurrentRuntimeDefinition(t)
	cases := []struct {
		name  string
		build func() (*GeneratedProject, error)
	}{
		{
			name: "typescript",
			build: func() (*GeneratedProject, error) {
				return BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{
					DependencySource: DependencySourceLocal,
					HttpRuntime:      HttpRuntimeHono,
					Port:             4100,
				})
			},
		},
		{
			name: "go",
			build: func() (*GeneratedProject, error) {
				return BuildGoProject(definition, BuildGoProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
		},
		{
			name: "python",
			build: func() (*GeneratedProject, error) {
				return BuildPythonProject(definition, BuildPythonProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
		},
		{
			name: "java",
			build: func() (*GeneratedProject, error) {
				return BuildJavaProject(definition, BuildJavaProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
		},
		{
			name: "csharp",
			build: func() (*GeneratedProject, error) {
				return BuildCSharpProject(definition, BuildCSharpProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			project, err := tc.build()
			if err != nil {
				t.Fatalf("build target: %v", err)
			}
			content := generatedProjectContent(project)
			for _, expected := range []string{
				"compat.lookup_and_prepare",
				"same_service",
				"grant_policy",
				"session_bound",
				"compat-secondary-service",
			} {
				if !strings.Contains(content, expected) {
					t.Fatalf("generated %s target does not preserve current runtime field %q", tc.name, expected)
				}
			}
		})
	}
}

func generatedProjectContent(project *GeneratedProject) string {
	var builder strings.Builder
	for _, file := range project.Files {
		builder.WriteString(file.Content)
		builder.WriteByte('\n')
	}
	return builder.String()
}
