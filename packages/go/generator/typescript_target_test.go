package generator

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBuildTypeScriptProject(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{
		DependencySource: DependencySourceRegistry,
		HttpRuntime:      HttpRuntimeHono,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildTypeScriptProject: %v", err)
	}

	if project.PackageName != "work-item-governance-service" {
		t.Fatalf("unexpected package name %q", project.PackageName)
	}
	assertHasFile(t, project.Files, "src/app.ts")
	assertHasFile(t, project.Files, "src/generated/capabilities.ts")
	assertHasFile(t, project.Files, "tests/service-smoke.test.ts")
	assertHasFile(t, project.Files, "integration-fronting/adapter-bindings.json")
	assertHasFile(t, project.Files, "integration-fronting/backend-profile.example.json")
	assertHasFile(t, project.Files, "integration-fronting/backend-templates/native-api.md")
	assertHasFile(t, project.Files, "integration-fronting/conformance.json")

	capabilityModule := fileContent(project.Files, "src/generated/capabilities.ts")
	runtimeTargetModule := fileContent(project.Files, "src/generated/runtime-target.ts")
	adapterModule := fileContent(project.Files, "src/runtime/backend-adapter.ts")
	frontingBindings := fileContent(project.Files, "integration-fronting/adapter-bindings.json")
	backendProfile := fileContent(project.Files, "integration-fronting/backend-profile.example.json")
	frontingConformance := fileContent(project.Files, "integration-fronting/conformance.json")
	if !strings.Contains(capabilityModule, "if (!configured) return capability.backend_bindings[0];") {
		t.Fatalf("generated capabilities module missing backend selection fallback")
	}
	if !strings.Contains(runtimeTargetModule, "export type GeneratedCapabilityInputMetadata") {
		t.Fatalf("runtime target module missing generated capability input type")
	}
	if !strings.Contains(runtimeTargetModule, "[key: string]: unknown") {
		t.Fatalf("runtime target module missing input index signature")
	}
	if !strings.Contains(adapterModule, "createDefaultBackendAdapter") {
		t.Fatalf("backend adapter module missing default adapter")
	}
	if !strings.Contains(adapterModule, "Generated host prepared a governed preview") {
		t.Fatalf("backend adapter module missing prepare-only preview text")
	}
	if !strings.Contains(frontingBindings, `"schema_version": "anip-integration-fronting/v0"`) {
		t.Fatalf("fronting binding pack missing schema")
	}
	if !strings.Contains(frontingBindings, `"raw_operation_refs": [`) {
		t.Fatalf("fronting binding pack missing raw operation refs")
	}
	if !strings.Contains(frontingConformance, `"status": "passed"`) {
		t.Fatalf("fronting conformance should pass for fixture")
	}
	if !strings.Contains(backendProfile, `"contract_boundary":`) {
		t.Fatalf("backend profile missing contract boundary guidance")
	}
}

func TestBuildTypeScriptProjectLocalDependencies(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{
		DependencySource: DependencySourceLocal,
		HttpRuntime:      HttpRuntimeHono,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildTypeScriptProject: %v", err)
	}

	packageJSON := fileContent(project.Files, "package.json")
	for _, dependency := range []string{
		`"@anip-dev/service": "file:`,
		`"@anip-dev/hono": "file:`,
		`"hono": "file:`,
		`"@hono/node-server": "file:`,
	} {
		if !strings.Contains(packageJSON, dependency) {
			t.Fatalf("package.json missing local dependency marker %q", dependency)
		}
	}
}

