package generator

import (
	"strings"
	"testing"
)

func TestBuildCSharpProject(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildCSharpProject(definition, BuildCSharpProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildCSharpProject: %v", err)
	}

	assertHasFile(t, project.Files, "WorkItemGovernanceService.csproj")
	assertHasFile(t, project.Files, "Program.cs")
	assertHasFile(t, project.Files, "GeneratedRuntimeTarget.cs")
	assertHasFile(t, project.Files, "GeneratedCapabilities.cs")
	assertHasFile(t, project.Files, "tests/WorkItemGovernanceService.Tests.csproj")
	assertHasFile(t, project.Files, "tests/GeneratedCapabilitiesTests.cs")

	projectFile := fileContent(project.Files, "WorkItemGovernanceService.csproj")
	if !strings.Contains(projectFile, `<ProjectReference Include="`) {
		t.Fatalf("csharp project missing local project references")
	}
	if !strings.Contains(projectFile, `Anip.AspNetCore.csproj`) {
		t.Fatalf("csharp project missing ASP.NET ANIP reference")
	}

	runtimeTarget := fileContent(project.Files, "GeneratedRuntimeTarget.cs")
	if !strings.Contains(runtimeTarget, "work_item.prepare_update") {
		t.Fatalf("generated runtime target missing expected capability id")
	}
	if !strings.Contains(runtimeTarget, `"backend_input_mode": "hybrid"`) {
		t.Fatalf("generated runtime target missing hybrid backend input mode")
	}

	program := fileContent(project.Files, "Program.cs")
	for _, expected := range []string{
		"ANIP_API_KEYS_JSON",
		"ANIP_SERVICE_ID",
		"ANIP_SERVICE_FILTER",
		"ASPNETCORE_URLS",
		"ANIP_HTTP_URL",
		"GeneratedCapabilities.CreateAll(BackendAdapter.Default, serviceFilter)",
	} {
		if !strings.Contains(program, expected) {
			t.Fatalf("generated Program.cs missing %q", expected)
		}
	}

	capabilities := fileContent(project.Files, "GeneratedCapabilities.cs")
	for _, expected := range []string{
		"CreateAll(BackendAdapterHandler backendAdapter, string? serviceFilter)",
	} {
		if !strings.Contains(capabilities, expected) {
			t.Fatalf("generated capabilities missing %q", expected)
		}
	}
	if !strings.Contains(capabilities, "AssertRequestedEffectsAllowed(capability, ctx);") {
		t.Fatalf("generated capabilities must deny forbidden requested effects before execution")
	}
	if strings.Index(capabilities, "AssertRequestedEffectsAllowed(capability, ctx);") > strings.Index(capabilities, "parameters = ApplyInputDefaults(capability, parameters);") {
		t.Fatalf("generated capabilities must check requested effects before applying defaults")
	}
	for _, forbidden := range []string{
		"ANIP_OPTIONAL_INPUT_OVERRIDES_JSON",
		"ANIP_COMPOSED_CAPABILITY_BRIDGE",
		"ANIP_BRIDGE_COMPOSED_CAPABILITIES",
	} {
		if strings.Contains(capabilities, forbidden) {
			t.Fatalf("generated capabilities should not expose declaration mutation hook %q", forbidden)
		}
	}
}

func TestBuildCSharpProjectRegistryDependencies(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildCSharpProject(definition, BuildCSharpProjectOptions{
		DependencySource: DependencySourceRegistry,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildCSharpProject: %v", err)
	}

	projectFile := fileContent(project.Files, "WorkItemGovernanceService.csproj")
	for _, expected := range []string{
		`<AnipVersion>0.24.8</AnipVersion>`,
		`<PackageReference Include="Anip.Core" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.Crypto" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.Server" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.Service" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.AspNetCore" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.Rest.AspNetCore" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.GraphQL.AspNetCore" Version="$(AnipVersion)" />`,
		`<PackageReference Include="Anip.Mcp.AspNetCore" Version="$(AnipVersion)" />`,
	} {
		if !strings.Contains(projectFile, expected) {
			t.Fatalf("registry csproj missing %q", expected)
		}
	}
	if strings.Contains(projectFile, "<ProjectReference ") {
		t.Fatalf("registry csproj should not include local project references")
	}

	readme := fileContent(project.Files, "README.md")
	if strings.Contains(readme, "after ANIP .NET packages are published") {
		t.Fatalf("registry readme still describes C# packages as unpublished")
	}
}

func TestBuildCSharpProjectSanitizesVersionLikeSystemName(t *testing.T) {
	definition := mustReadFixtureDefinition(t)
	definition.Identity.SystemName = "GitHub Fronting Showcase 0.2.0 Autopilot UI Gate"

	project, err := BuildCSharpProject(definition, BuildCSharpProjectOptions{
		DependencySource: DependencySourceRegistry,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildCSharpProject: %v", err)
	}

	assertHasFile(t, project.Files, "GitHubFrontingShowcase020AutopilotUIGate.csproj")
	program := fileContent(project.Files, "Program.cs")
	if !strings.Contains(program, "using GitHubFrontingShowcase020AutopilotUIGate;") {
		t.Fatalf("generated Program.cs did not import sanitized root namespace")
	}
	capabilities := fileContent(project.Files, "GeneratedCapabilities.cs")
	if !strings.Contains(capabilities, "namespace GitHubFrontingShowcase020AutopilotUIGate;") {
		t.Fatalf("generated capabilities did not use sanitized root namespace")
	}
}
