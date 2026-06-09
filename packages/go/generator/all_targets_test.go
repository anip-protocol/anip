package generator

import (
	"strings"
	"testing"
)

func TestAllTargetsUseSharedFixtureModel(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	cases := []struct {
		name              string
		build             func() (*GeneratedProject, error)
		entrypoint        string
		runtimeMetadata   string
		capabilitiesFile  string
		adapterCallMarker string
		policyFile        string
		expectedFileCount int
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
			entrypoint:        "src/main.ts",
			runtimeMetadata:   "src/generated/runtime-target.ts",
			capabilitiesFile:  "src/generated/capabilities.ts",
			adapterCallMarker: "backendAdapter.execute(capability, plan, plan.adapter_input, {",
			policyFile:        "src/runtime/policy.ts",
			expectedFileCount: 19,
		},
		{
			name: "go",
			build: func() (*GeneratedProject, error) {
				return BuildGoProject(definition, BuildGoProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
			entrypoint:        "main.go",
			runtimeMetadata:   "generated/runtime_target.go",
			capabilitiesFile:  "host/capabilities.go",
			adapterCallMarker: "BackendAdapterInstance.Execute(capability, plan, plan.AdapterInput, extensions.BackendInvocationContext{",
			policyFile:        "extensions/policy.go",
			expectedFileCount: 17,
		},
		{
			name: "python",
			build: func() (*GeneratedProject, error) {
				return BuildPythonProject(definition, BuildPythonProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
			entrypoint:        "src/work_item_governance_service/app.py",
			runtimeMetadata:   "src/work_item_governance_service/runtime_target.py",
			capabilitiesFile:  "src/work_item_governance_service/capabilities.py",
			adapterCallMarker: `backend_adapter.execute(capability, plan, plan["adapter_input"],`,
			policyFile:        "src/work_item_governance_service/policy.py",
			expectedFileCount: 17,
		},
		{
			name: "java",
			build: func() (*GeneratedProject, error) {
				return BuildJavaProject(definition, BuildJavaProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
			entrypoint:        "src/main/java/dev/anip/generated/work_item_governance_service/Application.java",
			runtimeMetadata:   "src/main/java/dev/anip/generated/work_item_governance_service/GeneratedRuntimeTarget.java",
			capabilitiesFile:  "src/main/java/dev/anip/generated/work_item_governance_service/GeneratedCapabilities.java",
			adapterCallMarker: `backendAdapter.execute(capability, plan, objectMap(plan.get("adapter_input")), ctx)`,
			policyFile:        "src/main/java/dev/anip/generated/work_item_governance_service/Policy.java",
			expectedFileCount: 16,
		},
		{
			name: "csharp",
			build: func() (*GeneratedProject, error) {
				return BuildCSharpProject(definition, BuildCSharpProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             4100,
				})
			},
			entrypoint:        "Program.cs",
			runtimeMetadata:   "GeneratedRuntimeTarget.cs",
			capabilitiesFile:  "GeneratedCapabilities.cs",
			adapterCallMarker: `backendAdapter(capability, plan, (Dictionary<string, object?>)plan["adapter_input"]!, ctx)`,
			policyFile:        "Policy.cs",
			expectedFileCount: 17,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			project, err := tc.build()
			if err != nil {
				t.Fatalf("build target: %v", err)
			}
			if project.SystemName != "work-item-governance-service" {
				t.Fatalf("unexpected system name %q", project.SystemName)
			}
			if len(project.Files) != tc.expectedFileCount {
				t.Fatalf("expected %d files, got %d", tc.expectedFileCount, len(project.Files))
			}

			assertHasFile(t, project.Files, "anip-service-definition.json")
			assertHasFile(t, project.Files, "integration-fronting/adapter-bindings.json")
			assertHasFile(t, project.Files, "integration-fronting/backend-profile.example.json")
			assertHasFile(t, project.Files, "integration-fronting/backend-selection.example.json")
			assertHasFile(t, project.Files, "integration-fronting/backend-templates/native-api.md")
			assertHasFile(t, project.Files, "integration-fronting/conformance.json")
			assertHasFile(t, project.Files, "integration-fronting/README.md")
			assertHasFile(t, project.Files, tc.entrypoint)
			runtimeContent := fileContent(project.Files, tc.runtimeMetadata)
			if !strings.Contains(runtimeContent, "work_item.search") {
				t.Fatalf("runtime metadata missing read capability")
			}
			if !strings.Contains(runtimeContent, "work_item.prepare_update") {
				t.Fatalf("runtime metadata missing prepare capability")
			}
			if !containsGeneratedMarker(runtimeContent, `"backend_input_mode": "hybrid"`) {
				t.Fatalf("runtime metadata missing hybrid backend input contract")
			}
			if !strings.Contains(runtimeContent, "change_reason") {
				t.Fatalf("runtime metadata missing explicit backend-only input")
			}
			if !containsGeneratedMarker(runtimeContent, `"validation_pattern": "^[A-Z][A-Z0-9_]+$"`) {
				t.Fatalf("runtime metadata missing input validation pattern")
			}
			if !containsGeneratedMarker(runtimeContent, `"clarification_hint": "Provide an explicit project key such as GTM or CORE."`) {
				t.Fatalf("runtime metadata missing input clarification hint")
			}
			if !containsGeneratedMarker(runtimeContent, `"grant_policy": {`) {
				t.Fatalf("runtime metadata missing v0.23 grant policy")
			}
			if !containsGeneratedMarker(runtimeContent, `"policy_bindings": [`) {
				t.Fatalf("runtime metadata missing generated policy bindings")
			}
			if !containsGeneratedMarker(runtimeContent, `"decision": "approval_required"`) {
				t.Fatalf("runtime metadata missing approval policy decision")
			}
			capabilitiesContent := fileContent(project.Files, tc.capabilitiesFile)
			if !strings.Contains(capabilitiesContent, "adapter_input") && !strings.Contains(capabilitiesContent, "AdapterInput") {
				t.Fatalf("capabilities module missing filtered adapter input plan")
			}
			if !strings.Contains(capabilitiesContent, tc.adapterCallMarker) {
				t.Fatalf("capabilities module forwards raw parameters instead of filtered adapter input")
			}
			policyContent := fileContent(project.Files, tc.policyFile)
			if !strings.Contains(policyContent, "No matching runtime policy binding; continuing.") {
				t.Fatalf("policy module does not treat generated policy bindings as sparse overrides")
			}
		})
	}
}
