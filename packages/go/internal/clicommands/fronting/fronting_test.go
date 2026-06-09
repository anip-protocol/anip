package fronting

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestScaffoldGeneratesFrontingProject(t *testing.T) {
	tempDir := t.TempDir()
	starterPath := filepath.Join(tempDir, "starter.json")
	if err := os.WriteFile(starterPath, []byte(`{
  "schema_version": "anip-fronting-starter/v0",
  "system_name": "jira_fronting_service",
  "domain_name": "work_management",
  "service_id": "jira_fronting_service",
  "service_name": "Jira Fronting Service",
  "backend_kind": "native_api",
  "connection_ref": "jira_api",
  "operations": [
    {
      "capability_id": "jira.issue.search_context",
      "title": "Search Jira Issues",
      "summary": "Search Jira issues through bounded governed inputs.",
      "method": "GET",
      "path": "/rest/api/3/search",
      "inputs": [
        {
          "name": "project_key",
          "type": "string",
          "required": true,
          "summary": "Project key.",
          "validation_pattern": "^[A-Z][A-Z0-9_]+$",
          "entity_reference": true,
          "catalog_ref": "jira.project_catalog",
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "jira.project_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "name": "limit",
          "type": "integer",
          "required": false,
          "summary": "Maximum issues to return.",
          "default_value": "25"
        }
      ]
    }
  ]
}`), 0o600); err != nil {
		t.Fatalf("write starter: %v", err)
	}
	outputDir := filepath.Join(tempDir, "out")
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"scaffold",
		"--starter", starterPath,
		"--target", "python",
		"--dependency-source", "local",
		"--transport", "stdio",
		"--output", outputDir,
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d stderr=%s", code, stderr.String())
	}

	assertFile(t, outputDir, "anip-service-definition.json")
	assertFile(t, outputDir, "integration-fronting/adapter-bindings.json")
	assertFile(t, outputDir, "integration-fronting/backend-profile.example.json")
	assertFile(t, outputDir, "integration-fronting/backend-templates/native-api.md")
	assertFile(t, outputDir, "src/jira_fronting_service/stdio_app.py")
	definitionBytes, err := os.ReadFile(filepath.Join(outputDir, "anip-service-definition.json"))
	if err != nil {
		t.Fatalf("read definition: %v", err)
	}
	if !strings.Contains(string(definitionBytes), `"contract_schema_version": "anip-service-definition/v1"`) {
		t.Fatalf("definition missing service definition schema: %s", string(definitionBytes))
	}
	bindingsBytes, err := os.ReadFile(filepath.Join(outputDir, "integration-fronting/adapter-bindings.json"))
	if err != nil {
		t.Fatalf("read bindings: %v", err)
	}
	bindings := string(bindingsBytes)
	if !strings.Contains(bindings, `"capability_id": "jira.issue.search_context"`) {
		t.Fatalf("bindings missing capability: %s", bindings)
	}
	if !strings.Contains(bindings, `"raw_operation_refs": [`) {
		t.Fatalf("bindings missing raw operation refs: %s", bindings)
	}
	if !strings.Contains(string(definitionBytes), `"catalog_ref": "jira.project_catalog"`) {
		t.Fatalf("definition missing starter catalog_ref: %s", string(definitionBytes))
	}
	if !strings.Contains(string(definitionBytes), `"mode": "backend_resolved"`) {
		t.Fatalf("definition missing starter resolution metadata: %s", string(definitionBytes))
	}
}

func TestScaffoldRejectsUnsafeCapabilityID(t *testing.T) {
	tempDir := t.TempDir()
	starterPath := filepath.Join(tempDir, "starter.json")
	if err := os.WriteFile(starterPath, []byte(`{
  "schema_version": "anip-fronting-starter/v0",
  "system_name": "bad_fronting",
  "operations": [{"capability_id": "../bad", "method": "GET", "path": "/x"}]
}`), 0o600); err != nil {
		t.Fatalf("write starter: %v", err)
	}
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"scaffold",
		"--starter", starterPath,
		"--target", "python",
		"--output", filepath.Join(tempDir, "out"),
	}, &stdout, &stderr)
	if code == 0 {
		t.Fatalf("expected non-zero exit")
	}
	if !strings.Contains(stderr.String(), "capability_id") {
		t.Fatalf("expected capability error, got %s", stderr.String())
	}
}

func assertFile(t *testing.T, root string, relativePath string) {
	t.Helper()
	if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(relativePath))); err != nil {
		t.Fatalf("expected file %s: %v", relativePath, err)
	}
}
