package generator

import (
	"strings"
	"testing"
)

const expectedReleasedRuntimeVersion = "0.24.12"

func TestGeneratedRegistryDependenciesUseCurrentReleasedRuntimeVersion(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	python, err := BuildPythonProject(definition, BuildPythonProjectOptions{DependencySource: DependencySourceRegistry})
	if err != nil {
		t.Fatalf("BuildPythonProject: %v", err)
	}
	assertContains(t, fileContent(python.Files, "pyproject.toml"), `anip-service==`+expectedReleasedRuntimeVersion)

	typescript, err := BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{DependencySource: DependencySourceRegistry})
	if err != nil {
		t.Fatalf("BuildTypeScriptProject: %v", err)
	}
	assertContains(t, fileContent(typescript.Files, "package.json"), `"@anip-dev/service": "`+expectedReleasedRuntimeVersion+`"`)

	goProject, err := BuildGoProject(definition, BuildGoProjectOptions{DependencySource: DependencySourceRegistry})
	if err != nil {
		t.Fatalf("BuildGoProject: %v", err)
	}
	assertContains(t, fileContent(goProject.Files, "go.mod"), `github.com/anip-protocol/anip/packages/go v`+expectedReleasedRuntimeVersion)

	java, err := BuildJavaProject(definition, BuildJavaProjectOptions{DependencySource: DependencySourceRegistry})
	if err != nil {
		t.Fatalf("BuildJavaProject: %v", err)
	}
	assertContains(t, fileContent(java.Files, "pom.xml"), `<anip.version>`+expectedReleasedRuntimeVersion+`</anip.version>`)

	csharp, err := BuildCSharpProject(definition, BuildCSharpProjectOptions{DependencySource: DependencySourceRegistry})
	if err != nil {
		t.Fatalf("BuildCSharpProject: %v", err)
	}
	assertContains(t, fileContent(csharp.Files, "WorkItemGovernanceService.csproj"), `<AnipVersion>`+expectedReleasedRuntimeVersion+`</AnipVersion>`)
}

func assertContains(t *testing.T, haystack string, needle string) {
	t.Helper()
	if !strings.Contains(haystack, needle) {
		t.Fatalf("missing %q", needle)
	}
}