func TestBuildTypeScriptProjectFrameworkVariants(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	cases := []struct {
		name             string
		runtime          HttpRuntime
		runtimePackage   string
		serverDependency string
		appMarker        string
		mainMarker       string
		testMarker       string
	}{
		{
			name:             "hono",
			runtime:          HttpRuntimeHono,
			runtimePackage:   "@anip-dev/hono",
			serverDependency: "@hono/node-server",
			appMarker:        `import { Hono } from "hono";`,
			mainMarker:       `import { serve } from "@hono/node-server";`,
			testMarker:       `app.request("/.well-known/anip")`,
		},
		{
			name:             "express",
			runtime:          HttpRuntimeExpress,
			runtimePackage:   "@anip-dev/express",
			serverDependency: "express",
			appMarker:        `import express from "express";`,
			mainMarker:       "app.listen(port",
			testMarker:       `request(app).get("/.well-known/anip")`,
		},
		{
			name:             "fastify",
			runtime:          HttpRuntimeFastify,
			runtimePackage:   "@anip-dev/fastify",
			serverDependency: "fastify",
			appMarker:        `import Fastify from "fastify";`,
			mainMarker:       `await app.listen({ host: "0.0.0.0", port });`,
			testMarker:       `app.inject({ method: "GET", url: "/.well-known/anip" })`,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			project, err := BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{
				DependencySource: DependencySourceRegistry,
				HttpRuntime:      tc.runtime,
				Port:             4100,
			})
			if err != nil {
				t.Fatalf("BuildTypeScriptProject: %v", err)
			}
			if project.Framework != string(tc.runtime) {
				t.Fatalf("unexpected framework metadata %q", project.Framework)
			}
			packageJSON := fileContent(project.Files, "package.json")
			app := fileContent(project.Files, "src/app.ts")
			main := fileContent(project.Files, "src/main.ts")
			smoke := fileContent(project.Files, "tests/service-smoke.test.ts")
			readme := fileContent(project.Files, "README.md")
			for _, expected := range []string{tc.runtimePackage, tc.serverDependency} {
				if !strings.Contains(packageJSON, expected) {
					t.Fatalf("package.json missing %q", expected)
				}
			}
			for _, expected := range []string{tc.appMarker, tc.mainMarker, tc.testMarker, "--framework " + string(tc.runtime)} {
				content := app + "\n" + main + "\n" + smoke + "\n" + readme
				if !strings.Contains(content, expected) {
					t.Fatalf("generated %s project missing %q", tc.name, expected)
				}
			}
		})
	}
}

func TestWriteGeneratedTypeScriptProject(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{
		DependencySource: DependencySourceRegistry,
		HttpRuntime:      HttpRuntimeHono,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildTypeScriptProject: %v", err)
	}

	outputDir := filepath.Join(t.TempDir(), "generated-service")
	if err := WriteGeneratedProject(project, outputDir, true); err != nil {
		t.Fatalf("WriteGeneratedProject: %v", err)
	}

	packageJSONBytes, err := os.ReadFile(filepath.Join(outputDir, "package.json"))
	if err != nil {
		t.Fatalf("read package.json: %v", err)
	}
	runtimeTargetBytes, err := os.ReadFile(filepath.Join(outputDir, "src/generated/runtime-target.ts"))
	if err != nil {
		t.Fatalf("read runtime target: %v", err)
	}
	if !strings.Contains(string(packageJSONBytes), `"name": "work-item-governance-service"`) {
		t.Fatalf("package.json missing generated package name")
	}
	if !strings.Contains(string(runtimeTargetBytes), "work_item.prepare_update") {
		t.Fatalf("runtime target missing expected capability id")
	}
	if !strings.Contains(string(runtimeTargetBytes), `"backend_input_mode": "hybrid"`) {
		t.Fatalf("runtime target missing hybrid backend input mode")
	}
}

func mustReadFixtureDefinition(t *testing.T) *AnipServiceDefinition {
	t.Helper()
	fixturePath := filepath.Join("testdata", "work-item-fronting-definition.json")
	data, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("read fixture definition: %v", err)
	}
	definition, err := ParseServiceDefinition(data)
	if err != nil {
		t.Fatalf("ParseServiceDefinition: %v", err)
	}
	return definition
}

func assertHasFile(t *testing.T, files []GeneratedFile, path string) {
	t.Helper()
	if fileContent(files, path) == "" {
		t.Fatalf("generated project missing file %s", path)
	}
}

func fileContent(files []GeneratedFile, path string) string {
	for _, file := range files {
		if file.Path == path {
			return file.Content
		}
	}
	return ""
}
