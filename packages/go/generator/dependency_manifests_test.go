package generator

import (
	"strings"
	"testing"
)

func TestReconcileDependencyManifestsRestoresTypeScriptLocalDependencies(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "demo-service",
		SystemName:  "Demo Service",
		Framework:   string(HttpRuntimeHono),
		Transports:  []string{string(TransportHTTP)},
		Files: []GeneratedFile{
			{Path: "package.json", Content: `{"dependencies":{"@anip-dev/service":"0.1.0","pg":"^8.16.3"},"devDependencies":{"tsx":"^4.20.6"},"scripts":{"start":"node dist/custom-main.js"}}`},
		},
	}

	if err := ReconcileDependencyManifests(project, "typescript", DependencySourceLocal); err != nil {
		t.Fatalf("ReconcileDependencyManifests: %v", err)
	}

	content, ok := generatedProjectFileContent(project, "package.json")
	if !ok {
		t.Fatal("expected package.json")
	}
	if strings.Contains(content, `"@anip-dev/service": "0.1.0"`) {
		t.Fatalf("stale dependency survived reconciliation: %s", content)
	}
	if !strings.Contains(content, `"@anip-dev/service": "file:`) || !strings.Contains(content, `"@anip-dev/hono": "file:`) {
		t.Fatalf("expected local TypeScript dependencies, got: %s", content)
	}
	if !strings.Contains(content, `"pg": "^8.16.3"`) {
		t.Fatalf("expected custom TypeScript dependency to be preserved, got: %s", content)
	}
	if !strings.Contains(content, `"tsx": "^4.20.6"`) {
		t.Fatalf("expected custom TypeScript dev dependency to be preserved, got: %s", content)
	}
	if !strings.Contains(content, `"start": "node dist/custom-main.js"`) {
		t.Fatalf("expected custom TypeScript script to be preserved, got: %s", content)
	}
}

func TestReconcileDependencyManifestsRestoresGoLocalDependencies(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "demo-service",
		SystemName:  "Demo Service",
		Transports:  []string{string(TransportHTTP)},
		CustomBundleTemplateValues: map[string]string{
			"GO_MODULE_PATH": "generated/demo-service",
		},
		Files: []GeneratedFile{
			{Path: "go.mod", Content: "module generated/demo-service\n\ngo 1.25.0\n\nrequire (\n\tgithub.com/anip-protocol/anip/packages/go v0.1.0\n\tgithub.com/jackc/pgx/v5 v5.8.0\n)\n"},
		},
	}

	if err := ReconcileDependencyManifests(project, "go", DependencySourceLocal); err != nil {
		t.Fatalf("ReconcileDependencyManifests: %v", err)
	}

	content, ok := generatedProjectFileContent(project, "go.mod")
	if !ok {
		t.Fatal("expected go.mod")
	}
	if strings.Contains(content, "v0.1.0") {
		t.Fatalf("stale dependency survived reconciliation: %s", content)
	}
	if !strings.Contains(content, "replace github.com/anip-protocol/anip/packages/go => ") {
		t.Fatalf("expected local Go replace directive, got: %s", content)
	}
	if !strings.Contains(content, "github.com/jackc/pgx/v5 v5.8.0") {
		t.Fatalf("expected custom Go dependency to be preserved, got: %s", content)
	}
	if _, ok := generatedProjectFileContent(project, "go.work"); !ok {
		t.Fatal("expected local Go workspace")
	}
}

func TestReconcileDependencyManifestsRestoresPythonLocalDependencies(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "demo-service",
		SystemName:  "Demo Service",
		Transports:  []string{string(TransportHTTP)},
		CustomBundleTemplateValues: map[string]string{
			"PYTHON_MODULE_NAME": "demo_service",
		},
		Files: []GeneratedFile{
			{Path: "pyproject.toml", Content: "[project]\ndependencies = [\"anip-service==0.1.0\", \"psycopg[binary]>=3.2.0\"]\n"},
		},
	}

	if err := ReconcileDependencyManifests(project, "python", DependencySourceLocal); err != nil {
		t.Fatalf("ReconcileDependencyManifests: %v", err)
	}

	content, ok := generatedProjectFileContent(project, "pyproject.toml")
	if !ok {
		t.Fatal("expected pyproject.toml")
	}
	if strings.Contains(content, "anip-service==0.1.0") {
		t.Fatalf("stale dependency survived reconciliation: %s", content)
	}
	if !strings.Contains(content, `"anip-service @ file://`) || !strings.Contains(content, `name = "demo-service"`) {
		t.Fatalf("expected local Python dependencies, got: %s", content)
	}
	if !strings.Contains(content, `"psycopg[binary]>=3.2.0"`) {
		t.Fatalf("expected custom Python dependency to be preserved, got: %s", content)
	}
}

func TestReconcileDependencyManifestsPreservesPythonCustomProjectIdentity(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "demo-service",
		SystemName:  "Demo Service",
		Transports:  []string{string(TransportHTTP)},
		CustomBundleTemplateValues: map[string]string{
			"PYTHON_MODULE_NAME": "demo_service",
		},
		Files: []GeneratedFile{
			{Path: "pyproject.toml", Content: "[project]\nname = \"custom-demo\"\nversion = \"9.9.9\"\ndependencies = [\"anip-service==0.1.0\", \"psycopg[binary]>=3.2.0\"]\n"},
		},
	}

	if err := ReconcileDependencyManifests(project, "python", DependencySourceLocal); err != nil {
		t.Fatalf("ReconcileDependencyManifests: %v", err)
	}

	content, ok := generatedProjectFileContent(project, "pyproject.toml")
	if !ok {
		t.Fatal("expected pyproject.toml")
	}
	if !strings.Contains(content, `name = "custom-demo"`) || !strings.Contains(content, `version = "9.9.9"`) {
		t.Fatalf("expected custom Python project identity to be preserved, got: %s", content)
	}
	if strings.Contains(content, "anip-service==0.1.0") || !strings.Contains(content, `"anip-service @ file://`) {
		t.Fatalf("expected managed Python dependency to be reconciled, got: %s", content)
	}
}
