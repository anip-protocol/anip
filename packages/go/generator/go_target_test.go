package generator

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestBuildGoProject(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildGoProject(definition, BuildGoProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildGoProject: %v", err)
	}

	assertHasFile(t, project.Files, "main.go")
	assertHasFile(t, project.Files, "app/service.go")
	assertHasFile(t, project.Files, "generated/runtime_target.go")
	assertHasFile(t, project.Files, "host/capabilities.go")
	assertHasFile(t, project.Files, "extensions/backend_adapter.go")
	assertHasFile(t, project.Files, "app/service_smoke_test.go")
	assertHasFile(t, project.Files, "go.work")

	goMod := fileContent(project.Files, "go.mod")
	if !strings.Contains(goMod, "replace github.com/anip-protocol/anip/packages/go => ") {
		t.Fatalf("go.mod missing local replace for ANIP Go packages")
	}

	runtimeModule := fileContent(project.Files, "generated/runtime_target.go")
	capabilityModule := fileContent(project.Files, "host/capabilities.go")
	if !strings.Contains(runtimeModule, "work_item.prepare_update") {
		t.Fatalf("generated runtime target missing expected capability id")
	}
	if !strings.Contains(runtimeModule, `"backend_input_mode": "hybrid"`) {
		t.Fatalf("generated runtime target missing hybrid backend input mode")
	}
	if !strings.Contains(capabilityModule, "assertRequestedEffectsAllowed(capability, ctx)") {
		t.Fatalf("generated capabilities module must deny forbidden requested effects before execution")
	}
	if strings.Index(capabilityModule, "assertRequestedEffectsAllowed(capability, ctx)") > strings.Index(capabilityModule, "params = applyInputDefaults(capability, params)") {
		t.Fatalf("generated capabilities module must check requested effects before applying defaults")
	}
}

func TestGeneratedGoProjectCompilesLocally(t *testing.T) {
	definition := mustReadFixtureDefinition(t)
	project, err := BuildGoProject(definition, BuildGoProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildGoProject: %v", err)
	}

	outputDir := filepath.Join(t.TempDir(), "generated-go-service")
	if err := WriteGeneratedProject(project, outputDir, true); err != nil {
		t.Fatalf("WriteGeneratedProject: %v", err)
	}

	cmd := exec.Command("go", "test", "./...")
	cmd.Dir = outputDir
	cmd.Env = os.Environ()
	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go test ./... failed: %v\n%s", err, string(output))
	}
}
