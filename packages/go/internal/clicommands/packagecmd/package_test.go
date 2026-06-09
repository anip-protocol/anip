package packagecmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const validBundleRef = "git+https://github.com/anip-protocol/custom-bundles.git@0123456789abcdef0123456789abcdef01234567#sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd"

func TestPublishBundleEmitsPublishRequest(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "package.json")
	writeTestPackageBundle(t, bundlePath)

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"publish-bundle",
		"--package-bundle", bundlePath,
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d stderr=%s", code, stderr.String())
	}

	var payload map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil {
		t.Fatalf("decode payload: %v\n%s", err, stdout.String())
	}
	if payload["package_id"] != "fronting-demo" || payload["package_version"] != "0.1.0" {
		t.Fatalf("unexpected package identity: %+v", payload)
	}
	if payload["project_ref"] != "studio:fronting-demo" {
		t.Fatalf("unexpected project ref: %+v", payload["project_ref"])
	}
	if _, ok := payload["manifest"].(map[string]any); !ok {
		t.Fatalf("expected manifest in publish request: %+v", payload)
	}
	if _, ok := payload["service_definition"].(map[string]any); !ok {
		t.Fatalf("expected service definition in publish request: %+v", payload)
	}
	if _, ok := payload["recommended_lock"].(map[string]any); !ok {
		t.Fatalf("expected recommended lock in publish request: %+v", payload)
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr, got %q", stderr.String())
	}
}

func TestPublishBundleNormalizesStudioPackageBundleLineage(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "package.json")
	payload := `{
		"bundle_schema_version": "anip-package-bundle/v1",
		"publication": {
			"package_id": "jira-fronting-showcase",
			"package_version": "0.2.1",
			"project_ref": "studio:project-jira",
			"product_revision_ref": "project-jira-product-design-revision-1@r1",
			"developer_revision_ref": "project-jira-developer-definition-revision-4",
			"contract_signature": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
			"publisher_id": "local-studio",
			"publisher_type": "local"
		},
		"package": {
			"package_id": "jira-fronting-showcase",
			"package_version": "0.2.1",
			"schema_version": "anip-service-definition/v1",
			"lineage": {
				"project_ref": "studio:project-jira",
				"product_revision": {"ref": "project-jira-product-design-revision-1@r1"},
				"developer_revision": {
					"ref": "project-jira-developer-definition-revision-4",
					"contract_signature": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
				}
			}
		},
		"manifest": {"name": "Jira Fronting", "readme": "Package README"},
		"service_definition": {"artifact_type": "anip_service_definition", "identity": {"system_name": "Jira Fronting"}},
		"lock": {"lock_schema_version": "anip-package-lock/v1"}
	}`
	if err := os.WriteFile(bundlePath, []byte(payload), 0o600); err != nil {
		t.Fatalf("write package bundle: %v", err)
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"publish-bundle",
		"--package-bundle", bundlePath,
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d stderr=%s", code, stderr.String())
	}

	var request map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &request); err != nil {
		t.Fatalf("decode payload: %v\n%s", err, stdout.String())
	}
	if request["product_revision_ref"] != "project-jira-product-design-revision-1@r1" {
		t.Fatalf("unexpected product revision ref: %+v", request)
	}
	if request["developer_revision_ref"] != "project-jira-developer-definition-revision-4" {
		t.Fatalf("unexpected developer revision ref: %+v", request)
	}
	if request["contract_signature"] != "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" {
		t.Fatalf("unexpected contract signature: %+v", request)
	}
}

func TestAttachImplementationEmitsPublishRequest(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "package.json")
	writeTestPackageBundle(t, bundlePath)

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"attach-implementation",
		"--package-bundle", bundlePath,
		"--package-version", "0.1.1",
		"--custom-code-bundle-ref", validBundleRef,
		"--implementation-material-title", "Reviewed custom bundle",
		"--bundle-tree-sha256", "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d stderr=%s", code, stderr.String())
	}

	var payload map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil {
		t.Fatalf("decode payload: %v\n%s", err, stdout.String())
	}
	if payload["package_id"] != "fronting-demo" || payload["package_version"] != "0.1.1" {
		t.Fatalf("unexpected package identity: %+v", payload)
	}
	materials, ok := payload["implementation_materials"].([]any)
	if !ok || len(materials) != 1 {
		t.Fatalf("expected one implementation material, got %+v", payload["implementation_materials"])
	}
	material := materials[0].(map[string]any)
	if material["ref"] != validBundleRef || material["title"] != "Reviewed custom bundle" {
		t.Fatalf("unexpected implementation material: %+v", material)
	}
	if material["bundle_tree_sha256"] != "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" {
		t.Fatalf("unexpected bundle tree digest: %+v", material)
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr, got %q", stderr.String())
	}
}

func TestBuildLocalEmitsVerifiablePackageBundleShape(t *testing.T) {
	tempDir := t.TempDir()
	definitionPath := filepath.Join(tempDir, "anip-service-definition.json")
	if err := os.WriteFile(definitionPath, []byte(validBuildLocalDefinitionJSON), 0o600); err != nil {
		t.Fatalf("write definition: %v", err)
	}
	outputDir := filepath.Join(tempDir, "registry-packages")

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"build-local",
		"--definition", definitionPath,
		"--package-id", "fronting-demo",
		"--package-version", "0.1.0",
		"--output-dir", outputDir,
		"--source-doc-url", "https://github.com/anip-protocol/anip/tree/main/docs/examples/fronting-demo",
		"--showcase-url", "https://github.com/anip-protocol/anip/tree/main/examples/showcase/fronting_demo",
		"--generated-at", "2026-05-15T00:00:00Z",
		"--write-definition",
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d stderr=%s", code, stderr.String())
	}

	bundleBytes, err := os.ReadFile(filepath.Join(outputDir, "fronting-demo-0.1.0.anip-package.json"))
	if err != nil {
		t.Fatalf("read bundle: %v", err)
	}
	var bundle map[string]any
	if err := json.Unmarshal(bundleBytes, &bundle); err != nil {
		t.Fatalf("decode bundle: %v", err)
	}
	if bundle["bundle_schema_version"] != "anip-package-bundle/v1" {
		t.Fatalf("unexpected bundle schema: %+v", bundle["bundle_schema_version"])
	}
	if _, err := os.Stat(filepath.Join(outputDir, "fronting-demo-0.1.0-service-definition.json")); err != nil {
		t.Fatalf("expected standalone service definition: %v", err)
	}
	receipt := bundle["receipt"].(map[string]any)
	if !strings.HasPrefix(stringValue(receipt["registry_signature"]), "ed25519:") {
		t.Fatalf("expected signed registry receipt, got %+v", receipt)
	}
	pkg := bundle["package"].(map[string]any)
	if pkg["published_at"] != "2026-05-15T00:00:00Z" {
		t.Fatalf("expected deterministic published_at, got %+v", pkg["published_at"])
	}
	manifest := bundle["manifest"].(map[string]any)
	if manifest["anip_spec_version"] != "anip/0.24" {
		t.Fatalf("expected current spec version, got %+v", manifest["anip_spec_version"])
	}
	readiness := manifest["agent_consumption_readiness"].(map[string]any)
	summary := readiness["summary"].(map[string]any)
	if summary["probes"] != float64(1) {
		t.Fatalf("expected readiness probe count, got %+v", summary)
	}
	consumability := manifest["agent_consumability"].(map[string]any)
	if consumability["schema_version"] != "anip-agent-consumability/v0" {
		t.Fatalf("expected consumability schema, got %+v", consumability)
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr, got %q", stderr.String())
	}
}

func TestAuditEffectsRejectsNonCanonicalEffectIDs(t *testing.T) {
	tempDir := t.TempDir()
	artifactPath := filepath.Join(tempDir, "package.json")
	payload := map[string]any{
		"service_definition": map[string]any{
			"capability_formalizations": []any{
				map[string]any{
					"capability_id": "demo.search",
					"business_effects": map[string]any{
						"produces":         []any{"content.summary"},
						"does_not_produce": []any{"external_send"},
					},
				},
			},
		},
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}
	if err := os.WriteFile(artifactPath, payloadBytes, 0o600); err != nil {
		t.Fatalf("write artifact: %v", err)
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{"audit-effects", "--path", tempDir}, &stdout, &stderr)
	if code != 1 {
		t.Fatalf("expected exit 1, got %d stdout=%s stderr=%s", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), `"effect_id": "external_send"`) {
		t.Fatalf("expected external_send finding, got %s", stdout.String())
	}
}

func TestBuildLocalAgentReadinessFlagsRequiredInputsWithoutMeaning(t *testing.T) {
	readiness := buildLocalAgentReadiness(map[string]any{
		"capability_formalizations": []any{
			map[string]any{
				"capability_id": "jira.story.prepare",
				"inputs": []any{
					map[string]any{
						"input_name": "summary",
						"required":   true,
					},
					map[string]any{
						"input_name":    "project_key",
						"required":      true,
						"semantic_type": "project_scope",
					},
				},
			},
		},
	}, []string{"jira.story.prepare"})

	if readiness["status"] != "needs_review" {
		t.Fatalf("expected needs_review readiness, got %+v", readiness["status"])
	}
	summary := readiness["summary"].(map[string]any)
	if summary["warnings"] != float64(1) {
		t.Fatalf("expected one readiness warning, got %+v", summary)
	}
	findings := readiness["findings"].([]any)
	if len(findings) != 1 {
		t.Fatalf("expected one finding, got %+v", findings)
	}
	finding := findings[0].(map[string]any)
	if finding["id"] != "jira.story.prepare:summary:classification" {
		t.Fatalf("unexpected finding: %+v", finding)
	}
}

func TestAttachImplementationComputesLocalBundleTreeDigest(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "package.json")
	writeTestPackageBundle(t, bundlePath)
	customDir := filepath.Join(tempDir, "custom")
	if err := os.MkdirAll(customDir, 0o755); err != nil {
		t.Fatalf("mkdir custom bundle: %v", err)
	}
	if err := os.WriteFile(filepath.Join(customDir, "custom_logic.py"), []byte("CAPABILITY = 'fronting.search'\n"), 0o600); err != nil {
		t.Fatalf("write custom file: %v", err)
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	code := Run([]string{
		"attach-implementation",
		"--package-bundle", bundlePath,
		"--package-version", "0.1.1",
		"--custom-code-bundle-ref", validBundleRef,
		"--custom-code-bundle", customDir,
	}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d stderr=%s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), `"bundle_tree_sha256": "sha256:`) {
		t.Fatalf("expected computed bundle tree digest, got %s", stdout.String())
	}
}

func TestAttachImplementationRejectsFloatingBundleRef(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "package.json")
	writeTestPackageBundle(t, bundlePath)

	var stderr bytes.Buffer
	code := Run([]string{
		"attach-implementation",
		"--package-bundle", bundlePath,
		"--package-version", "0.1.1",
		"--custom-code-bundle-ref", "git+https://github.com/acme/custom.git@main#sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
	}, &bytes.Buffer{}, &stderr)
	if code != 2 {
		t.Fatalf("expected exit 2, got %d", code)
	}
	if !strings.Contains(stderr.String(), "invalid custom code bundle ref") {
		t.Fatalf("expected invalid ref error, got %q", stderr.String())
	}
}

func writeTestPackageBundle(t *testing.T, path string) {
	t.Helper()
	payload := `{
		"bundle_schema_version": "anip-package-bundle/v1",
		"package": {
			"package_id": "fronting-demo",
			"package_version": "0.1.0",
			"project_ref": "studio:fronting-demo",
			"product_revision_ref": "product-r1",
			"developer_revision_ref": "developer-r3",
			"contract_signature": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			"schema_version": "anip-service-definition/v1",
			"lineage": {"project_ref": "studio:fronting-demo"},
			"manifest": {"name": "Fronting Demo", "readme": "Package README"},
			"service_definition": {"artifact_type": "anip_service_definition", "identity": {"system_name": "Fronting Demo"}},
			"recommended_lock": {"lock_schema_version": "anip-package-lock/v1"},
			"source_links": [{"title": "Repo", "url": "https://example.test/repo"}]
		}
	}`
	if err := os.WriteFile(path, []byte(payload), 0o600); err != nil {
		t.Fatalf("write package bundle: %v", err)
	}
}

const validBuildLocalDefinitionJSON = `{
  "artifact_type": "anip_service_definition",
  "contract_schema_version": "anip-service-definition/v1",
  "compiled_contract_identity": {
    "signature": "sha256:test-contract",
    "signature_algorithm": "sha256"
  },
  "identity": {
    "system_name": "Fronting Demo",
    "domain_name": "fronting",
    "delivery_model": "governed_integration_fronting",
    "architecture_shape": "single_service"
  },
  "service_topology_bindings": [
    {
      "id": "svc-fronting",
      "service_id": "fronting-service",
      "service_name": "Fronting Demo",
      "source_role": "integration_fronting",
      "source_capabilities": ["fronting.search"],
      "formalized_capability_ids": ["fronting.search"],
      "owned_concept_ids": ["fronting_record"]
    }
  ],
  "capability_formalizations": [
    {
      "id": "cap-fronting-search",
      "source_kind": "integration_fronting_source_doc",
      "service_id": "fronting-service",
      "capability_id": "fronting.search",
      "kind": "atomic",
      "title": "Search Fronting Records",
      "summary": "Search fronting records.",
      "intent_type": "read_only",
      "operation_type": "query",
      "side_effect_level": "read",
      "backend_operation": "searchFrontingRecords",
      "path_template": "/fronting/search",
      "output_shape": "fronting_search_result",
      "inputs": [
        {
          "input_name": "query",
          "input_type": "string",
          "required": true,
          "summary": "Search query.",
          "clarification_hint": "Ask for query when it is missing."
        }
      ]
    }
  ],
  "integration_fronting": {
    "mappings": [
      {
        "capability_id": "fronting.search",
        "bindings": [
          {
            "backend_kind": "native_api",
            "connection_ref": "fronting_api",
            "raw_operation_refs": ["GET /fronting/search"]
          }
        ]
      }
    ],
    "raw_operations": [
      {
        "id": "GET /fronting/search",
        "method": "GET",
        "path": "/fronting/search"
      }
    ]
  }
}`
